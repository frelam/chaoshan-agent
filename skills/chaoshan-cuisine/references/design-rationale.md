# Chaoshan Cuisine v2 — Design Rationale

## Why v2? (The "no rankings" pivot)

The original v1 design treated the food guide as a curated ranking system — find the "best" restaurants and rank them. The user pushed back in June 2026:

> "不要榜单，不要排序。排序是针对具体用户的，因人而异。"

This was the key insight. A restaurant that's perfect for a 22-year-old Beijing tourist on their first visit to Chaoshan is different from what a 40-year-old local from Shantou would choose. **Rankings are meaningless without context about who you are.**

## v2 Architecture

### Core Files

| File | Purpose |
|------|---------|
| `data/restaurants.yaml` | Raw reviews + per-reviewer demographics |
| `data/restaurant-summary.yaml` | Multi-dimensional aggregated profiles (no ranking) |
| `data/reviewer-profiles.yaml` | Reviewer portrait database (age/hometown/taste/credibility) |
| `data/beef-knowledge.yaml` | Stable beef-cut knowledge (unchanged from v1) |

### Key Design Choices

**1. Reviewer demographics are first-class data.**
Every review must include: hometown (city-level), age_range, type (local/tourist/returning), taste_tags. Without these, personalized recommendation cannot work.

**2. Per-dish scoring, not just overall.**
A restaurant might have a 5-star dish and a 2-star dish. Aggregate scores hide this. Each dish gets its own rating, price, and comment.

**3. Source tracking.**
Every review records `source_type` (self/community/web) and `source_url` for traceability. This prevents data-quality anxiety — you know where each review came from.

**4. Multi-dimensional aggregation.**
`restaurant-summary.yaml` breaks down scores by reviewer type, age group, and hometown. It never outputs a single ranking. The "ranking" is generated dynamically at query time based on the user's profile.

### The Two-Algorithm Architecture

```
Fairness Algorithm (FAIRNESS-ALGORITHM.md)
  — Aggregates all reviews into unbiased store profiles
  — Detects manipulation, preserves minority voices (≥15%)
  — Applies time decay (1y/2y/3y thresholds)
  — Output: multi-dimensional store card with no ranking

Personalization Algorithm (PERSONALIZATION-ALGORITHM.md)
  — Takes user profile as input (hometown/age/taste/companions/budget)
  — Finds similar reviewers from reviewer-profiles.yaml
  — Weighted aggregation by similarity score
  — Output: personalized recommendation + crowd comparison
```

The two algorithms are complementary, not competing. The user sees both a personalized recommendation AND the full crowd picture.

### Self-Evolution Focus

The self-evolve cron job focuses on:
1. Collecting new reviews with full reviewer demographics
2. Updating store status (open/closed/needs-review)
3. Extracting taste_tags from review text
4. Maintaining reviewer-profiles.yaml

It does NOT produce rankings or summaries — those are derived at query time.

### Current State (June 2026)

- Data files have structure but no real data yet (entries: [])
- First real data is expected from the self-evolve cron job
- Claude Code was used to do cross-file consistency checks in initial setup
- The teochew-self-evolve skill was the reference pattern for the cron-driven architecture
