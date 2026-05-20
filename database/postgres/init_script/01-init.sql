CREATE TABLE IF NOT EXISTS job_row_data (
    job_id TEXT PRIMARY KEY,
    更新日期 DATE NOT NULL,
    查詢職類 BIGINT NOT NULL,
    查詢關鍵字 TEXT NOT NULL,
    職務類別 TEXT NOT NULL,
    職缺名稱 TEXT NOT NULL,
    公司名稱 TEXT NOT NULL,
    公司連結 TEXT NOT NULL,
    產業別 TEXT NOT NULL,
    上班地點 TEXT NOT NULL,
    地區 TEXT,
    城市 TEXT NOT NULL,
    國家 TEXT NOT NULL,
    薪資下限 INT NOT NULL,
    薪資上限 INT NOT NULL,
    職缺描述 TEXT,
    職務需求 TEXT, -- 原為 float64 全部空值，可改為 TEXT
    工作經歷要求 TEXT NOT NULL,
    學歷要求 TEXT NOT NULL,
    科系要求 TEXT,
    擅長工具 TEXT,
    工作技能 TEXT,
    中文聽力 TEXT,
    中文口說 TEXT,
    中文閱讀 TEXT,
    中文寫作 TEXT,
    英文聽力 TEXT,
    英文口說 TEXT,
    英文閱讀 TEXT,
    英文寫作 TEXT,
    日文聽力 TEXT,
    日文口說 TEXT,
    日文閱讀 TEXT,
    日文寫作 TEXT,
    台語聽力 TEXT, -- 原為 float64 全部空值，可改為 TEXT
    台語口說 TEXT,
    台語閱讀 TEXT,
    台語寫作 TEXT,
    其他條件 TEXT,
    福利制度 TEXT,
    法定福利 TEXT,
    其他福利 TEXT,
    面試流程 TEXT, -- 原為 float64 全部空值，可改為 TEXT
    職缺連結 TEXT NOT NULL,
    爬取時間 TIMESTAMP NOT NULL,
    薪資_月薪制 TEXT,
    skills TEXT NOT NULL,
    xgboost_預測薪資 FLOAT
);

DROP TABLE IF EXISTS coursera_row_data;
CREATE TABLE IF NOT EXISTS coursera_row_data (
    course_name TEXT,
    評分 TEXT,
    評論數 TEXT,
    適合等級 TEXT,
    技能 TEXT,
    課程資訊 TEXT,
    師資 TEXT,
    開課時間 TEXT,
    lesson TEXT,
    總時數_時 NUMERIC,
    訂閱方式_月 TEXT,
    費用_US_月 INTEGER,
    訂閱方式_年 TEXT,
    費用_US_年 INTEGER,
    course_url TEXT,
    skills TEXT,               -- 暫時先 TEXT，避免 COPY 出錯
    rating_numeric NUMERIC,
    review_count INTEGER,
    credibility_score NUMERIC,
    quadrant TEXT,
    topic_id INTEGER,
    topic_label TEXT,
    credibility_tier TEXT,
    strategy_rating TEXT
);



-- ALTER TABLE coursera_row_data
-- ALTER COLUMN skills TYPE TEXT[]
-- USING (string_to_array(regexp_replace(skills, E'\\[|\\]|\\'','', 'g'), ',' ));


-- ===== START: 會員系統資料表 =====
CREATE TABLE IF NOT EXISTS members (
    member_id SERIAL PRIMARY KEY,
    username VARCHAR(80) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chat_history (
    history_id SERIAL PRIMARY KEY,
    member_id INTEGER NOT NULL REFERENCES members(member_id),
    conversation JSONB,
    suggested_job_vacancy TEXT,
    identified_skills TEXT[],
    recommended_courses TEXT[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);
-- ===== END: 會員系統資料表 =====
