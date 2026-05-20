import time
import os
import asyncio
from pymilvus import connections, utility,Collection,AsyncMilvusClient
from pymilvus.client.search_result import SearchResult
import singleton as sgtn
import redis_manager
from openai import OpenAI
from typing import List, Dict, Any
from typing_extensions import override
class MilvusManager(sgtn.Singleton_C):
    # 從環境變數或預設值取得 Milvus 連線資訊
    def __init__(self):
        super().__init__()
        self.__milvus_host = os.environ.get("MILVUS_HOST", "milvus")
        self.__milvus_port = os.environ.get("MILVUS_PORT", "19530")
        self.__milvus_name = "default"
        self.__async_client = None
        self.__collection_names: list[str] = None
        self.__client_openAI=None
        pass

    async def connect_milvus(self,set_api_key:str,max_retry: int = 10, interval: int = 3,do_calculate:bool=True,**kwargs)->bool:
        """嘗試連接到 Milvus 服務"""
        self._rds_man_obj=await redis_manager.RedisManager.get_object()
        self.__client_openAI = OpenAI(api_key=set_api_key)
        params={}
        for key, value in kwargs.items():
            params[key]=value
        self.__milvus_host = params.get("host", self.__milvus_host)
        self.__milvus_port = params.get("port", self.__milvus_port)
        self.__milvus_name=params.get("alias", self.__milvus_name)
        for i in range(1, max_retry + 1):
            try:
                connections.connect(alias=self.__milvus_name, host=self.__milvus_host, port=self.__milvus_port)
                # 建立非同步客戶端
                self.__async_client = AsyncMilvusClient(uri=f"{self.__milvus_host}:{self.__milvus_port}", alias=self.__milvus_name)
                # 列出所有 Collection
                self.__collection_names = utility.list_collections()
                print("✅ Milvus 成功連接:", self.__collection_names,self.__async_client)
                time.sleep(2)
                if do_calculate:
                    print("開始計算資料...")
                    for u in range(1, max_retry + 1):
                        if(await self.calculate_data() == 0):
                            break
                        print("Milvus檢測重試中...",u,"/",max_retry + 1)
                        time.sleep(10)
                return True
            except Exception as e:
                print(f"⏳ Milvus 無法連接 ({i}/{max_retry}); 重試 {self.__milvus_host}:{self.__milvus_port} ;{interval}s...")
                print("錯誤:",e)
                time.sleep(interval)
        print(f"❌ Milvus 連接失敗 {max_retry} 次.")
        return False

    async def close_milvus(self):
        await self.__async_client.close()

    async def calculate_data(self)-> int:
        """列出所有 Collection 並顯示其資料筆數"""
        if not connections.has_connection(self.__milvus_name):
            print("尚未連接到 Milvus。")
            return -1

        try:
            if not self.__collection_names:
                print("目前沒有任何 Collection。")
                return -2
            
            print("---Milvus Collection 檢測開始 ---",self.__async_client)
            # 並行計算所有 collection
            for name in self.__collection_names:
                # await self.__async_client.load_collection(name)
                # count = await self.__async_client.get_collection_stats(name)
                collection = Collection(name)# 取得 Collection 物件
                collection.load()# 將 Collection 載入記憶體以進行搜尋或統計
                count = collection.num_entities# 取得 Collection 中的實體 (entity) 數量
                print(f"Collection '{name}' 共有 {count} 筆資料。")
                
        except Exception as e:
            print(f"發生錯誤: {e}")
            return -3
        finally:
            print("---Milvus Collection 檢測結束 ---\n")
        return 0

    def get_embedding(self,text: str) -> List[float]:
        response = self.__client_openAI.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding

    async def search_job(self, **kwargs)-> List[Any]:
        #index_params={"index_type": "IVF_FLAT", "metric_type": "COSINE", "params": {"nlist": 180}}
        column_names = [ "job_title", "job_description"]
        sql_where = ""
        limit_count = 200
        for key, value in kwargs.items():
            if (key in column_names):
                if value != None:
                    sql_where += f"{value} "
            elif (key == "limit_count"):
                limit_count = value

        print("MilvusManager search_job() sql_where:",sql_where)
        if (len(sql_where)<=0):
            print("⚠️ 查詢條件不足")
            return None
        query_vector=self.get_embedding(sql_where)
        search_params = {
            "metric_type": "COSINE",
            "params": {"nprobe": 60}  # 可依需求調整
        }
        """
        | nprobe  | 速度 | 準確率 | 適用場景          |
        | ------- | -- | --- | ------------- |
        | 10~20  | 很快 | 中等  | 快速篩選、粗查       |
        | 30~60  | 中快 | 高   | 一般線上查詢（準確率足夠） |
        | 90~180 | 慢  | 最高  | 離線批量高精度任務     |
        """
        collection_name="roadmap_milvus_collection"
        collection = Collection(collection_name)
        collection.load()
        schema = collection.schema
        # await self.__async_client.load_collection(collection_name)
        # schema = await self.__async_client.describe_collection(collection_name)
        # dim=0
        # for field in schema["fields"]:
        #     print("field:", field)
        #     if field["name"] == "embedding":
        #         dim = field["params"]["dim"]
        #         break
        # print("collection.schema:",schema)
        # print("schema.fields:",schema.fields)
        for field in schema.fields:
            print("field:",field)
            if field.name == "embedding":
                dim=field.params["dim"]
                break
        # print("MilvusManager search_job() query_vector len:",len(query_vector),"; schema.dim:",dim)
        if (dim != len(query_vector)):
            print(f"⚠️ 查詢向量維度不符，預期 {dim}，實際 {len(query_vector)}")
            return None
        for i in range(0,5):
            try:
                results = collection.search(
                    data=[query_vector],           # 查詢的向量
                    anns_field="embedding",        # 向量欄位名
                    param=search_params,
                    limit=limit_count,                      # 取前*筆
                    output_fields=["title", "jd_text"]
                    #output_fields=["job_title", "job_description", "city"]  # 要回傳的非向量欄位
                )
            except Exception as e:
                print("MilvusManager search_job() error:",e,"\nretry ",i,"/5")
                collection = Collection(collection_name)
                collection.load()
                time.sleep(1)

        return results
    
    def search_result_to_list(self,results: SearchResult) -> List[Dict[str, Any]]:
        """
        將 Milvus search() 結果轉換為 list[dict]
        """
        output: List[Dict[str, Any]] = []
        for hits in results:  # 每個 query 的結果 (Hits)
            for hit in hits:  # 每個單筆結果 (Hit)
                row = {
                    "id": hit.id,              # 主鍵
                    "distance": hit.distance,  # 相似度/距離
                    "title":hit.entity.get("title", ""),
                    "jd_text": hit.entity.get("jd_text", "")
                }
                # 如果有回傳 output_fields，就放進去
                if hit.entity:
                    row.update(dict(hit.entity))
                output.append(row)
        return output
    
    async def process_job_search_handle(self,get_task:dict)->None:
        result=None
        for i in range(0,5):
            try:
                set_job_title=get_task.get("job_title",None)
                set_job_description=get_task.get("job_description",None)
                session_id=get_task.get(redis_manager.RedisManager.Function_DataID,None)
                print(set_job_title,set_job_description)
                search_data=await self.search_job(job_title=set_job_title, job_description=set_job_description)
                result=self.search_result_to_list(search_data)
                break
            except Exception as e:
                print("milvus_work():",e,";retry ",i,"/5")
                self.connect_milvus()
                time.sleep(1)
        if(result==None):
            result={}
        await self._rds_man_obj.push_search_MilvusResult(session_id,result)

    @override
    async def work(self, **kwargs)-> None:
        action_map = {
            "process_job_search": self.process_job_search_handle,
        }
        await self.work_task(redis_manager.RedisKeyInternalMain.MAIN_Milvus_In.value,redis_manager.RedisManager.Function_Name,action_map)

    @override
    async def work_test(self, **kwargs)-> None:
        
        '''
        {
        "job_title": ["工程師","分析師","程式設計"],
        "city": ["台北","桃園","新竹"],
        "job_description": "AI工程師，負責設計與實作人工智慧模型與系統，需具備機器學習、深度學習相關技能。"
        }
        '''
        get_test_task=await self._rds_man_obj.test_queue_pop(redis_manager.RedisKeyTestMain.MAIN_Milvus_Test.value)
        if not get_test_task:
            return
        print("milvus_test():",get_test_task)
        test_task=get_test_task["test_data_queue"]
        # print("test_task:",test_task,type(test_task))
        set_job_id=test_task.get("job_id",None)
        set_job_title=test_task.get("job_title",None)
        set_salary=test_task.get("salary",None)
        set_city=test_task.get("city",None)
        set_job_description=test_task.get("job_description",None)
        get_session_id=get_test_task.get("session_id",None)
        print(set_job_id,set_job_title,set_salary,set_city,set_job_description)
        search_data=await self.search_job(job_title=set_job_title, job_description=set_job_description)
        result=self.search_result_to_list(search_data)
        print("milvus result:",len(result),"\ndata:",result[0:2])
        pass