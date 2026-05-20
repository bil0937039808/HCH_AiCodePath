# AIPE01_G4_AiCodePath/backend/search_data_procese.py

import ast
import json
import os
import re
import time
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import psycopg2
import redis_manager
import singleton as sgtn
import Utility
from typing_extensions import override


class SearchDataProcess(sgtn.Singleton_C):
    def __init__(self):
        super().__init__()
        self.id_pool = []

    async def init_SearchDataProcess(self) -> None:
        self._rds_man_obj = await redis_manager.RedisManager.get_object()
        self.id_pool.clear()

    # --- START: 最終修正版的資料清理函式 ---
    def _clean_conversation_for_db(self, conversation: List[Dict]) -> List[Dict]:
        """
        清理從 Redis 讀取的對話紀錄，只保留使用者和助理的對話，
        並徹底過濾掉所有內部工具呼叫紀錄。
        """
        cleaned_convo = []
        if not isinstance(conversation, list):
            return cleaned_convo  # 如果傳入的不是列表，直接返回空列表

        for msg in conversation:
            # 1. 驗證訊息格式：必須是字典且包含 'role' 鍵
            if not isinstance(msg, dict) or "role" not in msg:
                continue

            role = msg.get("role")
            content = msg.get("content")

            # 2. 只處理 role 為 'user' 或 'assistant' 的訊息
            if role not in ["user", "assistant"]:
                continue

            cleaned_msg = {"role": role, "content": ""}

            if role == "user":
                if isinstance(content, str):
                    # 從 "session_id:...,text:..." 中提取真正的使用者訊息
                    match = re.search(r"text:(.*)", content, re.DOTALL)
                    cleaned_msg["content"] = (
                        match.group(1).strip() if match else content
                    )
                else:
                    cleaned_msg["content"] = str(content if content is not None else "")

            elif role == "assistant":
                # 從 Agent 回傳的複雜物件中提取純文字回應
                if (
                    isinstance(content, list)
                    and len(content) > 0
                    and isinstance(content[0], dict)
                ):
                    cleaned_msg["content"] = content[0].get("text", "")
                elif isinstance(content, str):
                    cleaned_msg["content"] = content
                else:
                    cleaned_msg["content"] = str(content if content is not None else "")

            # 3. 確保訊息內容不是空的才加入
            if cleaned_msg.get("content"):
                cleaned_convo.append(cleaned_msg)

        return cleaned_convo

    # --- END FIX ---

    async def save_chat_history(
        self,
        session_id: str,
        member_id: int,
        conversation: List[Dict],
        final_jobs: List[Dict],
    ):
        conn = None
        try:
            conn = psycopg2.connect(
                dbname=os.getenv("POSTGRES_DB"),
                user=os.getenv("POSTGRES_USER"),
                password=os.getenv("POSTGRES_PASSWORD"),
                host=os.getenv("POSTGRES_HOST", "Postgres16"),
                port=os.getenv("POSTGRES_PORT", "5432"),
            )

            cleaned_conversation = self._clean_conversation_for_db(conversation)

            with conn.cursor() as cur:
                conversation_json = json.dumps(cleaned_conversation, ensure_ascii=False)
                jobs_str = ", ".join(
                    [job.get("jobTitle", "N/A") for job in final_jobs[:5]]
                )

                cur.execute(
                    """
                    INSERT INTO chat_history (member_id, conversation, suggested_job_vacancy)
                    VALUES (%s, %s, %s)
                    """,
                    (member_id, conversation_json, jobs_str),
                )
                conn.commit()
            print(
                f"成功為使用者 member_id:{member_id} (session: {session_id}) 儲存一筆歷史紀錄。"
            )
        except Exception as e:
            print(f"儲存歷史紀錄到 PostgreSQL 時發生錯誤: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()

    def process_JobSearch_data(self, milvusData: dict, postgresData: dict):
        job_result = []
        if not milvusData and not postgresData:
            print("沒有可處理的職缺資料。")
            return job_result

        if milvusData != {} and postgresData != {}:
            try:
                ids1 = np.array([d["id"] for d in milvusData["data"]])
                ids2 = np.array([d["job_id"] for d in postgresData["data"]])
                common_ids = np.intersect1d(ids1, ids2)

                if len(common_ids) <= 0:
                    return []
                else:
                    job_data = [
                        d for d in postgresData["data"] if d["job_id"] in common_ids
                    ]
                    keep_fields = [
                        "companyName",
                        "jobTitle",
                        "location",
                        "salary",
                        "skills",
                        "jobLink",
                    ]
                    rename_map = {
                        "職缺名稱": "jobTitle",
                        "xgboost_預測薪資": "salary",#XGBoost_預測薪資 薪資_月薪制
                        "上班地點": "location",
                        "公司名稱": "companyName",
                        "職缺連結": "jobLink",
                    }
                    # job_tmp1 = [
                    #     {rename_map.get(k, k): v for k, v in record.items()}
                    #     for record in job_data
                    # ]
                    job_tmp1 = []
                    # 逐筆處理 job_data 中的每一筆記錄
                    for record in job_data:
                        print(f"處理記錄: {record}")  # 可選：用於除錯
                        new_record = {}
                        for key, value in record.items():# 逐個處理記錄中的每個欄位
                            print(f"  處理欄位: {key} = {value}")  # 可選：用於除錯
                            if key in rename_map:# 檢查是否需要重新命名欄位
                                new_key = rename_map[key]# 使用重新命名後的欄位名稱
                                print(f"    重新命名: {key} -> {new_key}")  # 可選：用於除錯
                            else:
                                new_key = key # 保持原始欄位名稱
                                print(f"    保持原名: {key}")  # 可選：用於除錯
                            new_record[new_key] = value# 將處理後的鍵值對加入新記錄
                        #print(f"處理後的記錄: {new_record}")  # 可選：用於除錯
                        job_tmp1.append(new_record)# 將處理完的記錄加入結果列表
                    print(f"最終結果包含 {len(job_tmp1)} 筆記錄")
                    df = pd.DataFrame(job_tmp1)
                    filtered_df = df[keep_fields]
                    filtered_df = Utility.clean_skill_list_column(filtered_df, "skills")
                    job_result = filtered_df.to_dict("records")
            except Exception as e:
                print(f"SearchDataProcess::process_JobSearch_data() error: {e}")
        return job_result

    async def process_job_search_handle(self, get_task: dict) -> None:
        pack_data = None
        is_SearchDataProcess_ok = 0
        user_id = None

        if isinstance(get_task, str):
            user_id = get_task
            get_task = {}
        else:
            user_id = get_task.get(redis_manager.RedisManager.Function_DataID, None)

        if not user_id:
            if not self.id_pool:
                return
            user_id = self.id_pool.pop(0)

        for i in range(0, 5):
            try:
                if not (
                    await self._rds_man_obj.check_search_MilvusResult(user_id)
                ) or not (await self._rds_man_obj.check_search_PostgresResult(user_id)):
                    self.id_pool.append(user_id)
                    return

                get_job_milvus_result = await self._rds_man_obj.pop_search_MilvusResult(
                    user_id
                )
                get_job_postgres_result = (
                    await self._rds_man_obj.pop_search_PostgresResult(user_id)
                )
                job_result = self.process_JobSearch_data(
                    get_job_milvus_result, get_job_postgres_result
                )
                pack_data = {
                    redis_manager.RedisManager.Function_Name: "process_job_search_result",
                    redis_manager.RedisManager.Function_DataID: user_id,
                    "error": 0,
                    "data": job_result,
                }
                redis_key = f"session:{user_id}:member_id"
                redis_client = self._rds_man_obj.get_db_client(
                    redis_manager.RedisDataBasesEnum.MAIN
                )
                member_id = None
                if redis_client:
                    member_id = await redis_client.get(redis_key)

                if member_id and job_result:
                    print(
                        f"Redis: 找到對應的 member_id: {member_id}，準備儲存歷史紀錄。"
                    )
                    full_conversation = await self._rds_man_obj.load_chat_session(
                        user_id
                    )
                    if full_conversation:
                        await self.save_chat_history(
                            user_id,
                            int(member_id),
                            full_conversation,
                            job_result,
                        )
                else:
                    print(
                        f"未找到 member_id 或無職缺結果，跳過儲存歷史紀錄。 (member_id: {member_id})"
                    )

                is_SearchDataProcess_ok = 0
                break
            except Exception as e:
                print(
                    f"SearchDataProcess::process_job_search_handle(): {e} ;retry {i+1}/5"
                )
                time.sleep(1)
                is_SearchDataProcess_ok = -1

        if pack_data is None:
            pack_data = {
                redis_manager.RedisManager.Function_Name: "process_job_search_result",
                redis_manager.RedisManager.Function_DataID: user_id,
                "error": is_SearchDataProcess_ok,
                "data": [],
            }

        await self._rds_man_obj.queue_push(
            pack_data, redis_manager.RedisKeyInternalMain.MAIN_FastAPI_In.value
        )

    @override
    async def work(self, **kwargs) -> None:
        get_task = await self._rds_man_obj.queue_pop(
            redis_manager.RedisKeyInternalMain.MMAIN_SearchDataProcess_In.value
        )
        if (get_task is None) and (len(self.id_pool) <= 0):
            return

        task_to_process = None
        if get_task is not None:
            task_to_process = dict(get_task)
            print("SearchDataProcess_work():", task_to_process)
        elif len(self.id_pool) > 0:
            task_to_process = self.id_pool.pop(0)

        if task_to_process:
            await self.process_job_search_handle(task_to_process)
