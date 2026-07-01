#!/usr/bin/env python3
"""
潮汕美食评价数据库 — 辅助模块
用于结构化存储、检索微信等渠道收到的美食评价。
"""

import sqlite3
import json
import os
import re
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent / "reviews.db"

# ============================================================
# 数据库连接
# ============================================================

def get_conn():
    """获取数据库连接（自动创建目录和表）"""
    os.makedirs(DB_PATH.parent, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    """初始化数据库（如果不存在则创建表）"""
    schema_path = DB_PATH.parent / "schema.sql"
    if not DB_PATH.exists():
        if schema_path.exists():
            conn = get_conn()
            conn.executescript(schema_path.read_text())
            conn.commit()
            conn.close()
            return True
    return DB_PATH.exists()

# ============================================================
# 店铺操作
# ============================================================

def find_or_create_restaurant(name, address=None, district=None, cuisine_type=None):
    """查找或创建店铺，返回 (id, is_new)"""
    conn = get_conn()
    cursor = conn.execute("SELECT id FROM restaurants WHERE name = ?", (name,))
    row = cursor.fetchone()
    if row:
        conn.close()
        return row["id"], False

    cursor = conn.execute("""
        INSERT INTO restaurants (name, address, district, cuisine_type)
        VALUES (?, ?, ?, ?)
    """, (name, address, district, cuisine_type))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id, True


def search_restaurants(query, limit=10):
    """搜索店铺，支持模糊匹配"""
    conn = get_conn()
    cursor = conn.execute("""
        SELECT r.*, 
               COUNT(rev.id) AS review_count,
               ROUND(AVG(rev.overall_rating), 2) AS avg_rating
        FROM restaurants r
        LEFT JOIN reviews rev ON rev.restaurant_id = r.id
        WHERE r.name LIKE ? OR r.address LIKE ? OR r.district LIKE ?
        GROUP BY r.id
        ORDER BY review_count DESC
        LIMIT ?
    """, (f"%{query}%", f"%{query}%", f"%{query}%", limit))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def list_restaurants_by_district(district=None, cuisine_type=None, limit=50):
    """按地区和品类列出店铺"""
    conn = get_conn()
    conditions = []
    params = []
    if district and district != "全部":
        conditions.append("r.district = ?")
        params.append(district)
    if cuisine_type and cuisine_type != "全部":
        conditions.append("r.cuisine_type = ?")
        params.append(cuisine_type)

    where = " AND ".join(conditions) if conditions else "1=1"
    cursor = conn.execute(f"""
        SELECT r.*, 
               COUNT(rev.id) AS review_count,
               ROUND(AVG(rev.overall_rating), 2) AS avg_rating
        FROM restaurants r
        LEFT JOIN reviews rev ON rev.restaurant_id = r.id
        WHERE {where}
        GROUP BY r.id
        ORDER BY review_count DESC, avg_rating DESC
        LIMIT ?
    """, (*params, limit))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows

# ============================================================
# 评价者操作
# ============================================================

def find_or_create_reviewer(wechat_user_id, display_name=None):
    """查找或创建评价者"""
    conn = get_conn()
    cursor = conn.execute("SELECT * FROM reviewers WHERE wechat_user_id = ?", (wechat_user_id,))
    row = cursor.fetchone()
    if row:
        # 更新最后出现时间
        conn.execute("""
            UPDATE reviewers SET last_seen_at = datetime('now', 'localtime'),
                                 display_name = COALESCE(?, display_name)
            WHERE id = ?
        """, (display_name, row["id"]))
        conn.commit()
        conn.close()
        return dict(row)

    cursor = conn.execute("""
        INSERT INTO reviewers (wechat_user_id, display_name, first_seen_at, last_seen_at)
        VALUES (?, ?, datetime('now', 'localtime'), datetime('now', 'localtime'))
    """, (wechat_user_id, display_name))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()

    conn = get_conn()
    cursor = conn.execute("SELECT * FROM reviewers WHERE id = ?", (new_id,))
    row = dict(cursor.fetchone())
    conn.close()
    return row


def update_reviewer_profile(reviewer_id, **kwargs):
    """更新评价者画像"""
    allowed = {"type", "hometown", "age_group", "taste_tags", "notes"}
    updates = {k: v for k, v in kwargs.items() if k in allowed}
    if not updates:
        return False

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [reviewer_id]
    conn = get_conn()
    conn.execute(f"UPDATE reviewers SET {set_clause} WHERE id = ?", values)
    conn.commit()
    conn.close()
    return True

# ============================================================
# 评价操作
# ============================================================

def add_review(restaurant_id, review_text, overall_rating=None, reviewer_id=None,
               visit_date=None, visit_context=None, would_revisit=None,
               price_level=None, dishes=None, pros=None, cons=None,
               tags=None, source="wechat", source_message_id=None):
    """添加一条评价，返回 review_id"""
    conn = get_conn()

    cursor = conn.execute("""
        INSERT INTO reviews (restaurant_id, reviewer_id, overall_rating, review_text,
                             visit_date, visit_context, would_revisit,
                             price_level, pros, cons, source, source_message_id,
                             created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))
    """, (restaurant_id, reviewer_id, overall_rating, review_text,
          visit_date, visit_context, would_revisit,
          price_level, json.dumps(pros) if pros else None,
          json.dumps(cons) if cons else None,
          source, source_message_id))
    review_id = cursor.lastrowid

    # 添加菜品评价
    if dishes:
        for dish in dishes:
            conn.execute("""
                INSERT INTO dishes (review_id, name, rating, price, comment, recommended)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (review_id, dish.get("name"), dish.get("rating"),
                  dish.get("price"), dish.get("comment"),
                  dish.get("recommended", 1)))

    # 添加标签
    if tags:
        for tag_name in tags:
            conn.execute("""
                INSERT OR IGNORE INTO tags (name) VALUES (?)
            """, (tag_name,))
            tag_row = conn.execute("SELECT id FROM tags WHERE name = ?", (tag_name,)).fetchone()
            if tag_row:
                conn.execute("""
                    INSERT OR IGNORE INTO review_tags (review_id, tag_id) VALUES (?, ?)
                """, (review_id, tag_row["id"]))

    # 更新 reviewers.total_reviews
    if reviewer_id:
        conn.execute("""
            UPDATE reviewers SET total_reviews = (
                SELECT COUNT(*) FROM reviews WHERE reviewer_id = ?
            ) WHERE id = ?
        """, (reviewer_id, reviewer_id))

    conn.commit()
    conn.close()
    return review_id


def get_restaurant_reviews(restaurant_id, limit=20):
    """获取某家店的所有评价"""
    conn = get_conn()
    cursor = conn.execute("""
        SELECT rev.*, rv.display_name, rv.type AS reviewer_type,
               rv.hometown, rv.age_group, rv.taste_tags AS reviewer_taste_tags
        FROM reviews rev
        LEFT JOIN reviewers rv ON rev.reviewer_id = rv.id
        WHERE rev.restaurant_id = ?
        ORDER BY rev.created_at DESC
        LIMIT ?
    """, (restaurant_id, limit))
    reviews = [dict(r) for r in cursor.fetchall()]

    # 补上每条的菜品评价
    for rev in reviews:
        cursor = conn.execute("SELECT * FROM dishes WHERE review_id = ?", (rev["id"],))
        rev["dishes"] = [dict(d) for d in cursor.fetchall()]

        cursor = conn.execute("""
            SELECT t.name FROM tags t
            JOIN review_tags rt ON rt.tag_id = t.id
            WHERE rt.review_id = ?
        """, (rev["id"],))
        rev["tags"] = [r["name"] for r in cursor.fetchall()]

    conn.close()
    return reviews


def search_reviews_text(query, limit=10):
    """全文检索评价内容"""
    conn = get_conn()
    cursor = conn.execute("""
        SELECT rev.*, r.name AS restaurant_name, r.district, r.cuisine_type,
               rv.display_name, rv.type AS reviewer_type
        FROM reviews_fts fts
        JOIN reviews rev ON fts.rowid = rev.id
        JOIN restaurants r ON rev.restaurant_id = r.id
        LEFT JOIN reviewers rv ON rev.reviewer_id = rv.id
        WHERE reviews_fts MATCH ?
        ORDER BY rank
        LIMIT ?
    """, (query, limit))
    results = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return results


def get_recommendations(user_profile=None, cuisine_type=None, district=None, limit=5):
    """获取推荐店铺（聚合评分）"""
    conn = get_conn()
    
    conditions = ["r.is_closed = 0"]
    params = []
    
    if cuisine_type and cuisine_type != "全部":
        conditions.append("r.cuisine_type = ?")
        params.append(cuisine_type)
    if district and district != "全部":
        conditions.append("r.district = ?")
        params.append(district)

    where = " AND ".join(conditions)
    
    base_sql = f"""
        SELECT r.id, r.name, r.address, r.district, r.cuisine_type,
               COUNT(rev.id) AS review_count,
               ROUND(AVG(rev.overall_rating), 2) AS avg_rating,
               ROUND(AVG(CASE WHEN rev.would_revisit = 1 THEN 1.0 ELSE 0 END) * 100, 0) AS revisit_rate,
               MAX(rev.created_at) AS last_review_date
        FROM restaurants r
        LEFT JOIN reviews rev ON rev.restaurant_id = r.id
        WHERE {where}
        GROUP BY r.id
        HAVING review_count >= 1
        ORDER BY avg_rating DESC, review_count DESC
        LIMIT ?
    """
    
    cursor = conn.execute(base_sql, (*params, limit))
    results = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return results

# ============================================================
# 评价解析器：从自然语言提取结构化信息
# ============================================================

def extract_restaurant_name(text):
    """从评价文本中粗提取店名（辅助用途，主要靠 LLM 结构化）"""
    # 常见的模式："店名" 或 「店名」 或 「店名」
    patterns = [
        r'["「『""](.+?)["」』""]',  # 引号括起来的
        r'去(?:了)?(.+?)(?:吃|用餐|探店|打卡)',
        r'(.+?)(?:这家店|那家店|这间|那间)',
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return m.group(1).strip()
    return None


def format_review_for_output(review):
    """将一条 DB 评价格式化为可读文本"""
    lines = []
    if review.get("display_name"):
        lines.append(f"👤 {review['display_name']}（{review.get('reviewer_type', '?')}）")
    
    if review.get("visit_date"):
        lines.append(f"📅 到店: {review['visit_date']}")
    
    lines.append(f"⭐ {review.get('overall_rating', '?')}/5")
    
    if review.get("dishes"):
        dish_lines = []
        for d in review["dishes"]:
            emoji = "✅" if d.get("recommended") else "⚠️"
            price_str = f"¥{d['price']}" if d.get("price") else ""
            dish_lines.append(f"  {emoji} {d['name']} {d.get('rating', '?')}/5 {price_str}")
            if d.get("comment"):
                dish_lines.append(f"    └ {d['comment']}")
        if dish_lines:
            lines.append("🍽️ 菜品:")
            lines.extend(dish_lines)
    
    if review.get("review_text"):
        lines.append(f"💬 {review['review_text']}")
    
    if review.get("pros"):
        try:
            pros = json.loads(review["pros"]) if isinstance(review["pros"], str) else review["pros"]
            if pros:
                lines.append(f"👍 好评: {' | '.join(pros)}")
        except (json.JSONDecodeError, TypeError):
            pass
    
    if review.get("cons"):
        try:
            cons = json.loads(review["cons"]) if isinstance(review["cons"], str) else review["cons"]
            if cons:
                lines.append(f"👎 差评: {' | '.join(cons)}")
        except (json.JSONDecodeError, TypeError):
            pass
    
    if review.get("tags"):
        if isinstance(review["tags"], str):
            try:
                tags = json.loads(review["tags"])
            except:
                tags = [review["tags"]]
        else:
            tags = review["tags"]
        lines.append(f"🏷️ {' '.join(tags)}")
    
    return "\n".join(lines)


# ============================================================
# 快捷查询（整合输出用）
# ============================================================

def get_restaurant_card(restaurant_id):
    """获取店铺信息卡片"""
    conn = get_conn()
    
    # 基本信息
    cursor = conn.execute("SELECT * FROM restaurants WHERE id = ?", (restaurant_id,))
    rest = dict(cursor.fetchone() or {})
    if not rest:
        conn.close()
        return None
    
    # 统计
    cursor = conn.execute("SELECT * FROM restaurant_stats WHERE restaurant_id = ?", (restaurant_id,))
    stats = dict(cursor.fetchone() or {})
    rest.update(stats)
    
    # 最近 3 条评价
    cursor = conn.execute("""
        SELECT rev.*, rv.display_name, rv.type AS reviewer_type,
               rv.hometown, rv.age_group
        FROM reviews rev
        LEFT JOIN reviewers rv ON rev.reviewer_id = rv.id
        WHERE rev.restaurant_id = ?
        ORDER BY rev.created_at DESC
        LIMIT 3
    """, (restaurant_id,))
    rest["recent_reviews"] = [dict(r) for r in cursor.fetchall()]
    
    conn.close()
    return rest


# ============================================================
# 趋势追踪操作
# ============================================================

import statistics
from collections import Counter


def record_trend(restaurant_id, period, period_type='monthly'):
    """计算并记录某家店在指定周期的聚合趋势数据。
    
    Args:
        restaurant_id: 店铺 ID
        period: 周期标识，如 '2026-07'（月度）或 '2026-W27'（周度）
        period_type: 'weekly' 或 'monthly'
    
    Returns:
        dict — 写入 trend_tracking 的记录；若已存在则返回 None
    """
    conn = get_conn()

    # 检查是否已有该周期记录
    existing = conn.execute(
        "SELECT id FROM trend_tracking WHERE restaurant_id = ? AND period = ?",
        (restaurant_id, period)
    ).fetchone()
    if existing:
        conn.close()
        return None

    # 解析周期边界
    if period_type == 'monthly':
        # period = '2026-07'
        year, month = period.split('-')
        start_date = f"{year}-{month}-01"
        if month == '12':
            end_date = f"{int(year)+1}-01-01"
        else:
            end_date = f"{year}-{int(month)+1:02d}-01"
    elif period_type == 'weekly':
        # period = '2026-W27' — 用 ISO 周推算起止
        from datetime import date, timedelta
        iso_year = int(period[:4])
        iso_week = int(period.split('W')[1])
        # 该周周一的日期
        jan4 = date(iso_year, 1, 4)
        start_of_jan4_week = jan4 - timedelta(days=jan4.isoweekday() - 1)
        monday = start_of_jan4_week + timedelta(weeks=iso_week - 1)
        start_date = monday.isoformat()
        end_date = (monday + timedelta(days=7)).isoformat()
    else:
        conn.close()
        raise ValueError(f"Unsupported period_type: {period_type}")

    # 1. 拉该周期的评价
    reviews_cursor = conn.execute("""
        SELECT overall_rating, would_revisit, pros, cons, id
        FROM reviews
        WHERE restaurant_id = ?
          AND visit_date >= ?
          AND visit_date < ?
    """, (restaurant_id, start_date, end_date))
    period_reviews = [dict(r) for r in reviews_cursor.fetchall()]

    if not period_reviews:
        conn.close()
        return None

    # 2. 计算聚合指标
    ratings = [r['overall_rating'] for r in period_reviews if r['overall_rating'] is not None]
    review_count = len(ratings)
    avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else None
    median_rating = round(statistics.median(ratings), 2) if ratings else None

    revisit_vals = [r['would_revisit'] for r in period_reviews if r['would_revisit'] is not None]
    would_revisit_rate = round(sum(revisit_vals) / len(revisit_vals), 2) if revisit_vals else None

    # 3. 菜品 TOP3
    dish_cursor = conn.execute("""
        SELECT d.name, COUNT(*) AS cnt, AVG(d.rating) AS avg_rating
        FROM dishes d
        JOIN reviews rev ON d.review_id = rev.id
        WHERE rev.restaurant_id = ?
          AND rev.visit_date >= ?
          AND rev.visit_date < ?
          AND d.recommended = 1
        GROUP BY d.name
        ORDER BY cnt DESC, avg_rating DESC
        LIMIT 3
    """, (restaurant_id, start_date, end_date))
    top_dishes_rows = [dict(r) for r in dish_cursor.fetchall()]
    top_dishes = json.dumps([
        {"name": d['name'], "count": d['cnt'], "avg_rating": round(d['avg_rating'], 2) if d['avg_rating'] else None}
        for d in top_dishes_rows
    ], ensure_ascii=False)

    # 菜品平均分（该周期内所有菜品）
    dish_avg_cursor = conn.execute("""
        SELECT AVG(d.rating) AS avg_dish_rating
        FROM dishes d
        JOIN reviews rev ON d.review_id = rev.id
        WHERE rev.restaurant_id = ?
          AND rev.visit_date >= ?
          AND rev.visit_date < ?
    """, (restaurant_id, start_date, end_date))
    avg_dish_rating_row = dish_avg_cursor.fetchone()
    avg_dish_rating = round(avg_dish_rating_row['avg_dish_rating'], 2) if avg_dish_rating_row and avg_dish_rating_row['avg_dish_rating'] else None

    # 4. 提取高频好评/差评词
    all_pros = []
    all_cons = []
    for r in period_reviews:
        if r['pros']:
            try:
                pros_list = json.loads(r['pros']) if isinstance(r['pros'], str) else r['pros']
                if isinstance(pros_list, list):
                    all_pros.extend(pros_list)
            except (json.JSONDecodeError, TypeError):
                pass
        if r['cons']:
            try:
                cons_list = json.loads(r['cons']) if isinstance(r['cons'], str) else r['cons']
                if isinstance(cons_list, list):
                    all_cons.extend(cons_list)
            except (json.JSONDecodeError, TypeError):
                pass

    def _top_keywords(items, top_n=5):
        """从词列表中提取出现最多的 TOP N"""
        if not items:
            return []
        counts = Counter(items)
        return [{"keyword": k, "count": v} for k, v in counts.most_common(top_n)]

    common_pros = json.dumps(_top_keywords(all_pros), ensure_ascii=False)
    common_cons = json.dumps(_top_keywords(all_cons), ensure_ascii=False)

    # 5. 写入
    conn.execute("""
        INSERT INTO trend_tracking
            (restaurant_id, period, period_type, review_count, avg_rating,
             median_rating, would_revisit_rate, avg_dish_rating,
             top_dishes, common_pros, common_cons)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (restaurant_id, period, period_type, review_count, avg_rating,
          median_rating, would_revisit_rate, avg_dish_rating,
          top_dishes, common_pros, common_cons))
    conn.commit()
    conn.close()

    return {
        "restaurant_id": restaurant_id,
        "period": period,
        "period_type": period_type,
        "review_count": review_count,
        "avg_rating": avg_rating,
        "median_rating": median_rating,
        "would_revisit_rate": would_revisit_rate,
        "avg_dish_rating": avg_dish_rating,
        "top_dishes": top_dishes,
        "common_pros": common_pros,
        "common_cons": common_cons
    }


def get_trend(restaurant_id, period_type='monthly', limit=12):
    """获取某家店的历史趋势数据（最近 N 个周期），按时间排序。
    
    Args:
        restaurant_id: 店铺 ID
        period_type: 'weekly' 或 'monthly'
        limit: 返回最近多少个周期
    
    Returns:
        list[dict] — 按 period 升序排列的趋势记录
    """
    conn = get_conn()
    cursor = conn.execute("""
        SELECT *
        FROM trend_tracking
        WHERE restaurant_id = ? AND period_type = ?
        ORDER BY period DESC
        LIMIT ?
    """, (restaurant_id, period_type, limit))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    # 按时间升序
    rows.reverse()
    return rows


def get_hot_restaurants(limit=10):
    """获取当前最热门的店铺（最近 30 天评价数最多）。
    
    Args:
        limit: 返回店铺数量
    
    Returns:
        list[dict] — 包含店铺信息和近期评价数
    """
    conn = get_conn()
    cursor = conn.execute("""
        SELECT r.id, r.name, r.district, r.cuisine_type,
               COUNT(rev.id) AS recent_review_count,
               ROUND(AVG(rev.overall_rating), 2) AS recent_avg_rating
        FROM restaurants r
        JOIN reviews rev ON rev.restaurant_id = r.id
        WHERE rev.created_at >= datetime('now', '-30 days')
        GROUP BY r.id
        ORDER BY recent_review_count DESC
        LIMIT ?
    """, (limit,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def get_declining_restaurants(limit=5):
    """检测评分下滑的店（最近 90 天 vs 前 90 天，下降 > 0.3 分的标记）。
    
    Args:
        limit: 返回店铺数量
    
    Returns:
        list[dict] — 下滑店铺列表，含前后评分和下降幅度
    """
    conn = get_conn()
    cursor = conn.execute("""
        SELECT r.id, r.name, r.district, r.cuisine_type,
               ROUND(AVG(CASE 
                   WHEN rev.created_at >= datetime('now', '-90 days') 
                   THEN rev.overall_rating 
                   ELSE NULL END), 2) AS recent_90d_avg,
               ROUND(AVG(CASE 
                   WHEN rev.created_at < datetime('now', '-90 days') 
                    AND rev.created_at >= datetime('now', '-180 days')
                   THEN rev.overall_rating 
                   ELSE NULL END), 2) AS prior_90d_avg,
               COUNT(CASE 
                   WHEN rev.created_at >= datetime('now', '-90 days') 
                   THEN 1 END) AS recent_count
        FROM restaurants r
        JOIN reviews rev ON rev.restaurant_id = r.id
        GROUP BY r.id
        HAVING recent_90d_avg IS NOT NULL
           AND prior_90d_avg IS NOT NULL
           AND (prior_90d_avg - recent_90d_avg) > 0.3
           AND recent_count >= 3
        ORDER BY (prior_90d_avg - recent_90d_avg) DESC
        LIMIT ?
    """, (limit,))
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    # 附加下降幅度
    for row in rows:
        row["decline"] = round(row["prior_90d_avg"] - row["recent_90d_avg"], 2)
    return rows


if __name__ == "__main__":
    # 初始化检查
    assert init_db(), "DB init failed"
    print("✅ 数据库可用")
    print(f"📍 {DB_PATH}")
