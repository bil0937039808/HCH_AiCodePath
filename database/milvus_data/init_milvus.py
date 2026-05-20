import time
import pandas as pd
from pymilvus import connections, utility, FieldSchema, CollectionSchema, DataType, Collection
import ast
# import os

class MilvusInit:
    def __init__(self):
        self.MILVUS_HOST = "milvus"
        self.MILVUS_PORT = "19530"
        self.collection_name = "roadmap_milvus_collection"
        self.insert_data=None
        self.collection=None
        pass

    def run(self):
        # 等待 Milvus 可用
        # print("Milvus: pandas pymilvus安裝完畢")
        while True:
            try:
                connections.connect("default", host=self.MILVUS_HOST, port=self.MILVUS_PORT)
                if utility.get_server_version():
                    break
            except Exception:
                print("初始化 等待 Milvus 容器就緒...")
                time.sleep(3)

        print("準備資料初始化")
        
        # 刪除舊 collection（如果已存在）
        if utility.has_collection(self.collection_name):
            print("資料已經存在")
            # return
            print("刪除舊 collection:")
            utility.drop_collection(self.collection_name)
        # print(os.getcwd())
        self.__create_collection()
        self.__load_data()
        self.__insert_data()
        print("資料載入完成")

    def __load_data(self):
        # 讀取 CSV
        df = pd.read_csv("./init/JOB_embedding.csv")#JOB_embedding.csv JOB_TEST_embedding.csv
        #job_id,職缺名稱,職缺描述,薪資,城市,薪資_月薪制,薪資分組,embedding
        #job_id,title,jd_text,embedding
        # 把 embedding 欄位的字串轉成 list[float]
        df["embedding"] = df["embedding"].apply(lambda x: ast.literal_eval(x))
        # 插入資料
        # self.insert_data = [
        #     df["job_id"].tolist(),
        #     df["embedding"].tolist(),
        #     df["職缺名稱"].tolist(),
        #     df["職缺描述"].tolist(),
        #     df["城市"].tolist()
        # ]
        self.insert_data = [
            df["job_id"].tolist(),
            df["embedding"].tolist(),
            df["title"].tolist(),
            df["jd_text"].astype(str).tolist()
        ]
        for i in range(len(self.insert_data)):
            print(f"載入欄位 {i}:", self.insert_data[i][0:1])

    def __create_collection(self):
        # 定義 schema
        # fields = [
        #     FieldSchema(name="job_id", dtype=DataType.VARCHAR ,max_length=32, is_primary=True, auto_id=False),
        #     FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=768),
        #     FieldSchema(name="job_title", dtype=DataType.VARCHAR, max_length=300, description="職缺名稱"),
        #     FieldSchema(name="job_description", dtype=DataType.VARCHAR, max_length=7500, description="職缺描述"),
        #     FieldSchema(name="city", dtype=DataType.VARCHAR, max_length=200, description="城市")
        # ]
        fields = [
            FieldSchema(name="job_id", dtype=DataType.VARCHAR ,max_length=32, is_primary=True, auto_id=False),
            FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=1536),
            FieldSchema(name="title", dtype=DataType.VARCHAR, max_length=500, description="職缺名稱"),
            FieldSchema(name="jd_text", dtype=DataType.VARCHAR, max_length=7500, description="職缺描述")
        ]
        schema = CollectionSchema(fields, description="Init collection")
        # 建立新 collection
        self.collection = Collection(name=self.collection_name, schema=schema)

    def __insert_data(self):
        print(f"存入資料共{len(self.insert_data[0])}筆")
        BATCH_SIZE = 500  # 或根據實際向量大小調整
        for i in range(0, len(self.insert_data[0]), BATCH_SIZE):
            batch = [col[i:i+BATCH_SIZE] for col in self.insert_data]
            self.collection.insert(batch)
        # self.collection.insert(self.insert_data)
        # 強制 flush 讓資料落盤
        self.collection.flush()
        print("完成資料總數:", self.collection.num_entities)
        # 建立索引
        self.collection.create_index(
            field_name="embedding",
            index_params={"index_type": "IVF_FLAT", "metric_type": "COSINE", "params": {"nlist": 180}}
        )
        self.collection.load()


if __name__ == "__main__":
    mlvs_init_obj=MilvusInit()
    mlvs_init_obj.run()