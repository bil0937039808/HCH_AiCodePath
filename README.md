# AiCodePath - 基於 LLM 與 RAG 的 AI 職涯求職與課程推薦平台

![Python](https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=for-the-badge&logo=fastapi)
![LangChain](https://img.shields.io/badge/LangChain-⚡-green?style=for-the-badge)
![Docker](https://img.shields.io/badge/Docker-🐳-blue?style=for-the-badge&logo=docker)
![Milvus](https://img.shields.io/badge/Milvus-Vector_DB-orange?style=for-the-badge)

AiCodePath 是一個專為轉職與求職者設計的 **AI 智慧媒合推薦平台**。本專案將大語言模型（LLM）與檢索增強生成（RAG）技術結合，串聯 **104 人力銀行** 的職缺資料庫與 **Coursera** 線上課程，透過自然語言對話引導使用者，自動檢索核心職缺並客製化編排個人的技能學習路徑。

本儲存庫主要存放**核心 AI 後端架構與 RAG 檢索管線（Pipeline）**的原始碼。

---

## 🎯 專案動機與核心功能

轉職者在投入陌生領域時，常面臨「專業技能不足」且「坊間課程與實際職缺技能需求脫節」的痛點。AiCodePath 作為智慧仲介平台，提供兩大核心 AI 服務：
1. **AI 職缺搜尋助理 (AI Job Search Assistant)**：利用 Tool Calling 將使用者的對話意圖轉化為結構化條件，精準檢索目標職缺。
2. **AI 課程編排推薦系統 (AI Learning Recommendation System)**：分析職缺所需技能，透過關聯式資料庫與 LLM 二次篩選，自動生成循序漸進的個人化學習路徑。

---

## 🏗️ 系統架構與設計模式 (Backend Architecture)

為了解決大語言模型（LLM）推論與大規模資料庫查詢所帶來的 **I/O 阻塞問題**，並確保系統具備高併發（High Concurrency）與高擴展性，後端採用了以下核心架構設計：

```text
[ 前端 Web UI ] 
      │ 🔀 WebSocket (雙向即時通訊、防阻塞)
      ▼
[ FastAPI 後端主程式 ] ─── (物件導向設計 / Singleton / 多型)
      │
      ├─► [ Redis Queue ] ──► (星狀相依解耦，異步任務處理)
      │
      └─► [ RAG 混合檢索管線 ]
            ├─► Milvus (向量資料庫 - 語意搜尋) ──┐
            │                                    ├──► [主鍵交集比對 (PK Intersection)] ──► 精準結果
            └─► PostgreSQL (關聯式資料庫 - 條件篩選) ┘
