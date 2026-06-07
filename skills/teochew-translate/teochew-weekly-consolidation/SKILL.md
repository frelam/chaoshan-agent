---
name: teochew-weekly-consolidation
version: "1.1.0"
description: "周度审视——总结提炼skill知识库，去碎片化。用Claude Code做重写，保留必要细节。每周一轮。"
triggers: ["周度审视", "consolidation", "知识总结", "去碎片化"]
requires:
  min_context: 32768
---

# 潮汕话 Skill 周度 Consolidated 流程

每周一 4:00 执行一次，审视整个 teochew-translate skill 的知识库，总结提炼，去碎片化。

**如果全景分析后确定没有任何可操作的变更（无重复、无编号错误、无不合理归类），直接输出 "本周无 consolidation 必要，已跳过" 并结束，不要强行修改。**

## 审视范围

```
teochew-translate/
├── SKILL.md              ← 触发词、翻译规则、15个 Few-Shot 示例
├── data/
│   ├── dictionary.yaml   ← 113+ 词汇条目
│   ├── slang.yaml        ← 38+ 俗语/有音无字词
│   ├── grammar.yaml      ← 语法规则表
│   └── examples.yaml     ← 30组例句
└── tests/cases.yaml      ← 15个测试用例（回归线）
```

## 执行步骤

### Step 1: 全景分析

读取所有数据文件，识别碎片化问题：

| 文件 | 检查点 |
|------|--------|
| dictionary.yaml | 是否有重复/相似条目可合并？多个条目是否隐含同一条语法规则？归类是否合理？ |
| slang.yaml | 是否有相近可合并的条目？有音无字词是否已找到标准汉字（可升入 dictionary）？ |
| grammar.yaml | 现有规则能否更简洁？是否有遗漏的语序/否定/疑问规则？ |
| examples.yaml | 例句是否重复/过时？能否更有代表性？ |
| SKILL.md | Few-Shot 是否臃肿？能否替换为更精炼的示例？整体提示词是否太长了？ |

### Step 2: 用 Claude Code 做总结提炼（可选 — 若不可用则跳到 Step 3）

将分析结果 + 数据文件传给 Claude Code 做重写。注意：Claude Code 已配置 DeepSeek v4 后端（ANTHROPIC_BASE_URL），`--print` 模式让它在非交互模式下输出结果。

```bash
cd ~/workspace/chaoshan-agent

# 方式：将分析总结作为 prompt，文件作为 context
claude --print -p "
作为潮汕话专家AI，审视以下技能文件，进行总结提炼、去碎片化。

## 我的分析
[将 Step 1 的分析总结写在这里]

## 原则
1. 可泛化的→提炼为语法规则，删掉冗余条目
2. 有音无字词、特色文化词、特殊用法保留详细记录
3. 相近条目合并，同一知识点不分散记录
4. 不可破坏 tests/cases.yaml 的15个用例覆盖
5. Peng'im 发音记录任何时候不得丢弃或简化声调标注

## 输出格式
请给出具体变更建议，每个文件一个节。
" --model deepseek-v4-pro --add-dir skills/teochew-translate
```

**⚠️ 已知问题 — 退路策略**：
- **Claude Code 可能未登录**：cron 环境下 `claude --print` 会报 "Not logged in" 错误（Claude Code 需要 OAuth 登录，即使后端是 DeepSeek）。此时不要阻塞流程——**直接跳到 Step 3，用自身的分析能力做判断和执行**。
- **`-f` 参数不可用**：某些版本的 claude CLI 不支持 `-f` 传文件。使用 `--add-dir` 代替（让 claude 能看到文件目录）或在 prompt 中嵌入文件摘要。
- 当 Claude Code 不可用时，你的分析能力（Step 1）就是主要的判断依据。碎片化问题通常很明显（重复条目、编号错误等），直接修复即可，不需要外部 AI 确认。

### Step 3: 评估变更建议并执行

对 Step 1 的分析结果（或 Claude Code 的输出，如可用）逐一判断：
- ✅ **明显正确的合并/精简** → 用 patch 或 terminal + sed/Python 执行
- ⚠️ **有风险的变更** → 先确认不破坏 tests/cases.yaml
- ❌ **可能丢失细节的** → 跳过，保留原样

**⚠️ patch 工具的重要陷阱**：当文件被 `read_file` 仅部分读取（使用 offset/limit 参数）后，patch 工具会**静默失败**——返回 "success" 但不写入任何内容，报 warning "was last read with offset/limit pagination (partial view)"。为避免此问题：
- 策略 A：用 `read_file` 无 offset/limit 读取整个文件后，再用 patch（适合小文件）
- **策略 B（推荐）**：直接用 `terminal` + `sed`/`Python` 做文本替换，跳过 patch 工具。对大文件（如 dictionary.yaml 2200+行）这更可靠。
- 策略 C：用 `write_file` 重写整个文件（风险高，容易丢失数据）

### Step 4: YAML 验证 + 回归测试

每次变更后，验证 YAML 格式正确性并确认测试用例仍有效：

```bash
# YAML 格式验证
cd ~/workspace/chaoshan-agent
python3 -c "import yaml; [exit(1) for f in ['dictionary.yaml','slang.yaml','grammar.yaml','examples.yaml'] if not yaml.safe_load(open(f'skills/teochew-translate/data/{f}'))]"

# 测试用例验证（手动检查 15 个用例的 key 要素）
# 重点确认：人称代词映射、语序转换、否定词选择
```

### Step 5: 同步 + 提交

```bash
# ⚠️ 注意 rsync 方向：
# 如果你直接在 ~/workspace/chaoshan-agent/（源码目录）编辑文件，方向是 source → hermes：
rsync -av ~/workspace/chaoshan-agent/skills/teochew-translate/ ~/.hermes/skills/teochew-translate/

# 如果你在 ~/.hermes/skills/（运行目录）编辑文件，方向是 hermes → source：
rsync -av ~/.hermes/skills/teochew-translate/ ~/workspace/chaoshan-agent/skills/teochew-translate/

# 两个目录必须始终保持一致。分不清方向时，先检查哪边有新修改：
diff -q ~/.hermes/skills/teochew-translate/data/dictionary.yaml ~/workspace/chaoshan-agent/skills/teochew-translate/data/dictionary.yaml

cd ~/workspace/chaoshan-agent
git add -A
git diff --cached --stat  # 确认变更内容后再提交
git commit -m "weekly: 潮汕话skill周度consolidation — $(date +%Y-%m-%d)"
git push
```

## 什么能动，什么不能动

### ✅ 可以总结提炼
- dictionary.yaml 中多个同义词条目可以合并
- 多个相似例句可以替换为一个更有代表性的
- Few-Shot 中内容重复的示例可以替换
- grammar.yaml 中啰嗦的规则描述可以精简

### ⛔ 必须保留细节
- 有音无字词（niam5, gog8, ziêg4, koi1, sah8, ko3, 妻疑 等）— 不能被抽象化
- **每个词的 Peng'im 发音记录** — 音标是潮汕话的灵魂，任何时候不得丢弃或简化声调标注
- **借音关系** — 标准汉字在潮汕话中被借用的发音≠普通话发音，必须保留两者的对应关系
- **借音推理能力** — SKILL.md 中的借音推理启发式（念出音试试）不可被简化或移除
- 文化专词（粿条、蚝烙、工夫茶等）— 不能简化为普通翻译
- 粗口詈语记录 — 要保持学术性留档
- 区域变体标注（潮州/汕头/揭阳/汕尾差异）

## Cron Job

```
job_id: 9caed8b7894a
schedule: 0 4 * * 1 (每周一 4:00)
skills: [teochew-translate, teochew-weekly-consolidation]
companion: 56c9a120fa45 (每日3:00 自演进学习 — 先学50条，周一再审视整理)
```

## 输出报告格式

```
📋 潮汕话周度 Consolidation 报告 — YYYY-MM-DD

【分析摘要】
  总条目数变更: dictionary NN→NN', slang NN→NN'
  合并条目: N 条
  提炼为规则: N 条
  删除冗余: N 条
  保留原样: N 条

【具体变更】
  - dictionary.yaml: ...
  - slang.yaml: ...
  - grammar.yaml: ...
  - examples.yaml: ...
  - SKILL.md: ...

【回归验证】
  测试用例: 15/15 ✅

【GitHub】
  提交: ed5774e..xxxxxxx
```
