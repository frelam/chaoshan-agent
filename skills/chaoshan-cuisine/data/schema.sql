-- ============================================================
-- 潮汕美食评价数据库 Schema v1.0
-- SQLite 数据库，存储微信/各渠道实时收到的店铺评价
-- ============================================================
-- 设计理念：
--   1. 与 YAML 评价库互补 —— DB 存"实时收到的评价"，YAML 存"自演进挖掘的评价"
--   2. 每条评价关联到店和评价者，支持交叉查询
--   3. FTS5 全文检索支持自然语言搜索评价内容
--   4. 评价者画像来自 WeChat 用户信息 + 逐步积累
-- ============================================================

-- 店铺表
CREATE TABLE IF NOT EXISTS restaurants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,                          -- 店名
    address TEXT,                                -- 地址
    district TEXT,                               -- 所属区县（金平区/湘桥区/榕城区 等）
    cuisine_type TEXT,                           -- 美食品类（牛肉火锅/粿条汤/蚝烙 等）
    coordinates_lat REAL,
    coordinates_lng REAL,
    phone TEXT,
    business_hours TEXT,                         -- 营业时间
    is_closed INTEGER DEFAULT 0,                 -- 是否已闭店
    aliases TEXT,                                -- 曾用名/别名，JSON 数组
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_restaurants_name ON restaurants(name);

-- 评价者表（微信联系人/贡献者）
CREATE TABLE IF NOT EXISTS reviewers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wechat_user_id TEXT UNIQUE,                  -- 微信用户标识
    display_name TEXT,                           -- 微信昵称
    type TEXT DEFAULT 'tourist',                 -- local / tourist / returning-visitor
    hometown TEXT,                               -- 来自哪座城市
    age_group TEXT,                              -- 年龄段：18-25 / 26-35 / 36-50 / 50+
    taste_tags TEXT,                             -- 口味偏好，JSON 数组 ["喜欢油香", "喜欢弹牙"]
    reliability REAL DEFAULT 1.0,                -- 可信度系数（根据历史评价质量动态调整）
    is_verified INTEGER DEFAULT 0,               -- 是否已验证身份
    total_reviews INTEGER DEFAULT 0,
    first_seen_at TEXT,
    last_seen_at TEXT,
    notes TEXT,                                  -- 自定义备注
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);

-- 评价表（核心表——一次探店 = 一条评价）
CREATE TABLE IF NOT EXISTS reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    restaurant_id INTEGER NOT NULL,              -- 关联到哪家店
    reviewer_id INTEGER,                         -- 评价者（可为 NULL，如果是匿名提取）
    overall_rating REAL CHECK(overall_rating >= 1 AND overall_rating <= 5),  -- 综合评分 1-5
    review_text TEXT NOT NULL,                   -- 完整评价原文
    visit_date TEXT,                             -- 到店日期 YYYY-MM-DD
    visit_context TEXT,                          -- 用餐场景（"周六午餐，带外地朋友"）
    would_revisit INTEGER,                       -- 1=会再去, 0=不会, NULL=未表态
    price_level TEXT,                            -- 价位：人均 <30 / 30-60 / 60-100 / 100+
    pros TEXT,                                   -- 好评点，JSON 数组
    cons TEXT,                                   -- 差评点，JSON 数组
    source TEXT DEFAULT 'wechat',                -- 来源：wechat / self-evolve / community
    source_message_id TEXT,                      -- 微信消息 ID（溯源用）
    is_derived INTEGER DEFAULT 0,                -- 1=从对话中提取, 0=用户主动评价
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_reviews_restaurant ON reviews(restaurant_id);
CREATE INDEX IF NOT EXISTS idx_reviews_reviewer ON reviews(reviewer_id);
CREATE INDEX IF NOT EXISTS idx_reviews_rating ON reviews(overall_rating);
CREATE INDEX IF NOT EXISTS idx_reviews_created ON reviews(created_at);

-- 菜品评价表（一道菜 = 一条记录）
CREATE TABLE IF NOT EXISTS dishes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    review_id INTEGER NOT NULL,                  -- 关联到哪条评价
    name TEXT NOT NULL,                          -- 菜名（如"脖仁""吊龙""蚝烙"）
    rating REAL CHECK(rating >= 1 AND rating <= 5),  -- 对该菜的单独评分
    price REAL,                                  -- 价格（元）
    comment TEXT,                                -- 口感描述
    recommended INTEGER DEFAULT 1,               -- 1=推荐, 0=不推荐, NULL=中性
    FOREIGN KEY (review_id) REFERENCES reviews(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_dishes_review ON dishes(review_id);
CREATE INDEX IF NOT EXISTS idx_dishes_name ON dishes(name);

-- 标签表
CREATE TABLE IF NOT EXISTS tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,                   -- 标签名（如"排队""老店""环境一般""物美价廉"）
    category TEXT                                -- 分类（atmosphere / price / service / etc.）
);

-- 评价-标签关联
CREATE TABLE IF NOT EXISTS review_tags (
    review_id INTEGER NOT NULL,
    tag_id INTEGER NOT NULL,
    PRIMARY KEY (review_id, tag_id),
    FOREIGN KEY (review_id) REFERENCES reviews(id) ON DELETE CASCADE,
    FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
);

-- 全文检索（支持脏话搜索评价内容）
CREATE VIRTUAL TABLE IF NOT EXISTS reviews_fts USING fts5(
    review_text,
    content='reviews',
    content_rowid='id'
);

-- ============================================================
-- 触发器：自动同步 FTS
-- ============================================================
CREATE TRIGGER IF NOT EXISTS reviews_ai AFTER INSERT ON reviews BEGIN
    INSERT INTO reviews_fts(rowid, review_text) VALUES (new.id, new.review_text);
END;

CREATE TRIGGER IF NOT EXISTS reviews_ad AFTER DELETE ON reviews BEGIN
    INSERT INTO reviews_fts(reviews_fts, rowid, review_text) VALUES('delete', old.id, old.review_text);
END;

CREATE TRIGGER IF NOT EXISTS reviews_au AFTER UPDATE ON reviews BEGIN
    INSERT INTO reviews_fts(reviews_fts, rowid, review_text) VALUES('delete', old.id, old.review_text);
    INSERT INTO reviews_fts(rowid, review_text) VALUES (new.id, new.review_text);
END;

-- ============================================================
-- 预置常用标签
-- ============================================================
INSERT OR IGNORE INTO tags (name, category) VALUES
    ('老店', 'reputation'),
    ('新店', 'reputation'),
    ('游客打卡', 'reputation'),
    ('本地人常去', 'reputation'),
    ('排队', 'service'),
    ('物美价廉', 'price'),
    ('价格偏高', 'price'),
    ('环境好', 'atmosphere'),
    ('环境一般', 'atmosphere'),
    ('无空调', 'atmosphere'),
    ('服务好', 'service'),
    ('服务一般', 'service'),
    ('停车方便', 'convenience'),
    ('停车困难', 'convenience'),
    ('外卖可点', 'convenience'),
    ('隐藏菜单', 'experience'),
    ('适合一人食', 'experience'),
    ('适合聚会', 'experience'),
    ('适合宵夜', 'experience'),
    ('踩雷', 'experience');

-- ============================================================
-- 统计视图：店铺聚合评分
-- ============================================================
CREATE VIEW IF NOT EXISTS restaurant_stats AS
SELECT
    r.id AS restaurant_id,
    r.name,
    r.district,
    r.cuisine_type,
    COUNT(rev.id) AS review_count,
    ROUND(AVG(rev.overall_rating), 2) AS avg_rating,
    ROUND(AVG(CASE WHEN rev.reviewer_id IS NOT NULL THEN rev.overall_rating END), 2) AS avg_rating_with_reviewer,
    ROUND(
        (SELECT AVG(d.rating) FROM dishes d
         JOIN reviews r2 ON d.review_id = r2.id
         WHERE r2.restaurant_id = r.id AND d.recommended = 1),
    2) AS avg_top_dish_rating,
    MIN(rev.created_at) AS first_review,
    MAX(rev.created_at) AS last_review
FROM restaurants r
LEFT JOIN reviews rev ON rev.restaurant_id = r.id
GROUP BY r.id
ORDER BY review_count DESC;

-- ============================================================
-- 趋势追踪表：按周/月聚合每家店的热度、品质变化
-- ============================================================
CREATE TABLE IF NOT EXISTS trend_tracking (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    restaurant_id INTEGER NOT NULL,
    period TEXT NOT NULL,            -- '2026-W27' (ISO周) 或 '2026-07' (月度)
    period_type TEXT NOT NULL,       -- 'weekly' 或 'monthly'
    review_count INTEGER DEFAULT 0,  -- 该周期内评价数
    avg_rating REAL,                 -- 该周期内平均分
    median_rating REAL,              -- 该周期内中位数
    would_revisit_rate REAL,         -- 该周期内愿意回头率
    avg_dish_rating REAL,            -- 该周期内菜品平均分
    top_dishes TEXT,                 -- 该周期内最推荐菜品 TOP3（JSON）
    common_pros TEXT,                -- 该周期内常见好评（JSON）
    common_cons TEXT,                -- 该周期内常见差评（JSON）
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (restaurant_id) REFERENCES restaurants(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_trend_restaurant_period ON trend_tracking(restaurant_id, period);

-- 趋势分析视图
CREATE VIEW IF NOT EXISTS trend_analysis AS
SELECT
    t.restaurant_id,
    r.name AS restaurant_name,
    r.district,
    r.cuisine_type,
    COUNT(DISTINCT t.period) AS periods_tracked,
    ROUND(AVG(t.avg_rating), 2) AS overall_avg_rating,
    ROUND(AVG(t.would_revisit_rate), 2) AS overall_revisit_rate,
    ROUND(
        (SELECT AVG(t2.avg_rating) FROM trend_tracking t2 
         WHERE t2.restaurant_id = t.restaurant_id 
         AND t2.created_at >= datetime('now', '-90 days')),
    2) AS recent_90d_avg,
    ROUND(
        (SELECT AVG(t2.avg_rating) FROM trend_tracking t2 
         WHERE t2.restaurant_id = t.restaurant_id 
         AND t2.created_at < datetime('now', '-90 days') 
         AND t2.created_at >= datetime('now', '-180 days')),
    2) AS prior_90d_avg
FROM trend_tracking t
JOIN restaurants r ON t.restaurant_id = r.id
GROUP BY t.restaurant_id;
