# 公平总结算法 (Fairness-Preserving Summarization Algorithm)

> 如何从多条食客评价中，生成一份不偏不倚、保留多元声音的店铺总结。

## 问题定义

给定一家店铺的 N 条食客评价（来自 `restaurants.yaml`），生成一条聚合总结（写入 `restaurant-summary.yaml`），满足以下约束：

1. **不偏不倚**：任何单一评价者或群体不能支配总结结果
2. **声音多元**：少数人的真实意见保留，不被"共识"吞噬
3. **抗操控**：检测并标记疑似刷分行为
4. **时间敏感**：反映店铺的最新状态，老评价适当降权
5. **人群分层**：本地人和游客的口味差异是信息，不是噪音

---

## 核心原则 (Principles)

### 原则 1：中位数代替平均数

**问题**：平均数（mean）对极值敏感。1 个 5 分或 1 个 1 分就能显著扭曲结果。

**方案**：用中位数（median）计算综合评分。

```
评分：3, 4, 4, 4, 5 → mean=4.0, median=4 ✓
评分：3, 4, 4, 4, 5, 5, 5, 5, 5, 5 → mean=4.5, median=5

加入一个极端低分：
评分：1, 4, 4, 4, 5, 5, 5, 5, 5, 5 → mean=4.3, median=5

median 保持 5，mean 降到 4.3。median 更能抵抗操控。
同时保留 quartile 信息：Q1=4, Q3=5 —— 从四分位距可以看出"大多数给 4-5 分，
只有 1 个人给 1 分"。
```

### 原则 2：少数声音保留

**问题**：如果 70% 的人说"好吃"，30% 的人说"太咸"，简单聚合会丢失"太咸"的声音。

**方案**：设置两个阈值——

| 阈值 | 含义 | 处理方式 |
|------|------|---------|
| ≥ 60%（共识阈值） | 多数评价者持有的观点 | 写入 `consensus.pros` 或 `consensus.cons` |
| 15%-60%（少数阈值） | 值得保留的不同声音 | 写入 `diverse_opinions`，标注持有者画像 |
| < 15%（极少数） | 个例/噪音 | 不写入（但仍保留在原始评价中） |

```
例：12 条评价

"汤底鲜美" → 10/12 = 83% → consensus.pros ✓
"牛肉新鲜" → 8/12 = 67%  → consensus.pros ✓
"太咸"     → 3/12 = 25%  → diverse_opinions ✓
"态度不好" → 1/12 = 8%   → 不写入 ✗（但保留在原始评价中）
```

### 原则 3：画像分层统计

**问题**：本地人觉得"正常"的咸淡，游客可能觉得"太淡"或"太咸"。合并统计会丢失这个信息。

**方案**：按 `reviewer.type` 分层：
- `local`：本地人视角（"从小吃到大"的标准）
- `tourist`：游客视角（"第一次吃"的标准，会和外地的对比）
- `returning-visitor`：回头客视角（介于两者之间）

每层独立计算 median rating 和常见关键词，写入 `demographic_breakdown`。

```
demographic_breakdown:
  local:
    count: 5
    median_rating: 4.5
    typical_comment: "水平稳定，和以前一样"
  tourist:
    count: 4
    median_rating: 4.0
    typical_comment: "惊艳！但有点咸"
  returning_visitor:
    count: 3
    median_rating: 4.5
    typical_comment: "每次来汕头都吃"
```

### 原则 4：时间衰减

**问题**：一家店 3 年前的水平和现在可能完全不同（换师傅、换老板、食材供应链变化）。

**方案**：评价权重随时间衰减——

| 评价年龄 | 权重 | 原因 |
|---------|------|------|
| ≤ 1 年 | 1.0 | 反映当前水平 |
| 1-2 年 | 0.8 | 基本可信 |
| 2-3 年 | 0.5 | 参考价值降低 |
| > 3 年 | 0.3 | 可能已过时 |

**例外**：如果店铺标签中有 `老店` 且评价中多次出现"水平稳定""和以前一样"，
3 年以上的评价权重提升至 0.6。

加权后的评分计算：
```
weighted_rating = median(每条评价的 rating × time_weight × reviewer_weight)
```

### 原则 5：评价者可信度

**问题**：不是所有评价者的话语权应该相等。

**方案**：评价者权重系统——

| 条件 | 权重 | 说明 |
|------|------|------|
| 默认 | 1.0 | 每人起点相同 |
| 贡献 ≥ 5 条有实质内容（>50字）的评价 | 1.2 | 经验积累，小幅提升 |
| 被标记为 suspicious_cluster 的评价者 | 0.3 | 疑似刷分者，可信度极低 |
| 单次评价的可信度上限 | 2.0 | 绝对上限——不让任何人支配 |

**重要**：reviewer_weight 永远不能超过 2.0。这是防止"KOL 垄断"的安全阀。

### 原则 6：反操控检测

**问题**：商家或利益相关者可能组织人在短时间内提交大量好评（或给竞争对手差评）。

**方案**：检测以下模式——

```
suspicious_cluster 检测条件（全部满足才标记）：
1. 同一家店，7 天内出现 ≥ 3 条新评价
2. 这些评价的 overall_rating 方差 < 0.3（几乎完全一致）
3. 这些评价的 review_text 有高度相似性（关键形容词重叠率 > 60%）
```

⚠️ 标记而不是删除——可疑评价仍然保留在 `restaurants.yaml` 中，
但在计算聚合统计时降权（weight = 0.3），并在 summary 中标注。

**误判保护**：如果标记的评价者在之后提交了其他店铺的
有实质差异的评价，自动解除标记。

### 原则 7：争议透明

**问题**：当评分方差很大（> 1.5），说明这家店评价两极化——"爱的人超爱，
不喜欢的人完全不喜欢"。这种争议本身是有价值的信息。

**方案**：
```
if rating_variance > 1.5:
    controversy.is_controversial = true
    controversy.note = "评价两极化——{高分人群特征}给了高分，
                        {低分人群特征}给了低分"
    在 summary 开头标注：⚠️ 评价争议较大
```

---

## 算法完整流程

```
ALGORITHM: FairRestaurantSummary(restaurant_id)

INPUT:  restaurant_id — 需要聚合的店铺标识
        restaurants.yaml — 原始评价数据
OUTPUT: 更新 restaurant-summary.yaml 中的对应条目

STEPS:

1. LOAD
   加载 restaurants.yaml 中 restaurant_name 匹配的所有评价
   → reviews[]

2. DEDUP
   移除明显重复的评价（同一 contributor + 同一 visit_date + 高度相似的 review_text）
   → clean_reviews[]

3. ANTI-MANIPULATION
   FOR EACH 7-day window:
       IF ≥3 reviews in window
          AND rating variance < 0.3
          AND text similarity > 60%:
           标记为 suspicious_cluster
           这些评价的 reviewer_weight = 0.3
   → scored_reviews[]（每条评价带 time_weight + reviewer_weight）

4. LAYERED STATISTICS
   a) 全局:
      ratings = [r.overall_rating for r in scored_reviews]
      weighted_ratings = [r.overall_rating × r.time_weight × r.reviewer_weight
                          for r in scored_reviews]
      median = median(ratings)
      weighted_median = weighted_median(weighted_ratings)
      variance = variance(ratings)
      Q1, Q3 = quartiles(ratings)
      distribution = {1: count, 2: count, 3: count, 4: count, 5: count}

   b) 分层 (group by reviewer.type):
      FOR EACH group in [local, tourist, returning-visitor]:
          group_median = median(group.reviews.ratings)
          group_count = len(group.reviews)

5. OPINION EXTRACTION
   从 review_text 和各 dish comment 中提取观点关键词

   a) 自动提取：
      - 好评关键词（出现在 rating ≥ 4 的评价中）
      - 差评关键词（出现在 rating ≤ 2 的评价中）
      - 使用简单的 N-gram 频率统计

   b) 共识判定：
      FOR EACH opinion keyword:
          frequency = count(opinion) / total_reviews
          IF frequency >= 0.60:
              ADD to consensus
          ELIF frequency >= 0.15:
              ADD to diverse_opinions (with count + ratio + held_by)

6. CONTROVERSY CHECK
    IF variance > 1.5:
        controversy = true
        分析高分群和低分群的 reviewer 特征差异

7. SUSPICIOUS SUMMARY
    IF suspicious_clusters detected:
        记录被标记的评价 ID 列表

8. GENERATE SUMMARY
    基于以上所有数据，用 AI 生成 ≤200 字的中文总结。
    总结要求：
    - 第一句：整体评价（"X人评价，中位评分X分"）
    - 如有争议："评价两极分化——……"
    - 必点菜品
    - 人群差异（如有）
    - 如有可疑评价：标注"suspicious"

9. WRITE
    将生成的结果写入 restaurant-summary.yaml

10. RETURN
    返回生成结果供 SKILL.md 的 AI 使用
```

---

## 参数可调表

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `consensus_threshold` | 0.60 | 共识判定阈值 |
| `minority_threshold` | 0.15 | 少数声音保留阈值 |
| `controversy_variance` | 1.5 | 争议判定方差阈值 |
| `suspicious_window_days` | 7 | 刷分检测时间窗口 |
| `suspicious_min_reviews` | 3 | 刷分判定最低评价数 |
| `suspicious_similarity` | 0.60 | 刷分文本相似度阈值 |
| `time_weights` | [1.0, 0.8, 0.5, 0.3] | 时间衰减权重（≤1y, 1-2y, 2-3y, >3y）|
| `max_reviewer_weight` | 2.0 | 单条评价权重上限 |
| `min_reviewer_weight` | 0.1 | 被标记评价的最低权重 |
| `credible_review_count` | 5 | 获得可信度加成的评价数阈值 |
| `credible_review_bonus` | 1.2 | 可信评价者权重加成 |

---

## 手动覆盖机制

公平算法生成的是**推荐总结**，不强制。如果人类维护者认为算法的总结
有偏差，可以手动编辑 `restaurant-summary.yaml` 中的对应条目，
并在 `overall` 中添加 `manually_adjusted: true` 和调整说明。

下次算法运行时，如果发现有 `manually_adjusted: true` 标记，
跳过该条目（尊重人工判断）。

---

## 演算示例

### 输入：8 条评价

| # | 评分 | reviewer | 时间 | 关键词 |
|---|------|----------|------|--------|
| 1 | 5 | local | 2月前 | 脖仁好,汤底鲜,牛肉新鲜 |
| 2 | 5 | local | 1月前 | 吊龙嫩,环境一般,排队久 |
| 3 | 4 | tourist | 3月前 | 好吃但太咸,服务一般 |
| 4 | 4 | tourist | 1月前 | 第一次吃,惊艳,有点咸 |
| 5 | 4 | local | 6月前 | 稳定,性价比高,人多 |
| 6 | 3 | tourist | 2年前 | 不如预期的好吃,咸 |
| 7 | 5 | local | 1月前 | 汕头第一,每次来都吃 |
| 8 | 5 | tourist | 2月前 | 最好吃的牛肉火锅 |

### 步骤

**1. 评分统计**
```
ratings = [5, 5, 4, 4, 4, 3, 5, 5]
median = 4.5  (排序: 3,4,4,4,5,5,5,5 → 中间两个 4 和 5 → 4.5)
mean = 4.375
Q1 = 4, Q3 = 5
variance ≈ 0.55
distribution = {1:0, 2:0, 3:1, 4:3, 5:4}
```

**2. 时间衰减**
```
#6 (2年前, weight=0.5): weighted rating = 3 × 0.5 = 1.5 (等价贡献)
其他 7 条都在 1 年内, weight=1.0
```

**3. 分层统计**
```
local: 4条, median=5.0
tourist: 4条, median=4.0  (2个4分, 1个3分, 1个5分)
```

**4. 观点提取**
```
"汤底鲜"/"牛肉新鲜" → 5/8=62.5% → consensus.pros ✓
"排队久"/"人多" → 4/8=50% → diverse_opinions
"太咸" → 3/8=37.5% → diverse_opinions (held_by: [tourist])
"服务一般" → 2/8=25% → diverse_opinions
"环境一般" → 2/8=25% → diverse_opinions
```

**5. 争议检查**
```
variance = 0.55 → < 1.5 → 不触发争议
```

**6. 生成总结**
```
⭐ 综合评分：4.5/5（8人评价，分布：3分×1, 4分×3, 5分×4）
🥩 必点：脖仁、吊龙
👍 共识：汤底鲜、牛肉新鲜
👎 差评：无普遍差评
💬 多元声音：
  - 3/8人觉得"太咸"（全部是游客）→ 游客可能要提醒少蘸沙茶
  - 4/8人提到"排队久/人多" → 高峰时段建议错峰
📊 人群差异：本地人评分(5.0) > 游客评分(4.0)
📝 总结：8位食客综合评分4.5。本地人评价一致高分(5.0)，游客评分(4.0)
         略低，主要意见是"偏咸"。汤底和牛肉新鲜度是公认亮点。排队是可
         预期的问题——高峰期建议错峰或做好心理准备。
```

---

---

## 版本历史

每次多Agent公平算法挑战赛（每周四）后，如有 Valid Bug 被确认并修复，在此记录算法变更。

> **版本号起点说明**：当前版本从 2.0.0 起计。版本 1.x 系列为早期内部迭代版本（未公开的草案），
> 2.0.0 是首个包含完整 7 项原则定义、算法流程、参数可调表和演算示例的公开基准版本。

| 版本 | 日期 | 变更类型 | 变更内容 | 挑战来源 | 详情 |
|------|------|---------|---------|---------|------|
| 2.0.0 | 2026-06-05 | 初始 | 算法初始版本（7项原则完整定义 + 算法流程 + 参数可调表 + 演算示例） | — | 首个公开基准版本，见本文档全部内容 |

### 版本号规则

```
版本号格式: X.Y.Z

X — 主版本：算法核心原则发生根本性变更（如评分方法从 mean 改为 median）
Y — 次版本：新增原则或参数可调表新增/变更关键参数
Z — 补丁版本：参数值微调、文档澄清、边缘案例处理规则补充
```

### 变更记录格式

每次算法变更记录包含：
- **变更前行为**：旧参数/规则下的行为
- **变更后行为**：新参数/规则下的行为
- **挑战详情**：哪个角色在哪个挑战中发现了问题，辩论摘要
- **影响评估**：对已有 restaurant-summary.yaml 中聚合结果的影响
- **回滚方案**：如果变更导致意外后果，如何回滚

### 待解决问题（Open Issues）

以下问题在挑战赛中被标记为 Edge Case，尚未解决，留待后续挑战赛继续探讨：

（暂无）

---

## 贡献者指南

### 如何写一条好评价

**✅ 好的评价：**
> "脖仁的雪花纹理漂亮，涮8秒刚好入口即化。吊龙今天的切工一般，有几片
> 稍厚影响口感。胸口朥涮了4分钟，脆爽弹牙完全不腻。整体4.5分——
> 扣0.5是因为周末排队40分钟太久了。"

特点：
- 具体到菜品的口感描述（不是"好吃"而是"入口即化"）
- 提到了不足（切工、排队）
- 有对比（今天 vs 以前）
- 给出了评分的理由

**❌ 不好的评价：**
> "超级好吃！！！汕头天花板！！！必须来！！！！！"

问题：
- 没有具体信息（什么好吃？为什么好吃？）
- 使用营销话术（"天花板"）
- 没有评分的理由
- 对其他人没有参考价值

### 评价的黄金法则

1. **具体 > 抽象**："脖仁入口即化" > "很好吃"
2. **有坏说坏**：诚实指出不足，没什么好怕的
3. **对比有价值**："比XX店的好"或"不如XX店"都有参考意义
4. **标注身份**：说明自己是本地人/游客/回头客，帮助读者理解你的口味基准
5. **拍照加分**：菜品照片比文字更直观（但这不是必选项）
