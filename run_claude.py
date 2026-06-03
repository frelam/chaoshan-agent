#!/usr/bin/env python3
"""Run claude with env vars from bashrc and prompt from file."""
import subprocess, os, sys

# Read API key from bashrc
key = None
with open(os.path.expanduser('~/.bashrc')) as f:
    for line in f:
        if line.startswith('export DEEPSEEK_API_KEY='):
            key = line.split('=', 1)[1].strip().strip("'\"")
            break

if not key:
    print("ERROR: Could not read DEEPSEEK_API_KEY", file=sys.stderr)
    sys.exit(1)

# Read prompt
prompt_path = os.path.expanduser('~/workspace/chaoshan-agent/research-zaosi-prompt.txt')
with open(prompt_path) as f:
    prompt = f.read()

# Setup env
env = os.environ.copy()
env['ANTHROPIC_BASE_URL'] = 'https://api.deepseek.com/anthropic'
env['ANTHROPIC_API_KEY'] = key
env['ANTHROPIC_AUTH_TOKEN'] = key
env['ANTHROPIC_MODEL'] = 'deepseek-v4-pro[1m]'

# Run claude
workdir = os.path.expanduser('~/workspace/chaoshan-agent')
proc = subprocess.run(
    ['claude', '-p', prompt],
    cwd=workdir,
    capture_output=True, text=True, timeout=600,
    env=env
)

print(f"EXIT_CODE: {proc.returncode}")
stdout = proc.stdout
stderr = proc.stderr
if len(stdout) > 3000:
    print("STDOUT (last 3000 chars):")
    print(stdout[-3000:])
else:
    print("STDOUT:")
    print(stdout)
if stderr:
    print("STDERR:")
    print(stderr[-1000:])
