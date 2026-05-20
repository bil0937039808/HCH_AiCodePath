# 1. 使用輕量級 Ubuntu 基底
FROM ubuntu:22.04

# 2. 安裝基本工具與 Python 環境
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    python3 python3-pip python3-dev build-essential vim curl && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# 3. 設定 Python 連結
RUN ln -s /usr/bin/python3 /usr/bin/python

# 4. 設定工作目錄
WORKDIR /home/workspace

# 5. 複製專案檔案
COPY . .

# 6. 安裝 PyTorch (CPU 版本) 與其他依賴
#    使用官方 CPU-only index
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch==2.2.0 torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt


# CMD ["jupyter", "lab", "--ip=0.0.0.0", "--allow-root"]

#docker build -t <自訂名稱(映像檔)> .
#docker run --gpus all -it --name <自訂名稱(容器)> -p <jupyter對外port>:8888 -v ${PWD}:<自訂義Docker內部的路徑> <自訂名稱(映像檔)>