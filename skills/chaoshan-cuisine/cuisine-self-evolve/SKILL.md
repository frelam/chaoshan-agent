---
name: cuisine-self-evolve
version: "3.0.0"
description: "潮汕美食自演进策略 v3 — 数据收集 + 公平算法多Agent挑战赛。每周一收集评价，每周四6个Agent从不同视角挑战公平算法，辩论后优化。"
triggers:
  - "美食自演进"
  - "美食更新"
  - "美食时效性"
  - "发现新店"
  - "闭店检查"
  - "算法挑战"
  - "公平算法"
  - "算法优化"
  - "cuisine self-evolve"
  - "food update"
  - "评价收集"
  - "challenge"
requires:
  min_context: 16384
skills:
  - chaoshan-cuisine
data:
  - ../data/restaurants.yaml
  - ../data/restaurant-summary.yaml
  - ../data/reviewer-profiles.yaml
  - ../docs/FAIRNESS-ALGORITHM.md
  - data/search-sources.md
  - data/restaurant-check-template.md
---

# 潮汕美食 Skill 自演进策略

## 整体架构

```
每周1次 (cron: 每周一 06:00)   ← 常规更新轮（收集数据）
  │
  ├─ 1. 批量搜索: web_search × 4-6 种查询 → 提取店铺/评价/状态信息
  ├─ 2. 去重归类: 按店铺名+地区去重，标记已知店 vs 新店
  ├─ 3. 新店发现: 搜索到的不在数据库中的店铺 → 进入模板化录入管道
  ├─ 4. 时效核验: 已有店铺 → 检查是否闭店/有无新评价
  ├─ 5. 验证: 交叉验证（多个来源对照）+ 识别营销推广
  ├─ 6. 数据追加:
  │    ├─ 新评价 → restaurants.yaml (entries 末尾)
  │    ├─ 新店铺初稿 → references/pending-restaurants.md（待人工审）
  │    └─ 确认闭店 → data/closed-restaurants.yaml
  ├─ 7. 版本管理: 小版本+1, total_reviews/total_restaurants 递增
  ├─ 8. 同步源码: rsync → ~/workspace/chaoshan-agent/
  └─ 9. GitHub: git add → commit → push

每周1次 (cron: 每周四 06:00)   ← 公平算法挑战赛（优化算法）
  │
  ├─ 1. 加载 FAIRNESS-ALGORITHM.md + restaurant-summary.yaml
  ├─ 2. 多Agent挑战:
  │    ├─ 本地老饕 → 算法是否忽视本地人声音？
  │    ├─ 外地游客 → 算法是否偏袒本地人？
  │    ├─ 数据科学家 → 统计分析是否存在缺陷？
  │    ├─ 营销号操盘手 → 算法有什么漏洞可钻？
  │    ├─ 文化研究者 → 算法忽略了什么文化语境？
  │    └─ 公平性审计员 → 算法是否存在系统性偏见？
  ├─ 3. 公开辩论: 挑战提出者回应质疑，至少3轮交互
  ├─ 4. 共识投票:
  │    ├─ 🔴 Valid Bug → 确定修复方案
  │    ├─ 🟡 Edge Case → 记录在案
  │    └─ 🟢 Not Valid → 驳回
  ├─ 5. 算法更新: FAIRNESS-ALGORITHM.md 版本 bump
  ├─ 6. 生成挑战报告
  ├─ 7. 同步源码: rsync → ~/workspace/chaoshan-agent/
  └─ 8. GitHub: git add → commit → push

月初 (每月1日 06:00)           ← 深度核验轮
  │
  ├─ 1. 全量检查: 遍历 restaurant-summary.yaml 中的店铺
  ├─ 2. 标记需复核: 最后一条评价 > 6 个月的店铺
  ├─ 3. 逐个搜索核验: 对标记店铺做生存状态检查
  ├─ 4. 已闭店 → 移入 data/closed-restaurants.yaml + 从 summary 移除
  ├─ 5. 正常营业 → 更新 last_verified 时间戳
  ├─ 6. 发现新评价 → 追加、更新 summary
  └─ 7. 版本管理 + rsync + git push

季度 (每季度初 06:00)          ← 全面整合轮
  │
  ├─ 1. 重新运行公平算法（重新聚合 restaurant-summary.yaml）
  ├─ 2. 整合 pending-restaurants 中积累的新店
  ├─ 3. 合并 duplicate 店铺条目
  ├─ 4. 更新分类标签一致性
  ├─ 5. 输出季度报告
  └─ 6. 版本管理 + rsync + git push
```

## 数据文件

| 文件 | 用途 |
|------|------|
| `../data/restaurants.yaml` | 食客原始评价 + 评价者画像 — 每次自演进追加新评价 |
| `../data/restaurant-summary.yaml` | 店铺多维聚合画像 — 季度重新运行时更新 |
| `../data/beef-knowledge.yaml` | 牛肉知识库 — 极少更新 |
| `../data/reviewer-profiles.yaml` | 评价者画像数据库 — 每次追加新评价者时同步更新 |
| `data/closed-restaurants.yaml` | 已闭店记录 |
| `data/search-sources.md` | 搜索策略参考 |
| `references/pending-restaurants.md` | 待人工审核的新店铺初稿 |

## 搜索策略（6种方向 + 2个轮换策略）

### 每周常规查询（6选3-4，轮换使用）

```
本周查询集 = 从以下6类中随机选3-4个不同方向的查询

每类选1-2个具体查询，确保覆盖不同品类和地区
```

#### 方向A：跨品类榜单/推荐（广度扫描）

```
web_search("潮汕美食探店 推荐 2026")
web_search("汕头必吃美食 本地人推荐")
web_search("潮州古城美食攻略 2026")
web_search("揭阳美食 本地人常去")
web_search("汕尾美食 推荐")
web_search("潮汕美食 真实评价 避雷")
```

#### 方向B：品类专项（深度挖掘某一品类本周焦点）

```
web_search("汕头牛肉火锅 推荐 2026")
web_search("潮州肠粉 哪家好吃")
web_search("汕头蚝烙 老店推荐")
web_search("揭阳粿条汤 好吃")
web_search("潮汕生腌 推荐")
web_search("汕头夜粥 大排档")
web_search("潮汕卤鹅 哪家好吃")
web_search("汕头甜汤 糖水")
web_search("潮汕砂锅粥 推荐")
web_search("南澳岛 海鲜")
```

#### 方向C：地区专项（聚焦一个地区深度扫描）

```
web_search("汕头金平区 美食")
web_search("汕头龙湖区 美食推荐")
web_search("潮州湘桥区 小吃")
web_search("揭阳榕城区 老字号")
web_search("澄海 美食")
web_search("饶平 美食")
web_search("普宁 美食")
```

#### 方向D：反营销/避雷（收集差评和真实声音）

```
web_search("汕头 踩雷 网红店")
web_search("潮汕 网红店 不好吃")
web_search("汕头 避雷 美食")
web_search("潮汕旅游 美食坑")
web_search("潮汕 营销过度 店")
```

#### 方向E：店铺生存核验（针对已有店铺）

```
# 动态生成：从 restaurant-summary.yaml 中选 oldest_updated 的 3-5 个店铺
# 格式: web_search("[店铺名] [地区] 营业")
web_search("八合里海记牛肉店 汕头 营业")
web_search("[店铺名] 还在营业吗")
```

#### 方向F：时令/新趋势（捕捉季节性美食和新兴品类）

```
web_search("潮汕 夏季美食 推荐")
web_search("汕头 新店 开业")
web_search("潮汕 宵夜 大排档 2026")
web_search("汕头 深夜美食")
web_search("潮州 夜宵 推荐")
```

### 搜索参数建议

- 每次运行 **不要超过 6 次 web_search**（限制工具调用）
- 优先选择和上次不同的方向，避免信息重复
- 搜索关键词中加入年份（如"2026"）提高时效性
- 搜索"避雷""踩雷"类关键词获取反营销信息

### 营销推广识别指南

| 信号 | 营销推广可能性 | 说明 |
|------|--------------|------|
| "天花板" "yyds" "封神" "绝绝子" | ⚠️ 高 | 套路化营销话术 |
| "必须打卡" "不x就白来了" | ⚠️ 高 | 制造焦虑式推广 |
| 大量相似措辞的短评 | ⚠️ 高 | 可能水军刷评 |
| 明确说"自费""无广"的评价 | ✅ 可信较高 | 但需交叉验证 |
| 有具体口感描述+照片的评价 | ✅ 可信中等 | 真实评价概率高 |
| 有差评细节的评价 | ✅ 可信高 | 营销号很少写差评 |
| 本地人 vs 游客评价对比 | ✅ 参考价值 | 保留两种声音 |

## 验证方法

### 评价可信度三档判定

```
可信度高（直接追加）：
- 多个来源提到同一观点
- 有具体口感/价格描述
- 来源为个人博客/知乎长文/小红书非KOL
- 同时包含好评和差评

可信度中等（追加 + 标记"待交叉验证"）：
- 单一来源但细节具体
- 来源为小红书/大众点评常规用户
- 有具体菜名和价格

可信度低（不追加，存入 pending）：
- 单一来源、措辞空洞
- 只有"好吃""推荐"没有具体描写
- 疑似营销推广
- 无任何具体信息（价格/地址/菜品）
```

### 店铺生存状态判定

```
正常营业：
- 多个来源提到近期（3个月内）到店
- 大众点评/小红书有近期评价
- 外卖平台可搜到

可能闭店：
- 最近评价 > 12 个月
- 搜索无近期提及
- 标记为"需复核"，等待下次月度核验

确认闭店：
- 多个来源确认（如"已倒闭""转让中"）
- 地图上显示永久关闭
- → 移入 closed-restaurants.yaml
- → 从 restaurant-summary.yaml 移除
- → 在 restaurants.yaml 中标记 closed
```

## 数据更新规则

### 追加新评价到 restaurants.yaml

```yaml
- id: rev-auto-{date}-{seq}
  restaurant_name: "店铺名"
  address: "地址"
  district: "所属区县"
  cuisine_type: "品类"
  reviewer:
    id: "web-{hash}"              # 基于 hometown+age_range 生成稳定ID
    type: tourist
    hometown: "（推测城市）"
    age_range: "18-25"
    taste_tags: ["推测标签"]
  visit_date: "YYYY-MM-DD"
  dishes_ordered:
    - name: "菜名"
      rating: 4
      price: 25
      comment: "口感描述"
  overall_rating: 4.5
  review_text: "AI自动提取整理的评价摘要（注明来源）"
  would_revisit: true
  tags: [品类, self-evolved, 待人工复核]
  contributor: "cuisine-self-evolve"
  source_type: self
  source_url: ""
  date: "YYYY-MM-DD"
```

### 新增店铺（不在数据库中）

- 不直接追加到 restaurants.yaml
- 先写入 `references/pending-restaurants.md`（待人工审核）
- 季度核验时人工审核后正式录入

### 已有店铺的新评价

- 直接追加到 restaurants.yaml entries
- 更新 restaurant-summary.yaml 中该店铺的 `last_updated`
- 如果新评价明显拉低或拉高评分，标记为"评分波动提醒"

### 闭店处理

```
确认闭店后：
1. data/closed-restaurants.yaml ← 追加记录（含闭店日期、确认来源）
2. restaurants.yaml ← 为该店铺所有评价添加 tag: [closed]
3. restaurant-summary.yaml ← 移除该店铺或标记为 closed
4. 版本号 bump
```

### 时间衰减

```
评价 visit_date 距今:
  ≤ 1年    → 评分权重 1.0（正常，反映当前水平）
  1-2年    → 评分权重 0.8（基本可信）
  2-3年    → 评分权重 0.5（参考价值降低）
  > 3年    → 评分权重 0.3（可能已过时）
  
  例外：老店且评价中多次出现"水平稳定"则 >3年评价权重提至 0.6
```

```
店铺 last_updated 距今:
  < 3个月   → 正常，无需复核
  3-12个月  → 标记"数据偏旧"
  > 12个月  → 标记"需复核"，月度核验优先检查
```

## 版本管理

### restaurants.yaml

```
meta.version: 小版本+1（每次追加）
meta.total_reviews: +N
meta.last_updated: 更新日期
```

### reviewer-profiles.yaml

```
meta.version: 追加时 +1
meta.total_profiles: +N（如有新评价者）
meta.last_updated: 更新日期
```

### restaurant-summary.yaml

```
meta.version: 仅在季度重新运行时更新
meta.last_updated: 更新日期
```

### closed-restaurants.yaml

```
meta.version: 追加时 +1
meta.total_closed: +N
meta.last_updated: 更新日期
```

## 同步命令

```bash
# 从 Hermes runtime 同步到源码仓库
rsync -av ~/.hermes/skills/chaoshan-cuisine/ ~/workspace/chaoshan-agent/skills/chaoshan-cuisine/

# 从源码仓库同步到 Hermes runtime（修改 SKILL.md 后）
rsync -av ~/workspace/chaoshan-agent/skills/chaoshan-cuisine/ ~/.hermes/skills/chaoshan-cuisine/
```

## GitHub 提交

有数据变更时执行：

```bash
cd ~/workspace/chaoshan-agent
git add -A
git commit -m "auto: 潮汕美食自演进 $(date +%Y-%m-%d) — +N条新评价，X家店铺核验"
git push
```

无变更则跳过。GitHub 已通过 gh CLI 认证（frelam 账号，HTTPS 协议），可直接 push。

## 输出报告格式

### 周度常规轮报告

```
📊 潮汕美食自演进报告 — 2026-06-08（周一）

【搜索统计】
  搜索方向: 4 种（榜单/品类/地区/避雷）
  已执行查询: N 个
  提取新评价: X 条
  发现新店铺: Y 家（已写入 pending）
  核验已有店铺: Z 家

【验证结果】
  ✅ 可信直接追加: A 条
  ⚠️ 待交叉验证: B 条
  ❌ 营销推广/不可靠: C 条
  🚫 确认闭店: D 家

【数据变更】
  restaurants.yaml: v1.0.0 → v1.0.1 (+A 条评价)
  reviewer-profiles.yaml: v1.0.0 → v1.0.1 (+N 个新评价者)
  closed-restaurants.yaml: D 家已记录
  pending-restaurants: Y 家待审核

【新评价摘要】
  🏠 店铺名（区县）
  💬 "评价摘要…"
  ⭐ 评分: N/5 | 品类: XXX
  🔗 来源: web_search

【时效提醒】
  ⏰ 以下店铺 > 6 个月未更新，建议核验：
  - 店铺名（区县，最后更新: YYYY-MM-DD）
  - ...

【GitHub】
  提交: 是/否
  提交信息: auto: 潮汕美食自演进 YYYY-MM-DD — +X条
```

### 月初深度核验报告

```
📊 潮汕美食月度核验报告 — 2026-07-01

【全量店铺统计】
  数据库总店铺: N 家
  本次核验: N 家
  ✅ 正常营业: N 家
  ⏰ 需复核: N 家（无近期数据）
  🚫 确认闭店: N 家（已移入 closed）

【详细核验清单】
  ✅ 店铺名（区县）— 正常，最近评价: YYYY-MM
  ⏰ 店铺名（区县）— 最后评价 YYYY-MM，无新数据
  🚫 店铺名（区县）— 确认闭店（来源: web_search）
  ...

【数据变更】
  restaurants.yaml: +N 条
  restaurant-summary.yaml: 更新时间戳
  closed-restaurants.yaml: +N 家
```

### 季度整合报告

```
📊 潮汕美食季度整合报告 — 2026-Q2

【店铺统计】
  总店铺数: N 家
  本季度新增: N 家
  本季度闭店: N 家
  覆盖品类: N 类
  覆盖区县: N 个

【评价统计】
  总评价数: N 条
  本季度新增: N 条
  本地人评价: N 条（占比 X%）
  游客评价: N 条（占比 Y%）
  回访客评价: N 条（占比 Z%）

【公平算法】
  已重新运行: 是
  评分变化店铺: N 家
  争议店铺: N 家（方差 > 1.5）
  可疑聚集: N 家（已标记不删除）

【品类热力】
  🔥 最热门品类: XXX（N 家店铺，N 条评价）
  📈 增长最快品类: XXX（环比 +X%）
  📉 下降品类: XXX（环比 -X%）

【GitHub】
  本季度提交次数: N 次
  新增评价: N 条
  新增店铺: N 家
```

## Cron 配置建议

```yaml
# 每周常规更新 — 每周一 06:00
schedule: "0 6 * * 1"
prompt: |
  运行潮汕美食自演进流程。
  执行步骤：
  1. 加载 cuisine-self-evolve + chaoshan-cuisine 两个 skill
  2. 按搜索策略执行 4-6 次 web_search（覆盖不同方向）
  3. 提取新评价/新店铺/状态变更信息
  4. 查重、去营销推广
  5. 追加到 restaurants.yaml / pending / closed
  6. 版本号 bump
  7. rsync + git push
  8. 输出完整报告
skills:
  - chaoshan-cuisine
  - cuisine-self-evolve

# 月初深度核验 — 每月1日 06:00
schedule: "0 6 1 * *"
prompt: |
  运行潮汕美食月度核验流程。
  执行步骤：
  1. 加载 chaoshan-cuisine + cuisine-self-evolve
  2. 遍历所有店铺，按 last_updated 排序
  3. 对 > 6 个月未更新的店铺逐个搜索核验
  4. 确认闭店的做迁移标记
  5. 正常营业的更新 last_verified
  6. 输出月度核验报告
skills:
  - chaoshan-cuisine
  - cuisine-self-evolve

# 每周公平算法挑战赛 — 每周四 06:00
schedule: "0 6 * * 4"
prompt: |
  你是潮汕美食公平算法挑战赛的主持人（Orchestrator）。你的任务：
  协调6个不同立场的子Agent，对 FAIRNESS-ALGORITHM.md 中的公平算法进行全面审查。

  ⚠️ 重要：你必须自主完成全部10个步骤，无需人工干预。每个步骤失败时有重试和降级策略。

  ## 前置准备

  先确定本次挑战的元信息：
  - 计算轮次编号：列出 data/challenge-logs/ 下已有的 challenge-*.md 文件，取最大编号+1；如果目录为空，则编号=001
  - 日期 = 今天（YYYY-MM-DD）
  - 输出文件名 = challenge-{轮次编号}-{日期}.md

  ## 第1步：加载数据

  并行读取以下3个文件（使用 Read 工具）：
  1. `docs/FAIRNESS-ALGORITHM.md` — 完整算法文档（你需要把其中的7项原则、参数可调表、算法流程等内容记住）
  2. `data/restaurant-summary.yaml` — 店铺聚合数据（你需要提取 meta.algorithm_version、meta.total_restaurants、meta.total_reviews_processed）
  3. `data/restaurants.yaml` — 原始评价数据（抽样读取前100行了解数据结构即可，完整数据留给子Agent读取）

  ## 第2步：创建6个子Agent

  使用 `delegate_task` 工具，同时创建6个子Agent（以下 prompt 直接用于每个子Agent的 task 参数）。
  每个子Agent必须独立加载 `docs/FAIRNESS-ALGORITHM.md` 和 `data/restaurant-summary.yaml`。

  ---

  ### Agent 1：本地老饕 🧓
  委托 prompt：
  ```
  你是「本地老饕」——祖辈三代在汕头，最懂"老味道"的美食家。

  你的立场：你担心算法太迁就游客口味、时间衰减对本地人老评价过于激进、
  游客评价权重被放大、本地人的"从小吃到大"基准被低估。

  请执行以下操作：
  1. 加载 docs/FAIRNESS-ALGORITHM.md 和 data/restaurant-summary.yaml
  2. 从你的立场出发，仔细审视算法每个原则和参数，寻找以下类型的漏洞：
     - 时间衰减是否对本地老评价不公平？（本地人3年前的评价仍然可能比游客上周的评价更准确）
     - 画像分层统计中，local 的中位数评分是否被 time_decay 过度惩罚？
     - reviewer_weight 系统是否对资深本地贡献者不够激励？
     - 少数声音保留的 15% 阈值是否会让本地人的细微意见被埋没？
     - 其他你觉得从本地人视角不合理的地方
  3. 提出 1-2 个具体挑战。每个挑战必须包含：
     a) 涉及算法的哪个原则/参数（引用具体的章节号或参数名）
     b) 为什么这是个问题（理论论证 + 如可能用真实数据举例）
     c) 后果严重程度评估
     d) 建议的改进方向（如果已有想法）
  4. 以以下格式输出：

  === 本地老饕的挑战 ===
  ## 挑战 L-1：[挑战标题]
  涉及章节：...
  问题描述：...
  论据：...
  严重程度：P0/P1/P2
  建议：...

  ## 挑战 L-2：[挑战标题]（如有）
  ...
  ```

  ### Agent 2：外地游客 🧳
  委托 prompt：
  ```
  你是「外地游客」——第一次来潮汕的北京游客，对潮汕美食充满期待但也容易"踩雷"。

  你的立场：你担心算法偏袒本地人、忽略可及性（环境/服务/排队）、
  可信度评估对游客不合理、品类差异被本地化视角抹平。

  请执行以下操作：
  1. 加载 docs/FAIRNESS-ALGORITHM.md 和 data/restaurant-summary.yaml
  2. 从你的立场出发，仔细审视算法，寻找以下类型的漏洞：
     - 本地人的评分是否系统性偏高？（"从小吃到大"的情怀加成）
     - 算法是否忽略了环境/服务/排队等对游客很重要的维度？
     - 时间衰减是否对游客有利（游客的评价总是近期的）而造成系统性偏差？
     - consensus 判定（60%阈值）是否可能让本地人主导共识，游客的合理意见被归入 diverse_opinions？
     - 评价者可信度系统是否对"只来一次"的游客不公平？
     - 其他你觉得从外地游客视角不合理的地方
  3. 提出 1-2 个具体挑战，格式同 Agent 1。
  4. 以以下格式输出：

  === 外地游客的挑战 ===
  ## 挑战 T-1：[挑战标题]
  涉及章节：...
  问题描述：...
  论据：...
  严重程度：P0/P1/P2
  建议：...

  ## 挑战 T-2：[挑战标题]（如有）
  ...
  ```

  ### Agent 3：数据科学家 📊
  委托 prompt：
  ```
  你是「数据科学家」——推荐系统算法工程师，擅长统计分析和机器学习。

  你的立场：你关注算法的数学严谨性——样本量置信度、评分分布偏差、
  冷启动问题、统计方法是否有缺陷、参数选择是否有理论依据。

  请执行以下操作：
  1. 加载 docs/FAIRNESS-ALGORITHM.md 和 data/restaurant-summary.yaml
  2. 从统计学和算法设计角度审视，寻找以下类型的漏洞：
     - 中位数替代平均数虽然抗极值，但在小样本（N<5）时是否足够稳健？
     - 加权中位数（weighted_median）的数学定义是否明确？weighted_median 的计算方式是否合理？
     - 时间衰减权重 [1.0, 0.8, 0.5, 0.3] 的选择依据是什么？衰减曲线是否过于陡峭？
     - 反操控检测的三条件（7天+≥3条+方差<0.3）是否容易绕过？（比如刷分者分散在8天）
     - recipe_confidence 如何计算？小样本店铺的评分是否应该有置信区间展示？
     - 参数可调表中的默认值是否有统计理论支撑？
     - 画像分层统计时，如果某个 reviewer.type 只有 1 条评价，是否应该展示 median？
     - 其他统计方法上的缺陷
  3. 提出 1-2 个具体挑战，用数据和逻辑论证。
  4. 以以下格式输出：

  === 数据科学家的挑战 ===
  ## 挑战 D-1：[挑战标题]
  涉及参数/章节：...
  统计分析：...
  问题严重性：P0/P1/P2
  建议修正：...

  ## 挑战 D-2：[挑战标题]（如有）
  ...
  ```

  ### Agent 4：营销号操盘手 🎭
  委托 prompt：
  ```
  你是「营销号操盘手」——你知道如何操纵大众点评、小红书的评价系统。
  你现在扮演"坏人"角色，目标是找出当前反操控机制的全部漏洞。

  你的立场：你要证明当前反操控检测可以被绕过，从而帮算法变得更健壮。

  请执行以下操作：
  1. 加载 docs/FAIRNESS-ALGORITHM.md 和 data/restaurant-summary.yaml
  2. 攻击心态审视反操控机制（原则6），寻找以下漏洞：
     - 7天3条的检测窗口是否太窄？如果我分散在14天发5条呢？
     - 方差<0.3 的阈值——如果我刷 4,4,5（方差≈0.33），是否就绕过了？
     - 文本相似度>60%——我让每个刷手用不同措辞写评价，能否绕过？
     - "标记而不删除"是否太宽容？被标记的评价者后续写1条有差异的评价就能自动解除？
     - 有没有其他攻击向量？比如：
       * 给竞争对手差评（刷1分，分散时间+不同措辞）
       * 通过大量贡献低质量评价提升 reviewer_weight 到 1.2
       * 利用贡献者画像系统（如果不同来源的评价者无法关联）
       * 季节性攻击（在旅游旺季批量操作，混入真实游客中）
     - 其他可能的操控手法
  3. 提出 1-2 个具体挑战，每个挑战=一个可执行的攻击方案。
  4. 以以下格式输出：

  === 营销号操盘手的挑战 ===
  ## 攻击方案 M-1：[攻击名称]
  目标：操控什么（提高评分/降低评分/影响共识/...）
  攻击手法：...
  为何当前反操控检测无法捕获：...
  可行性评估：高/中/低
  建议加强措施：...

  ## 攻击方案 M-2：[攻击名称]（如有）
  ...
  ```

  ### Agent 5：文化研究者 📖
  委托 prompt：
  ```
  你是「文化研究者」——研究潮汕饮食文化的人类学者。

  你的立场：你关注算法是否忽略了文化语境——
  品类差异、地域差异、不同代际的口味变迁、节日/时令对评价的影响。

  请执行以下操作：
  1. 加载 docs/FAIRNESS-ALGORITHM.md 和 data/restaurant-summary.yaml
  2. 从文化人类学视角审视，寻找以下类型的漏洞：
     - 跨品类评分不可比：牛肉火锅的4分和街边肠粉的4分含义完全不同，算法是否考虑了这一点？
     - 地域差异：汕头市区的店 vs 饶平乡下的店，评价标准是否应该不同？
     - 代际差异：50+ 本地人的口味 vs 18-25 年轻人的口味，在 by_age 分层中有区分，但时间衰减是否对老年人（不太写新评价）不公平？
     - 时令影响：夏季的海鲜评价 vs 冬季的火锅评价，季节性波动是否被误判为品质变化？
     - "老店"标签的认定标准：多久算老店？10年？30年？算法中的"老店"定义是否清晰？
     - 潮汕饮食的"灵魂"——如工夫茶文化、祭祀粿品——是否在评价体系中得到了体现？
     - 其他文化语境相关的漏洞
  3. 提出 1-2 个具体挑战。
  4. 以以下格式输出：

  === 文化研究者的挑战 ===
  ## 挑战 C-1：[挑战标题]
  文化语境：...
  问题描述：...
  论据：...
  严重程度：P0/P1/P2
  建议：...

  ## 挑战 C-2：[挑战标题]（如有）
  ...
  ```

  ### Agent 6：公平性审计员 ⚖️
  委托 prompt：
  ```
  你是「公平性审计员」——第三方 AI 公平性审计专家。

  你的立场：你不偏向任何一方，你的任务是全局审视算法的系统性偏见。

  请执行以下操作：
  1. 加载 docs/FAIRNESS-ALGORITHM.md 和 data/restaurant-summary.yaml
  2. 从 AI 公平性审计框架审视，寻找以下类型的漏洞：
     - 透明度：算法是否可被外部审计？加权中位数的计算过程是否可以被任何人重现？
     - 可解释性：生成的 summary 是否能让用户理解分数是怎么来的？
     - 问责性：如果算法出错（如误判刷分），有没有申诉/纠错机制？——当前只有"手动覆盖"（手动编辑 summary），但原始评价的权重调整后如何申诉？
     - 代表性：当前 reviewer.type 只有 local/tourist/returning-visitor，是否遗漏了重要人群？（如：外地的潮汕人后代、在潮汕工作的外地人）
     - 偏见放大：时间衰减 + 评价者可信度 + 反操控降权 —— 多个权重相乘后，是否会让某些边缘群体的声音被多重惩罚？
     - 人口统计公平性：by_age / by_hometown 分层后，如果某个交叉分组（如"26-35岁北京游客"）样本量极小，是否会导致有偏结论？
     - GDPR/隐私：reviewer 的 hometown + age_range + taste_tags 是否可能重识别真实个人？
     - 其他系统性偏见
  3. 提出 1-2 个具体挑战。
  4. 以以下格式输出：

  === 公平性审计员的挑战 ===
  ## 挑战 A-1：[挑战标题]
  公平性维度：...
  问题描述：...
  论据：...
  严重程度：P0/P1/P2
  建议：...

  ## 挑战 A-2：[挑战标题]（如有）
  ...
  ```

  ---

  ## 第3步：汇总挑战

  收集所有6个子Agent的输出。你应该得到 6-12 个挑战。将它们整理成一个统一的挑战列表：

  | 编号 | 提出者 | 标题 | 涉及章节/参数 | 严重程度 |
  |------|--------|------|-------------|---------|
  | CH-01 | 本地老饕 | ... | ... | P0/P1/P2 |
  | CH-02 | 外地游客 | ... | ... | P0/P1/P2 |
  | ... | ... | ... | ... | ... |

  ## 第4步：公开辩论（3轮）

  你作为主持人，需要主持3轮辩论。不要创建新的子Agent——你在自己的上下文中模拟辩论过程。

  ### 第1轮：交叉质疑
  对每个挑战，让提出者之外的其他角色（你模拟他们的立场）提出质疑：
  - 对于每个挑战，至少2个其他角色提出反驳或补充
  - 记录质疑内容

  ### 第2轮：提出者回应
  对每个挑战，让提出者回应第1轮的质疑：
  - 论证是否被削弱/加强
  - 是否有新的认识

  ### 第3轮：最终陈述
  对每个挑战，6个角色各自给出最终立场：同意（✅）/ 不同意（❌）/ 有条件同意（⚠️）

  ## 第5步：共识投票

  根据第3轮的投票结果，对每个挑战进行分类：

  | 票数（同意+有条件同意） | 结果 | 后续动作 |
  |------------------------|------|---------|
  | ≥4 | 🔴 Valid Bug | 必须提出修复方案 |
  | 2-3 | 🟡 Edge Case | 记录在案，暂无修复 |
  | 0-1 | 🟢 Not Valid | 驳回并记录理由 |

  ## 第6步：修复方案（仅 Valid Bug）

  对每个 Valid Bug：
  1. 设计具体的修复方案（参数调整/规则变更/新增机制）
  2. 评估影响范围（哪些店铺的 summary 会受影响）
  3. 给出回滚方案（如果修复导致意外后果）
  4. 确定 FAIRNESS-ALGORITHM.md 的版本号变更：
     - 新增原则/关键参数变更 → Y+1（次版本）
     - 参数值微调/文档澄清 → Z+1（补丁版本）
     - 原则根本性变更 → X+1（主版本）

  ## 第7步：更新 FAIRNESS-ALGORITHM.md

  使用 Edit 工具，对 FAIRNESS-ALGORITHM.md 做以下更新：
  1. 如果有 Valid Bug，修改相应的算法描述/参数
  2. 在"版本历史"章节的表格中新增一行：
     ```
     | X.Y.Z+1 | YYYY-MM-DD | {变更类型} | {变更描述} | {提出者角色} | 见 challenge-{NNN}-{日期}.md |
     ```
  3. 如果有 Edge Case 留待观察，在"待解决问题"表格中新增条目

  ## 第8步：写入挑战日志

  使用 Bash 工具，将完整的挑战报告写入文件：
  - 文件路径：`data/challenge-logs/challenge-{NNN}-{日期}.md`
  - 内容格式：参考 `data/challenge-logs/challenge-template.md` 的结构，填入实际内容

  确保日志包含：
  - 挑战者名单
  - 每个挑战的详细论据
  - 辩论过程（3轮摘要）
  - 投票结果表格
  - 实际算法变更（如有）
  - 未解决问题

  ## 第9步：同步源码

  ```bash
  rsync -av ~/.hermes/skills/chaoshan-cuisine/ ~/workspace/chaoshan-agent/skills/chaoshan-cuisine/
  ```

  ## 第10步：Git提交

  ```bash
  cd ~/workspace/chaoshan-agent
  git add -A
  git commit -m "auto: 多Agent挑战赛 第{N}轮 $(date +%Y-%m-%d) — {总结：如 '确认2个Valid Bug，1个Edge Case'}"
  git push
  ```

  ## 第11步：输出挑战报告

  在对话中输出本次挑战赛的完整报告摘要，格式如下：

  ```
  ═══════════════════════════════════════════
  潮汕美食公平算法 — 第{N}轮挑战报告
  日期: YYYY-MM-DD
  ═══════════════════════════════════════════

  【数据概况】
    算法版本: vX.Y.Z → vX'.Y'.Z'（如有变更）
    店铺数据: N 家店铺，N 条评价

  【挑战统计】
    总挑战数: N
    🔴 Valid Bug: N
    🟡 Edge Case: N
    🟢 Not Valid: N

  【Valid Bug 摘要】
    1. {标题}（{提出者}）→ {修复方案摘要}
    2. ...

  【Edge Case 摘要】
    1. {标题}（{提出者}）→ 已记录，待观察

  【Not Valid 摘要】
    1. {标题}（{提出者}）→ 驳回理由

  【算法变更】
    详见 challenge-{NNN}-{日期}.md

  【GitHub】
    已提交: auto: 多Agent挑战赛 第{N}轮 YYYY-MM-DD

  【下轮挑战】
    YYYY-MM-DD（下周四）
  ```

  ## 异常处理

  - 如果某个子Agent创建失败 → 重试1次，仍失败则用5个Agent继续（在报告中注明）
  - 如果某个子Agent输出格式不规范 → 尝试从其输出中提取关键信息，仍无法提取则标注"Agent输出不可解析，已跳过"
  - 如果数据文件为空（restaurant-summary.yaml 中 entries: []）→ 子Agent仍然可以基于算法文档做理论分析，在报告中标注"无实际数据，纯理论分析"
  - 如果 rsync 失败 → 跳过，在报告中注明"rsync失败，需手动同步"
  - 如果 git push 失败 → 尝试 git pull --rebase 后重试，仍失败则在报告中注明
  - 任何步骤失败都不要阻塞后续步骤，继续执行并记录失败

  ## 重要提醒

  - ✅ 你是主持人，不要自己提出挑战——让6个子Agent来做
  - ✅ 辩论阶段是你自己模拟6个角色的对话，不需要再创建子Agent
  - ✅ 所有文件路径相对于 skills/chaoshan-cuisine/ 目录（你的 CWD）
  - ✅ 如果同一轮中多个挑战指向同一个问题，合并为一个 Valid Bug
  - ✅ Edge Case 也要写入挑战日志——它们是后续挑战赛的"种子问题"
  - ✅ 保持所有输出和文件内容使用中文
skills:
  - chaoshan-cuisine
  - cuisine-self-evolve

# 季度整合 — 每季度第1天 06:00
schedule: "0 6 1 1,4,7,10 *"
prompt: |
  运行潮汕美食季度整合流程。
  执行步骤：
  1. 加载 chaoshan-cuisine + cuisine-self-evolve
  2. 审核 pending-restaurants 中的新店铺
  3. 重新运行公平算法聚合 restaurant-summary.yaml
  4. 合并重复店铺
  5. 更新分类标签
  6. 输出季度报告
  7. rsync + git push
skills:
  - chaoshan-cuisine
  - cuisine-self-evolve
```

## 工具调用限制管理

| 阶段 | 估计调用次数 | 优化建议 |
|------|-------------|---------|
| 搜索发现 | 4-6 | 每次 run 用 4-6 个 web_search，分散在不同方向 |
| 提取归类 | 2-3 | 批量读取数据文件做内存校验 |
| 验证判断 | 3-5 | 通过交叉验证减少误判 |
| 数据写入 | 3-8 | 每次只处理 3-8 条新数据 |
| 同步&提交 | 3-4 | rsync + git 操作 |

## 安全管理

- 只追加高度确信的数据（有可靠来源证据）
- 不确定的新店 → 写入 pending-restaurants 待人工审阅
- 营销推广类信息 → 直接丢弃
- 每次变更后运行 rsync 同步 + git push
- 不做大幅删除——闭店店铺标记 closed 而非删除，保留历史记录
- 不满意的评价也值得保留——多元声音是核心价值

## 多Agent挑战-协商机制

### 核心理念

与其让一个人（或一个 AI）设计公平算法，不如让多个不同立场的「专家委员会」来挑战它。
每个 Agent 扮演一个特定的利益相关者角色，从自己的视角找出算法的盲点和漏洞。

### Agent 角色设计

| 角色 | 立场 | 擅长挑战 |
|------|------|---------|
| **本地老饕** 🧓 | 祖辈三代在汕头，最懂"老味道" | 算法太迁就游客口味、时间衰减过于激进、游客评价权重被放大 |
| **外地游客** 🧳 | 第一次来潮汕的北京游客 | 算法偏袒本地人、忽略可及性（环境/服务）、可信度评估不合理 |
| **数据科学家** 📊 | 推荐系统算法工程师 | 样本量置信度、评分分布偏差、冷启动问题、统计方法缺陷 |
| **营销号操盘手** 🎭 | 知道如何操纵评价系统的"坏人" | 反操控盲点、刷分手法、审查周期漏洞 |
| **文化研究者** 📖 | 研究潮汕饮食文化的学者 | 品类差异、地域差异、文化语境缺失、跨品类评分不可比 |
| **公平性审计员** ⚖️ | 第三方 AI 审计 | 系统性偏见、透明度缺乏、少数群体被忽视、人群细分粒度不均 |

### 挑战-协商流程

```
┌──────────────────────────────────────────────────┐
│              第1阶段：挑战提案                     │
│  ├─ 每个Agent加载 FAIRNESS-ALGORITHM.md           │
│  ├─ 加载 restaurant-summary.yaml（看真实数据）      │
│  ├─ 提出 1-2 个具体挑战（理论或数据驱动）            │
│  └─ 挑战必须有论据支持                             │
├──────────────────────────────────────────────────┤
│              第2阶段：公开辩论                     │
│  ├─ 所有挑战汇总展示、Agent依次回应                 │
│  ├─ 互相指出论证的漏洞                             │
│  └─ 至少 3 轮交互                                 │
├──────────────────────────────────────────────────┤
│              第3阶段：共识投票                     │
│  ├─ 🔴 Valid Bug   → 确认为问题，讨论修复方案       │
│  ├─ 🟡 Edge Case   → 边缘案例，记录在案            │
│  └─ 🟢 Not Valid   → 驳回，说明理由                │
├──────────────────────────────────────────────────┤
│              第4阶段：算法更新                     │
│  ├─ 修复方案转化为具体参数/规则变更                  │
│  ├─ 更新 FAIRNESS-ALGORITHM.md                   │
│  ├─ 必要时更新数据结构                              │
│  └─ 记录挑战日志                                   │
└──────────────────────────────────────────────────┘
```

### 挑战输出模板

```
═══════════════════════════════════════════
潮汕美食公平算法 — 第N轮挑战报告
日期: YYYY-MM-DD
═══════════════════════════════════════════

【本期挑战者】
  1. 本地老饕（Local Gourmet）
  2. 外地游客（First-time Tourist）
  ...

【挑战议题】

  🔴 Valid Bug (2个)

  1. 时间衰减参数不合理
     提出者: 本地老饕
     论据: "本地人3年前的评分衰减到0.3，但游客上周的权重1.0"
     辩论摘要: 数据科学家指出本地人评分一致性更高...
     修复方案: 引入 reviewer_type 权重调节系数
     优先级: P0 - 高

  2. ...

  🟡 Edge Case (3个)
  🟢 Not Valid (1个)

【算法变更】
  FAIRNESS-ALGORITHM.md: vX.Y.Z → vX.Y.Z+1
  变更:
  - 引入 reviewer_type 权重调节系数（3.2节）
  - 新增置信区间展示规则（4.5节）
  - 反操控检测增加30天窗口（5.3节）
```

### 挑战日志存储

```
data/challenge-logs/
├── challenge-001-2026-06-11.md   # 第1轮挑战日志
├── challenge-002-2026-06-18.md   # 第2轮挑战日志
└── ...
```

每次挑战结果写入一个 markdown 文件，记录：
- 挑战者名单
- 每个挑战的详细论据和辩论过程
- 投票结果
- 实际算法变更
- 未解决的问题（留待下轮）
