---
name: cuisine-self-evolve
version: "2.0.0"
description: "潮汕美食自演进策略 v2 — 持续收集真实评价 + 评价者画像，构建公平充足的信息库。支撑个性化推荐算法。覆盖牛肉火锅/粿条汤/蚝烙/肠粉/卤鹅/砂锅粥等品类。"
triggers:
  - "美食自演进"
  - "美食更新"
  - "美食时效性"
  - "发现新店"
  - "闭店检查"
  - "cuisine self-evolve"
  - "food update"
  - "评价收集"
requires:
  min_context: 16384
skills:
  - chaoshan-cuisine
data:
  - ../data/restaurants.yaml
  - ../data/restaurant-summary.yaml
  - ../data/reviewer-profiles.yaml
  - data/search-sources.md
  - data/restaurant-check-template.md
---

# 潮汕美食 Skill 自演进策略

## 整体架构

```
每周1次 (cron: 每周一 06:00)   ← 常规更新轮
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
