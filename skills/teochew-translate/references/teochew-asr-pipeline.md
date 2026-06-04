# 潮汕话语音识别 (ASR) → 翻译 → TTS 完整管线

## 管线架构

```
潮汕话语音
    │
    ▼
[ASR] ————— 待解决：目前无成熟的潮汕话语音识别模型
    │
    ▼  潮汕话文字 / Peng'im
[teochew-translate] ← 已有
    │
    ▼  普通话文字
[TTS] ————— 可选：CosyVoice 闽南话 / Edge TTS 普通话
    │
    ▼
普通话语音
```

## ASR 测试记录

| 模型 | 日期 | 结果 | 备注 |
|------|------|------|------|
| Whisper tiny (openai) | 2026-06-04 | ❌ **完全失败** | 见下方详细日志 |
| SenseVoice (FunAudioLLM) | 未测 | ❓ 待测试 | 支持50+语言 + 中文方言 |
| Qwen3-Omni | 未测 | ❓ 待测试 | 阿里端到端多模态，7B |
| Paraformer (ModelScope) | 未测 | ❓ 待测试 | 阿里方言ASR |

### Whisper tiny 测试日志

**测试音频**: YouTube 潮汕话视频"潮汕斌姨带大家领略潮州广济桥的风光"
**参数**: `--model tiny --language zh`
**下载大小**: 72.1MB (whisper tiny模型), 1.3MB (20秒音频片段)

**输出结果**（完全乱码）：

```
等候醒病
慢著的K-C在客廠光旅
C-Eggs有小座
K-B-Eggs有那樣管理
...
鋼著鋼著鋼（重复6次）
```

**结论**:
- Whisper tiny 完全无法理解潮汕话，输出随机字符夹杂英文
- no_speech_prob 高达 0.87（Whisper自身认为这段可能没有语音）
- Whisper large-v3 可能稍好，但不期望有本质改善
- Whisper 训练数据中潮汕话覆盖率极低

## 待测模型

### SenseVoice (阿里FunAudioLLM)
- 支持50+语言 + 中文方言
- 小而快，适合CPU推理
- 与CosyVoice同团队出品
- 安装: `pip install funasr`
- 需测试能否识别潮汕话

### Qwen3-Omni
- 阿里千问端到端多模态模型（音频+文字+图像）
- 7B参数，GPU推荐
- 可能通过 DashScope (阿里云百炼) API 调用
- 需测试对潮汕话的音频理解能力

## 当前最佳替代方案

在没有成熟的潮汕话ASR之前，替代路线：

1. **人工输入潮汕话文字** → teochew-translate → TTS（完全人工输入）
2. **先转写为普通话** → TTS（放弃保留潮汕味的诉求）
3. **CosyVoice 闽南话模式**（见 cosyvoice-tts-teochew.md）— 输入普通话→输出带闽南味的语音，可接受的话就用这个

## 未来方向

- **微调 Whisper / SenseVoice**: 收集潮汕话语音+文字标注数据，微调现有模型
- **数据来源**: YouTube潮汕话视频、潮汕话播客、潮汕话教学资源
- **数据量估计**: 至少 10-20小时 标注数据才能训出可用ASR
- **开源标注工具**: LabelStudio, MAUS 等
