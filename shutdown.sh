#!/bin/bash
set -e

# ===============================
# 參數設定
# ===============================
NETWORK_NAME="roadmap_network"
MILVUS_COMPOSE="docker-compose-milvus.yml"
BACKEND_COMPOSE="docker-compose-main.yml"
FLAG_FILE="./database/milvus_data/.init_done"

# ===============================
# 1️⃣ 關閉 backend 與相關服務
# ===============================
echo "=== 關閉 backend 服務 ==="
docker-compose -f $BACKEND_COMPOSE down

# ===============================
# 2️⃣ 關閉 milvus-init 與 milvus
# ===============================
echo "=== 關閉 milvus-init & milvus ==="
docker-compose -f $MILVUS_COMPOSE down

# ===============================
# 3️⃣ 選擇性刪除 network
# ===============================
if docker network ls | grep -qw "$NETWORK_NAME"; then
    echo "✅ network $NETWORK_NAME 存在，準備刪除..."
    docker network rm "$NETWORK_NAME"
else
    echo "❌ network $NETWORK_NAME 不存在，無需刪除"
fi

# ===============================
# 4️⃣ 清除 milvus-init flag（可選）
# ===============================
if [ -f "$FLAG_FILE" ]; then
    echo "⚠️ 清除初始化 flag"
    rm -f "$FLAG_FILE"
fi
sudo rm ./database/postgres/init_csv/*_clean.csv
echo "✅ 系統已全部關閉完成"