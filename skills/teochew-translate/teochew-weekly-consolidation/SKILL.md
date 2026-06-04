---
name: teochew-weekly-consolidation
version: "1.0.0"
description: "周度审视——总结提炼skill知识库，去碎片化。用Claude Code做重写，保留必要细节。每周一轮。"
triggers: ["周度审视", "consolidation", "知识总结", "去碎片化"]
requires:
  min_context: 32768
---

# 潮汕话 Skill 周度 Consolidated 流程

每周执行一次，审视整个 teochew-translate skill 的知识库，总结提炼，去碎片化。

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

### Step 2: 用 Claude Code 做总结提炼

将分析结果 + 数据文件传给 Claude Code 做重写：

```bash
cd ~/workspace/chaoshan-agent

# 方式：将分析总结作为 prompt，文件作为 context
claude --print -p "
作为潮汕话专家AI，审视以下技能文件，进行总结提炼、去碎片化。

## 我的分析
[将 Step 1 的分析总结写在这里]

## 数据文件内容
[附上各文件的摘要/关键内容]

## 原则
1. 可泛化的→提炼为语法规则，删掉冗余条目
2. 有音无字词、特色文化词、特殊用法保留详细记录
3. 相近条目合并，同一知识点不分散记录
4. Few-Shot 精简替换重复的、增加更多样化的
5. 不可破坏 tests/cases.yaml 的15个用例覆盖

## 输出格式
请给出具体变更建议，格式：
### dictionary.yaml
- 合并/删除/移动: ...

### slang.yaml
- 合并/升级/删除: ...

### grammar.yaml  
- 新增/简化/修改: ...

### SKILL.md
- 精简/替换/重组: ...

### examples.yaml
- 替换/合并: ...
" --model deepseek-v4-pro -f skills/teochew-translate/SKILL.md -f skills/teochew-translate/data/dictionary.yaml -f skills/teochew-translate/data/slang.yaml -f skills/teochew-translate/data/grammar.yaml -f skills/teochew-translate/data/examples.yaml -f skills/teochew-translate/tests/cases.yaml
```

### Step 3: 评估变更建议

对 Claude Code 的输出逐一判断：
- ✅ **明显正确的合并/精简** → 用 patch 或 write_file 执行
- ⚠️ **有风险的变更** → 先跑 tests/cases.yaml 确认不破坏
- ❌ **可能丢失细节的** → 跳过，保留原样

### Step 4: 回归测试

每次变更后手动验证关键测试点。最后整体检查 tests/cases.yaml 全部 15 个用例是否仍能通过。

### Step 5: 同步 + 提交

```bash
rsync -av ~/.hermes/skills/teochew-translate/ ~/workspace/chaoshan-agent/skills/teochew-translate/
cd ~/workspace/chaoshan-agent
git add -A
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
- 文化专词（粿条、蚝烙、工夫茶等）— 不能简化为普通翻译
- 粗口詈语记录 — 要保持学术性留档
- 区域变体标注（潮州/汕头/揭阳/汕尾差异）

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
