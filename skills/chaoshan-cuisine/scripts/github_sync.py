#!/usr/bin/env python3
"""
GitHub Sync Script for Chaoshan Cuisine Skill

Pushes local changes (SKILL.md, data YAML files, scripts, etc.) to the
frelam/chaoshan-agent GitHub repo via gh API (GFW-safe).

Usage:
    python scripts/github_sync.py

What gets synced:
    - SKILL.md
    - data/*.yaml (restaurants, restaurant-summary, beef-knowledge, reviewer-profiles)
    - scripts/*.py
    - docs/*.md
    - references/*.md
    - tests/*.py
    - cuisine-self-evolve/SKILL.md
    - README.md

NOT synced (local-only):
    - data/reviews.db (SQLite runtime DB with WeChat user IDs)
    - __pycache__/, *.pyc, .DS_Store, Thumbs.db
"""

import json
import base64
import os
import sys
import glob
import subprocess
import hashlib
from pathlib import Path

REPO = "frelam/chaoshan-agent"
BRANCH = "main"
SKILL_DIR = Path(__file__).resolve().parent.parent  # chaoshan-cuisine root
REPO_PREFIX = "skills/chaoshan-cuisine"

# Files/dirs to sync (relative to SKILL_DIR)
INCLUDED_PATTERNS = [
    "SKILL.md",
    "README.md",
    "data/*.yaml",
    "data/schema.sql",
    "data/db_helper.py",
    "data/challenge-logs/*.md",
    "scripts/*.py",
    "docs/*.md",
    "references/*.md",
    "tests/*.py",
    "cuisine-self-evolve/SKILL.md",
]

EXCLUDED_PATTERNS = [
    "data/reviews.db",
    "data/reviews.db-journal",
    "data/reviews.db-wal",
    "data/reviews.db-shm",
    "__pycache__/",
    "*.pyc",
    ".DS_Store",
    "Thumbs.db",
]


def is_excluded(path: Path) -> bool:
    """Check if path matches any exclusion pattern."""
    rel = str(path.relative_to(SKILL_DIR))
    for pat in EXCLUDED_PATTERNS:
        if pat.endswith("/"):
            if pat.rstrip("/") in rel or rel.startswith(pat):
                return True
        elif glob.fnmatch.fnmatch(rel, pat):
            return True
    return False


def collect_files() -> list[tuple[str, Path]]:
    """Collect (repo_path, local_path) pairs for all files to sync."""
    files = []
    for pattern in INCLUDED_PATTERNS:
        for path in sorted(SKILL_DIR.glob(pattern)):
            if path.is_file() and not is_excluded(path):
                repo_path = f"{REPO_PREFIX}/{path.relative_to(SKILL_DIR).as_posix()}"
                files.append((repo_path, path))
    return files


def gh_api(method: str, path: str, data: dict = None) -> dict:
    """Call GitHub API via gh CLI."""
    cmd = ["gh", "api", "-X", method, path]
    input_data = json.dumps(data) if data else None
    if input_data:
        cmd.extend(["--input", "-"])
    result = subprocess.run(
        cmd, input=input_data, capture_output=True, text=True, timeout=60
    )
    if result.returncode != 0:
        raise RuntimeError(f"gh api failed: {result.stderr[:500]}")
    if result.stdout.strip():
        return json.loads(result.stdout)
    return {}


def get_remote_file_sha(repo_path: str) -> str | None:
    """Get SHA of a file currently in the repo, or None if not present."""
    try:
        result = gh_api("GET", f"/repos/{REPO}/contents/{repo_path}?ref={BRANCH}")
        return result.get("sha")
    except RuntimeError:
        return None


def should_skip(local_path: Path, repo_path: str, existing_sha: str | None) -> bool:
    """Check if file has actually changed compared to remote."""
    # If file doesn't exist remotely, always push
    if existing_sha is None:
        return False

    # Compute local git blob SHA to compare
    with open(local_path, "rb") as f:
        content = f.read()
    # Git blob header: "blob <size>\0"
    blob_content = f"blob {len(content)}\0".encode() + content
    local_sha = hashlib.sha1(blob_content).hexdigest()

    return local_sha == existing_sha


def push_changes():
    """Push changed files to GitHub via API."""
    files = collect_files()
    if not files:
        print("No files to sync.")
        return

    print(f"Checking {len(files)} files for changes...")

    # Build new tree items (only changed files)
    tree_items = []
    changed_files = []
    for repo_path, local_path in files:
        existing_sha = get_remote_file_sha(repo_path)
        if should_skip(local_path, repo_path, existing_sha):
            print(f"  ⏭️  {repo_path} — unchanged")
            continue

        with open(local_path, "rb") as f:
            content_b64 = base64.b64encode(f.read()).decode()

        blob = gh_api("POST", f"/repos/{REPO}/git/blobs",
                      {"content": content_b64, "encoding": "base64"})
        tree_items.append({
            "path": repo_path,
            "mode": "100644",
            "type": "blob",
            "sha": blob["sha"],
        })
        changed_files.append(repo_path)
        print(f"  📄 {repo_path} — updated")

    if not tree_items:
        print("\n✅ No changes to push.")
        return

    # Get base commit
    ref = gh_api("GET", f"/repos/{REPO}/git/ref/heads/{BRANCH}")
    base_sha = ref["object"]["sha"]
    base_commit = gh_api("GET", f"/repos/{REPO}/git/commits/{base_sha}")

    # Create new tree (merge with existing)
    new_tree = gh_api("POST", f"/repos/{REPO}/git/trees", {
        "base_tree": base_commit["tree"]["sha"],
        "tree": tree_items,
    })

    # Create commit
    commit_msg = f"sync: 自动同步潮汕美食数据更新 ({len(changed_files)} files)"
    new_commit = gh_api("POST", f"/repos/{REPO}/git/commits", {
        "message": commit_msg,
        "tree": new_tree["sha"],
        "parents": [base_sha],
    })

    # Update branch
    gh_api("PATCH", f"/repos/{REPO}/git/refs/heads/{BRANCH}", {
        "sha": new_commit["sha"], "force": True,
    })

    print(f"\n✅ Synced {len(changed_files)} files to {REPO}:{BRANCH}")
    print(f"   Commit: {new_commit['sha'][:7]}")
    for f in changed_files:
        print(f"   • {f}")


if __name__ == "__main__":
    push_changes()
