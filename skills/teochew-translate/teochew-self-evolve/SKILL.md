---
name: teochew-self-evolve
version: "1.4.0"
description: "潮汕话 skill 自演进流程 — 每次搜索5个翻译对，每日5次（07:00/10:00/13:00/16:00/20:00），自测验证，数据更新，同步源码，自动提交GitHub。由 5 个 cron job 驱动。"
triggers: ["自演进", "自我学习", "每日学习", "5样本"]
requires:
  min_context: 16384
---

# 潮汕话 Skill 自演进策略

## 整体架构

```
每日5次 (cron jobs: 07:00 / 10:00 / 13:00 / 16:00 / 20:00)
  │
  ├─ 1. 搜索发现: web_search × 2-3 种查询 → 提取约5个翻译对
  ├─ 2. 查重过滤: 检查 dictionary.yaml + slang.yaml 是否已存在
  ├─ 3. **自测验证**: 用 skill 翻译预测 → 对比搜索数据
  │    ├─ **先做借音推理**: 对新词先标出 Teochew 读音，念出来看看是否和已知口语词对得上
  │    ├─ 预测一致 → 标记可信
  │    ├─ 不一致且搜索可靠 → 进入学习更新
  │    └─ 不一致且搜索不可靠 → 丢弃
  ├─ 4. **学习更新**:
  │    ├─ standard → dictionary.yaml (对应分类末尾)
  │    ├─ phonic_only/slang → slang.yaml (phonic_only段末尾)
  │    └─ 不确定 → references/pending-vocab-merge.md
  ├─ 5. version bump: 小版本+1, total_entries 递增
  ├─ 6. rsync 同步源码: → ~/workspace/chaoshan-agent/
  └─ 7. GitHub: git add → commit → push
```

## 搜索策略（6种查询 + 4个备选来源）

### 主策略（web_search，按序执行）

每轮提取 5-15 对：

1. `web_search("潮汕话 常用词汇 100个 普通话对照")`
2. `web_search("潮汕方言日常用语 普通话翻译")`
3. `web_search("潮汕话 入门 常用语")`
4. `web_search("teochew dialect common words mandarin")`
5. `web_search("潮汕话 怎么说 普通话 对照")`
6. `web_search("潮汕方言特色词 释义")`

### ⚠️ 备选来源（web_search 不可用时）

当 web_search 因网络限制超时/返回空时，fallback 到以下可靠来源：

1. **neoTeochew.org JSON 语料库**
   - 地址: `https://neoTeochew.org/words`（含 4307 条语料，JSON 格式 ~4MB）
   - 用法: `curl -sL 'https://neoTeochew.org/words' | jq '.[] | {char: .chinese, mandarin: .mandarin, pengim: .pronunciation}'`
   - 优势: 结构化的潮汕话→普通话对照，有 Peng'im 标注
   - 注意: JSON 可能较大，先 `head -c 10000` 预览结构

2. **learn-teochew GitHub 仓库 (kbseah/learn-teochew)**
   - 地址: `https://raw.githubusercontent.com/kbseah/learn-teochew/main/`
   - 推荐文件: `numbers.md`（数字词汇）、`address.md`（称谓）、`grammar.md`（语法）
   - 用法: `curl -sL 'https://raw.githubusercontent.com/kbseah/learn-teochew/main/numbers.md'`
   - 优势: 标准 Peng'im 标注，学术级准确

3. **GitHub API 搜索相关仓库**
   - 查询: `curl -sL 'https://api.github.com/search/repositories?q=teochew&sort=stars&per_page=10'`
   - 提取有实际语料的仓库 URL 再逐一下载
   - 注意: API 有速率限制（未认证 60 req/h），慎用

4. **mogher.com 潮汕在线词典**
   - 查词: `curl -sL 'https://www.mogher.com/query?utf8=✓&q=[词汇]'`
   - 优势: 逐词查询，反向验证已提取的数据

提取标准：
- 明确的潮汕话 ↔ 普通话对照
- **优先有拼音（Peng'im）标注的** — 发音记录比字面更重要，无拼音的数据尽量不取
- 优先高频日常用词
- 排除过生僻或无可靠来源的
- **排除无发音记录的字面翻译对**（如只有"𠀾=不会"但无拼音 bhoi6 的条目）— 这种数据合入后会污染音标库

## 工具调用限制管理

⚠️ **重要：每次运行的可用工具调用有限（约 50 次），但每次只处理 ~5 条新词，所以完全够用。**

| 阶段 | 估计调用次数 | 建议 |
|------|-------------|------|
| 搜索发现 | 3-5 | 用 1-2 个备选来源获取数据即可 |
| 查重过滤 | 2-3 | 批量读取数据文件做内存校验 |
| 验证&写入 | 5-10 | 每次只处理 ~5 条新词 |
| 同步&提交 | 3-4 | rsync + git 操作 |

## 数据更新规则

### dictionary.yaml 追加
- 找对应 tags 分类末尾
- 保持 YAML 字段顺序: char → mandarin → pengim → example → example_mandarin → tags → note
- 缩进 2 空格

### slang.yaml 追加 (phonic_only)
- 新 id 为下一个序号（当前最大 p6）
- 字段: id → pronunciation → approximate_char → mandarin_meaning → usage → example_teochew → example_mandarin → tags → note

### ⚠️ 借音字的特殊处理
当发现一个词是**借音字**（标准汉字的潮汕读音与字面义完全无关）时：
- 必须在 `note` 字段写明 "借音字，[标准汉字]读[潮汕音]表[实际义]，非字面义"
- 必须保证 Peng'im 发音记录完整，这是借音推理的依据
- 如果搜索到的数据有字面无音标，补上推测的 Peng'im 并在 note 注明
- 例：妻疑 → note: "借音字，'妻疑'读 ci1 ghi5 表'脏'，非字面'妻子怀疑'意"

### version bump
- dictionary.yaml: version 小版本+1, total_entries +N
- slang.yaml: version 小版本+1, total_entries +N
- SKILL.md: version 小版本+1

## 同步命令

```bash
rsync -av ~/.hermes/skills/teochew-translate/ ~/workspace/chaoshan-agent/skills/teochew-translate/
```

## GitHub 提交

有数据变更时执行：
```bash
cd ~/workspace/chaoshan-agent
git add -A
git commit -m "auto: 潮汕话自演进 $(date +%Y-%m-%d) — +N条新增词汇"
git push
```

无变更则跳过。GitHub 已通过 gh CLI 认证（frelam 账号，HTTPS 协议），可直接 push。

## 输出报告格式

```
📊 潮汕话自演进报告 — YYYY-MM-DD

【搜索统计】
  搜索来源: N 个
  提取翻译对: X 个
  去重后新词: Y 个

【验证结果】
  预测一致（已可信）: A 个
  预测不一致 → 学习更新: B 个
  数据不可靠（丢弃）: C 个
  **借音推理发现**: D 个（其中发音与字面义不同）

【数据变更】
  dictionary.yaml: vX.Y.Z → vX.Y.Z' (+N 条)
  slang.yaml: vX.Y.Z → vX.Y.Z' (+N 条)
  pending-merge: N 条待审

【GitHub】
  提交: 是/否
  提交信息: xxx
  仓库: frelam/chaoshan-agent

【新增词汇摘要】
  - XXX (拼音) → 普通话释义
  - ...
```

## 安全管理

- 只追加高度确信的数据（有可靠来源证据）
- 不确定的写入 pending-merge 待人工审阅
- 每次变更后运行 rsync 同步 + git push
- Cron jobs: 56c9a120fa46~56c9a120fa50 (每日07:00/10:00/13:00/16:00/20:00运行，每批5条)
- Companion cron: 9caed8b7894a (每周一4:00 周度consolidation — 审视skill去碎片化)
- repo: frelam/chaoshan-agent (GitHub, gh CLI auth)
