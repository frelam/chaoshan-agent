# ARCHITECTURE.md — 潮汕 Agent 技能仓库

> 基于 Hermes Agent 框架的潮汕文化技能集合，每个能力一个 skill，即装即用。

## 设计原则

| 原则 | 说明 |
|------|------|
| **框架解耦** | 不 fork Hermes，不依赖特定版本；skills 是纯数据+prompt，框架升级不受影响 |
| **技能独立** | 每个 skill 是一个目录，自包含 SKILL.md + data/ + tests/ |
| **知识开源** | 知识数据用 Markdown/YAML 维护，GitHub PR 共建 |
| **模型可配** | API endpoint/model 通过 SKILL.md 声明需求，用户自己的 Hermes 配置解析 |
| **零安装** | `cp -r skills/<name> ~/.hermes/skills/` 即用 |

---

## 项目结构

```
chaoshan-agent/
├── ARCHITECTURE.md           # 本文件
├── README.md                 # 项目简介、快速开始
├── LICENSE                   # Apache 2.0
│
├── skills/                   # ★ 技能仓库（每个目录 = 一个 skill）
│   ├── teochew-translate/    # 潮汕话翻译
│   │   ├── SKILL.md          #   技能定义 + prompt
│   │   ├── data/
│   │   │   ├── dictionary.yaml   # 潮汕话词典
│   │   │   ├── grammar.yaml      # 语法规则
│   │   │   └── examples.yaml     # 例句对
│   │   ├── tests/
│   │   │   └── cases.yaml        # 测试用例
│   │   └── README.md             # 技能说明
│   │
│   ├── overseas-reunion/     # 华侨寻亲
│   │   ├── SKILL.md
│   │   ├── data/
│   │   │   ├── village-registry.yaml  # 村落登记
│   │   │   ├── surname-map.yaml       # 姓氏分布
│   │   │   └── inquiry-template.yaml  # 寻亲表格模板
│   │   ├── tests/
│   │   └── README.md
│   │
│   ├── chaoshan-cuisine/     # 潮汕美食评价
│   │   ├── SKILL.md
│   │   ├── data/
│   │   │   ├── dishes.yaml         # 菜品库（做法、口味、典故）
│   │   │   ├── restaurants.yaml    # 老店名录
│   │   │   └── flavor-wheel.yaml   # 风味轮
│   │   ├── tests/
│   │   └── README.md
│   │
│   ├── gongfu-tea/           # 工夫茶
│   │   ├── SKILL.md
│   │   ├── data/
│   │   │   ├── tea-varieties.yaml
│   │   │   ├── etiquette.yaml
│   │   │   └── tools.yaml
│   │   ├── tests/
│   │   └── README.md
│   │
│   └── _template/            # 技能模板（新建 skill 时复制）
│       ├── SKILL.md
│       ├── data/
│       ├── tests/
│       └── README.md
│
├── cli/                      # 命令行辅助工具
│   ├── install.sh            # 一键安装指定 skill 到 ~/.hermes/skills/
│   └── validate.py           # 校验 SKILL.md 格式
│
├── docs/
│   ├── CONTRIBUTING.md       # 贡献指南
│   └── skill-spec.md         # SKILL.md 规范详细说明
│
└── .github/
    ├── workflows/
    │   └── validate.yml     # CI：校验所有 skill 格式
    └── PULL_REQUEST_TEMPLATE.md
```

---

## SKILL.md 规范

每个 `skills/<name>/SKILL.md` 是 Hermes 框架加载的技能入口。格式如下：

```markdown
---
# SKILL.md — 技能元数据 + Prompt 模板
# 此文件为 YAML front matter + Markdown body 结构
# Hermes 解析 front matter 注册技能，body 为 system prompt

name: teochew-translate
version: "1.0.0"
description: "潮汕话 ↔ 普通话/英语 双向翻译"
author: "chaoshan-agent contributors"
license: "Apache-2.0"

# 模型需求（声明式，由 Hermes 配置映射）
requires:
  min_context: 8192          # 最小上下文窗口
  preferred_model: null      # null 表示不强制，继承用户配置
  tools: []                  # 需要的 MCP 工具（无则为 []）

# 关键词触发（Hermes 根据匹配度路由到该 skill）
triggers:
  - "潮汕话"
  - "翻译"
  - "teochew"
  - "潮语"
  - "呾"

# 依赖的其他 skill（可选）
depends: []

# 知识文件（相对于本 skill 目录）
data:
  - data/dictionary.yaml
  - data/grammar.yaml
  - data/examples.yaml
---

你是潮汕话翻译助手，精通潮州话（Teochew / 潮语）。

## 知识来源
从以下数据文件获取翻译知识：
- `data/dictionary.yaml`：词汇对照表
- `data/grammar.yaml`：语法规则
- `data/examples.yaml`：例句对照

## 翻译规则
1. 先判断输入是潮汕话还是目标语言
2. 查阅 dictionary.yaml 逐词翻译
3. 对照 grammar.yaml 调整语序
4. 参考 examples.yaml 验证自然度
5. 输出格式：原文 → 译文，附注音（潮州话拼音方案 Peng'im）

## 示例
- 输入「汝食饱未？」→ "你吃饭了吗？" (le² ziah⁸ ba² bhuē⁷?)
- 输入"你好" → 「汝好」(le² ho²)
```

### 格式规范

| 组件 | 说明 |
|------|------|
| **YAML front matter** | 机器可读元数据，Hermes 解析后注册 skill |
| **Markdown body** | 自然语言 system prompt，注入 LLM 上下文 |
| **`data/` 文件** | 结构化知识，YAML 或 Markdown，LLM 可读取 |
| **`tests/` 文件** | 测试用例，CI 自动运行 `validate.py` |

### 数据文件规范

```yaml
# data/dictionary.yaml 示例
# 每条记录含：字/词、潮拼、释义、例句
- char: "食"
  pengim: "ziah⁸"
  meaning: "吃"
  example: "食饭 (吃饭)"
  tags: [verb, daily]

- char: "汝"
  pengim: "le²"
  meaning: "你"
  example: "汝好 (你好)"
  tags: [pronoun]
```

> 数据用 YAML 而非 JSON：人类可读、注释友好、Git diff 清晰。

---

## 知识数据开源共建方案

### 数据层

```
每个 skill 的 data/ 目录 = 该领域知识库
数据格式 = YAML（结构化） + Markdown（叙述性）
```

### 共建流程

```
[用户] → fork 仓库 → 编辑 data/*.yaml → 运行 validate.py → PR → CI 校验 → 审核合并
```

### 数据贡献入口（按难度分级）

| 级别 | 内容 | 文件 |
|------|------|------|
| 🟢 入门 | 补充词汇、例句 | `data/dictionary.yaml` |
| 🟡 进阶 | 补充语法规则、风味描述 | `data/grammar.yaml` |
| 🔴 深度 | 新建 skill、设计数据模型 | `skills/<new>/` |

### 数据质量要求

- YAML 格式合法（CI 自动检查）
- 每条数据有 `source` 字段标注出处（古籍/口述/网页）
- 多人贡献同一文件以追加为主，冲突时 maintainer 判定

### 溯源字段模板

```yaml
- char: "工夫茶"
  pengim: "gang¹ hu¹ dê⁵"
  meaning: "潮汕工夫茶，中国茶道活化石"
  source:
    type: book
    title: "潮汕工夫茶话"
    author: "XXX"
    page: 42
  contributor: "@github-user"
  date: "2026-06-03"
```

---

## 用户使用流程

### 第一步：安装 Hermes Agent

```bash
# 安装 Hermes（一次性）
pip install hermes-agent
hermes init  # 创建 ~/.hermes/ 配置目录
```

### 第二步：配置模型 API

```bash
# 编辑 ~/.hermes/config.yaml
# 或通过环境变量
export HERMES_API_URL="https://api.openai.com/v1"
export HERMES_MODEL="gpt-4o"
export HERMES_API_KEY="sk-xxx"
```

### 第三步：安装潮汕技能

```bash
# 方式 A：克隆仓库，复制技能
git clone https://github.com/chaoshan/chaoshan-agent.git
cd chaoshan-agent
./cli/install.sh teochew-translate    # 安装指定 skill
./cli/install.sh --all                # 安装全部 skill

# 方式 B：从 release 下载单个 skill 压缩包
hermes skill install https://github.com/chaoshan/chaoshan-agent/releases/download/v1.0/teochew-translate.zip
```

### 第四步：使用

```bash
# 交互模式
hermes chat
# > 帮我翻译"汝食饱未？"

# 单次查询
hermes ask "潮州工夫茶怎么泡？"
```

---

## 贡献指南（摘要）

详见 [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md)。

### 贡献技能

```bash
# 1. Fork 仓库
# 2. 从模板创建新 skill
cp -r skills/_template skills/my-new-skill

# 3. 编辑
vim skills/my-new-skill/SKILL.md
vim skills/my-new-skill/data/*.yaml
vim skills/my-new-skill/tests/cases.yaml

# 4. 校验
python cli/validate.py skills/my-new-skill

# 5. 提交 PR
git checkout -b feat/my-new-skill
git add skills/my-new-skill
git commit -m "feat: add my-new-skill"
gh pr create
```

### 贡献数据

```bash
# 1. 直接 GitHub Web 编辑 data/*.yaml
# 2. 或本地编辑后提 PR
git checkout -b data/add-teochew-words
vim skills/teochew-translate/data/dictionary.yaml
python cli/validate.py skills/teochew-translate
git commit -m "feat: add 20 teochew vocabulary entries"
gh pr create
```

### 审核标准

- [ ] SKILL.md front matter 合法
- [ ] 数据文件 YAML 合法
- [ ] 测试用例通过
- [ ] 有 source 溯源
- [ ] 不包含个人信息（寻亲数据除外且需脱敏）

---

## Hermes Agent 集成方式

### 框架如何加载 Skill

```
~/.hermes/
├── config.yaml          # 用户配置（模型、API）
├── skills/              # ★ Hermes 扫描此目录
│   ├── teochew-translate/
│   │   └── SKILL.md     #   发现并注册
│   ├── overseas-reunion/
│   │   └── SKILL.md
│   └── ...
└── cache/               # 运行时缓存
```

Hermes 启动时：
1. 扫描 `~/.hermes/skills/*/SKILL.md`
2. 解析 front matter，注册 skill name + triggers
3. 用户输入 → 匹配 triggers → 注入对应 SKILL.md body 作为 system prompt
4. 如果 `data:` 字段非空，将数据文件内容追加到 context

### 与 Hermes 的解耦方式

| 耦合点 | 解耦策略 |
|--------|----------|
| **技能注册** | 遵循 Hermes 的 SKILL.md 扫描约定；不修改 Hermes 源码 |
| **模型调用** | 不在 SKILL.md 里写死 API；由 `~/.hermes/config.yaml` 统一管理 |
| **版本依赖** | SKILL.md 只声明 `min_context` 等能力需求，不依赖特定 framework 版本 |
| **工具调用** | 如需 MCP 工具，在 `requires.tools` 声明；Hermes 按名匹配已配置的工具 |

### 安装脚本逻辑

```
./cli/install.sh teochew-translate

执行流程：
1. 检查 ~/.hermes/skills/ 是否存在（不存在则 mkdir）
2. 检查目标 skill 是否已安装（已安装则提示覆盖确认）
3. cp -r skills/<name> ~/.hermes/skills/<name>
4. 输出：✅ teochew-translate 已安装到 ~/.hermes/skills/
5. 提示：hermes chat 中尝试说"潮汕话翻译"即可触发
```

### 版本兼容性

- SKILL.md 规范遵循语义化版本（semver）
- 这个仓库只定义技能内容，不发布 PyPI 包
- 技能版本与框架版本独立演进
- 当 Hermes 的 SKILL.md 规范 Breaking change 时，更新 `skills/_template/` 并发布新版本

---

## FAQ

**Q: 和直接写 prompt 有什么区别？**
A: Skill = 结构化 prompt + 知识数据 + 测试用例 + 社区维护。知识持续更新，质量有 CI 保证。

**Q: 必须用 Hermes 吗？**
A: 当前 target Hermes，但 SKILL.md 格式足够通用，换成其他支持 "system prompt 注入" 的框架只需改加载层。

**Q: 数据贡献会接受 AI 生成的吗？**
A: 接受但必须标注 `source: ai-generated`，且人工审核通过。优先真人贡献的一手知识。

---

*潮汕文化，开源传承。*
