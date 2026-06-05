# 潮汕话翻译技能公开部署方案

如何让其他人通过不同渠道使用 teochew-translate 翻译能力。

## 背景

现有 Hermes 微信网关通过 iLink (ilinkai.weixin.qq.com) 连接，bot 身份为 `@im.bot` 虚拟账号。
**该账号无法被拉入普通微信群**（iLink 平台限制，见 Hermes `gateway/platforms/weixin.py` L1280-1290）。
因此「拉 bot 进群」的方案不可行。

## 方案对比

| 方案 | 难度 | 成本 | 受众 | 备注 |
|------|------|------|------|------|
| Web 页面 | ⭐ 低 | 0 | 任何人（有链接） | ✅ 已验证可运行 |
| 微信公众号 | ⭐⭐ 中 | 0（个人订阅号） | 关注者 | 需注册 + 服务器 URL |
| 企业微信 (WeCom) | ⭐⭐ 中 | 0 | 企业成员 | Hermes 有原生适配器 |
| iLink 微信群 | ❌ 不可行 | — | — | `@im.bot` 不能拉群 |

## 方案详情

### 方案 1：Web 翻译页面（推荐）✅ 已验证可运行

最简单的方案，一个单页 HTML，任何人在微信内置浏览器中打开就能用。

**架构（2026-06-05 实测）**：
```
用户浏览器 ──HTTPS──→ localhost.run 隧道 ──→ 本机 :8000 ──→ FastAPI backend ──→ DeepSeek API
```

**项目结构**（见 `~/workspace/teochew-translate-web/`）：
```
teochew-translate-web/
├── index.html          # 移动端友好的单页 HTML（微信内置浏览器适配）
├── api/
│   ├── server.py       # FastAPI 后端（本地开发用）
│   └── index.py        # Vercel Python serverless（部署用）
├── vercel.json         # Vercel 部署配置
├── run.py              # 本地启动脚本
├── start.sh            # 一键拉起脚本（杀进程→启动→隧道→显示URL）
├── requirements.txt
└── .gitignore
```

**启动命令**：
```bash
# 方式一：一键脚本
cd ~/workspace/teochew-translate-web && ./start.sh

# 方式二：手动分步启动
cd ~/workspace/teochew-translate-web
python3 -m uvicorn api.server:app --host 0.0.0.0 --port 8000 &
sleep 2
ssh -o StrictHostKeyChecking=no -R 80:localhost:8000 nokey@localhost.run
```

**start.sh 脚本内容**：
```bash
#!/bin/bash
pkill -f "uvicorn api.server:app" 2>/dev/null || true
cd ~/workspace/teochew-translate-web
python3 -m uvicorn api.server:app --host 0.0.0.0 --port 8000 &
sleep 2
curl -s -o /dev/null -w "Server: HTTP %{http_code}\n" http://localhost:8000/
ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=30 -R 80:localhost:8000 nokey@localhost.run 2>&1 | grep -E "https://.*\\.lhr\\.life"
```

**API 接口**：
```
POST /api/translate
Body: {"text": "食饱未？"}
Response: {"success": true, "result": "...翻译结果..."}
```

**前端要点**：
- 响应式设计，max-width 640px，适合手机
- 输入框 + 示例按钮（常见潮汕短语一键测试）
- 结果展示卡片，带滑入动画
- 适配微信内置浏览器（无外部依赖，纯 CSS + 原生 JS）
- 支持 Enter 提交 + Shift+Enter 换行

**技术栈**：
- 后端：FastAPI / Vercel Python Runtime
- 前端：纯 HTML + CSS + JS（零依赖）
- LLM：DeepSeek flash（deepseek-v4-flash），system prompt 使用 SKILL.md 核心内容
- 隧道：localhost.run（免费，无需注册，自动 TLS 终结）
- 部署备选：Vercel（需添加 DEEPSEEK_API_KEY 环境变量）

**隧道方案实测对比**：

| 方案 | 结果 | 原因 |
|------|------|------|
| ngrok v3 | ❌ 需注册 authtoken | 免费邮箱注册即可 |
| localtunnel (npx) | ❌ 挂起无输出 | 可能被网络环境限制 |
| serveo.net | ❌ SSH 连接超时 | DNS 可达但 SSH 握手失败 |
| localhost.run | ✅ 可用 | 无需密钥，`nokey@localhost.run` 直接连 |
| Cloudflare Tunnel | ❌ GitHub 下载超时 | 二进制下载被限速/超时 |

**Tunnel stability notes**：
- localhost.run 免费隧道不稳定，可能随时断开
- 如果断开了，重新运行 start.sh 即可
- 每次重启后 URL（`*.lhr.life`）会变化，需要重新分享给朋友
- 如需永久稳定的 URL，建议部署到 Vercel（免费，配置 DEEPSEEK_API_KEY 环境变量即可）

### 方案 2：微信公众号

**前提**：需要有身份证注册的个人订阅号（无需营业执照）。

**配置步骤**：
1. 注册微信公众号（订阅号）
2. 后台 → 开发 → 基本配置 → 服务器配置
3. 启用开发者模式，填写服务器 URL（指向 Hermes webhook 或自建后端）
4. Hermes 侧使用 `webhook.py` 适配器接收消息
5. 用户关注公众号 → 发消息 → 自动翻译回复

**注意事项**：
- 个人订阅号有回复时效限制（48 小时内可主动回复）
- 服务器 URL 需要公网可访问（可用 localhost.run / ngrok / FRP 内网穿透）
- 需要配置 token 加解密的对接逻辑

### 方案 3：企业微信 (WeCom)

Hermes 已有原生 `wecom.py` 适配器，支持：
- 企业微信群聊机器人
- 消息回调
- 图片/文件/语音消息

**配置步骤**（详见 `hermes gateway setup`）：
1. 注册企业微信
2. 创建自建应用
3. 配置消息回调 URL
4. 在 Hermes `.env` 中配置 `WECOM_*` 环境变量
5. 启动 wecom 平台

适合团队内部使用场景。

## 关键技术决策

### Web 页面模式：调用方式选择

| 方式 | 优点 | 缺点 |
|------|------|------|
| 直接调 LLM API | 简单，不依赖 Hermes | 无记忆，每次独立 |
| 通过 Hermes API | 有记忆/技能上下文 | 依赖 Hermes 运行 |
| MCP Serve | 标准协议 | 学习成本略高 |

### 微信 OCR + 语音输入

Web 页面在微信内置浏览器中打开时，微信自带的「长按识别」功能支持：
- 语音转文字输入
- 图片 OCR 识别文字
- 复制粘贴

这些可以直接利用，无需额外开发。

### 后端 System Prompt 关键内容

翻译质量取决于 system prompt。核心内容包括：
- 翻译方向自动检测（潮汕话↔普通话关键字/特征字判断）
- 输出格式强制（原文/翻译/拼音/语法说明/文化注释）
- 语法规则表（否定词、语序、比较句、疑问句等）
- 文化注释要求
- Peng'im 音标规范
- 务必使用 DeepSeek flash 模型（便宜且够用），pro 模型没必要

## iLink 平台已知限制

来源：Hermes `gateway/platforms/weixin.py` 源码 L1280-1290

- `@im.bot` 账号不能拉入普通微信群
- 群消息通常不会投递到 iLink bot（即使 `WEIXIN_GROUP_POLICY=open`）
- iLink 主要用于个人号 DM 场景
- 如果需要群聊能力，必须走微信公众号或企业微信

## 相关参考

- Hermes webhook 文档：https://hermes-agent.nousresearch.com/docs/user-guide/features/webhook
- Hermes API Server：`hermes mcp serve`
- iLink 官网：https://ilinkai.weixin.qq.com
- localhost.run 文档：https://localhost.run/docs/
