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

**方案**：评价权重随时间连续衰减——使用指数衰减函数替代离散阶梯。

```
# 指数时间衰减函数
λ = time_decay_rate  # 衰减率，按店铺类型动态调整
time_weight = exp(-λ × years_since_review)

# 默认 λ 值
默认λ_for_all: 0.3       # 一般店铺，半衰期约2.3年
网红/连锁店λ: 0.7        # 半衰期约1年，口味和品质变化快
稳定老店λ: 0.15          # 半衰期约4.6年，口味稳定
```

| 店铺类型 | λ值 | 半衰期 | 1年后权重 | 3年后权重 |
|---------|-----|--------|----------|----------|
| 网红/连锁店 | 0.7 | ~1年 | 0.50 | 0.12 |
| 一般店铺 | 0.3 | ~2.3年 | 0.74 | 0.41 |
| 稳定老店 | 0.15 | ~4.6年 | 0.86 | 0.64 |

**语义匹配的老店例外规则**：不再机械匹配关键词"水平稳定""和以前一样"。
改为同义语义簇匹配，涵盖但不限于：

```
语义簇「水平稳定」包含：
  "水平稳定"、"和以前一样"、"味道还是那个味"、
  "三十年不变"、"保持水准"、"火候一直稳"、
  "从我爸那辈就在这吃"、"从小吃到大，味道没变"、
  "一直没有让人失望"、"品质如一"
```

匹配到语义簇中任意表述的评价，其 time_weight 衰减上限提升至 **0.7**。

**纵贯对比评价加权**：同一 review 对同一家店有跨越 ≥2 年的多次评价时，
该 reviewer 在该店的评价额外获得 +0.2 的纵贯权重加成（不超过 max_reviewer_weight 2.0 上限）。

```
# 加权中位数计算中的总权重：
weight_i = time_weight_i × reviewer_weight_i  # 基础权重
if 纵贯对比评价:            # 评价文本包含时间对比关键词
    weight_i = min(weight_i × 1.2, max_reviewer_weight)
if 同店铺纵贯评价:           # 同一reviewer对同一店≥2年有多次评价
    weight_i = min(weight_i + 0.2, max_reviewer_weight)
```

加权后的评分计算：
```
# 标准化加权中位数（Standard Weighted Median）
# 正确做法：按评分排序，累计权重达到总权重50%时对应的评分值
weights = [r.time_weight × r.reviewer_weight for r in scored_reviews]
ratings_sorted = sorted(zip([r.overall_rating for r in scored_reviews], weights),
                       key=lambda x: x[0])
total_weight = sum(weights)
cumulative = 0
for rating, w in ratings_sorted:
    cumulative += w
    if cumulative >= 0.5 × total_weight:
        weighted_median = rating
        break

# 同时计算加权四分位数
weighted_Q1 = 累计权重达25%时的评分值
weighted_Q3 = 累计权重达75%时的评分值
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

**方案**：三层反操控检测系统——

### 第1层：滑动窗口检测（替代固定7天窗口）

```
suspicious_cluster 检测条件（满足**任意2条**即可触发标记）：

1. 滑动窗口：使用步长1天的重叠式7天滑动窗口检测
   任意窗口内出现 ≥ 3 条新评价（消除边界规避）

2. 方差基线偏离（替代硬阈值 < 0.3）：
   计算该店铺全部评价的历史评分方差 baseline_variance
   计算滑动窗口内评价的方差 window_variance
   IF window_variance < baseline_variance × 0.5:
       标记为 suspicious（评分一致性异常偏低）

3. 文本重叠模式检测（替代硬阈值 > 60%）：
   比较窗口内评价的关键形容词集合
   使用 Jaccard 相似度检测异常重叠
   IF 窗口内平均文本相似度 > 店铺历史基线 + 2σ:
       标记为 suspicious
```

### 第2层：行为模式分析（非隐私方式）

```
4. 提交间隔模式检测：
   检测固定时间间隔（如恰好每48小时）提交的模式
   IF 间隔标准差 < 2 小时: 标记为 suspicious

5. 小团体重合度检测：
   检测一组评价者在多个店铺间以相同组合出现
   使用二部图的模块度检测
```

### 第3层：误判保护与二次标记

```
三重误判保护：

- 正常解除标记：被标记的评价者后续提交3条有实质差异的
  其他店铺评价后，自动解除第1层标记
- 二次标记永久化：解除标记后再次被标记的，触发永久标记
  （权重 0.1，不可解除）
- 申诉通道：店铺或评价者可通过 GitHub Issue 提交申诉，
  人工复核后恢复权重
```

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
   FOR EACH 7-day sliding window (步长1天):
       window_reviews = (window内所有评价)
       IF len(window_reviews) ≥ 3:
           check_count = True
           check_variance = window_variance < baseline_variance × 0.5
           check_text = window_text_similarity > baseline + 2σ
           IF sum([check_count, check_variance, check_text]) >= 2:
               标记为 suspicious_cluster
               这些评价的 reviewer_weight = 0.3
   # 第2层：行为模式检测（同上）
   # 第3层：二次标记永久化（权重 0.1）
   → scored_reviews[]（每条评价带 time_weight + reviewer_weight）

4. LAYERED STATISTICS
   a) 全局:
      ratings = [r.overall_rating for r in scored_reviews]
      # 标准化加权中位数：按评分排序，累计权重达50%时对应的评分值
      weights = [r.time_weight × r.reviewer_weight for r in scored_reviews]
      weighted_median = weighted_median_corrected(ratings, weights)
      # 同时计算加权四分位数
      weighted_Q1 = weighted_percentile(ratings, weights, 0.25)
      weighted_Q3 = weighted_percentile(ratings, weights, 0.75)
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

||| 参数 | 默认值 | 说明 |
|||------|--------|------|
||| `consensus_threshold` | 0.60 | 共识判定阈值 |
||| `minority_threshold` | 0.15 | 少数声音保留阈值 |
||| `controversy_variance` | 1.5 | 争议判定方差阈值 |
||| `time_decay_rate_default` | 0.3 | 一般店铺时间衰减率λ（指数衰减函数） |
||| `time_decay_rate_trendy` | 0.7 | 网红/连锁店衰减率λ（半衰期约1年） |
||| `time_decay_rate_stable` | 0.15 | 稳定老店衰减率λ（半衰期约4.6年） |
||| `longitudinal_bonus` | 0.2 | 纵贯对比评价额外权重加成 |
||| `old_shop_semantic_cluster` | true | 是否启用老店同义语义簇匹配 |
||| `suspicious_window_days` | 7 | 刷分检测滑动窗口（步长1天） |
||| `suspicious_min_reviews` | 3 | 刷分判定最低评价数 |
||| `suspicious_condition_trigger` | 2 | 任意N条条件满足即触发（原AND逻辑） |
||| `variance_baseline_ratio` | 0.5 | 窗口方差 < 历史基线 × 此值触发标记 |
||| `similarity_baseline_sigma` | 2 | 文本相似度 > 基线 + N×σ 触发标记 |
||| `max_reviewer_weight` | 2.0 | 单条评价权重上限 |
||| `min_reviewer_weight` | 0.3 | 第1层标记评价的最低权重 |
||| `permanent_min_weight` | 0.1 | 二次标记永久化的最低权重 |
||| `credible_review_count` | 3 | 获得可信度加成的评价数阈值（从5降至3） |
||| `credible_review_bonus` | 1.15 | 可信评价者权重加成（从1.2降至1.15，平衡营销风险） |
||| `deep_review_bonus` | 1.05 | 单条深度评价加成（>100字+具体菜品描述，新参数） |
||| `max_weight_decay_ratio` | 0.3 | 最终权重不低于原生time_weight×此值（新参数，CH-05/第2轮） |
||| `season_relevance_decay` | 0.5 | 反季评价额外衰减系数（新参数，CH-08/第2轮） |
||| `cold_start_protection` | true | 前20条评价启用固定阈值保护（新参数，CH-06/第2轮） |
||| `density_detection_days` | 30 | 累计评价密度检测周期（天，新参数，CH-07/第2轮） |
||| `density_detection_threshold` | 6 | 密度检测周期内超过此值触发关注（新参数，CH-07/第2轮） |
||| `tourist_group_exemption` | true | 旅行团群体行为豁免（新参数，CH-04/第2轮） |
||| `information_value_weighting` | true | 是否启用信息价值加权共识（新参数，CH-02/第2轮） |
||| `flavor_baseline_detection` | true | 是否启用风味基准面跨菜系感知检测（新参数，CH-01/第2轮） |
||| `complaint_sla_hours` | 48 | 申诉确认时限（新参数，CH-10/第2轮） |
||| `complaint_review_days` | 7 | 人工复核完成时限（新参数，CH-10/第2轮） |
|| `density_threshold_inclusive` | true | 密度检测阈值是否包含等于（CH-04/第3轮，新参数） |
|| `max_tourist_group_window` | 15 | 旅游团豁免单窗口最大条数（CH-05/第3轮，新参数） |
|| `cold_start_disable_tourist_exemption` | true | 冷启动期间禁用旅游团豁免（CH-05/第3轮，新参数） |
|| `post_hoc_tourist_verification` | true | 旅游团豁免事后验证（CH-05/第3轮，新参数） |
|| `holiday_cluster_exemption` | true | 节日本地人集中评价豁免（CH-09/第3轮，新参数） |
|| `age_group_schema` | 18-25/26-35/36-50/51+ | 代际分段统一为四段（CH-08/第3轮，调整） |
|| `cultural_semantic_detection` | true | 文化语义簇识别（CULTURAL_SEMANTIC_CLUSTER）（CH-11/第3轮，新参数） |
|| `cultural_semantic_bonus` | 1.5 | 文化语义信息价值额外加分（CH-11/第3轮，新参数） |
|| `small_sample_confidence` | true | 是否展示小样本置信度（CH-07/第3轮，新参数） |
|| `queue_crowd_note` | true | 是否在summary中生成客流提示（CH-10/第3轮，新参数） |
|| `holiday_adjusted_rating` | false | 是否计算节假日调整评分（CH-10/第3轮，默认关闭，新参数） |
|| `implementation_alignment_check` | true | 每次聚合前检查文档vs代码参数一致性（CH-01/第3轮，新参数） |
|| `interaction_audit_enabled` | false | 是否启用权重链交互效应审计（CH-02/第3轮，默认为审计模式，新参数） |

---

## v2.2.0 新增机制（第2轮挑战赛）

以下机制为第2轮多Agent挑战赛确认的10个Valid Bug修复方案。详细讨论见 `challenge-002-2026-06-25.md`。

### 加权衰减下限保护（`max_weight_decay_ratio`）

```
# 在 individual weight 计算末尾加入下限保护
final_weight_i = max(
    raw_weight_i,  # time_weight_i × reviewer_weight_i
    base_time_weight_i × max_weight_decay_ratio  # 下限保护
)

# 其中 base_time_weight_i 是该评价的纯时间衰减权重（不含 reviewer_weight 降权）
# max_weight_decay_ratio = 0.3 保证无降权时的70%权重不会被标记完全吞噬
```

**目的**：防止非标记因素（时间衰减）与标记降权（reviewer_weight=0.3）连乘后产生过度惩罚，同时避免 `min_reviewer_weight` 参数的反向提权效应。

### 时令感知时间衰减（`season_relevance_decay`）

```
IF 评价包含时令相关食材关键词（薄壳/羊肉炉/春菜/冬笋等）：
    season_of_review = extract_season(review_text)
    current_season = get_current_season()
    IF season_of_review != current_season:
        time_weight = time_weight × season_relevance_decay  # 系数0.5
    # 同季评价不受此影响
ELSE:
    time_weight = time_weight  # 保持现有逻辑不变
```

**目的**：解决时令食材评价的跨季参考价值衰减问题，使专精时令食材的店铺获得更准确的评分。

### 信息价值加权共识（`information_value_weighting`）

在共识判定步骤（算法步骤5b）中，将纯频率判据改为信息价值加权频率：

```
def information_value(review_text):
    score = 1.0  # baseline
    if has_specific_dish(text):           # 提及具体菜品/部位
        score += 0.5
    if has_technical_term(text):           # 火候/切工/筋太多等专业词汇
        score += 0.8
    if has_comparison(text):               # "比XX店好/差"
        score += 0.5
    if has_specific_negative(text):        # 具体差评（非泛泛而谈）
        score += 0.7
    if is_vague_praise(text):              # "好吃""超棒"等
        score *= 0.6  # 降权
    return min(score, 3.0)

effective_frequency = sum(information_value(r) for r in reviews_with_opinion) / sum(information_value(r) for r in all_reviews)
IF effective_frequency >= consensus_threshold:
    进入 consensus
ELIF effective_frequency >= minority_threshold:
    进入 diverse_opinions
```

**目的**：防止泛泛好评（"汤底鲜"）霸占共识，增加专业判断（"火候控制不稳定"）的影响力。

### 风味基准面检测（`flavor_baseline_detection`）

```
IF 评价包含跨菜系口味偏差关键词（"太咸""太淡""太油"等）：
    baseline_salt = cuisine_type 的风味基准面（如潮汕菜: salt=high）
    reviewer_hometown = reviewer.hometown
    IF (reviewer.type == tourist AND reviewer_hometown != "潮汕"):
        # 统计显著性检验：该评价者所在群体对该品类的该关键词频率
        IF frequency(tourist, "太咸", 潮汕菜) >> frequency(local, "太咸", 潮汕菜):
            标记为 cross_cuisine_perception
            不进入 consensus.cons
            进入 cuisine_perception_notes（与 summary 关联展示）
    IF (reviewer.type == local OR reviewer.hometown in 潮汕地区):
        "太咸" → 正常进入 opinion extraction（可能反映真实出品问题）
```

**目的**：区分跨菜系口味适应偏差和真实出品问题，保护正宗本土口味不受系统性降分。

### 累计密度检测（`density_detection_days` / `density_detection_threshold`）

```
# 在滑动窗口检测之外，新增累计密度检测层
60/30天内同一家店的评价总数统计
IF 30天内评价总数 > density_detection_threshold (6):
    即使每个7天窗口都<3条，也触发关注
    进入方差和文本重叠检查
```

**目的**：堵住"缓慢渗透"攻击（每8-10天2条，总窗口<3条绕过的漏洞）。

### 冷启动保护（`cold_start_protection`）

```
IF 店铺评价总数 < 20 OR 开店时间 < 30天:
    # 新店冷启动期间采用更严格的临时标准
    FOR EACH 滑动窗口:
        IF len(window_reviews) >= 3:
            # 条件2：使用固定阈值替代 baseline 比较
            check_variance = window_variance < 0.05  # 固定阈值
            # 条件3：使用固定 Jaccard 阈值替代 baseline+2σ
            check_text = window_avg_jaccard > 0.40  # 固定阈值
            IF sum([True, check_variance, check_text]) >= 2:
                标记为 suspicious_cluster
```

**目的**：解决新店 baseline_variance=0 导致条件2永不可触发的问题。

### 旅行团群体豁免（`tourist_group_exemption`）

```
# 在滑动窗口检测中增加排除条件
IF 窗口内评价者满足以下条件：
    1. 评价者 hometown 分布在 ≥ 3 个不同城市
    2. 评价者.type 包含 tourist（或全部为 tourist）
    3. 评价中包含旅游语境关键词（"跟团""导游""旅行""第一次来"等）
THEN:
    不触发 suspicious_cluster 标记
    改为标记为 "tourist_group"（仅记录，不影响权重）
```

**目的**：防止合法旅行团的集中评价被误判为刷分簇。

### 信誉度评价双通道

```
# 原 credible_review_count=5 → 改为 3
# 新增单条深度评价通道：
IF 单条评价 > 100字 AND 包含 ≥ 2 个具体菜品名称 AND 包含口感描述:
    该条评价获得 deep_review_bonus = 1.05× 权重加成
    （不依赖累计数量，一次性游客也能获得）
# 综合评价者权重：
reviewer_weight = min(1.0 + credible_bonus + deep_bonuses, max_reviewer_weight)
其中 credible_bonus = (credible_review_count >= 3) ? (credible_review_bonus - 1.0) : 0
     deep_bonuses = sum(deep_review_bonus - 1.0 for each deep review)
```

**目的**：在保持抗营销门槛的同时，给一次性游客的深度评价合理权重。

### 申诉通道 SLA

```
申诉通道（GitHub Issue）处理标准：
1. 确认收件：提交后 48 小时内（complaint_sla_hours）自动回复确认收件
2. 人工复核：确认收件后 7 个工作日内（complaint_review_days）完成复核
3. 复核标准：
   a) 申诉人提供到店证明（支付记录/照片/定位记录）
   b) 评价为本人真实体验
   c) 无证据表明参与组织化评价操控
4. 复核结果通知：通过 GitHub Issue 评论通知申诉人
5. 重审权：首次申诉被驳回后，可在 30 天后申请重审（需提供新证据）
```

**目的**：为申诉通道提供可执行的时间标准和流程规范，避免黑箱。

### 代际与文化坐标系统

```python
# 新增 reviewer 可选字段（v2.3.0 统一为四段）
reviewer:
  age_group: "18-25" | "26-35" | "36-50" | "51+"  # optional，四段统一
  cultural_context: local | diaspora | tourist | returning_visitor  # 扩展原 type
  diaspora_departure_year: 1995  # optional，仅 diaspora 填写

# 分层统计增加 by_age_group 维度（仅当数据充足时激活）
# 当某层样本数 < 3 时，不展示该层 median_rating
# 代际差异检测：如果同店铺 by_age_group 的中位数差 > 1.0，
# 标记 "intergenerational_divergence: true"
```

**目的**：解决 local 单层分类抹杀代际口味代沟的问题。支持渐进式扩展——字段可选，有数据后自动激活。

---

## v2.3.0 新增机制（第3轮挑战赛）

以下机制为第3轮多Agent挑战赛确认的11个Valid Bug修复方案。详细讨论见 `challenge-003-2026-07-02.md`。

### 文化语义簇识别（`cultural_semantic_detection` / `cultural_semantic_bonus`）

```python
# 在 information_value() 函数中新增分支
CULTURAL_SEMANTIC_CLUSTER = {
    "祭祀": ["拜老爷", "拜祖", "祭祖", "老爷饭", "上供", "拜神"],
    "家传": ["阿嬷做", "阿妈做", "外婆做", "老姆做", "婶姆做"],
    "合礼": ["有礼数", "合礼", "有规矩", "老传统", "传统做法"],
    "手工": ["手工做", "手拍", "手打", "手搓", "现做"],
}

if has_cultural_semantic(text):
    score += cultural_semantic_bonus  # +1.5
    # 不进入 is_vague_praise ×0.6 分支
```

**目的**：修复文化语义盲区（CH-11），防止「适合拜老爷」「阿嬷做」等潮汕高信息密度评价被 `is_vague_praise` 误判降权。

### 代际分段统一（`age_group_schema`）

`age_group` 字段统一为四段 `18-25 / 26-35 / 36-50 / 51+`，与 `restaurants.yaml` 和 `reviewer-profiles.yaml` 一致。

原三段 `18-30 / 31-50 / 51+` 被废弃。新增的 **26-35** 段可捕捉潮汕「油脂优先→鲜嫩优先」口味转型期的关键代际信号。

### Diaspora 文化坐标操作化

```python
IF cultural_context == "diaspora" AND diaspora_departure_year < 2010:
    # 口味冻结在传统时代——标记感知偏差
    "太淡" / "不够香" / "不够味" → diaspora_frozen_perception
    不进入 consensus.cons
    进入 diaspora_perspective_notes
```

**目的**：修复 diaspora 操作化真空（CH-08），为外迁潮汕人提供正确的评价处理路径。

### 密度检测阈值包含等于（`density_threshold_inclusive`）

```python
# 原：density_detection_threshold = 6，条件为 >6
# 改为：density_detection_threshold = 6，条件为 >=6（当 density_threshold_inclusive=true）
IF 30天内评价总数 >= density_detection_threshold:
    触发方差和文本重叠检查

# 同时使用滑动窗口替代固定日历月
# 新增均匀渗透检测：30天内6条且每条间隔δ<7天时标记为"均匀渗透"
```

**目的**：修复密度检测阈值边界绕过（CH-04—M-1），防止恰好6条永不触发的漏洞。

### 旅行团豁免加固

```python
# 新增限制条件
IF len(window) > max_tourist_group_window (15):  # 单窗口上限
    超出部分正常触发 suspicious 检测

IF cold_start_disable_tourist_exemption:
    # 冷启动期间（前20条/30天）不触发旅行团豁免

# 事后验证（post_hoc_tourist_verification）
标记为 tourist_group 的评价，7天后检查：
    IF 这些账号再无任何其他评价（真实旅行团会评价其他店）:
        自动转为 suspicious_cluster
```

**目的**：修复旅行团豁免自声明零验证漏洞（CH-05—M-2），防止大规模集中渗透。

### 节日本地人豁免（`holiday_cluster_exemption`）

```python
IF 窗口内评价者全部为 local type AND window_variance == 0:
    skip check_variance  # all_local + 全5分不触发方差条件

# 可选增强：在春节/国庆期间（节前7天至节后7天）
# sliding_window.suspicious_min_reviews 临时提升至 6
```

**目的**：修复春节/长假本地人社群误伤（CH-09），保护最有价值的本地确认性评价不被反操控系统标记。

### 风味基准面召回机制

```python
# 在 flavor_baseline_detection 中增加负面反馈回路
IF 某店铺的 tourist 群体持续（≥6个月，≥15条）对同一维度（如"太咸"）提出批评:
    自动升级为 quality_warning
    提示可能的出品退化趋势，无论统计显著性检验结果

# 差评强度阈值区分
IF 评价包含极端口味描述（"咸到不能吃"、"齁咸"等）:
    不进入 cross_cuisine_perception
    正常进入 opinion extraction（视为可能的出品问题）

# local confirm 条件
IF local 群体中无人显式确认口味正常（"咸淡适中""味道刚好"）:
    即使 tourist 频率 > local，也不触发 cross_cuisine_perception
    改为进入 diverse_opinions（标注 cross_cuisine_note）
```

**目的**：修复风味基准面过度排除游客真实差评（CH-06—T-1），防止"修复后新漏洞"过滤掉真实的质量退化信号。

### 小样本置信度量化（`small_sample_confidence`）

```python
# 在 rating_overview 中新增字段
confidence_95_ci: [2.8, 4.8]  # Bootstrap 或 Bayesian 方法
small_sample_warning: true     # N<5 时标记

# 评分量级标注
if count < 5:
    note = "⚠️ 评价数较少（仅N条），评分可能存在统计波动"
elif count < 20:
    note = "📊 N人评价，评分有一定参考价值"
else:
    note = "✅ N人评价，评分数据充足"
```

**目的**：量化小样本评分的不确定性（CH-07—D-1），避免 N=1 的评分被当做可靠估计。

### 客流提示与季节性感知（`queue_crowd_note` / `holiday_adjusted_rating`）

```python
# 在 demographic_breakdown 中增加客流提示
IF 店铺有排队标签 AND |local.median - tourist.median| > 1.0:
    summary 追加提示：
    "游客评分偏低可能与节假日客流高峰有关，建议参考平日评价"

# 可选：holiday_adjusted_rating（默认关闭）
IF holiday_adjusted_rating AND 数据充足（≥10条节假日评价）:
    在 demographic_breakdown 中同时展示"平日评分"和"节假日评分"
```

**目的**：修复客流拥堵导致游客评分系统性偏低（CH-10—T-2），帮助用户正确理解 demographic_breakdown 差异的归因。

### 权重链交互效应审计（`interaction_audit_enabled`）

```python
IF interaction_audit_enabled:
    FOR EACH 评价:
        追踪全路径影响力指数——从 raw_weight 到最终可见性
        输出：原始权重 → time_decay后 → reviewer_weight后 → season_decay后 →
              max_weight_decay_ratio后的可见性级别(consensus/diverse/note/丢弃)
```

**目的**：审计多重权重链的级联效应（CH-02—L-1+A-2），揭示边缘评价者的锥形崩塌路径。默认为审计模式（false），仅在审计运行时启用。

### 文档-代码对齐检查（`implementation_alignment_check`）

```python
# 每次聚合运行前的预检查
FROM FAIRNESS-ALGORITHM.md 参数可调表:
    提取所有参数名列表 → doc_params[]
FROM run_aggregation.py 源代码:
    grep 搜索每个参数名 → code_found_params[]
差异列表 = doc_params - code_found_params
IF 差异列表非空:
    输出 WARNING: "以下参数在文档中定义但未在代码中实现：{差异列表}"
    建议在聚合运行前优先对齐
```

**目的**：防止文档-代码再次脱节（CH-01—A-1），确保每轮挑战赛的修复方案真正落实到代码层面。

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

|| 版本 | 日期 | 变更类型 | 变更内容 | 挑战来源 | 详情 |
||------|------|---------|---------|---------|------|
|| 2.0.0 | 2026-06-05 | 初始 | 算法初始版本（7项原则完整定义 + 算法流程 + 参数可调表 + 演算示例） | — | 首个公开基准版本，见本文档全部内容 |
|| 2.1.0 | 2026-06-18 | 多原则修复 | 修复3个Valid Bug：①加权中位数数学定义修正 ②时间衰减改为连续指数衰减+语义匹配 ③反操控改为三层检测系统(滑动窗口+基线偏离+二次标记永久化) | 数据科学家, 公平性审计员, 本地老饕, 营销号操盘手 | 第1轮多Agent挑战赛，见 challenge-001-2026-06-18.md |
||| 2.2.0 | 2026-06-25 | 全原则增强 | 修复10个Valid Bug：①新增max_weight_decay_ratio参数 ②修复Jaccard+2σ正态假设+B细节校正 ③计数阈值无累计密度检测 ④风味基准面+跨菜系感知标注 ⑤时令感知时间衰减 ⑥代际分层+文化坐标系统 ⑦游客群体误判保护 ⑧信息价值加权共识 ⑨旅游团豁免 ⑩申诉通道SLA | 全部6个角色 | 第2轮多Agent挑战赛，见 challenge-002-2026-06-25.md |
||| 2.3.0 | 2026-07-02 | 全原则增强 + 结构性修复 | 修复11个Valid Bug：①文档-代码对齐检查 ②权重链交互效应审计 ③多重比较校正补全 ④密度检测阈值包含等于 ⑤旅行团豁免加固 ⑥风味基准面召回机制 ⑦小样本置信度量化 ⑧代际分段统一+Diaspora操作化 ⑨节日本地人豁免 ⑩客流提示与季节性感知 ⑪文化语义簇识别 | 全部6个角色 | 第3轮多Agent挑战赛，见 challenge-003-2026-07-02.md |

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

|| 编号 | 问题 | 提出者 | 投票结果 | 说明 | 状态 |
||------|------|--------|---------|------|------|
|| EI-01 | credible_review_count=5 对一次性游客歧视 | 外地游客 🧳 | 第1轮->Edge Case；第2轮->4/6同意->Valid Bug | 修复：改为计数+单条深度评价双通道，已合入v2.2.0 | 已修复 |
||| EI-02 | 缺失环境/服务/排队/价格结构化维度 | 外地游客 🧳 | 2同意/0反对/0弃权->Edge Case；第3轮->升级讨论（CH-10部分覆盖） | 方向正确但实现复杂、有光环效应、增加攻击面。CH-10（客流提示queue_crowd_note）作为渐进式实现的第一步，已合入v2.3.0 | 仍为Edge Case，部分缓解 |
||| EI-03 | 60%共识阈值+15%少数阈值构成多数暴政 | 本地老饕 🧓 | 2同意/0反对/0弃权->Edge Case | 与CH-02信息价值加权共识部分重叠，已通过信息价值加权机制缓解 | 降级为观察 |
||| EI-06 | Bayesian Shrinkage 全局先验污染 | 数据科学家 📊 + 营销号操盘手 🎭 | 第3轮->5/6同意->Valid Bug 修复 | 已合入v2.3.0 small_sample_confidence 置信区间量化；Bayesian收缩因先验污染风险暂缓 | 已修复（置信区间部分），收缩待下轮 |
|| EI-04 | 代际+地域+人群代表性盲区 | 文化研究者 + 公平性审计员 | 第1轮->Edge Case；第2轮->5/6同意->Valid Bug | 修复：新增optional的age_group/season字段 + 文化坐标系统 | 已修复 |
|| EI-05 | 时令文化维度完全缺失 | 文化研究者 | 第1轮->Edge Case；第2轮->6/6同意->Valid Bug | 修复：新增时令感知时间衰减season_relevance | 已修复 |

> **Edge Case 重审规则**：每轮挑战赛优先重审上一个 Edge Case，确认是否升级为 Valid Bug 或降级为 Not Valid。
> **争议 Edge Case**（🟡🔶）：EI-02(2同意)和EI-03(2同意)在6票中仅2票同意，需重点关注——同意方认为P0，反对方认为存在副作用。

---

---

## 趋势指标（Trend Indicators）

### 问题定义

店铺的评分并非静态——品质可能随时间变化（换师傅、换老板、供应链波动）。单一聚合评分无法反映这些**趋势变化**。需要将时间序列分析纳入公平算法。

### 方案：四维趋势跟踪

在每次聚合运行时，计算并记录以下趋势指标，写入 `restaurant-summary.yaml` 的 `trends` 字段。

```yaml
# 新增趋势字段（在 rating_overview 同级）
trends:
  monthly:
    - month: "2026-06"
      avg_rating: 4.3
      review_count: 5
      would_revisit_rate: 0.80
    - month: "2026-05"
      avg_rating: 4.5
      review_count: 3
      would_revisit_rate: 1.0
    # ...
  quarterly:
    - quarter: "2026-Q2"
      avg_rating: 4.4
      review_count: 12
      would_revisit_rate: 0.92
    - quarter: "2026-Q1"
      avg_rating: 4.2
      review_count: 8
      would_revisit_rate: 0.75
    # ...
  direction: stable  # rising / stable / declining
  volatility: low    # low / medium / high — 月度评分标准差 < 0.3 为 low
  notable_change: "最近3个月评价数量从8条增至12条，活跃度上升"  # AI 判断
```

### 维度 1：月度滚动均分（Monthly Rolling Average）

```
月度评分 = 当月内所有评价的 overall_rating 平均值
月度评价数 = 当月内评价总数
月度 would_revisit_rate = 当月内 would_revisit=1 的比例
```

- 不足一个月的也作为一个完整月计算
- 无评价的月份**跳过**（不填充 0）

### 维度 2：季度滚动均分（Quarterly Rolling Average）

```
季度评分 = 该季度内所有评价的 overall_rating 平均值
季度评价数 = 累计
季度 would_revisit_rate = 该季度内 would_revisit=1 的比例
```

- 季度定义：Q1(1-3月), Q2(4-6月), Q3(7-9月), Q4(10-12月)
- 不足一个季度的也作为一个完整季度计算

### 维度 3：趋势方向判定

基于最近 3 个月（或最近 3 个有数据的月份）的评分变化，判定趋势方向：

```python
def determine_trend(monthly_data):
    if len(monthly_data) < 2:
        return "insufficient_data"
    
    # 取最近 3 个月（如有）
    recent = monthly_data[-3:]
    ratings = [m["avg_rating"] for m in recent]
    
    # 计算简单线性回归斜率
    n = len(ratings)
    x = list(range(n))
    slope = (n * sum(x[i] * ratings[i] for i in range(n)) - sum(x) * sum(ratings)) / \
            (n * sum(xi**2 for xi in x) - sum(x)**2) if n > 1 else 0
    
    if slope > 0.2:
        return "rising"
    elif slope < -0.2:
        return "declining"
    else:
        return "stable"
```

### 维度 4：波动率判定

```python
def determine_volatility(monthly_data):
    if len(monthly_data) < 3:
        return "low"
    
    ratings = [m["avg_rating"] for m in monthly_data]
    std_dev = statistics.stdev(ratings)
    
    if std_dev > 0.5:
        return "high"
    elif std_dev > 0.3:
        return "medium"
    else:
        return "low"
```

### 趋势信息在 summary 中的使用

```python
# 在 AI 生成的 summary 末尾附加趋势信息
if trends.direction == "rising":
    "📈 近几个月评分呈上升趋势（从{X}升至{Y}），评价数量也在增加"
elif trends.direction == "declining":
    "📉 近几个月评分呈下降趋势（从{X}降至{Y}），建议关注近期评价"
elif trends.direction == "stable":
    "📊 评分稳定在{X}左右，无明显波动"

if trends.volatility == "high":
    "⚠️ 评分波动较大（标准差>{std}），评价质量可能不稳定"
```

### 趋势数据持久化

趋势数据同时写入 SQLite 数据库的 `trend_tracking` 表（如存在），便于后续查询和历史回溯。

```sql
CREATE TABLE IF NOT EXISTS trend_tracking (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    restaurant_id INTEGER NOT NULL,
    period_type TEXT NOT NULL,       -- 'monthly' or 'quarterly'
    period_start TEXT NOT NULL,      -- 'YYYY-MM' for monthly, 'YYYY-QQ' for quarterly
    avg_rating REAL,
    review_count INTEGER,
    would_revisit_rate REAL,
    aggregated_at TEXT DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (restaurant_id) REFERENCES restaurants(id)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_trend_unique 
    ON trend_tracking(restaurant_id, period_type, period_start);
```

---

## 时间衰减 — 离散阶梯实现（v2.0 默认实现）

除前述连续指数衰减外，本算法还支持一种**离散阶梯式时间衰减**方案，已在 `restaurant-summary.yaml` 的 `meta.algorithm.time_decay` 中配置为默认值：

```yaml
time_decay:
  within_1y: 1.0              # 1年内（含）评价，权重 1.0
  within_2y: 0.8              # 1-2年评价，权重 0.8
  within_3y: 0.5              # 2-3年评价，权重 0.5
  over_3y: 0.3                # 超过3年评价，权重 0.3
  old_shop_bonus: true        # 老店且评价稳定时，>3年评价权重提升至 0.6
```

### 离散加权中位数的计算

```python
def compute_time_decay_weight(review_date, now, is_stable_old_shop=False):
    years_since = (now - review_date).days / 365.25
    
    if years_since <= 1.0:
        weight = 1.0
    elif years_since <= 2.0:
        weight = 0.8
    elif years_since <= 3.0:
        weight = 0.5
    else:
        if is_stable_old_shop:
            weight = 0.6   # 老店bonus：老店且评价稳定的，>3年权重提升到0.6
        else:
            weight = 0.3
    
    return weight
```

**老店判定条件**（同时满足视为稳定老店）：
1. 店铺开业时间 ≥ 3 年（或第一条评价距今 ≥ 3 年）
2. 评价数量 ≥ 5 条
3. 评分方差 < 1.0（评价稳定，无明显争议）

### 离散 vs 指数衰减的对比

| 特性 | 离散阶梯 | 连续指数衰减 |
|------|---------|-------------|
| 实现复杂度 | 低 | 中 |
| 可解释性 | 高（直观易懂） | 中 |
| 精度 | 粗粒度（逐年降权） | 细粒度（每天平滑衰减） |
| 参数数量 | 4 个阈值 | 1 个 λ 值 |
| 推荐场景 | 初期/小数据量 | 大数据量/需要精细调节 |

实现时两者选一即可。默认建议使用**离散阶梯**方案，保持可读性和易维护性。当数据量增长后，可切换至指数衰减方案以获得更精确的权重分配。

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
