# 潮汕美食评价数据库 — 架构说明

## 为什么需要 SQLite DB？（YAML 之外的另一层）

原有的 YAML 系统（restaurants.yaml / restaurant-summary.yaml）是为**自演进批量收集**设计的：
- 每周一次 cron 批量追加
- 经过交叉验证、去营销处理
- 有版本号和元信息管理

但微信渠道来的实时评价**不适合直接写 YAML**：
- 一条消息来一次，没有"批量追加"的时机
- 评价者档案需要逐步积累，不是一次性写好的
- 需要快速 FTS5 全文检索（YAML 无全文索引）
- 需要聚合查询（AVG/COUNT/GROUP BY）——YAML 全靠 Python 在内存算

所以：**SQLite 存实时消息，YAML 存经过验证的批量数据**。

## 双存储架构

```
来源              存储             聚合/查询
────────────────────────────────────────────────
微信消息 ──────→ SQLite reviews.db ──→ 实时推荐
自演进挖掘 ────→ YAML restaurants.yaml ──→ 公平算法聚合
                                             │
                                             ↓
                                       统一输出给用户
```

查询优先级：SQLite > YAML（新鲜度优先）。数据不足时回退。

## 核心表设计

### reviews（核心表）

每条评价独立存在，不覆盖、不合并。同一个人对同一家店去多次，每次都是新记录。

关键字段设计考量：

| 字段 | 为什么这么设计 |
|------|--------------|
| `overall_rating CHECK(1-5)` | 限制范围防止脏数据，5分制符合大众点评习惯 |
| `would_revisit INTEGER` | 比评分更真实的指标——愿意回头比高分更有说服力 |
| `pros / cons TEXT (JSON)` | 分离好差评方便聚合查询，JSON 数组保持灵活 |
| `price_level TEXT` | 枚举值而非具体数字——人均价格用户常模糊表述 |
| `source_message_id` | 可溯源到原始微信消息，审核/纠错用 |
| `is_derived INTEGER` | 区分"用户主动评价" vs "从闲聊中提取" |

### dishes（菜品评价）

独立表而非 JSON 字段的原因：
- 可以按菜品聚合（"大家都推荐这家店的脖仁"）
- 支持跨店菜品对比（"A 店的脖仁 vs B 店的脖仁"）
- 统计维度更多（推荐率/平均分/价格分布）

### reviewers（评价者档案）

`wechat_user_id` 作为唯一标识，跨会话持久化。
画像字段逐步填充，不留空（NULL = 未知）。不要一次性问用户太多信息。

可信度 `reliability` 保留供未来使用——目前默认 1.0，后续可根据：
- 历史评价质量（具体 vs 空洞）
- 评分与大众一致性
- 评价数量

等维度动态调整。

## 常用查询模式

### 1. 按地区/品类推荐

```python
# 汕头金平区的牛肉火锅，前 5 名
get_recommendations(district="金平区", cuisine_type="牛肉火锅", limit=5)
```

### 2. 搜索某家店

```python
# 模糊匹配店名/地址
search_restaurants("八合里")
```

### 3. 查看某家店的完整信息

```python
# 含统计 + 最近 3 条评价
get_restaurant_card(restaurant_id=1)
```

### 4. 按评价内容模糊搜索

```python
# FTS5 全文检索
search_reviews_text("入口即化 牛肉")
```

### 5. 个性化推荐（未来）

```python
# 找到和某用户画像相似的评价者的高评分店铺
# 当前 DB 层面暂未实现——需在应用层根据 reviewer.type/hometown/age_group 加权
```

## 预置标签说明

20 个预置标签分 5 类：
- **reputation**: 老店/新店/游客打卡/本地人常去
- **service**: 排队/服务好/服务一般
- **price**: 物美价廉/价格偏高
- **atmosphere**: 环境好/环境一般/无空调
- **convenience**: 停车方便/停车困难/外卖可点
- **experience**: 隐藏菜单/适合一人食/适合聚会/适合宵夜/踩雷

不足时自动 INSERT OR IGNORE，不限制只能从预置选。

## DB 文件

```
~/.hermes/skills/chaoshan-cuisine/data/
├── reviews.db          # SQLite 数据库文件
├── schema.sql          # 建表脚本（用于重新创建/迁移）
├── db_helper.py        # Python 操作模块（推荐直接用这个）
└── ...
```

`schema.sql` 和 `db_helper.py` 在一起——`init_db()` 会自动读取 schema 文件建表。不要单独移动。
