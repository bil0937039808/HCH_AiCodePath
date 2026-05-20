# scripts/set_milvus_root_password.py
from pymilvus import MilvusClient

client = MilvusClient(uri="http://milvus:19530", token="root:Milvus")
client.update_credential("root", "admin")  # 改密碼為 admin
print("✅ Milvus root 密碼已更新為 admin")
