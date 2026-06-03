#!/usr/bin/env bash
# ============================================================
# Chaoshan Agent — 潮汕文化 Agent 安装脚本
# 将 teochew-translate skill 安装到 Hermes Agent 中
# ============================================================
set -euo pipefail

HERMES_SKILLS_DIR="${HERMES_HOME:-$HOME/.hermes}/skills"
SKILL_SRC="skills/teochew-translate"
TARGET="$HERMES_SKILLS_DIR/teochew-translate"

echo "==> 🔍 检查 Hermes Agent 目录…"
if [ ! -d "$HERMES_SKILLS_DIR" ]; then
  echo "错误：未找到 Hermes skills 目录 ($HERMES_SKILLS_DIR)"
  echo "请先安装 Hermes Agent: https://hermes-agent.nousresearch.com/docs"
  exit 1
fi

echo "==> 📁 复制 skill 到 $TARGET"
if [ -d "$TARGET" ]; then
  echo "警告：目标目录已存在，将覆盖更新"
fi

# 确保脚本在项目根目录执行
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if [ ! -d "$SKILL_SRC" ]; then
  echo "错误：未找到 skill 源码目录 ($SKILL_SRC)"
  echo "请确保在 chaoshan-agent 项目根目录运行此脚本"
  exit 1
fi

# 创建目标目录并复制
mkdir -p "$TARGET"
cp -r "$SKILL_SRC/"* "$TARGET/"
echo "==> ✅ Skill 已安装到 $TARGET"

# 列出安装的文件
echo ""
echo "安装的文件:"
find "$TARGET" -type f | sed "s|$TARGET/|  • |"

echo ""
echo "==> 🎉 安装完成！"
echo "现在可以在 Hermes Agent 中使用潮汕话翻译了。"
echo "试试发送：\"瓦爱来去踢桃\""
