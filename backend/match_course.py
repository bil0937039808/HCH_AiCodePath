# -*- coding: utf-8 -*-
"""
課程匹配與推薦模組

此模組負責：
- 從本地 CSV 載入課程資料
- 依據使用者提供的技能關鍵字過濾出相符課程
- 呼叫 Gemini 產生式模型，根據過濾結果產生循序漸進的課程推薦清單
設計上以非同步流程為主，並將 I/O 與阻塞性工作委派到背景執行緒，以提升整體效能。
"""
import ast
import json
import os
import time
from functools import partial
from pathlib import Path
from typing import List

import google.generativeai as genai
import pandas as pd
import redis_manager
import singleton as sgtn
import Utility
from anyio import to_thread  # 關鍵：把同步阻塞工作丟到 thread pool
from openai import AsyncOpenAI
from pydantic import BaseModel, Field, ValidationError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from typing_extensions import override
from pprint import pprint

# 改正：os.Path 不存在，請用 pathlib.Path
class CourseRecommendation(BaseModel):
    """
    代表單一課程推薦項目的結構定義。

    欄位說明：
    - rank: 推薦排序（1 為最高）
    - course_title: 課程名稱
    - course_url: 課程網址
    - reason: 推薦理由（簡潔且可操作）
    - level: 適合等級（beginner/intermediate/advanced）
    - skills: 課程涵蓋的技能摘要
    - Course_duration: 課程總時數（以數值表示）
    """

    rank: int = Field(description="推薦排序，從 1 到 5")
    course_title: str = Field(description="推薦的課程名稱")
    course_url: str = Field(description="推薦的課程網址")
    reason: str = Field(description="推薦理由")
    level: str = Field(description="課程適合等級")
    skills: str = Field(description="課程涵蓋的技能")
    Course_duration: float = Field(description="課程時長")
    web_review: str = Field(description="彙整的網路評價與重點，來源概述或引用")
    prep_notes: str = Field(description="開課前的預習重點與學習準備建議")
"""
rank: backendCourse.rank,
      title: backendCourse.course_title,
      url: backendCourse.course_url,
      reason: backendCourse.reason,
      level: backendCourse.level,
      skills: backendCourse.skills,
      hours: backendCourse.Course_duration,
      webReview: backendCourse.web_review,
      prepNotes: backendCourse.prep_notes,
      // 為了保持向後兼容，添加一些原有格式的欄位
      provider: this.extractProvider(backendCourse.course_url),
      skill: backendCourse.skills.split(',')[0].trim(), // 取第一個技能作為主要技能
      rating: this.levelToRating(backendCourse.level),
      price: 0 // 暫時設為免費，可根據需求調整
"""

class TopCourses(BaseModel):
    recommendations: List[CourseRecommendation]


class MatchCourse(sgtn.Singleton_C):
    def __init__(self):
        super().__init__()

    async def init_MatchCourse(
        self, set_api_key_openAI: str, set_api_key_gemini: str
    ) -> None:
        self._rds_man_obj = await redis_manager.RedisManager.get_object()
        if not set_api_key_gemini or not set_api_key_openAI:
            # raise RuntimeError("API_KEY 未設定或為空，請在環境變數或 key.env 設定")
            print("API_KEY 未設定或為空，請在環境變數或 key.env 設定")
        genai.configure(api_key=set_api_key_gemini)
        self.client = AsyncOpenAI(api_key=set_api_key_openAI)

    def safe_literal_eval(self, s) -> list | tuple:
        """
        安全地將字串解析為 Python 字面量結構。

        常見於 CSV 欄位中存放的 list/tuple 字串表示，例如 "['Python','SQL']"。
        若解析失敗（非合法字面量或語法錯誤），回傳空清單以避免流程中斷。

        參數:
        - s: 可能為 list/tuple 等結構的字串表示

        回傳:
        - 解析成功的物件，若失敗則回傳空清單 []
        """
        try:
            return ast.literal_eval(s)
        except (ValueError, SyntaxError):
            return []

    async def __use_csv(self):
        CSV_PATH = Path(
            r"C:\Users\user\Desktop\AIPE01_G4_AiCodePath\data\merged_coursera_data.csv"
        )
        # 讀取課程 CSV 檔案（屬 I/O 阻塞，委派到背景 thread 執行）
        if not CSV_PATH.exists():
            print(f"CSV 檔不存在：{CSV_PATH}")
            # raise FileNotFoundError(f"CSV 檔不存在：{CSV_PATH}")
        read_csv_call = partial(pd.read_csv, CSV_PATH, encoding="utf-8")
        df_course = await to_thread.run_sync(read_csv_call)
        return df_course

    # ====== 非同步版本 ======
    async def recommend_courses(self, skills: List[str]) -> dict:
        """
        非同步課程推薦主流程。

        說明:
        - 將資料載入等阻塞性工作委派至背景執行緒（thread pool）
        - 依據使用者技能關鍵字過濾課程

        參數:
        - skills: 使用者想學的技能清單（字串列表）

        回傳:
        - dict

        可能拋出:
        - RuntimeError: API Key 未設定或 LLM 呼叫發生錯誤
        """
        if not skills:
            return {"error": -1, "recommendations": []}

        # 載入 .env，讀取並設定 Gemini API 金鑰
        load_dotenv(dotenv_path=self.__env_path)
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            print("GEMINI_API_KEY 未設定或為空，請在環境變數或 .env 設定")
            # raise RuntimeError("GEMINI_API_KEY 未設定或為空，請在環境變數或 .env 設定")
        genai.configure(api_key=api_key)

        df_course = self.__use_csv()

        # 動態偵測技能欄位（支援 'skills' 或 '技能'），並解析為清單
        skills_col = (
            "skills"
            if "skills" in df_course.columns
            else ("技能" if "技能" in df_course.columns else None)
        )
        if not skills_col:
            print("找不到技能欄位（'skills' 或 '技能'），請確認 CSV 欄位名稱")
            # raise ValueError("找不到技能欄位（'skills' 或 '技能'），請確認 CSV 欄位名稱")

        def _parse_skills_cell(cell_value):
            if cell_value is None or (
                isinstance(cell_value, float) and pd.isna(cell_value)
            ):
                return []
            if isinstance(cell_value, (list, tuple)):
                return [str(s).strip() for s in cell_value if str(s).strip()]
            if isinstance(cell_value, str):
                text = cell_value.strip()
                if (text.startswith("[") and text.endswith("]")) or (
                    text.startswith("(") and text.endswith(")")
                ):
                    parsed = self.safe_literal_eval(text)
                    if isinstance(parsed, (list, tuple)):
                        return [str(s).strip() for s in parsed if str(s).strip()]
                return [s.strip() for s in text.split(",") if s.strip()]
            return []

        df_course["skills_list"] = df_course[skills_col].apply(_parse_skills_cell)

        # 將使用者輸入技能標準化（去前後空白、轉小寫）以提升比對準確度
        search_skills = {str(s).strip().lower() for s in skills if str(s).strip()}

        def has_matching_skill(skill_list):
            normalized_skills = {str(s).strip().lower() for s in (skill_list or [])}
            return not normalized_skills.isdisjoint(search_skills)

        # 篩選出至少含有一項使用者技能，並限制 credibility_tier 為 Tier 1 或 Tier 2
        match_mask = df_course["skills_list"].apply(has_matching_skill)
        tier_col = (
            "credibility_tier" if "credibility_tier" in df_course.columns else None
        )
        if tier_col:
            tier_mask = (
                df_course[tier_col]
                .astype(str)
                .str.contains(r"\bTier\s*1\b|\bTier\s*2\b", case=False, regex=True)
            )
            result_df = df_course[match_mask & tier_mask].copy()
        else:
            result_df = df_course[match_mask].copy()

        if result_df.empty:
            return {"error": -1, "recommendations": []}

        # 依每個技能挑出最多 3 門候選課，排序依據：Tier 1 > Tier 2 > 其他；其次 rating_numeric、review_count
        def tier_priority(value: str) -> int:
            text = str(value)
            if "Tier 1" in text:
                return 1
            if "Tier 2" in text:
                return 2
            return 3

        shortlist_frames = []
        for user_skill in search_skills:
            skill_mask = result_df["skills_list"].apply(
                lambda items: user_skill
                in {str(s).strip().lower() for s in (items or [])}
            )
            subset = result_df[skill_mask].copy()
            if subset.empty:
                continue
            if tier_col:
                subset["_tier_priority"] = subset[tier_col].apply(tier_priority)
            else:
                subset["_tier_priority"] = 3
            if "rating_numeric" not in subset.columns:
                subset["rating_numeric"] = pd.NA
            if "review_count" not in subset.columns:
                subset["review_count"] = pd.NA
            subset = subset.sort_values(
                by=["_tier_priority", "rating_numeric", "review_count"],
                ascending=[True, False, False],
            )
            subset["selected_skill"] = user_skill
            shortlist_frames.append(subset.head(3))

        if not shortlist_frames:
            return {"error": -1, "recommendations": []}

        shortlist_df = pd.concat(shortlist_frames, ignore_index=True)
        if "課程網址" in shortlist_df.columns:
            shortlist_df = shortlist_df.drop_duplicates(
                subset=["課程網址"], keep="first"
            )
        else:
            shortlist_df = shortlist_df.drop_duplicates(
                subset=["課程名稱"], keep="first"
            )
        return {
            "error": 0,
            "skills_col": skills_col,
            "shortlist_df": shortlist_df,
            "search_skills": search_skills,
        }

    """
    你是一位 專業的線上課程推薦專家 與 職涯規劃顧問。
        你的任務是根據給定的課程清單，幫助 0 基礎的轉職者 規劃一條清晰的學習路徑。

        需求：
        推薦最適合的課程，盡量避免內容重複。若多個課程涵蓋相同技能，只需挑選最合適的一個。
        課程排序需循序漸進，由淺入深，幫助學習者逐步建立技能。

        額外注意事項：
        使用者是 完全零基礎，需要從入門知識開始。
        課程安排需兼顧 基礎打底 → 實作應用 → 進階專題 的邏輯決定順序。
        （beginner → intermediate → advanced）
        請保持建議 簡潔、專業、易於理解。
        請只推薦課程名稱為中文或英文的課程。

        重要條件：
        - 挑選課程時盡量已beginner 為主，除非使用者上的課程中已幫使用者補齊基礎，才推薦intermediate或advanced。
        - 我們已替每項技能挑選最多 3 門候選課程（見下方清單）。
        - 對每項技能，請你再「到網路上查評價」並彙整（可以使用官方課程頁面、Coursera 評論、部落格或社群討論作為依據），再從 3 門裡面選出「最適合的一門」。
        - 若你無法即時存取網路，請以候選資料中的 rating_numeric、review_count、課綱與技能覆蓋度作為替代依據，並將 web_review 標記來源為 "N/A"。
        - 決策依據：credibility_tier（Tier 1 > Tier 2）、rating_numeric、review_count、課綱與技能覆蓋度、近期口碑趨勢。
        - 最後輸出每一項技能各 1 門課程，避免重複課程；若衝突，請為後者改選下一個最佳候選。
        - 請為每一門最終課程提供：推薦原因（reason）、網路評價摘要（web_review，請給出來源簡述與網址；若無法查到給 "N/A"）、以及開課前的預習筆記（prep_notes，條列 3-6 點）。
        - 最後產出課程後請再次檢查是否有沒有涵蓋到的技能，若有技能沒有涵蓋到請在網路上搜尋相關教學影片，並以同樣的格式回傳。

        二次檢查：
        - 請再次檢查課程是否依照上述重要條件處理，如果有不符合的部分請修正。
        請輸出「純 JSON」，格式如下，不要加入多餘文字：

        優先使用以下提供之資料,如果無法配對再自己上網搜尋
        使用者想學的技能如下：

        每項技能的候選課程（每項技能最多 3 門，含 tier 與指標）：

        
    """

    def __build_prompt(self, search_skills: set[str], input_data_json: str) -> str:
        # 設計提示詞：要求模型輸出符合 pydantic 結構的「純 JSON」，並強調排序與去重原則
        print(
            "CourseRecommendation::__build_prompt()",
            input_data_json,
            type(input_data_json),
            "\n",
            sorted(list(search_skills)),
            type(sorted(list(search_skills))),
        )
        # input_data_json=None
        prompt_using_json = f"""
        You are a professional online course recommendation expert and career planning consultant.
        Your task is to help career changers with zero prior knowledge plan a clear learning path based on a given list of courses.

        Requirements:
        Recommend the most appropriate courses, minimizing duplication. If multiple courses cover the same skills, select the most appropriate one.
        Courses should be arranged in a progressive, step-by-step manner, from easy to difficult, to help learners gradually build their skills.

        Additional Notes:
        The user has absolutely no prior knowledge and needs to start with introductory knowledge.
        Courses should be arranged in a logical order: foundational knowledge → practical application → advanced topics.

        (Beginner → Intermediate → Advanced)
        Please keep your recommendations concise, professional, and easy to understand.
        Please only recommend courses with titles in Chinese or English.

        Important Requirements:
        - When selecting courses, prioritize beginners. Only recommend intermediate or advanced courses if the user's previous courses have already helped them build their foundation.
        - We've selected up to three candidate courses for each skill (see the list below).
        - For each skill, please research online reviews (using the official course page, Coursera reviews, blogs, or community discussions) and select the most suitable course from these three.
        - If you don't have immediate access to the internet, use the candidate's rating_numeric, review_count, syllabus, and skill coverage as alternative criteria, marking the web_review source as "N/A."
        - Decision-making criteria: credibility_tier (Tier 1 > Tier 2), rating_numeric, review_count, syllabus and skill coverage, and recent word-of-mouth trends.
        - Finally, output one course for each skill to avoid duplication; if there is a conflict, select the next best candidate.
        - For each finalized course, please provide: reason for recommendation (reason), summary of online reviews (web_review; please provide a brief description of the source and URL; if unavailable, mark "N/A"), and pre-course preparation notes (prep_notes; list 3-6 items).
        - After finalizing the course, please double-check to see if any skills are missing. If any skills are missing, please search online for relevant instructional videos and submit them in the same format.

        Secondary Review:
        - Please double-check that the course complies with the above key requirements. If any are not met, please correct them.

        Please output "pure JSON" in the following format, without any extraneous text:
        {{
        "recommendations": [
            {{
            "rank": int,
            "course_title": str,
            "course_url": str,
            "reason": str,
            "level": str,
            "skills": str,
            "Course_duration": int,
            "web_review": str,
            "prep_notes": "A single string with newline characters (\\n) for line breaks, listing 3-6 preparation points. Example: '1. First point.\\n2. Second point.\\n3. Third point.'"
            }}
        ],
        }}
        The skills the user wants to learn are as follows:
        {sorted(list(search_skills))}
        Please give priority to the information provided below. If you cannot find a match,you can search online .
        Candidate courses for each skill (up to 3 courses per skill, including tiers and indicators):
        ```json
        {input_data_json}
        ```
        """

        return prompt_using_json

    async def __build_input_data_json(
        self, skills_col: list[str], shortlist_df: pd.DataFrame
    ) -> str:
        candidate_cols = [
            "course_url",
            "course_name",
            "評分",
            "評論數",
            "Metadata",
            skills_col,
            "課程資訊",
            "總時數_時",
            "rating_numeric",
            "review_count",
            "credibility_tier",
            "matched_skill",
        ]
        """
            "課程網址",
            "課程名稱",
            "評分",
            "評論數",
            "Metadata",
            skills_col,
            "課程資訊",
            "學習時長",
            "rating_numeric",
            "review_count",
            "credibility_tier",
            "selected_skill",
        """
        """
            course_name TEXT,
            評分 TEXT,
            評論數 TEXT,
            適合等級 TEXT,
            技能 TEXT,
            課程資訊 TEXT,
            師資 TEXT,
            開課時間 TEXT,
            lesson TEXT,
            總時數_時 NUMERIC,
            訂閱方式_月 TEXT,
            費用_US_月 INTEGER,
            訂閱方式_年 TEXT,
            費用_US_年 INTEGER,
            course_url TEXT,
            skills TEXT,               -- 暫時先 TEXT，避免 COPY 出錯
            rating_numeric NUMERIC,
            review_count INTEGER,
            credibility_score NUMERIC,
            quadrant TEXT,
            topic_id INTEGER,
            topic_label TEXT,
            credibility_tier TEXT,
            strategy_rating TEXT

            matched_skill
        """
        exist_cols = [c for c in candidate_cols if c in shortlist_df.columns]
        df_toGMN = shortlist_df[exist_cols].copy().reset_index(drop=True)

        # 將資料轉為 JSON 字串，方便嵌入到提示詞中
        input_data_json = df_toGMN.to_json(
            orient="records", force_ascii=False, indent=2
        )
        return input_data_json

    async def ai_planning(
        self, skills_col: list[str], shortlist_df: pd.DataFrame, search_skills: set[str]
    ) -> dict:
        """
        非同步課程推薦主流程。

        說明:
        - LLM 呼叫等阻塞性工作委派至背景執行緒（thread pool）
        - 依據使用者技能關鍵字過濾課程，並請求 LLM 依難度由淺入深生成推薦


        回傳:
        - dict，符合 TopCourses 結構，例如: {"recommendations": [{...}, ...]}

        可能拋出:
        - RuntimeError: API Key 未設定或 LLM 呼叫發生錯誤
        - ValueError: LLM 輸出非有效 JSON 或驗證失敗
        """
        input_data_json = await self.__build_input_data_json(skills_col, shortlist_df)
        prompt_using_json = self.__build_prompt(search_skills, input_data_json)
        print("input_data_json:", input_data_json)
        # 準備 Gemini 模型與產生設定
        model = genai.GenerativeModel("gemini-2.5-pro")
        gen_cfg = genai.GenerationConfig(
            response_mime_type="application/json",
            temperature=0.2,
        )

        # 定義重試策略
        @retry(
            wait=wait_exponential(
                multiplier=1, min=4, max=10
            ),  # 每次重試的間隔時間會指數增長
            stop=stop_after_attempt(3),  # 最多重試 3 次
            retry=retry_if_exception_type(RuntimeError),  # 只對 RuntimeError 進行重試
            reraise=True,  # 重試失敗後重新拋出最後一個異常
        )
        async def call_with_retry():
            """
            獨立的非同步函數來執行 API 呼叫並處理回應。
            """
            call_gen = partial(
                model.generate_content, prompt_using_json, generation_config=gen_cfg
            )
            response = await to_thread.run_sync(call_gen)

            # 在嘗試訪問 .text 之前，先檢查回應是否有效
            if response.candidates and (
                response.candidates[0].finish_reason is None
                or response.candidates[0].finish_reason == 0
            ):
                return response.text
            else:
                finish_reason = (
                    response.candidates[0].finish_reason
                    if response.candidates
                    else "No candidates"
                )
                block_reason = (
                    response.prompt_feedback.block_reason
                    if response.prompt_feedback
                    else "N/A"
                )
                error_message = f"Gemini API 呼叫失敗, finish_reason: {finish_reason}, block_reason: {block_reason}"
                print(error_message)
                # raise RuntimeError(error_message)

        try:
            # 呼叫帶有重試機制的函數
            json_text = await call_with_retry()
            json_data = json.loads(json_text)

            # --- START: 新增的格式修正邏輯 ---
            # 在 Pydantic 驗證前，手動修正 prep_notes 的格式
            if "recommendations" in json_data and isinstance(
                json_data["recommendations"], list
            ):
                for course in json_data["recommendations"]:
                    # 檢查 prep_notes 是否為 list
                    if "prep_notes" in course and isinstance(
                        course["prep_notes"], list
                    ):
                        # 如果是 list，就將其元素用換行符號連接成一個單一字串
                        course["prep_notes"] = "\n".join(map(str, course["prep_notes"]))
            # --- END: 新增的格式修正邏輯 ---
            # print("course[prep_notes]: ", course["prep_notes"])
            pprint(json_data)
            validated_data = TopCourses(**json_data)
            return validated_data.dict()

        except json.JSONDecodeError:
            print("模型輸出的不是有效 JSON")
            # raise ValueError("模型輸出的不是有效 JSON")
        except ValidationError as e:
            print(f"JSON 格式驗證失敗: {e}")
            pprint(json_data)
            print("詳細錯誤訊息:", e.errors())
            # raise ValueError(f"JSON 格式驗證失敗: {e}")
        except Exception as e:
            # 捕獲 tenacity 最後拋出的 RuntimeError
            print(f"呼叫推薦流程發生錯誤: {e}")
            # raise RuntimeError(f"呼叫推薦流程發生錯誤: {e}")

    async def ai_planning_GPT(
        self, skills_col: list[str], shortlist_df: pd.DataFrame, search_skills: set[str]
    ) -> dict:
        """
        非同步課程推薦主流程 (GPT-4.1 版本)。
        """
        input_data_json = await self.__build_input_data_json(skills_col, shortlist_df)
        prompt_using_json = self.__build_prompt(search_skills, input_data_json)

        # print("input_data_json:", input_data_json)
        # 重試策略
        @retry(
            wait=wait_exponential(multiplier=1, min=4, max=10),
            stop=stop_after_attempt(3),
            retry=retry_if_exception_type(RuntimeError),
            reraise=True,
        )
        async def call_with_retry():
            """
            獨立非同步函數，呼叫 OpenAI GPT-4.1 API。
            """
            response = await self.client.chat.completions.create(
                model="gpt-4.1",#gpt-4.1
                messages=[
                    {
                        "role": "system",
                        "content": "你是一個專業的課程推薦系統，輸出必須是有效 JSON。",
                    },
                    {"role": "user", "content": prompt_using_json},
                ],
                # temperature=0.2,
                response_format={"type": "json_object"},  # 強制 JSON 輸出
            )

            if response.choices and response.choices[0].message.content:
                return response.choices[0].message.content
            else:
                # raise RuntimeError("GPT-4.1 API 回傳空結果")
                print("GPT-4.1 API 回傳空結果")

        try:
            # 呼叫 GPT-4.1
            json_text = await call_with_retry()
            json_data = json.loads(json_text)

            # --- START: 新增的格式修正邏輯 ---
            if "recommendations" in json_data and isinstance(
                json_data["recommendations"], list
            ):
                for course in json_data["recommendations"]:
                    # 檢查 prep_notes 是否為 list
                    if "prep_notes" in course and isinstance(
                        course["prep_notes"], list
                    ):
                        # 如果是 list，就將其元素用換行符號連接成一個單一字串
                        course["prep_notes"] = "\n".join(map(str, course["prep_notes"]))
            # --- END: 新增的格式修正邏輯 ---

            # 驗證 JSON 格式
            validated_data = TopCourses(**json_data)
            return validated_data.dict()

        except json.JSONDecodeError:
            print("模型輸出的不是有效 JSON")
        except ValidationError as e:
            print(f"JSON 格式驗證失敗: {e}")
        except Exception as e:
            print(f"呼叫推薦流程發生錯誤: {e}")

    async def courses_recommend_handle(self, get_task: dict) -> None:
        is_MatchCourse_ok = 0
        try:
            is_MatchCourse_ok = 0
            get_session_id = get_task.get(
                redis_manager.RedisManager.Function_DataID, None
            )
            set_skills_col = get_task.get("skills_col", [])
            set_shortlist_df = get_task.get("shortlist_df", [])
            set_search_skills = get_task.get("search_skills", [])
            set_srlst_df = Utility.dict_list_to_dataframe(set_shortlist_df)
            set_srch_sk = Utility.dict_to_set(set_search_skills)
            # get_validated_data=await self.ai_planning(set_skills_col,set_srlst_df,set_srch_sk)
            get_validated_data = await self.ai_planning_GPT(
                set_skills_col, set_srlst_df, set_srch_sk
            )
        except Exception as e:
            is_MatchCourse_ok = -1
            print("MatchCourse::courses_recommend_handle():", e)
            time.sleep(1)

        if get_validated_data is None:
            get_validated_data = {"recommendations": []}

        result = {
            redis_manager.RedisManager.Function_Name: "courses_recommend",
            redis_manager.RedisManager.Function_DataID: get_session_id,
            "validated_data": get_validated_data,
            "error": is_MatchCourse_ok,
        }
        await self._rds_man_obj.queue_push(
            result, redis_manager.RedisKeyInternalMain.MAIN_FastAPI_In.value
        )

    @override
    async def work(self, **kwargs):
        action_map = {
            "courses_recommend": self.courses_recommend_handle,
        }
        await self.work_task(
            redis_manager.RedisKeyInternalMain.MAIN_MatchCourse_In.value,
            redis_manager.RedisManager.Function_Name,
            action_map,
        )
