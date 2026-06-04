---
name: teochew-self-evolve
version: "1.1.0"
description: "潮汕话 skill 自演进流程 — 每日搜索50个翻译对，自测验证，数据更新，同步源码，自动提交GitHub。由 cron job 驱动。"
triggers: ["自演进", "自我学习", "每日学习", "50样本"]
requires:
  min_context: 16384
---

# 潮汕话 Skill 自演进策略

## 整体架构

```
每日运行 (cron job: 0 10 * * *)
  │
  ├─ 1. 搜索发现: web_search × 6 种查询 → 提取约50个翻译对
  ├─ 2. 查重过滤: 检查 dictionary.yaml + slang.yaml 是否已存在
  ├─ 3. 自测验证: 用 skill 翻译预测 → 对比搜索数据
  │    ├─ 一致 → 标记可信
  │    ├─ 不一致且搜索可靠 → 进入学习更新
  │    └─ 不一致且搜索不可靠 → 丢弃
  ├─ 4. 学习更新:
  │    ├─ standard → dictionary.yaml (对应分类末尾)
  │    ├─ phonic_only/slang → slang.yaml (phonic_only段末尾)
  │    └─ 不确定 → references/pending-vocab-merge.md
  ├─ 5. version bump: 小版本+1, total_entries 递增
  ├─ 6. rsync 同步源码: → ~/workspace/chaoshan-agent/
  └─ 7. GitHub: git add → commit → push
```

## 搜索策略（6种查询）

依次执行，每轮提取 5-15 对：

1. `web_search("潮汕话 常用词汇 100个 普通话对照")`
2. `web_search("潮汕方言日常用语 普通话翻译")`
3. `web_search("潮汕话 入门 常用语")`
4. `web_search("teochew dialect common words mandarin")`
5. `web_search("潮汕话 怎么说 普通话 对照")`
6. `web_search("潮汕方言特色词 释义")`

提取标准：
- 明确的潮汕话 ↔ 普通话对照
- 优先有拼音（Peng'im）标注的
- 优先高频日常用词
- 排除过生僻或无可靠来源的

## 数据更新规则

### dictionary.yaml 追加
- 找对应 tags 分类末尾
- 保持 YAML 字段顺序: char → mandarin → pengim → example → example_mandarin → tags → note
- 缩进 2 空格

### slang.yaml 追加 (phonic_only)
- 新 id 为下一个序号（当前最大 p6）
- 字段: id → pronunciation → approximate_char → mandarin_meaning → usage → example_teochew → example_mandarin → tags → note

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
- Cron job ID: 56c9a120fa45 (每天10:00运行)
- repo: frelam/chaoshan-agent (GitHub, gh CLI auth)
