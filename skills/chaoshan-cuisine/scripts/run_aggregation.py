#!/usr/bin/env python3
"""
潮汕美食评价聚合脚本 — 公平算法引擎

[!] 重要警告 - 文档-代码对齐情况 [!]
本文档对应的公平算法版本为 docs/FAIRNESS-ALGORITHM.md v2.3.0。
当前代码仅实现了 v2.0 基础功能（离散时间衰减 + 简单反操控）。
v2.2.0/v2.3.0 新增的 25+ 个参数和机制尚未在代码中实现。
详见 docs/FAIRNESS-ALGORITHM.md 参数可调表和 data/challenge-logs/。

从 SQLite reviews.db 读取评价数据，按公平算法聚合后写入 restaurant-summary.yaml。
支持 --dry-run 参数预览输出而不写文件。

用法:
    python scripts/run_aggregation.py              # 实际聚合并写文件
    python scripts/run_aggregation.py --dry-run    # 预览输出，不写文件

依赖: Python 3.7+, PyYAML
"""

import argparse
import json
import math
import os
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

# ── 确保能找到 data/db_helper.py ────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
DATA_DIR = SKILL_DIR / "data"
sys.path.insert(0, str(DATA_DIR))

try:
    from db_helper import get_conn, init_db
except ImportError as e:
    print(f"❌ 无法导入 db_helper.py: {e}")
    print(f"   查找路径: {DATA_DIR}")
    sys.exit(1)

try:
    import yaml
except ImportError:
    print("❌ 需要 PyYAML: pip install pyyaml")
    sys.exit(1)

# ── 路径配置 ─────────────────────────────────────────────────────────────────
SUMMARY_YAML = DATA_DIR / "restaurant-summary.yaml"

# ── 公平算法参数 ─────────────────────────────────────────────────────────────
# 与 restaurant-summary.yaml meta.algorithm 保持同步
TIME_DECAY = {
    "within_1y": 1.0,    # 1年内权重1.0
    "within_2y": 0.8,    # 1-2年权重0.8
    "within_3y": 0.5,    # 2-3年权重0.5
    "over_3y": 0.3,      # 超过3年权重0.3
}
OLD_SHOP_BONUS_WEIGHT = 0.6   # 老店且评价稳定时 >3年评价权重
MINORITY_THRESHOLD = 0.15     # ≥15% 的观点独立保留
CONTROVERSY_VARIANCE = 1.5    # 方差 > 1.5 标记为争议

# 反操控参数
SUSPICIOUS_WINDOW_DAYS = 7
SUSPICIOUS_MIN_REVIEWS = 3

NOW = datetime.now()


# ══════════════════════════════════════════════════════════════════════════════
# 辅助函数
# ══════════════════════════════════════════════════════════════════════════════

def parse_date(date_str):
    """解析日期字符串，返回 datetime 或 None"""
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def compute_time_decay_weight(created_at, is_stable_old_shop=False):
    """计算离散时间衰减权重"""
    review_date = parse_date(created_at)
    if not review_date:
        return 1.0  # 无法解析日期的默认权重

    years_since = (NOW - review_date).days / 365.25

    if years_since <= 1.0:
        return TIME_DECAY["within_1y"]
    elif years_since <= 2.0:
        return TIME_DECAY["within_2y"]
    elif years_since <= 3.0:
        return TIME_DECAY["within_3y"]
    else:
        if is_stable_old_shop:
            return OLD_SHOP_BONUS_WEIGHT
        else:
            return TIME_DECAY["over_3y"]


def is_stable_old_shop(review_count, variance, has_old_reviews):
    """判断是否为稳定老店（开张≥3年、≥5条评价、方差<1.0）"""
    return review_count >= 5 and variance < 1.0 and has_old_reviews


def compute_weighted_median(ratings_with_weights):
    """
    计算加权中位数
    ratings_with_weights: [(rating, weight), ...] 列表
    """
    if not ratings_with_weights:
        return 0.0

    sorted_items = sorted(ratings_with_weights, key=lambda x: x[0])
    total_weight = sum(w for _, w in sorted_items)
    if total_weight == 0:
        return 0.0

    cumulative = 0.0
    half = total_weight / 2.0
    prev_rating = sorted_items[0][0]

    for rating, weight in sorted_items:
        cumulative += weight
        if cumulative >= half:
            # 如果正好在中间，取前后评分的均值
            if cumulative - weight < half and cumulative > half:
                return (prev_rating + rating) / 2.0
            return rating
        prev_rating = rating

    return sorted_items[-1][0]


def compute_variance(ratings):
    """计算方差"""
    if len(ratings) < 2:
        return 0.0
    return statistics.variance(ratings)


def safe_json_loads(value):
    """安全加载 JSON 字符串"""
    if not value:
        return []
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def get_quarter(month):
    """返回月份对应的季度字符串"""
    if month <= 3:
        return 1
    elif month <= 6:
        return 2
    elif month <= 9:
        return 3
    else:
        return 4


# ══════════════════════════════════════════════════════════════════════════════
# 数据加载
# ══════════════════════════════════════════════════════════════════════════════

def load_all_data():
    """从 SQLite 加载所有数据"""
    init_db()
    conn = get_conn()

    # 1. 加载所有店铺
    # 先获取列名
    cursor = conn.execute("SELECT * FROM restaurants")
    col_names = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    restaurants = [dict(zip(col_names, r)) for r in rows]

    # 2. 加载所有评价（含评价者信息）
    cursor = conn.execute("""
        SELECT rev.*, rv.display_name, rv.type AS reviewer_type,
               rv.hometown, rv.age_group, rv.taste_tags AS reviewer_taste_tags
        FROM reviews rev
        LEFT JOIN reviewers rv ON rev.reviewer_id = rv.id
        ORDER BY rev.restaurant_id, rev.created_at
    """)
    col_names = [desc[0] for desc in cursor.description]
    reviews = [dict(zip(col_names, r)) for r in cursor.fetchall()]

    # 3. 加载所有菜品评价
    cursor = conn.execute("SELECT * FROM dishes")
    col_names = [desc[0] for desc in cursor.description]
    dishes = [dict(zip(col_names, d)) for d in cursor.fetchall()]

    # 4. 加载所有标签
    cursor = conn.execute("""
        SELECT rt.review_id, t.name
        FROM review_tags rt
        JOIN tags t ON t.id = rt.tag_id
    """)
    col_names = [desc[0] for desc in cursor.description]
    review_tags = [dict(zip(col_names, r)) for r in cursor.fetchall()]

    # 5. 检查 trend_tracking 表是否存在
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='trend_tracking'"
    )
    has_trend_table = cursor.fetchone() is not None

    conn.close()

    # 按 review_id 索引标签
    tags_by_review = defaultdict(list)
    for rt in review_tags:
        tags_by_review[rt["review_id"]].append(rt["name"])

    # 按 review_id 索引菜品
    dishes_by_review = defaultdict(list)
    for d in dishes:
        dishes_by_review[d["review_id"]].append(d)

    # 对每条评价补充标签和菜品
    for rev in reviews:
        rev["dish_items"] = dishes_by_review.get(rev["id"], [])
        rev["tag_names"] = tags_by_review.get(rev["id"], [])

    return restaurants, reviews


# ══════════════════════════════════════════════════════════════════════════════
# 单店铺聚合计算
# ══════════════════════════════════════════════════════════════════════════════

def aggregate_restaurant(restaurant, reviews):
    """
    对一家店铺的所有评价执行公平算法聚合
    返回一个 dict 适配 restaurant-summary.yaml 的 entries 格式
    """
    if not reviews:
        return None

    # ── 0. 基本信息 ──────────────────────────────────────────────────────
    entry = {
        "id": f"rest-{restaurant['id']:03d}",
        "name": restaurant["name"],
        "address": restaurant.get("address") or "",
        "district": restaurant.get("district") or "",
        "cuisine_type": restaurant.get("cuisine_type") or "",
    }

    if restaurant.get("coordinates_lat") and restaurant.get("coordinates_lng"):
        entry["coordinates"] = {
            "lat": restaurant["coordinates_lat"],
            "lng": restaurant["coordinates_lng"],
        }

    # ── 1. 基础评分统计 ──────────────────────────────────────────────────
    ratings = []
    ratings_with_time = []
    would_revisit_list = []
    created_dates = []

    for rev in reviews:
        r = rev.get("overall_rating")
        if r is not None:
            ratings.append(r)
            created_at = rev.get("created_at")
            created_dates.append(created_at)

        wr = rev.get("would_revisit")
        if wr is not None:
            would_revisit_list.append(wr)

    review_count = len(reviews)
    if not ratings:
        return None

    # 评分分布
    distribution = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    for r in ratings:
        distribution[int(round(r))] = distribution.get(int(round(r)), 0) + 1

    variance = compute_variance(ratings)

    # 判断是否有超过3年的老评价
    has_old_reviews = False
    for d in created_dates:
        dt = parse_date(d)
        if dt and (NOW - dt).days > 365.25 * 3:
            has_old_reviews = True
            break

    stable_old_shop = is_stable_old_shop(review_count, variance, has_old_reviews)

    # 时间衰减加权评分
    ratings_with_weights = []
    for rev in reviews:
        r = rev.get("overall_rating")
        if r is None:
            continue
        w = compute_time_decay_weight(rev.get("created_at"), stable_old_shop)
        ratings_with_weights.append((r, w))

    weighted_median = compute_weighted_median(ratings_with_weights)
    simple_median = statistics.median(ratings) if ratings else 0.0

    # 最新评价日期
    all_dates = [parse_date(r.get("created_at")) for r in reviews]
    all_dates = [d for d in all_dates if d]
    last_review_date = max(all_dates).strftime("%Y-%m-%d") if all_dates else ""

    # would_revisit 率
    if would_revisit_list:
        would_revisit_rate = round(
            sum(1 for w in would_revisit_list if w == 1) / len(would_revisit_list),
            2,
        )
    else:
        would_revisit_rate = None

    entry["rating_overview"] = {
        "median": round(simple_median, 2),
        "weighted_median": round(weighted_median, 2),
        "count": review_count,
        "distribution": distribution,
        "variance": round(variance, 2),
        "last_review_date": last_review_date,
        "last_verified": NOW.strftime("%Y-%m-%d"),
    }

    # ── 2. 趋势数据 ──────────────────────────────────────────────────────
    monthly_data = defaultdict(lambda: {"ratings": [], "would_revisit": []})
    quarterly_data = defaultdict(lambda: {"ratings": [], "would_revisit": []})

    for rev in reviews:
        dt = parse_date(rev.get("created_at"))
        if not dt:
            continue

        month_key = dt.strftime("%Y-%m")
        quarter_key = f"{dt.year}-Q{get_quarter(dt.month)}"

        r = rev.get("overall_rating")
        if r is not None:
            monthly_data[month_key]["ratings"].append(r)
            quarterly_data[quarter_key]["ratings"].append(r)

        wr = rev.get("would_revisit")
        if wr is not None:
            monthly_data[month_key]["would_revisit"].append(wr)
            quarterly_data[quarter_key]["would_revisit"].append(wr)

    trends = {"monthly": [], "quarterly": [], "direction": "insufficient_data", "volatility": "low"}

    for month_key in sorted(monthly_data.keys()):
        d = monthly_data[month_key]
        avg_r = round(statistics.mean(d["ratings"]), 2) if d["ratings"] else 0
        wr_rate = round(sum(1 for w in d["would_revisit"] if w == 1) / len(d["would_revisit"]), 2) if d["would_revisit"] else None
        trends["monthly"].append({
            "month": month_key,
            "avg_rating": avg_r,
            "review_count": len(d["ratings"]),
            "would_revisit_rate": wr_rate,
        })

    for q_key in sorted(quarterly_data.keys()):
        d = quarterly_data[q_key]
        avg_r = round(statistics.mean(d["ratings"]), 2) if d["ratings"] else 0
        wr_rate = round(sum(1 for w in d["would_revisit"] if w == 1) / len(d["would_revisit"]), 2) if d["would_revisit"] else None
        trends["quarterly"].append({
            "quarter": q_key,
            "avg_rating": avg_r,
            "review_count": len(d["ratings"]),
            "would_revisit_rate": wr_rate,
        })

    # 趋势方向判定（最近3个月线性回归斜率）
    monthly_ratings = [m["avg_rating"] for m in trends["monthly"][-3:]]
    if len(monthly_ratings) >= 2:
        n = len(monthly_ratings)
        x = list(range(n))
        x_mean = statistics.mean(x)
        y_mean = statistics.mean(monthly_ratings)
        numerator = sum((x[i] - x_mean) * (monthly_ratings[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        slope = numerator / denominator if denominator != 0 else 0
        if slope > 0.2:
            trends["direction"] = "rising"
        elif slope < -0.2:
            trends["direction"] = "declining"
        else:
            trends["direction"] = "stable"

    # 波动率判定
    if len(monthly_ratings) >= 3:
        std_dev = statistics.stdev(monthly_ratings)
        if std_dev > 0.5:
            trends["volatility"] = "high"
        elif std_dev > 0.3:
            trends["volatility"] = "medium"
        else:
            trends["volatility"] = "low"

    entry["trends"] = trends

    # ── 3. 人群细分评分 ──────────────────────────────────────────────────
    # 按评价者类型
    by_type_data = defaultdict(list)
    for rev in reviews:
        r = rev.get("overall_rating")
        if r is None:
            continue
        rtype = rev.get("reviewer_type") or "unknown"
        by_type_data[rtype].append(rev)

    demographics = {"by_type": {}, "by_age": {}, "by_hometown": []}

    for rtype, revs in sorted(by_type_data.items()):
        type_ratings = [r["overall_rating"] for r in revs if r.get("overall_rating") is not None]
        type_wr = [r["would_revisit"] for r in revs if r.get("would_revisit") is not None]
        if type_ratings:
            wr_rate = round(sum(1 for w in type_wr if w == 1) / len(type_wr), 2) if type_wr else None
            demographics["by_type"][rtype] = {
                "count": len(revs),
                "median_rating": round(statistics.median(type_ratings), 2),
                "would_revisit_rate": wr_rate,
            }

    # 按年龄段
    by_age_data = defaultdict(list)
    for rev in reviews:
        r = rev.get("overall_rating")
        if r is None:
            continue
        age = rev.get("age_group") or "unknown"
        by_age_data[age].append(rev)

    for age, revs in sorted(by_age_data.items()):
        age_ratings = [r["overall_rating"] for r in revs if r.get("overall_rating") is not None]
        if age_ratings:
            demographics["by_age"][age] = {
                "count": len(revs),
                "median_rating": round(statistics.median(age_ratings), 2),
            }

    # 按家乡
    by_hometown_data = defaultdict(list)
    for rev in reviews:
        r = rev.get("overall_rating")
        if r is None:
            continue
        hometown = rev.get("hometown") or "未知"
        by_hometown_data[hometown].append(rev)

    for hometown, revs in sorted(by_hometown_data.items()):
        ht_ratings = [r["overall_rating"] for r in revs if r.get("overall_rating") is not None]
        if ht_ratings:
            demographics["by_hometown"].append({
                "hometown": hometown,
                "count": len(revs),
                "median_rating": round(statistics.median(ht_ratings), 2),
            })

    entry["demographics"] = demographics

    # ── 4. 共识观点提取 ──────────────────────────────────────────────────
    # 4a. 菜品聚合
    dish_stats = defaultdict(lambda: {"ratings": [], "mentions": 0, "prices": [], "comments": []})
    for rev in reviews:
        for dish in rev.get("dish_items", []):
            name = dish.get("name", "")
            if not name:
                continue
            r = dish.get("rating")
            price = dish.get("price")
            comment = dish.get("comment")

            dish_stats[name]["mentions"] += 1
            if r is not None:
                dish_stats[name]["ratings"].append(r)
            if price:
                dish_stats[name]["prices"].append(price)
            if comment:
                dish_stats[name]["comments"].append(comment)

    consensus = {"must_try": [], "pros": [], "cons": []}

    # 按提及次数排序选推荐菜
    sorted_dishes = sorted(dish_stats.items(), key=lambda x: x[1]["mentions"], reverse=True)
    for name, stats in sorted_dishes:
        avg_r = round(statistics.mean(stats["ratings"]), 2) if stats["ratings"] else 0
        prices = [p for p in stats["prices"] if p]
        price_str = ""
        if prices:
            p_min, p_max = min(prices), max(prices)
            price_str = f"{p_min}-{p_max}元" if p_min != p_max else f"{p_min}元"

        best_comment = ""
        if stats["comments"]:
            best_comment = max(stats["comments"], key=len)  # 取描述最详细的

        consensus["must_try"].append({
            "dish": name,
            "avg_rating": avg_r,
            "mention_count": stats["mentions"],
            "price_range": price_str,
            "best_comment": best_comment,
        })

    # 4b. Pros/Cons 聚合
    all_pros = []
    all_cons = []
    for rev in reviews:
        pros = safe_json_loads(rev.get("pros"))
        cons = safe_json_loads(rev.get("cons"))
        for p in pros:
            # 处理中文 unicode 转义
            clean_p = p.encode("utf-8").decode("unicode_escape") if "\\u" in str(p) else p
            all_pros.append(clean_p)
        for c in cons:
            clean_c = c.encode("utf-8").decode("unicode_escape") if "\\u" in str(c) else c
            all_cons.append(clean_c)

    if all_pros:
        pro_counter = Counter(all_pros)
        total_reviews = len(reviews)
        for pro, count in pro_counter.most_common(5):
            if count / total_reviews >= 0.15:
                consensus["pros"].append(pro)

    if all_cons:
        con_counter = Counter(all_cons)
        total_reviews = len(reviews)
        for con, count in con_counter.most_common(5):
            if count / total_reviews >= 0.15:
                consensus["cons"].append(con)

    # 4c. 标签聚合
    all_tags = []
    for rev in reviews:
        all_tags.extend(rev.get("tag_names", []))
    if all_tags:
        tag_counter = Counter(all_tags)
        entry["tags"] = [tag for tag, count in tag_counter.most_common(8)]

    entry["consensus"] = consensus

    # ── 5. 少数派声音检测 ────────────────────────────────────────────────
    diverse_opinions = []

    # 检测 pros/cons 中的 minority 观点（占比 >= 15% 但 < 60%）
    if all_pros:
        total_reviews = len(reviews)
        pro_counter = Counter(all_pros)
        for pro, count in pro_counter.most_common(5):
            ratio = count / total_reviews
            if MINORITY_THRESHOLD <= ratio < 0.60:
                # 找出持此观点的人群
                held_types = set()
                for rev in reviews:
                    rev_pros = safe_json_loads(rev.get("pros"))
                    clean_rev_pros = [
                        p.encode("utf-8").decode("unicode_escape") if "\\u" in str(p) else p
                        for p in rev_pros
                    ]
                    if pro in clean_rev_pros:
                        rtype = rev.get("reviewer_type") or "unknown"
                        held_types.add(rtype)
                existing = [d for d in diverse_opinions if d["opinion"] == f"👍 {pro}"]
                if not existing:
                    diverse_opinions.append({
                        "opinion": f"👍 {pro}",
                        "count": count,
                        "ratio": round(ratio, 2),
                        "held_by": {
                            "types": sorted(held_types) if held_types else ["unknown"],
                            "note": "",
                        },
                    })

    if all_cons:
        total_reviews = len(reviews)
        con_counter = Counter(all_cons)
        for con, count in con_counter.most_common(5):
            ratio = count / total_reviews
            if MINORITY_THRESHOLD <= ratio < 0.60:
                held_types = set()
                for rev in reviews:
                    rev_cons = safe_json_loads(rev.get("cons"))
                    clean_rev_cons = [
                        c.encode("utf-8").decode("unicode_escape") if "\\u" in str(c) else c
                        for c in rev_cons
                    ]
                    if con in clean_rev_cons:
                        rtype = rev.get("reviewer_type") or "unknown"
                        held_types.add(rtype)
                existing = [d for d in diverse_opinions if d["opinion"] == f"👎 {con}"]
                if not existing:
                    diverse_opinions.append({
                        "opinion": f"👎 {con}",
                        "count": count,
                        "ratio": round(ratio, 2),
                        "held_by": {
                            "types": sorted(held_types) if held_types else ["unknown"],
                            "note": "",
                        },
                    })

    entry["diverse_opinions"] = diverse_opinions

    # ── 6. 争议标记 ───────────────────────────────────────────────────────
    is_controversial = variance > CONTROVERSY_VARIANCE
    controversy_note = ""
    if is_controversial:
        # 分析高分群和低分群特征
        high_raters = [rev for rev in reviews if (rev.get("overall_rating") or 0) >= 4]
        low_raters = [rev for rev in reviews if (rev.get("overall_rating") or 0) <= 2]
        high_types = set(rev.get("reviewer_type") or "?" for rev in high_raters)
        low_types = set(rev.get("reviewer_type") or "?" for rev in low_raters)
        controversy_note = (
            f"评价两极化——{', '.join(sorted(high_types)) or '部分'}给了高分，"
            f"{', '.join(sorted(low_types)) or '部分'}给了低分"
        )

    entry["controversy"] = {
        "is_controversial": is_controversial,
        "note": controversy_note,
    }

    # ── 7. 反操控检测 ────────────────────────────────────────────────────
    # 7天窗口内同一店铺3条以上集中评价标记为可疑
    suspicious_review_ids = []

    # 按 created_at 排序
    sorted_reviews = sorted(
        reviews,
        key=lambda r: parse_date(r.get("created_at")) or datetime.min,
    )

    for i, rev in enumerate(sorted_reviews):
        rev_date = parse_date(rev.get("created_at"))
        if not rev_date:
            continue
        # 检查此后7天内是否有3条以上
        window_end = rev_date + timedelta(days=SUSPICIOUS_WINDOW_DAYS)
        window_reviews = []
        for j in range(i, len(sorted_reviews)):
            j_date = parse_date(sorted_reviews[j].get("created_at"))
            if j_date and rev_date <= j_date <= window_end:
                window_reviews.append(sorted_reviews[j])

        if len(window_reviews) >= SUSPICIOUS_MIN_REVIEWS:
            for wr in window_reviews:
                if wr["id"] not in suspicious_review_ids:
                    suspicious_review_ids.append(wr["id"])

    entry["suspicious"] = {
        "has_suspicious_clusters": len(suspicious_review_ids) > 0,
        "suspicious_review_ids": suspicious_review_ids,
    }

    # ── 8. 营业状态 ──────────────────────────────────────────────────────
    entry["status"] = "active"
    entry["status_note"] = ""
    if restaurant.get("is_closed"):
        entry["status"] = "closed"
        entry["status_note"] = "已闭店"

    # ── 9. 生成 AI 摘要 ──────────────────────────────────────────────────
    summary_parts = []

    # 整体评分
    median_str = str(entry["rating_overview"]["weighted_median"])
    summary_parts.append(
        f"{review_count}人评价，加权中位评分{median_str}/5"
    )

    # 争议
    if is_controversial:
        summary_parts.append("评价争议较大，口味分化明显")

    # 趋势
    if trends["direction"] == "rising":
        summary_parts.append("近期评分呈上升趋势")
    elif trends["direction"] == "declining":
        summary_parts.append("近期评分呈下降趋势")

    # 推荐菜
    if consensus["must_try"]:
        top_dishes = [d["dish"] for d in consensus["must_try"][:3]]
        summary_parts.append(f"推荐菜：{'/'.join(top_dishes)}")

    # 人群差异
    if demographics["by_type"]:
        type_diffs = []
        for rtype, data in demographics["by_type"].items():
            type_diffs.append(f"{rtype}评分{data['median_rating']}")
        summary_parts.append(f"人群差异：{'，'.join(type_diffs)}")

    # 少数派声音
    if diverse_opinions:
        voices = [d["opinion"] for d in diverse_opinions[:2]]
        summary_parts.append(f"不同声音：{'；'.join(voices)}")

    entry["summary"] = "。".join(summary_parts) + "。"
    entry["last_updated"] = NOW.strftime("%Y-%m-%d")

    return entry


# ══════════════════════════════════════════════════════════════════════════════
# 趋势数据写入 DB
# ══════════════════════════════════════════════════════════════════════════════

def write_trends_to_db(restaurant_id, trends):
    """将趋势数据写入 trend_tracking 表（如存在）"""
    try:
        conn = get_conn()
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='trend_tracking'"
        )
        if not cursor.fetchone():
            conn.close()
            return

        for month_data in trends.get("monthly", []):
            conn.execute(
                """
                INSERT OR REPLACE INTO trend_tracking
                    (restaurant_id, period_type, period, review_count, avg_rating, would_revisit_rate)
                VALUES (?, 'monthly', ?, ?, ?, ?)
                """,
                (
                    restaurant_id,
                    month_data["month"],
                    month_data["review_count"],
                    month_data["avg_rating"],
                    month_data["would_revisit_rate"],
                ),
            )

        for q_data in trends.get("quarterly", []):
            conn.execute(
                """
                INSERT OR REPLACE INTO trend_tracking
                    (restaurant_id, period_type, period, review_count, avg_rating, would_revisit_rate)
                VALUES (?, 'quarterly', ?, ?, ?, ?)
                """,
                (
                    restaurant_id,
                    q_data["quarter"],
                    q_data["review_count"],
                    q_data["avg_rating"],
                    q_data["would_revisit_rate"],
                ),
            )

        conn.commit()
        conn.close()
    except Exception as e:
        print(f"  ⚠️ 趋势写入失败: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# 主流程
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="潮汕美食评价聚合 — 公平算法引擎"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="预览模式：打印输出到 stdout，不写文件",
    )
    args = parser.parse_args()

    print(f"📊 潮汕美食公平算法聚合引擎 v2.0")
    print(f"    评价数据库: {DATA_DIR / 'reviews.db'}")
    print(f"    输出文件:   {SUMMARY_YAML}")
    if args.dry_run:
        print(f"    模式:       预览模式 (--dry-run)")
    print()

    # 加载数据
    restaurants, reviews = load_all_data()
    print(f"📦 加载完成:")
    print(f"   店铺: {len(restaurants)} 家")
    print(f"   评价: {len(reviews)} 条")

    # 按 restaurant_id 分组
    reviews_by_restaurant = defaultdict(list)
    for rev in reviews:
        reviews_by_restaurant[rev["restaurant_id"]].append(rev)

    # 聚合每家店铺
    entries = []
    total_reviews_processed = 0

    for rest in restaurants:
        rid = rest["id"]
        rest_reviews = reviews_by_restaurant.get(rid, [])
        if not rest_reviews:
            continue

        print(f"\n🏪 {rest['name']} ({len(rest_reviews)} 条评价)...")
        entry = aggregate_restaurant(rest, rest_reviews)

        if entry is None:
            print(f"   ⚠️ 聚合失败（无有效评分）")
            continue

        entries.append(entry)
        total_reviews_processed += len(rest_reviews)

        # 写入趋势数据到 DB
        if not args.dry_run:
            write_trends_to_db(rid, entry.get("trends", {}))

        # 输出摘要
        overview = entry["rating_overview"]
        print(f"   ✅ 中位数: {overview['median']} | 加权中位数: {overview['weighted_median']} | 方差: {overview['variance']}")
        if entry["controversy"]["is_controversial"]:
            print(f"   ⚠️ 争议标记: 是")
        if entry["suspicious"]["has_suspicious_clusters"]:
            print(f"   🔍 反操控标记: {len(entry['suspicious']['suspicious_review_ids'])} 条可疑评价")
        if entry["diverse_opinions"]:
            for do in entry["diverse_opinions"][:2]:
                print(f"   💬 少数派: {do['opinion']} ({do['ratio']*100:.0f}%)")
        print(f"   📈 趋势: {entry['trends']['direction']} | 波动: {entry['trends']['volatility']}")

    # 构建 YAML 结构
    meta = {
        "name": "潮汕美食店铺总览",
        "version": "2.0.0",
        "total_restaurants": len(entries),
        "total_reviews_processed": total_reviews_processed,
        "last_updated": NOW.strftime("%Y-%m-%d"),
        "algorithm_version": "2.0.0",
        "algorithm": {
            "rating_method": "median",
            "time_decay": TIME_DECAY,
            "old_shop_bonus": True,
            "minority_threshold": MINORITY_THRESHOLD,
            "consensus_threshold": 0.60,
            "anti_manipulation": {
                "suspicious_window_days": SUSPICIOUS_WINDOW_DAYS,
                "suspicious_min_reviews": SUSPICIOUS_MIN_REVIEWS,
                "suspicious_action": "flag_not_delete",
            },
        },
    }

    output = {
        "meta": meta,
        "entries": entries,
    }

    # 输出
    if args.dry_run:
        print("\n" + "=" * 60)
        print("📋 预览输出 (--dry-run)")
        print("=" * 60)
        print(yaml.dump(output, allow_unicode=True, default_flow_style=False, sort_keys=False))
    else:
        # 读取原有 YAML 保留 meta 注释和模板注释
        try:
            existing_content = SUMMARY_YAML.read_text(encoding="utf-8")
        except FileNotFoundError:
            existing_content = ""

        # 写文件
        with open(SUMMARY_YAML, "w", encoding="utf-8") as f:
            f.write("# ============================================================\n")
            f.write("# 潮汕美食店铺总览 — 多维聚合画像 (Aggregated Profiles)\n")
            f.write("# ============================================================\n")
            f.write("# 每条记录 = 一家店铺的综合画像\n")
            f.write("# 数据来源：从 reviews.db 通过公平算法自动聚合生成\n")
            f.write("#\n")
            f.write("# 设计理念：\n")
            f.write("#   - 不展示单一排名/排序。排序是针对用户的，因人而异。\n")
            f.write("#   - 展示多维度数据，让用户自己判断。\n")
            f.write("#   - 保留少数派声音（≥15%的观点独立展示）。\n")
            f.write("#   - 反操控检测（短期大量集中打分标记不删除）。\n")
            f.write("#   - 时间衰减加权（越近的评价权重越高）。\n")
            f.write("#\n")
            f.write("# 聚合算法：见 docs/FAIRNESS-ALGORITHM.md\n")
            f.write("# 个性化推荐：见 docs/PERSONALIZATION-ALGORITHM.md\n")
            f.write("# ============================================================\n")
            f.write("\n")
            yaml.dump(output, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
            f.write("\n")

        print(f"\n✅ 聚合完成！已写入 {SUMMARY_YAML}")
        print(f"   店铺: {len(entries)} 家")
        print(f"   评价: {total_reviews_processed} 条")

    return 0


if __name__ == "__main__":
    sys.exit(main())
