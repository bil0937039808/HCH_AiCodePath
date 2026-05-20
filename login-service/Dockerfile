# 使用官方 Python 映像檔
FROM python:3.10-slim

# 設定工作目錄
WORKDIR /app

# 複製並安裝 Python 套件需求
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製所有應用程式碼
COPY . .

# 設定容器啟動時執行的指令
CMD ["flask", "run", "--host=0.0.0.0", "--port=5000"]