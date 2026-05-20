#!/bin/bash
CSV_FILE_JOB="Job_Row_Data.csv"
CSV_FILE_COURSERA="coursera_total_report.csv"
PG_IMPORT_DIR="/data"
echo "projectDB初始化開始..."
set -e
echo "CSV 清理控制字元與行尾符號..."
# 清理控制字元與行尾符號
tr -d '\v' < "$PG_IMPORT_DIR/$CSV_FILE_JOB" | sed 's/\r$//' > "$PG_IMPORT_DIR/${CSV_FILE_JOB%.csv}_clean.csv"
chown postgres:postgres "$PG_IMPORT_DIR/${CSV_FILE_JOB%.csv}_clean.csv"

echo "📥 開始匯入 CSV 資料到 PostgreSQL..."
# 使用 psql 連線並執行 COPY 指令
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "\
COPY job_row_data
    (
        job_id, 更新日期, 查詢職類, 查詢關鍵字, 職務類別, 職缺名稱, 公司名稱, 公司連結,
        產業別, 上班地點, 地區, 城市, 國家, 薪資下限, 薪資上限, 職缺描述, 職務需求,
        工作經歷要求, 學歷要求, 科系要求, 擅長工具, 工作技能, 中文聽力, 中文口說, 中文閱讀,
        中文寫作, 英文聽力, 英文口說, 英文閱讀, 英文寫作, 日文聽力, 日文口說, 日文閱讀, 日文寫作,
        台語聽力, 台語口說, 台語閱讀, 台語寫作, 其他條件, 福利制度, 法定福利, 其他福利, 面試流程,
        職缺連結, 爬取時間, 薪資_月薪制, skills,xgboost_預測薪資
    ) FROM '$PG_IMPORT_DIR/${CSV_FILE_JOB%.csv}_clean.csv' 
    WITH (
        FORMAT csv,
        HEADER,
        NULL 'NaN',
        ENCODING 'UTF8'
    );"

psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "\
    COPY coursera_row_data
        (
            course_name, 評分, 評論數, 適合等級, 技能, 課程資訊, 師資, 開課時間, lesson,
            總時數_時, 訂閱方式_月, 費用_US_月, 訂閱方式_年, 費用_US_年, course_url,
            skills, rating_numeric, review_count, credibility_score,
            quadrant, topic_id, topic_label, credibility_tier,
            strategy_rating
        ) FROM '$PG_IMPORT_DIR/${CSV_FILE_COURSERA%.csv}.csv' 
        WITH (
            FORMAT csv,
            HEADER,
            ENCODING 'UTF8'
        );"

#把 skills 轉換成 TEXT[]
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "\
    ALTER TABLE coursera_row_data
    ALTER COLUMN skills TYPE TEXT[]
    USING string_to_array(regexp_replace(skills, '[\[\]'']', '', 'g'), ',');"

#建立 GIN 索引 (加速 skills 陣列查詢)
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "\
    CREATE INDEX idx_courses_skills ON coursera_row_data USING gin (skills);"

echo "✅ CSV 匯入完成"
# 建立旗標檔表示完成
echo "init_done" > /var/lib/postgresql/data/.init_done