# 店铺核验模板 & 闭店记录

> 本文档定义店铺状态核验的标准化流程和闭店记录的写入规范。
> 用于月度深度核验和日常搜索发现。

## 店铺核验流程

### 何时触发核验

```
触发条件                           →  操作
─────────────────────────────────────────────────────
周度搜索中发现某店铺可能变更状态    →  立即核验
某店铺 last_updated > 6个月        →  月度核验优先检查
季度整合中的全量检查               →  系统遍历
用户主动反馈店铺状态变化            →  优先核验
```

### 核验步骤

```
Step 1: 搜索确认
  执行 2-3 个查询：
  web_search("{店铺名} {地区}")
  web_search("{店铺名} 营业 2026")
  web_search("{店铺名} 倒闭 转让")

Step 2: 证据收集
  收集以下信息：
  - 至少 2 个独立来源提到相同结论
  - 提取具体时间点（"上个月还去过""去年就关了"）
  - 记录来源类型（个人评价/新闻/平台状态）

Step 3: 状态判定

  │  正常营业                    可能闭店                     确认闭店
  │  ──────────────────────     ─────────────────────        ─────────────────
  │  多个近期来源提及该店        最近评价>12个月               多个来源确认闭店
  │  有具体日期<3个月            无近期任何提及                地图显示永久关闭
  │  无任何闭店信号              web_search无结果              新闻/社区确认
  │
  │  → 更新 last_verified       → 标记"需复核"               → 执行闭店流程
  │  → 如有新评价则追加          → 下次核验优先                → 移入 closed

Step 4: 记录存档
  无论结果如何，在本次运行报告中记录核验结论。
```

## 闭店记录模板

### closed-restaurants.yaml

```yaml
# ============================================================
# 潮汕美食 — 已闭店记录
# ============================================================
# 记录确认已停止营业的店铺
# 确认标准：至少 2 个独立来源确认闭店
# 保留历史评价数据（不删除 restaurants.yaml 中的原始评价）
# ============================================================

meta:
  name: 潮汕美食已闭店记录
  version: "1.0.0"
  total_closed: 0
  last_updated: "2026-06-08"

entries:
  # --- TEMPLATE: 闭店记录 ---
  # - id: closed-000
  #   restaurant_name: ""
  #   address: ""
  #   district: ""
  #   cuisine_type: ""
  #   confirmed_closed_date: "YYYY-MM-DD"     # 确认闭店的日期
  #   last_known_open: "YYYY-MM-DD"           # 最后确认营业的日期
  #   confirmation_sources:                    # 确认来源，至少2个
  #     - type: web_search
  #       evidence: "搜索到的闭店描述"
  #       date: "YYYY-MM-DD"
  #   status: confirmed_closed                 # confirmed_closed | suspected_closed
  #   note: "备注信息"
```

### 闭店记录示例

```yaml
entries:
  - id: closed-001
    restaurant_name: "示例店（已闭店）"
    address: "汕头市某区某路"
    district: "某区"
    cuisine_type: "牛肉火锅"
    confirmed_closed_date: "2026-05-20"
    last_known_open: "2025-12-15"
    confirmation_sources:
      - type: web_search
        evidence: "多个来源提到已于2026年初转让"
        date: "2026-05-20"
      - type: web_search
        evidence: "大众点评显示'商户已关闭'"
        date: "2026-05-20"
    status: confirmed_closed
    note: "经营4年的老店，因租金上涨闭店"
```

## 执行闭店流程清单

确认闭店后，执行以下操作：

```
□ 1. 追加到 data/closed-restaurants.yaml
□ 2. 在 restaurants.yaml 中：
     - 为该店所有评价添加 tag: [closed]
     - 保留原始评价（不删除，保持数据完整性）
□ 3. 在 restaurant-summary.yaml 中：
     - 标记该店铺为 closed
     - 或直接从 entries 中移除（季度整合时做）
□ 4. 版本号 bump（三个数据文件均需更新）
     - restaurants.yaml: meta.total_reviews?（不变，保留历史）
     - restaurant-summary.yaml: meta.last_updated
     - closed-restaurants.yaml: meta.version +1, total_closed +1
□ 5. rsync 同步源码
□ 6. git commit -m "auto: 闭店 — {店铺名}（{确认时间}）"
□ 7. git push
```

## 争议处理

### 不确定闭店时

当搜索到矛盾信息（有人说开了有人说关了）：
1. 标记为 `suspected_closed` 而不是 `confirmed_closed`
2. 在 closed-restaurants.yaml 中 status 设为 suspected_closed
3. 等待下一次月度核验再确认
4. 不在 restaurants.yaml 中标记 closed

### 疑似闭店但数据宝贵时

如果一家闭店店铺有大量历史评价：
1. 保持 restaurants.yaml 中的原始评价不变
2. 仅在 closed-restaurants.yaml 记录闭店
3. 在 restaurant-summary.yaml 的 summary 末尾备注"该店已于 YYYY-MM 闭店"
4. fair algorithm 计算时 exclude 闭店店铺

### 闭店店铺重开

如果发现之前记录的闭店店铺重新开业：
1. 在 closed-restaurants.yaml 更新记录（添加 re_open 信息）
2. 从 restaurants.yaml 移除 closed 标记
3. 重新加入 restaurant-summary.yaml
4. 在 summary 中注明重开信息
