#!/bin/bash
set -e

# ===============================
# 參數設定
# ===============================
NETWORK_NAME="roadmap_network"
BUILD_FLAG=$1  # 可傳入 "build" 或空值
BUILD_FLAG_STR="--build"

MILVUS_COMPOSE="docker-compose-milvus.yml"
BACKEND_COMPOSE="docker-compose-main.yml"
FLAG_FILE="./database/milvus_data/.init_done"
# ===============================
# 1️⃣ 檢查並建立 network
# ===============================
if docker network ls | grep -qw "$NETWORK_NAME"; then
    echo "✅ Network $NETWORK_NAME 已存在"
else
    echo "❌ Network $NETWORK_NAME 不存在，建立中..."
    docker network create "$NETWORK_NAME"
fi
echo "=== 初始化資料夾 ==="
sudo rm -rf ./database/postgres/pg_data
mkdir ./database/postgres/pg_data
sudo chmod 777 ./database/postgres/init_csv
sudo chmod 777 ./database/postgres/init_script
sudo chmod +x ./database/postgres/init_script/*.sh
sudo chmod 666 ./database/postgres/init_csv/*.csv
if [ -f "./database/postgres/init_csv/*_clean.csv" ]; then
    echo "刪除 _clean.csv"
    sudo rm ./database/postgres/init_csv/*_clean.csv 
fi
# ===============================
# 2️⃣ 啟動 milvus 與 milvus-init
# ===============================
echo "=== 啟動 milvus + milvus-init ==="
if [ "$BUILD_FLAG" == $BUILD_FLAG_STR ]; then
    echo "使用 $BUILD_FLAG_STR"
    docker-compose -f $MILVUS_COMPOSE up --build -d
else
    docker-compose -f $MILVUS_COMPOSE up -d
fi

# ===============================
# 3️⃣ 等待 milvus-init 完成 flag
# ===============================
echo "⏳ 等待 milvus-init 完成:"
echo "資料初始化(約3分鐘) ..."
while [ ! -f "$FLAG_FILE" ]; do
    echo "等待中..."
    sleep 60
done
echo "✅ milvus-init 已完成"

# ===============================
# 4️⃣ 啟動 backend 及相關服務
# ===============================
echo "=== 啟動 backend ==="
if [ "$BUILD_FLAG" == $BUILD_FLAG_STR ]; then
    docker-compose -f $BACKEND_COMPOSE up --build 
else
    docker-compose -f $BACKEND_COMPOSE up 
fi

echo "🎉 所有服務已啟動完成！"