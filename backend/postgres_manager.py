import asyncio
import time
from typing import Any, Dict, List

import asyncpg
import pandas as pd
import redis_manager

# import psycopg2
import singleton as sgtn
import Utility
from typing_extensions import override


class PostgresManager(sgtn.Singleton_C):
    def __init__(self):
        super().__init__()
        self.host = "localhost"
        self.port = 15432
        self.user = "admin"
        self.password = "admin"
        self.dbname = "projectdb"
        self.conn = None

    async def connect_postgres(self, do_calculate: bool = True, **kwargs) -> bool:
        self._rds_man_obj = await redis_manager.RedisManager.get_object()
        params = {}
        for key, value in kwargs.items():
            params[key] = value
        self.host = params.get("host", self.host)
        self.port = params.get("port", self.port)
        self.user = params.get("user", self.user)
        self.password = params.get("password", self.password)
        self.dbname = params.get("dbname", self.dbname)
        print(
            f"PostgreSQL 連線參數: {self.host}:{self.port}, {self.user}, {self.dbname}"
        )
        for i in range(0, 10):
            try:
                self.conn = await asyncpg.connect(
                    host=self.host,
                    port=self.port,
                    user=self.user,
                    password=self.password,
                    database=self.dbname,
                )
                if do_calculate:
                    if await self.calculate_data() > 0:
                        print("完成連線")
                        break
                    else:
                        print("PostgreSQL重新計算中...", i, "/10")
                        self.conn = None
                        time.sleep(10)
                else:
                    break
            except Exception as e:
                self.conn = None
                print(f"PostgreSQL 連線失敗: {e} ,", i, "/10")
                time.sleep(1)

    async def close_postgres(self) -> None:
        if not self.conn:
            print("PostgreSQL 連線未建立")
            return
        await self.conn.close()
        print("PostgreSQL 連線已關閉")

    async def search_job(self, **kwargs) -> List[Any]:
        if not self.conn:
            print("請先連接到 PostgreSQL 資料庫")
            return None
        # job_id:[str],job_title:[str],salary:[int or str,2],city:[str],job_description:str
        kwargs_names = ["job_id", "job_title", "salary", "city", "job_description"]#
        column_names = ["job_id", "職缺名稱", "薪資", "上班地點", "職缺描述"]#上班地點 城市
        sql_where = ""
        params = {}

        for key, value in kwargs.items():
            params[key] = value
        # print("search_job:",params)
        s_job_id = params.get("job_id", None)
        if s_job_id:
            # id IN (1, 3, 5, 7);
            sql_where += f"{column_names[0]} IN ("
            for id_one in s_job_id:
                sql_where += f"{id_one}, "
            sql_where = sql_where.rsplit(", ", 1)[0]
            sql_where += ") AND "
        s_job_title = params.get("job_title", None)
        if s_job_title:
            # name LIKE '%張%';
            sql_where += " ( "
            for title_one in s_job_title:
                sql_where += f"{column_names[1]} LIKE '%{title_one}%' OR "
            sql_where = sql_where.rsplit("OR", 1)[0]
            sql_where += ") AND "
        s_salary = params.get("salary", None)
        if s_salary:
            salary_column = ["薪資下限", "薪資上限"]
            salary_singl = [">=", "<="]
            qur_tmp = " ( "
            for i in range(0, 2):
                set_salary_num = 0
                if s_salary[i] > 0:
                    set_salary_num = int(s_salary[i])
                qur_tmp = (
                    qur_tmp
                    + f"{salary_column[i]} {salary_singl[i]} {set_salary_num} AND "
                )
            qur_tmp = qur_tmp.rsplit("AND", 1)[0]
            qur_tmp = qur_tmp + " ) AND "
            sql_where += qur_tmp

        s_city = params.get("city", None)
        if s_city:
            # city = '台北';
            sql_where += " ( "
            for city_one in s_city:
                sql_where += f"{column_names[3]} LIKE '%{city_one}%' OR "
            sql_where = sql_where.rsplit("OR", 1)[0]
            sql_where += ") AND "

        s_job_description = params.get("job_description", None)
        if s_job_description:
            sql_where += f"{column_names[4]} LIKE '%{s_job_description}%'  "

        # print("PostgresManager search_job() sql_where:",sql_where)
        if len(sql_where) <= 0:
            print("⚠️ 查詢條件不足")
            return None
        sql_where = sql_where.rsplit("AND", 1)[
            0
        ]  # sql_where.rsplit("AND", 1)從右邊開始切1次，回傳陣列=['除了最後一個AND之外', '']
        limit = kwargs.get("limit", 5000)
        sql_where += f"LIMIT {limit} ;"
        sql = """
        SELECT job_id, 職缺名稱, 公司名稱, 公司連結,上班地點, 國家, 薪資下限, 薪資上限,  職缺描述, skills, 職缺連結,薪資_月薪制,xgboost_預測薪資 
        FROM job_row_data
        WHERE """
        re_data = None
        sql = sql + sql_where
        print("PostgresManager search_job() SQL:", sql)
        try:
            # result = await self.conn.fetch(sql, (sql_where,))
            rows = await self.conn.fetch(sql)
            if rows:
                print("查詢成功(長度):", len(rows))
                result: List[Dict] = [dict(r) for r in rows]
                re_data = result
            else:
                print("⚠️ 查無此條件:", kwargs)
        except Exception as e:
            print(f"查詢失敗: {e}")
        return re_data

    async def search_courses_recommend(self, skills: str) -> dict:
        """
        使用 PostgreSQL 取代 CSV 的課程推薦流程
        """

        if not skills:
            return {"error": -1, "recommendations": []}
        if len(skills) <= 0:
            return {"error": -11, "recommendations": []}
        skills_list = []
        for i in skills:
            skills_list.append(i.split("、"))
        flattened = [item for sublist in skills_list for item in sublist]
        # 標準化技能（小寫、去空白）
        search_skills = {s.strip().lower() for s in flattened if s.strip()}
        if not search_skills:
            return {"error": -2, "recommendations": []}

        # SQL 查詢：使用 UNNEST 展開使用者技能，JOIN courses
        sql = """
        WITH matched AS (
            SELECT c.*, s.skill AS matched_skill,
            ROW_NUMBER() OVER (
                PARTITION BY s.skill
                ORDER BY 
                    CASE 
                        WHEN credibility_tier LIKE 'Tier 1%' THEN 1
                        WHEN credibility_tier LIKE 'Tier 2%' THEN 2
                        ELSE 3 
                    END,
                    rating_numeric DESC NULLS LAST,
                    review_count DESC NULLS LAST
            ) AS rn
            FROM coursera_row_data c
            CROSS JOIN UNNEST($1::text[]) AS s(skill)
            WHERE EXISTS (
                SELECT 1 FROM UNNEST(c.skills) AS skill_item 
                WHERE LOWER(skill_item) LIKE '%' || LOWER(s.skill) || '%'
            )
            AND credibility_tier IN ('Tier 1: 頂級明星', 'Tier 2: 穩固明星')
        )
        SELECT DISTINCT ON (COALESCE(course_url, course_name)) *
        FROM matched WHERE rn <= 1;
        """
        #
        print(list(search_skills))
        rows = await self.conn.fetch(sql, list(search_skills))

        if not rows:
            return {"error": -3, "recommendations": []}

        # 轉成 DataFrame
        df = pd.DataFrame([dict(r) for r in rows])
        shortlist_df = Utility.dataframe_to_dict_list(df)
        return_search_skills = Utility.set_to_dict(search_skills)
        # print("shortlist_df:",shortlist_df)
        # 保持與舊版一致的回傳結構
        return {
            "error": 0,
            "skills_col": "skills",  # DB schema 統一用 skills 欄位
            "shortlist_df": shortlist_df,
            "search_skills": return_search_skills,
        }

    async def get_all_databases(self) -> List[str]:
        rows = await self.conn.fetch(
            """
            SELECT datname
            FROM pg_database
            WHERE datistemplate = false
            AND datname NOT IN ('postgres')
        """
        )
        return [r["datname"] for r in rows]

    async def get_all_tables(self) -> List[tuple]:
        rows = await self.conn.fetch(
            """
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
            AND table_type = 'BASE TABLE'
        """
        )
        return [(r["table_schema"], r["table_name"]) for r in rows]

    async def estimate_table_rows(self, schema, table) -> int:
        row = await self.conn.fetchrow(
            """
            SELECT reltuples::bigint AS estimate
            FROM pg_class
            WHERE oid = $1::regclass
        """,
            f"{schema}.{table}",
        )
        return int(row["estimate"]) if row else 0

    async def process_database(self, dbname) -> int:
        tables = await self.get_all_tables()
        total = 0
        print("---Postgres table 檢測開始 ---")
        for schema, table in tables:
            count = await self.estimate_table_rows(schema, table)
            total += count
            print(f"[{dbname}.{schema}.{table}] -> {count} rows (estimated)")
            if count < 0 and table != "members" and table != "chat_history":
                print("table:", table)
                total = count
                break
        return total

    async def calculate_data(self) -> int:
        if not self.conn:
            print("PostgreSQL 連線未建立")
            return
        databases = await self.get_all_databases()
        get_count_list = await asyncio.gather(
            *[self.process_database(db) for db in databases]
        )
        if any(x < 0 for x in get_count_list):
            results = -1
        else:
            results = sum(get_count_list)
        print("---Postgres 檢測結束 ---\n")
        return results

    async def process_job_search_handle(self, get_task: dict) -> None:
        result = None
        is_postgres_ok = 0

        # --- START: 新增的連線檢查與重連邏輯 ---
        if not self.conn or self.conn.is_closed():
            print("⚠️ PostgreSQL 連線遺失，嘗試重新連線...")
            # 這裡的 connect_postgres 也需要確保能處理好 Docker 內部的服務名稱
            await self.connect_postgres(
                do_calculate=False,  # 重連時不需要重新計算資料筆數
                host="Postgres16",
                port=5432,
                user="admin",
                password="admin",
                dbname="projectdb",
            )
            if not self.conn:
                print("❌ PostgreSQL 重連失敗，任務無法執行。")
                # 可以考慮將任務推回隊列或記錄到錯誤日誌
                # ...
                return  # 直接返回，不執行後續邏輯
        # --- END: 新增邏輯 ---

        for i in range(0, 5):
            try:
                # set_job_id=get_task.get("job_id",None)
                # set_job_title=get_task.get("job_title",None)
                set_salary = get_task.get("salary_range", None)
                set_city = get_task.get("city", None)
                session_id = get_task.get(
                    redis_manager.RedisManager.Function_DataID, None
                )
                print(set_city)
                result = await self.search_job(salary=set_salary, city=set_city)
                is_postgres_ok = 0
                break
            except Exception as e:
                is_postgres_ok = -1
                result = None
                print("postgres_work():", e, ";retry ", i, "/5")
                time.sleep(1)
                self.connect_postgres()
        if result == None:
            result = {}
        await self._rds_man_obj.push_search_PostgresResult(session_id, result)

    async def job_skills_handle(self, get_task: dict) -> None:
        is_postgres_ok = 0
        for i in range(0, 5):
            try:
                set_skills = get_task.get("select_skills", [])
                get_session_id = get_task.get(
                    redis_manager.RedisManager.Function_DataID, None
                )
                get_recommend = await self.search_courses_recommend(set_skills)
                is_postgres_ok = 0
                break
            except Exception as e:
                is_postgres_ok = -1
                print("postgres_work():", e, ";retry ", i, "/5")
                time.sleep(1)
                self.connect_postgres()
        if get_recommend["error"] == 0 and is_postgres_ok == 0:
            result = {
                redis_manager.RedisManager.Function_Name: "courses_recommend",
                redis_manager.RedisManager.Function_DataID: get_session_id,
                "error": 0,
                "skills_col": "skills",
                "shortlist_df": get_recommend["shortlist_df"],
                "search_skills": get_recommend["search_skills"],
            }
        else:
            print("job_skills error:", get_recommend, is_postgres_ok)
            result = {
                redis_manager.RedisManager.Function_Name: "courses_recommend",
                redis_manager.RedisManager.Function_DataID: get_session_id,
                "error": get_recommend["error"] * 10 + is_postgres_ok,
            }
        await self._rds_man_obj.queue_push(
            result, redis_manager.RedisKeyInternalMain.MAIN_MatchCourse_In.value
        )

    @override
    async def work(self, **kwargs) -> None:
        action_map = {
            "process_job_search": self.process_job_search_handle,
            "job_skills": self.job_skills_handle,
        }
        await self.work_task(
            redis_manager.RedisKeyInternalMain.MAIN_Postgres_In.value,
            redis_manager.RedisManager.Function_Name,
            action_map,
        )

    @override
    async def work_test(self, **kwargs):
        """
        {
        "job_title": ["工程師","分析師","程式設計"],
        "work_location": ["台北","桃園","新竹"],
        "salary_range": [40000,50000],
        "job_description": "程式設計"
        }

        """
        get_test_task = await self._rds_man_obj.test_queue_pop(
            redis_manager.RedisKeyTestMain.MAIN_Postgres_Test.value
        )
        if not get_test_task:
            return
        print("postgres_test():", get_test_task)
        test_task = get_test_task["test_data_queue"]
        # # print("test_task:",test_task,type(test_task))
        # set_job_id=test_task.get("job_id",None)
        # set_job_title=test_task.get("job_title",None)
        # set_salary=test_task.get("salary_range",None)
        # set_city=test_task.get("work_location",None)
        # set_job_description=test_task.get("job_description",None)
        # print(set_job_id,set_job_title,set_salary,set_city,set_job_description)
        # result=await self.search_job(job_id=set_job_id,job_title=set_job_title,
        #     salary=set_salary,city=set_city, job_description=set_job_description)
        # print("postgres result:",result[0:2])
        try:
            """
            {
            "select_skills":["系統架構規劃、軟體工程系統開發、軟體程式設計、結構化程式設計、模組化系統設計、機器學習、AI"],
            "session_id":"tttttttt"
            }

            """
            set_skills = test_task.get("select_skills", [])
            get_session_id = get_test_task.get("session_id", None)
            print("select_skills:", set_skills, type(set_skills))
            get_recommend = await self.search_courses_recommend(set_skills)
        except Exception as e:
            print(e)

        if get_recommend["error"] == 0:
            # print("job_skills get_recommend:",get_recommend)
            result = {
                redis_manager.RedisManager.Function_Name: "courses_recommend",
                redis_manager.RedisManager.Function_DataID: get_session_id,
                "skills_col": "skills",
                "shortlist_df": get_recommend["shortlist_df"],
                "search_skills": get_recommend["search_skills"],
            }
            await self._rds_man_obj.queue_push(
                result, redis_manager.RedisKeyInternalMain.MAIN_MatchCourse_In.value
            )
        else:
            print("job_skills error:", get_recommend)
        pass

        # debug_sql = """
        #     SELECT DISTINCT UNNEST(skills) as skill_item
        #     FROM coursera_row_data
        #     WHERE LOWER(array_to_string(skills, ' ')) LIKE '%ai%'
        #     LIMIT 10;
        # """
        # rows = await self.conn.fetch(debug_sql)
        # print("包含 'ai' 的技能:", rows)
        # tier_sql = """
        #     SELECT DISTINCT credibility_tier, COUNT(*)
        #     FROM coursera_row_data
        #     GROUP BY credibility_tier;
        # """
        # rows = await self.conn.fetch(tier_sql)
        # print("Credibility tiers:", rows)
        # simple_sql = """
        #     SELECT course_name, skills, credibility_tier
        #     FROM coursera_row_data
        #     WHERE LOWER(array_to_string(skills, ' ')) LIKE '%ai%'
        #     LIMIT 5;
        # """
        # rows = await self.conn.fetch(simple_sql)
        # print("簡單測試結果:", rows)
        # test_sql = """
        #     SELECT course_name, skills, credibility_tier
        #     FROM coursera_row_data
        #     WHERE LOWER(array_to_string(skills, ' ')) LIKE '%generative ai%'
        #     AND credibility_tier IN ('Tier 1: 頂級明星', 'Tier 2: 穩固明星')
        #     LIMIT 3;
        # """
        # test_rows = await self.conn.fetch(test_sql)
        # print("驗證結果:", test_rows)
