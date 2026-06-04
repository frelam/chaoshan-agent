# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Chaoshan Agent — 潮汕文化 Agent。A collection of self-evolving AI skills for Chaoshan (Teochew) cultural heritage, delivered as **Hermes Agent Skills**. Currently the first skill, `teochew-translate`, provides **Teochew ↔ Mandarin** bidirectional translation with Peng'im romanization, grammar conversion, and cultural annotation. More skills (chaoshan-cuisine, gongfu-tea, overseas-reunion) are planned.

Skills consist of structured YAML knowledge bases and SKILL.md prompt definitions, not executable code.

The project has **two cron-driven pipelines**: daily self-evolution (learn ~50 new vocabulary pairs from web searches, verify, append to data files) and weekly consolidation (Claude Code-driven review to de-fragment knowledge, merge duplicates, extract grammar rules).

## Architecture

```
skills/teochew-translate/
├── SKILL.md                # Skill definition + system prompt (YAML front matter + Markdown body)
├── data/
│   ├── dictionary.yaml     # 115+ vocabulary entries with Peng'im, examples, category tags
│   ├── grammar.yaml        # Grammar rules: word order, negation, comparatives, questions
│   ├── examples.yaml       # 30 annotated translation example pairs
│   └── slang.yaml          # 38+ slang, proverbs, phonic-only words, swear words
├── tests/cases.yaml        # 15 regression test cases (3 difficulty levels)
├── teochew-self-evolve/    # Daily 50-sample learning pipeline (SKILL.md)
├── teochew-weekly-consolidation/  # Weekly de-fragmentation pipeline (SKILL.md)
└── references/             # Pending merges, TTS reference docs
```

**Key design principles:**
- Framework-decoupled: skills are pure data + prompts, Hermes just scans `SKILL.md` files
- Skills are self-contained directories with their own `data/` and `tests/`
- Knowledge is YAML (human-readable, comment-friendly, clean git diffs)
- `~/.hermes/skills/teochew-translate/` is the runtime directory; this repo is the source-of-truth. Changes must be synced both ways.

## Commands

```bash
# Install the skill to Hermes Agent
bash install.sh

# Run Claude Code with the Teochew prompt (uses DeepSeek v4 backend)
bash run-teochew.sh

# Run Claude Code manually with custom prompt files
claude -p "$(cat teochew-prompt.txt)" --model deepseek-v4-pro

# Run with prompt + data files as context
claude -p "$(cat teochew-prompt.txt)" -f skills/teochew-translate/SKILL.md \
  -f skills/teochew-translate/data/dictionary.yaml \
  -f skills/teochew-translate/data/slang.yaml

# rsync from Hermes runtime dir to source repo (after auto-evolution modifies data)
rsync -av ~/.hermes/skills/teochew-translate/ ~/workspace/chaoshan-agent/skills/teochew-translate/

# rsync from source repo to Hermes runtime dir (after manual edits)
rsync -av ~/workspace/chaoshan-agent/skills/teochew-translate/ ~/.hermes/skills/teochew-translate/
```

There is no build step, no linter, and no test runner — this is a structured knowledge + prompt project, not a code project. Translation quality is verified by running through the 15 cases in `tests/cases.yaml` manually with Claude Code.

## LLM Backend

Uses **DeepSeek v4 Pro** via the Anthropic-compatible API (`ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic`). The model is set via `ANTHROPIC_MODEL=deepseek-v4-pro[1m]`. API key is read from `~/.bashrc` (`DEEPSEEK_API_KEY`). The `run_claude.py` script encapsulates this setup for automated (cron) runs.

## Data File Conventions

All YAML data files follow a consistent structure:

```yaml
meta:
  name: ...
  version: "X.Y.Z"     # Semantic versioning; patch bump on corrections/additions
  total_entries: N+
  categories: [...]

entries:
  - char: 潮汕话        # Always present in dictionary
    mandarin: 普通话
    pengim: peng1 im2   # Always with tone numbers 1-8
    example: ...        # Teochew example
    example_mandarin: ...
    tags: [category, ...]
    note: ...           # Optional
```

- **dictionary.yaml**: Standard vocabulary — 2-space YAML indent, fields in canonical order: `char → mandarin → pengim → example → example_mandarin → tags → note`
- **slang.yaml**: Special expressions — phonic-only words use `phonic_only:` sub-list with `id: pN`, pros/verbs use flat entries
- **grammar.yaml**: Grammar rules in structured tables
- **examples.yaml**: Translation pairs with `id`, `category`, `grammar_points`
- **tests/cases.yaml**: Regression cases with `id`, `test_type`, `difficulty`, `expected_output`, `focus`

When modifying data files from user corrections, always bump the `meta.version` patch number and update `total_entries` if entries are added/removed.

## Self-Evolution Pipelines

Two cron jobs (managed via Claude Code's CronCreate) drive automated knowledge growth:

| Job | Schedule | Purpose |
|-----|----------|---------|
| `56c9a120fa45` | Daily 3:00 | Search web for 50 Teochew-Mandarin pairs, deduplicate, self-test, append to data files, git push |
| `9caed8b7894a` | Weekly Mon 4:00 | Load all data files into Claude Code for de-fragmentation review, merge duplicates, extract rules |

The daily pipeline writes uncertain findings to `references/pending-vocab-merge.md` rather than polluting the dictionary.

## Preservation Rules (Weekly Consolidation)

When consolidating/simplifying data, these must **never** be abstracted away:
- Peng'im pronunciation with tone numbers — the soul of Teochew
- Phonic-only words (有音无字: niam5, gog8, ziêg4, koi1, ko3, ci1-ghi5, etc.)
- Borrowed-character relationships (借音字 — standard characters used for sound, not meaning)
- The 借音推理 heuristic in SKILL.md (read characters in Teochew to guess meaning from sound)
- Cultural specialty terms (粿条, 蚝烙, 工夫茶)
- Swear word/vulgarity records (academic documentation)
- Regional variant annotations (潮州/汕头/揭阳/汕尾)

## Git Workflow

- Conventional commits: `feat:`, `fix:`, `docs:`, `auto:`, `weekly:`
- Squash-merge to main via PR
- Auto-commits from the daily pipeline use format: `auto: 潮汕话自演进 YYYY-MM-DD — +N条新增词汇`
- Weekly consolidation commits: `weekly: 潮汕话skill周度consolidation — YYYY-MM-DD`
- Remote: `origin https://github.com/frelam/chaoshan-agent.git`
- Branch before manual changes; auto-evolution commits directly to main
