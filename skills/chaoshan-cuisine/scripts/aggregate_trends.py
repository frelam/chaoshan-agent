#!/usr/bin/env python3
"""
潮汕美食评价数据库 — 趋势聚合脚本

遍历所有有评价的店铺，按月度计算趋势记录并写入 trend_tracking 表。
支持 --dry-run 参数预览变更而不实际写入。

用法：
    python aggregate_trends.py              # 全量聚合（跳过已有周期）
    python aggregate_trends.py --dry-run    # 仅预览，不写入
    python aggregate_trends.py --period-type weekly   # 改为周度聚合
    python aggregate_trends.py --restaurant-id 3      # 仅对某家店聚合
"""

import sys
import os
import argparse
from datetime import datetime, date, timedelta

# 确保可找到 db_helper
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'data'))
from db_helper import get_conn, record_trend


def get_monthly_periods(restaurant_id):
    """获取某家店所有评价的月度周期列表（去重后）"""
    conn = get_conn()
    cursor = conn.execute("""
        SELECT DISTINCT strftime('%Y-%m', visit_date) AS period
        FROM reviews
        WHERE restaurant_id = ? AND visit_date IS NOT NULL
        ORDER BY period
    """, (restaurant_id,))
    periods = [r['period'] for r in cursor.fetchall()]
    conn.close()
    return periods


def get_weekly_periods(restaurant_id):
    """获取某家店所有评价的 ISO 周周期列表（去重后）"""
    conn = get_conn()
    cursor = conn.execute("""
        SELECT DISTINCT visit_date
        FROM reviews
        WHERE restaurant_id = ? AND visit_date IS NOT NULL
        ORDER BY visit_date
    """, (restaurant_id,))
    dates = [r['visit_date'] for r in cursor.fetchall()]
    conn.close()

    periods = set()
    for d in dates:
        dt = datetime.strptime(d, '%Y-%m-%d').date()
        iso_year, iso_week, _ = dt.isocalendar()
        periods.add(f"{iso_year}-W{iso_week:02d}")
    return sorted(periods)


def get_all_restaurant_ids():
    """获取所有有评价记录的店铺 ID"""
    conn = get_conn()
    cursor = conn.execute("""
        SELECT DISTINCT restaurant_id FROM reviews
        ORDER BY restaurant_id
    """)
    ids = [r['restaurant_id'] for r in cursor.fetchall()]
    conn.close()
    return ids


def aggregate(period_type='monthly', dry_run=False, restaurant_id=None):
    """执行趋势聚合"""
    if restaurant_id:
        restaurant_ids = [restaurant_id]
    else:
        restaurant_ids = get_all_restaurant_ids()

    total_restaurants = len(restaurant_ids)
    total_new_records = 0
    total_skipped = 0

    print(f"📊 趋势聚合开始 — 周期类型: {period_type}")
    print(f"   店铺数: {total_restaurants}")
    if dry_run:
        print("   🔍 DRY RUN 模式 — 不会写入任何数据")
    print()

    for idx, rid in enumerate(restaurant_ids, 1):
        conn = get_conn()
        cursor = conn.execute("SELECT name FROM restaurants WHERE id = ?", (rid,))
        row = cursor.fetchone()
        conn.close()
        name = row['name'] if row else f'ID={rid}'

        # 获取该店所有周期
        if period_type == 'monthly':
            periods = get_monthly_periods(rid)
        elif period_type == 'weekly':
            periods = get_weekly_periods(rid)
        else:
            print(f"  ❌ 不支持的周期类型: {period_type}")
            return

        if not periods:
            print(f"  [{idx}/{total_restaurants}] ⏭️  {name} — 无有效 visit_date，跳过")
            continue

        new_count = 0
        skipped_count = 0

        for period in periods:
            if dry_run:
                # 仅检查是否已存在，不写入
                test_conn = get_conn()
                existing = test_conn.execute(
                    "SELECT id FROM trend_tracking WHERE restaurant_id = ? AND period = ?",
                    (rid, period)
                ).fetchone()
                test_conn.close()
                if existing:
                    skipped_count += 1
                else:
                    new_count += 1
            else:
                result = record_trend(rid, period, period_type)
                if result is None:
                    skipped_count += 1
                else:
                    new_count += 1

        total_new_records += new_count
        total_skipped += skipped_count

        status = f"✅ {new_count} 新增" if new_count else ""
        if skipped_count:
            status += f" / ⏭️ {skipped_count} 跳过" if status else f"⏭️ {skipped_count} 跳过"
        print(f"  [{idx}/{total_restaurants}] {'🏪' if new_count else '  '} {name} — {status}")

    print()
    print(f"📋 汇总")
    print(f"   ⏭️  跳过（已有记录）: {total_skipped}")
    if dry_run:
        print(f"   📝 将会新增: {total_new_records} 条记录")
    else:
        print(f"   ✅ 新增: {total_new_records} 条记录")
    print("🎉 聚合完成")


def main():
    parser = argparse.ArgumentParser(
        description="潮汕美食数据库 — 趋势聚合脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='预览模式，不写入数据库'
    )
    parser.add_argument(
        '--period-type', choices=['monthly', 'weekly'], default='monthly',
        help='聚合周期类型（默认: monthly）'
    )
    parser.add_argument(
        '--restaurant-id', type=int, default=None,
        help='仅对指定店铺 ID 聚合'
    )
    args = parser.parse_args()

    aggregate(
        period_type=args.period_type,
        dry_run=args.dry_run,
        restaurant_id=args.restaurant_id
    )


if __name__ == '__main__':
    main()
