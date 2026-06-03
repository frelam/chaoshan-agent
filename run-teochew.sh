#!/bin/bash
export DEEPSEEK_API_KEY=sk-04dd46a3aa6c4c87b114b1feb33597ed
export ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic
export ANTHROPIC_API_KEY=sk-04dd46a3aa6c4c87b114b1feb33597ed
export ANTHROPIC_AUTH_TOKEN=sk-04dd46a3aa6c4c87b114b1feb33597ed
export ANTHROPIC_MODEL=deepseek-v4-pro[1m]
cd /home/charles/workspace/chaoshan-agent
claude -p "$(cat teochew-prompt.txt)" 2>&1
