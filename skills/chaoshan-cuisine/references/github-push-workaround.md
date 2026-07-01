# GitHub Push Workaround (GFW 绕过)

## 问题

在中国大陆直连 GitHub 时，`git push` 的 HTTPS/SSH 传输层会被 GFW 干扰，
表现为 TLS 连接中断（`GnuTLS recv error (-110): The TLS connection was non-properly terminated`），
导致推送失败。但 `gh api`（GitHub REST API）不受影响，因为走的是不同的 HTTP 路径。

## 替换方案：通过 GitHub API 推送

使用 `gh api` 手动创建 Git 对象，绕过传输层封锁：

```python
import subprocess, json, base64

def gh_api(method, path, data=None):
    cmd = ['gh', 'api', '-X', method, path]
    if data:
        cmd.extend(['--input', '-'])
    result = subprocess.run(
        cmd, input=json.dumps(data) if data else None,
        capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        raise RuntimeError(f"gh api failed: {result.stderr}")
    return json.loads(result.stdout) if result.stdout.strip() else {}

def push_via_api(repo, branch, file_map, commit_message):
    """
    Push files to GitHub via API when git push is blocked.
    
    Args:
        repo: "owner/repo"
        branch: "main"
        file_map: {"path/in/repo": "/local/path", ...}
        commit_message: "commit message"
    """
    # 1. Create blobs for all files
    tree_items = []
    for repo_path, local_path in file_map.items():
        with open(local_path, 'rb') as f:
            content = base64.b64encode(f.read()).decode()
        blob = gh_api("POST", f"/repos/{repo}/git/blobs",
                      {"content": content, "encoding": "base64"})
        tree_items.append({
            "path": repo_path, "mode": "100644",
            "type": "blob", "sha": blob["sha"]
        })

    # 2. Get base commit & tree
    ref = gh_api("GET", f"/repos/{repo}/git/ref/heads/{branch}")
    base_sha = ref["object"]["sha"]
    base_commit = gh_api("GET", f"/repos/{repo}/git/commits/{base_sha}")

    # 3. Create new tree (merge with existing)
    new_tree = gh_api("POST", f"/repos/{repo}/git/trees", {
        "base_tree": base_commit["tree"]["sha"],
        "tree": tree_items
    })

    # 4. Create commit
    new_commit = gh_api("POST", f"/repos/{repo}/git/commits", {
        "message": commit_message,
        "tree": new_tree["sha"],
        "parents": [base_sha]
    })

    # 5. Update branch
    gh_api("PATCH", f"/repos/{repo}/git/refs/heads/{branch}", {
        "sha": new_commit["sha"], "force": True
    })

    return new_commit["sha"]

# 使用示例
push_via_api(
    repo="frelam/chaoshan-agent",
    branch="main",
    file_map={
        "skills/chaoshan-cuisine/SKILL.md": "/path/to/SKILL.md",
        ".gitignore": "/path/to/.gitignore",
    },
    commit_message="feat: 更新说明"
)
```

## 前提条件

- `gh` CLI 已安装并认证（`gh auth status`）
- token 有 `repo` 权限

## 注意

- `force=True` 会直接覆盖分支，确保本地与远端无冲突
- 推送后本地 git ref 不会自动更新，需在之后运行 `gh repo sync` 或 `git fetch`（如果网络允许）
