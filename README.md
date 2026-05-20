# AiCodePath - 基於 LLM 與 Hybrid RAG 的職缺媒合與智慧學習路徑規劃系統

![Python](https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=for-the-badge&logo=fastapi)
![LangChain](https://img.shields.io/badge/LangChain-⚡-green?style=for-the-badge)
![Docker](https://img.shields.io/badge/Docker-🐳-blue?style=for-the-badge&logo=docker)
![Milvus](https://img.shields.io/badge/Milvus-Vector_DB-orange?style=for-the-badge)

## 📌 專案概述 (Project Overview)
**AiCodePath** 是一個專為求職轉職者設計的 AI 智慧媒合與學習規劃平台。針對轉職者在投入陌生領域時面臨的「技能落差」與「缺乏具體學習路徑」之痛點，本專案將 **104 人力銀行** 的職缺資訊與 **Coursera** 線上課程進行深度整合。透過大語言模型 (LLM) 與檢索增強生成 (RAG) 技術，使用者能以自然語言進行對話，系統則會自動檢索精準職缺、分析技能缺口，並客製化編排個人化的課程學習路徑。

> 💡 **Core Highlight**：本儲存庫主要展示系統的**核心後端架構（Backend Architecture）**與 **AI/RAG 研發成果**。全案本人開發 70% 的 Python 程式碼，實作了非同步任務佇列、即時雙向通訊、多服務容器化部署及 RAG 混合檢索 Pipeline，表達具備解決複雜併發與資料流阻塞的後端工程能力。

---

## 🛠️ 技術棧 (Tech Stack)
* **後端核心**: Python, FastAPI, Object-Oriented Programming (OOP, 繼承/多型/Singleton)
* **大語言模型與 RAG**: OpenAI API (GPT 系列), Milvus (向量資料庫), Pydantic (結構化輸出), Prompt Engineering
* **資料儲存與快取**: PostgreSQL (關聯式資料庫), Redis (快取 & 任務佇列)
* **即時通訊與非同步處理**: WebSocket, Redis Queue (RQ)
* **DevOps & 部署**: Docker, Docker Compose, Nginx (反向代理)

---

## 🏗️ 核心架構與工程設計 (Engineering Highlights)

### 1. RAG 混合檢索設計 (Hybrid Search Pipeline)
為了解決傳統純向量搜尋在處理特定硬性條件（如薪資、工作地點）時的語意模糊，以及傳統關鍵字搜尋缺乏語意理解的缺點，本專案設計了 **Hybrid Search** 機制：
* **語意搜尋層**: 利用 **Milvus 向量資料庫** 進行職缺與技能描述的向量嵌入 (Embedding) 語意比對。
* **精確篩選層**: 利用 **PostgreSQL** 負責結構化欄位（如地點、薪資範圍、學歷要求）的精確過濾。
* **交集最佳化 (Intersection Matching)**：兩路搜尋並行後，在後端透過主鍵 (Primary Key) 進行交集比對。此舉大幅減少了傳遞給 LLM 的無效上下文，不僅降低了 Token 成本，更提高搜尋精準度。

### 2. FastAPI + WebSocket 即時雙向通訊（防阻塞設計）
由於 AI 生成與大型資料庫檢索屬於高耗時的 I/O 操作，為了避免傳統 HTTP POST 請求導致的前端連線阻塞並處理多使用者同時操作，系統全面導入 WebSocket 協定：
* **單一連線、多工處理**: 每個前端使用者進入對應視窗時僅建立一條 WebSocket 連線，並重複使用直至關閉網站（實作多使用者 Session 管理）。
* **自訂指令路由 (Command Switching)**: 前後端透過結構化 JSON 封包傳輸，封包中包含獨立的指令名稱 ID（例如：對話、職缺搜尋、路徑生成）。後端採用 Switch 機制動態分流至對應功能模組。
* **非同步解耦體驗**: 送出與接收完全解耦，前端可在等待 LLM 或資料庫回應的耗時過程中，保持介面的流暢互動，允許使用者執行其他事務，處理併發 I/O 的阻塞問題。

### 3. 星狀相依與 Redis Queue 非同步解耦架構
為了建立具備高度擴充性且易於維護的系統，後端全面導入物件導向設計，並採用個人曾在論文上提出之**星狀相依（Star Dependency）**架構：
* **模組解耦**: 各項功能模組彼此不直接進行強相依的 `import`，降低程式碼之間的耦合度。
* **事件驅動**: 所有模組間的資料與指令皆包裝成標準 JSON/dict，並統一傳入 **Redis Queue** 中。各服務接收端透過輪詢佇列來消化任務。這種統一渠道的設計，不僅提升了系統的除錯 (Debug) 能力，也強化了模組的獨立運作與擴充性。

### 4. LLM 提示詞工程與安全防護 (Prompt Engineering & Guardrails)
* **角色定位與結構化輸出**: 將 LLM 賦予的「求職諮詢顧問」角色，並結合 **Pydantic** 強制要求模型輸出結構化資料，確保後端系統能穩定解析。
* **資安與行為防護**: 在提示詞中建立防護規則，當使用者提及與求職、技能學習無關的敏感或非專案範疇的話題時，AI 將啟動防護機制並婉拒回答。
* **開發與成本優化策略**: 開發前期先使用成本較低的模型（如 GPT-4.1-nano）快速暴露出提示詞結構缺陷並進行修正，調整穩定後再移轉至 GPT 高級模型，優化最終的回應語氣與排版，有效控管開發預算。

### 5. Docker 多容器編排與 Healthcheck 運作管理
專案採用 **Docker** 進行部署，建構了一個包含前端（Nginx）、後端主程式、以及多元資料庫群（PostgreSQL, Redis, Milvus, MinIO, Etcd 等）的獨立容器集群：
* **嚴格啟動順序管理**: 透過 Docker Compose 配置，結合 `healthcheck` 機制，確保基礎資料庫與基礎組件完全就緒後，才啟動後端主程式，最後再開啟前端 Nginx 反向代理，避免因服務啟動時差導致的連線崩潰。

---

## 🔄 技術演進與反思 (Engineering Evolution)
在專案研發的早期階段，團隊曾嘗試完全本地化運算（採用 Hugging Face 開源模型與 FAISS 向量庫）。然而，在實際工程測試後發現：
1. 本地硬體資源受限，導致大型模型推理與回應時間 (Latency) 過長。
2. 純向量庫在缺乏關聯式資料庫（如 PostgreSQL）的複合硬性條件篩選時，整體招回表現與彈性甚至不如傳統關鍵字搜尋，缺乏商用優勢。
    
經過團隊的技術評估與工程權衡後，決定將架構轉為現行的 **LLM 雲端 API + Milvus & PostgreSQL 混合檢索 RAG**。這項重構不僅提升了回應速度，更增加了 AI 對話與課程編排的精準度，我們在此次技術瓶頸時，表達了評估與果斷重構能力。

---

## 👥 個人核心貢獻 (Individual Contributions)
全案由 7 人團隊協作開發，本人作為**後端開發/架構師**，獨立撰寫了 **2,500+ 行 Python 程式碼**，具體貢獻如下：
1. **後端架構設計**: 獨立設計並實作 AI Backend 的星狀相依架構，利用 FastAPI 處理非同步併發 I/O。
2. **RAG 管道架構**: 建立 Milvus 向量庫與 PostgreSQL 的混合檢索 Pipeline，實作雙資料庫主鍵交集篩選邏輯。
3. **高併發與防阻塞優化**: 實作 Redis Queue 非同步工作流程，並設計 WebSocket 雙向即時通訊與單一 URL 多工路由機制。
4. **容器化部署管理**: 負責完整 Docker 環境編排，撰寫多容器 Docker Compose 並實作基於 Healthcheck 的服務依賴管理。
