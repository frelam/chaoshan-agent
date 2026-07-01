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


if __name__ == "__main__":
    # 初始化检查
    assert init_db(), "DB init failed"
    print("✅ 数据库可用")
    print(f"📍 {DB_PATH}")
