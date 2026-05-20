import json
import time
from enum import Enum, auto
from typing import Any, Dict, List

import redis
import redis.asyncio as aioredis
import singleton as sgtn


class RedisDataBasesEnum(Enum):
    DockerToDocker = 0
    MAIN = auto()
    DB = auto()


class RedisTableEnum1(Enum):
    MAIN_String_CHAT = 0
    MAIN_List_Test = auto()
    MAIN_List_Queue = auto()
    MAIN_List_JobMilvusResult = auto()
    MAIN_List_JobPostgresResult = auto()


class RedisKeyInternalMain(Enum):
    MAIN_Postgres_In = 0
    MAIN_Milvus_In = auto()  # 1
    # MAIN_MongoDB_In = auto()#2
    MAIN_OpenAI_In = auto()  # 3
    MAIN_FastAPI_In = auto()  # 4
    MMAIN_SearchDataProcess_In = auto()  # 5
    MAIN_MatchCourse_In = auto()


class RedisKeyTestMain(Enum):
    MAIN_Postgres_Test = 0
    MAIN_Milvus_Test = auto()  # 1
    MAIN_OpenAI_Test = auto()  # 2


class RedisTable:
    databases_num: int = 0
    enmu_def: Enum = None


class RedisDataBases:
    databases_url: str = ""
    databases_num: int = 0
    databases_obj: redis.asyncio.client.Redis = None
    rds_tbls: List[RedisTable] = []


class RedisManager(sgtn.Singleton_C):
    Function_Name = "Function_Name"
    Function_DataID = "Function_DataID"

    def __init__(self):
        super().__init__()
        self._rds_man_obj = self
        self.__redis_host = "redis7"  # redis7 localhost
        self.__redis_port = 6379
        self.__redis_password = "admin"
        self.__redis_databases = [RedisDataBases()]
        # redis://:password@hostname:port/db_number
        self.__redis_url_base = (
            str("redis://:")
            + str(self.__redis_password)
            + str("@")
            + str(self.__redis_host)
            + str(":")
            + str(self.__redis_port)
            + str("/")
        )
        self.__redis_test_key = "test_key"
        self.isConnect = False
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass

    def __enum_from(self, enum_class, start_value):
        for member in enum_class:
            if member.value >= start_value:
                yield member

    async def connect_redis(self, **kwargs) -> bool:
        params = {}
        for key, value in kwargs.items():
            params[key] = value
        self.__redis_host = params.get("host", self.__redis_host)
        self.__redis_port = params.get("port", self.__redis_port)
        self.__redis_password = params.get("password", self.__redis_password)
        self.__redis_url_base = (
            str("redis://:")
            + str(self.__redis_password)
            + str("@")
            + str(self.__redis_host)
            + str(":")
            + str(self.__redis_port)
            + str("/")
        )
        print("\n🔴 連線Redis的databases:")
        self.__redis_databases.clear()
        max_retries = 3
        connect_up = 0
        for attempt in range(1, max_retries + 1):
            try:
                self.isConnect = True
                for i in self.__enum_from(RedisDataBasesEnum, connect_up):
                    rds_new_obj = RedisDataBases()
                    rds_new_obj.databases_num = i.value
                    rds_new_obj.databases_url = self.__redis_url_base + str(i.value)
                    rds_new_obj.databases_obj = aioredis.from_url(
                        rds_new_obj.databases_url, decode_responses=True
                    )
                    if await rds_new_obj.databases_obj.ping():
                        print(
                            f"✅ Redis connected [{rds_new_obj.databases_num}] successfully."
                        )
                    self.__redis_databases.append(rds_new_obj)
                    await rds_new_obj.databases_obj.flushdb()
                    connect_up = connect_up + 1

            except Exception as e:
                print(f"❌ Redis connection failed: {e}")
                self.isConnect = False
                if attempt == max_retries:
                    print("停止重試。")
                else:
                    print(f"準備重試({attempt}/3)...")
                time.sleep(1)

        print("定義Redis的table(key):")
        for k in RedisTableEnum1:
            rds_tbl_obj = RedisTable()
            rds_tbl_obj.enmu_def = k
            rds_tbl_obj.databases_num = RedisDataBasesEnum.MAIN.value
            self.__redis_databases[rds_tbl_obj.databases_num].rds_tbls.append(
                rds_tbl_obj
            )
            print(rds_tbl_obj.enmu_def, rds_tbl_obj.databases_num)
        print("--- 檢測Redis內容 ---")
        for u in RedisDataBasesEnum:
            print(f"=== Redis 資料庫{u.name}({u.value})內容 ===")
            await self.inspect_redis_keys(u.value)
        print("--- Redis 檢測完成 ---\n")
        return self.isConnect

    async def close_redis(self):
        max_retries = 3
        connect_down = 0
        isDisconnect = False
        print("Redis 關閉中...")
        for attempt in range(1, max_retries + 1):
            try:
                isDisconnect = True
                for i in self.__enum_from(RedisDataBasesEnum, connect_down):
                    await self.__redis_databases[i.value].databases_obj.close()
                    connect_down = connect_down + 1

            except Exception as e:
                print(f"❌ Redis close failed: {e}")
                isDisconnect = False
                if attempt == max_retries:
                    print("停止重試。")
                else:
                    print(f"準備重試({attempt}/3)...")
                time.sleep(1)
        return isDisconnect

    async def inspect_redis_keys(self, db: int = 0) -> Dict[str, Any]:
        result = {}
        try:
            redis_client = self.__redis_databases[db].databases_obj
            keys = await redis_client.keys("*")  # 取得所有 key
            for key in keys:
                key_str = key  # bytes -> str
                key_type = await redis_client.type(key)

                if key_type == b"string":
                    count = 1
                elif key_type == b"list":
                    count = await redis_client.llen(key)
                elif key_type == b"set":
                    count = await redis_client.scard(key)
                elif key_type == b"hash":
                    count = await redis_client.hlen(key)
                elif key_type == b"zset":
                    count = await redis_client.zcard(key)
                else:
                    count = None  # 其他類型或未知

                result[key_str] = {"type": key_type, "count": count}

            for key, info in result.items():
                print(f"Key: {key} | Type: {info['type']} | Count: {info['count']}")
        except Exception as e:
            print("Redis 資料庫閱讀錯誤:", e)
        finally:
            print(f"=== Redis 資料庫{db}內容結束 ===")
            #     await redis_client.close()
        return result

    def __get_table(self, db: int, table: int) -> tuple:
        return (
            self.__redis_databases[db].rds_tbls[table],
            self.__redis_databases[db].databases_obj,
        )

    async def add_chat(self, session_id: str, data: dict) -> bool:
        rds_chat_key, rds_chat_obj = self.__get_table(
            RedisDataBasesEnum.MAIN.value, RedisTableEnum1.MAIN_String_CHAT.value
        )
        redis_key = f"{rds_chat_key.enmu_def.name}_{session_id}"
        for i in range(0, 2):
            try:
                await rds_chat_obj.set(
                    redis_key,
                    json.dumps(
                        {
                            "messages": self.__to_serializable(data["messages"]),
                            # "current_agent": self.__to_serializable(data["current_agent"])
                        }
                    ),
                )
                break
            except Exception as e:
                print("add_chat():", e)
                rds_chat_obj = aioredis.from_url(
                    self.__redis_url_base + str(RedisDataBasesEnum.MAIN.value),
                    decode_responses=True,
                )
        return True

    async def load_chat_session(self, session_id: str) -> tuple:
        """從 Redis 載入 session 對話"""
        data = None
        rds_chat_key, rds_chat_obj = self.__get_table(
            RedisDataBasesEnum.MAIN.value, RedisTableEnum1.MAIN_String_CHAT.value
        )
        redis_key = f"{rds_chat_key.enmu_def.name}_{session_id}"
        for i in range(0, 2):
            try:
                data = await rds_chat_obj.get(redis_key)
                if data:
                    data = json.loads(data)
                    return data["messages"]
            except Exception as e:
                print("load_chat_session():", e)
                rds_chat_obj = aioredis.from_url(
                    self.__redis_url_base + str(RedisDataBasesEnum.MAIN.value),
                    decode_responses=True,
                )
        return []

    def __to_serializable(self, obj):
        if isinstance(obj, (str, int, float, bool)) or obj is None:
            return obj
        elif isinstance(obj, dict):
            return {k: self.__to_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self.__to_serializable(v) for v in obj]
        elif hasattr(obj, "__dict__"):
            return {k: self.__to_serializable(v) for k, v in obj.__dict__.items()}
        else:
            return str(obj)

    # -------------------------------------------------------------------------------------------------------------------------------
    # -------------------------------------------------------------------------------------------------------------------------------
    async def __queue_push_base(
        self, value: dict, set_key: str, rds_table_index: int
    ) -> int:
        """
        將資料轉為 JSON 後加入 Queue 尾端，回傳當前長度
        value 可以是 dict、list、str 等可序列化物件
        """
        if not self.isConnect:
            print(f"queue_push() error: isConnect:{self.isConnect}")
            return -1
        rds_test_key, rds_db_obj = self.__get_table(
            RedisDataBasesEnum.MAIN.value, rds_table_index
        )
        redis_key = f"{rds_test_key.enmu_def.name}_{set_key}"
        try:
            json_str = json.dumps(value, ensure_ascii=False)
        except Exception as e:
            print("queue_push_base() error:", e)
        # print(f"queue_push(): {redis_key} -> {json_str}")
        return await rds_db_obj.rpush(redis_key, json_str)

    async def queue_push(self, value: dict, index: int) -> int:
        redis_key = f"{index}"
        return await self.__queue_push_base(
            value, redis_key, RedisTableEnum1.MAIN_List_Queue.value
        )

    async def test_queue_push(self, value: dict, test_index: int) -> int:
        redis_key = f"{test_index}"
        return await self.__queue_push_base(
            value, redis_key, RedisTableEnum1.MAIN_List_Test.value
        )

    async def __push_search_base(
        self, session_id: str, data: List[dict], redis_key: str, redis_table: int
    ) -> bool:
        """將搜尋結果推送到指定的 Redis Key"""
        try:
            data_stuct = {"session_id": session_id, "data": data}
            await self.__queue_push_base(data_stuct, redis_key, redis_table)
            return True
        except Exception as e:
            print("__push_search_base():", e)
            return False

    async def push_search_MilvusResult(self, session_id: str, data: List[dict]) -> bool:
        redis_key = f"{RedisTableEnum1.MAIN_List_JobMilvusResult.name}_{session_id}"
        return await self.__push_search_base(
            session_id, data, redis_key, RedisTableEnum1.MAIN_List_JobMilvusResult.value
        )

    async def push_search_PostgresResult(
        self, session_id: str, data: List[dict]
    ) -> bool:
        redis_key = f"{RedisTableEnum1.MAIN_List_JobPostgresResult.name}_{session_id}"
        return await self.__push_search_base(
            session_id,
            data,
            redis_key,
            RedisTableEnum1.MAIN_List_JobPostgresResult.value,
        )

    # -------------------------------------------------------------------------------------------------------------------------------
    # -------------------------------------------------------------------------------------------------------------------------------
    async def __queue_pop_base(self, set_key: str, rds_table_index: int) -> dict | None:
        """
        從 Queue 頭端取出 JSON 資料並轉回 Python 物件
        """
        if not self.isConnect:
            return None
        rds_test_key, rds_db_obj = self.__get_table(
            RedisDataBasesEnum.MAIN.value, rds_table_index
        )
        redis_key = f"{rds_test_key.enmu_def.name}_{set_key}"
        raw = await rds_db_obj.lpop(redis_key)
        # await r.lrange(key, 0, 0)
        if raw != None:
            # print(f"queue_pop(): {redis_key} <- {raw}")
            get_task = json.loads(raw)
            return get_task
        return None

    async def queue_pop(self, index: int) -> dict | None:
        redis_key = f"{index}"
        return await self.__queue_pop_base(
            redis_key, RedisTableEnum1.MAIN_List_Queue.value
        )

    async def test_queue_pop(self, test_index: int) -> dict | None:
        redis_key = f"{test_index}"
        return await self.__queue_pop_base(
            redis_key, RedisTableEnum1.MAIN_List_Test.value
        )

    async def __pop_search_base(self, redis_key: str, redis_table: int) -> dict | None:
        data = None
        try:
            data = await self.__queue_pop_base(redis_key, redis_table)
            return data
        except Exception as e:
            print("__pop_search_base():", e)
        return None

    async def pop_search_MilvusResult(self, session_id: str) -> dict:
        redis_key = f"{RedisTableEnum1.MAIN_List_JobMilvusResult.name}_{session_id}"
        return await self.__pop_search_base(
            redis_key, RedisTableEnum1.MAIN_List_JobMilvusResult.value
        )

    async def pop_search_PostgresResult(self, session_id: str) -> dict:
        redis_key = f"{RedisTableEnum1.MAIN_List_JobPostgresResult.name}_{session_id}"
        return await self.__pop_search_base(
            redis_key, RedisTableEnum1.MAIN_List_JobPostgresResult.value
        )

    async def check_search_MilvusResult(self, session_id: str) -> bool:
        rds_test_key, rds_db_obj = self.__get_table(
            RedisDataBasesEnum.MAIN.value,
            RedisTableEnum1.MAIN_List_JobMilvusResult.value,
        )
        redis_key = f"{rds_test_key.enmu_def.name}_{RedisTableEnum1.MAIN_List_JobMilvusResult.name}_{session_id}"
        return await rds_db_obj.exists(redis_key) > 0

    async def check_search_PostgresResult(self, session_id: str) -> bool:
        rds_test_key, rds_db_obj = self.__get_table(
            RedisDataBasesEnum.MAIN.value,
            RedisTableEnum1.MAIN_List_JobPostgresResult.value,
        )
        redis_key = f"{rds_test_key.enmu_def.name}_{RedisTableEnum1.MAIN_List_JobPostgresResult.name}_{session_id}"
        return await rds_db_obj.exists(redis_key) > 0

    # --- START: 在類別末尾新增這個函式 ---
    def get_db_client(self, db_enum: RedisDataBasesEnum) -> redis.asyncio.client.Redis:
        """
        公開的輔助函式，用於安全地獲取指定 DB 的 redis 客戶端實例。
        """
        try:
            db_index = db_enum.value
            if 0 <= db_index < len(self._RedisManager__redis_databases):
                return self._RedisManager__redis_databases[db_index].databases_obj
        except Exception as e:
            print(f"獲取 Redis client 失敗: {e}")
        return None

    # --- END: 新增函式 ---