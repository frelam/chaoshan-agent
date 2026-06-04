# 潮汕话 TTS 语音合成方案

CosyVoice 3.0 调查结果（2026-06-04）

## Fun-CosyVoice 3.0

**阿里通义实验室** 出品，基于 LLM 的多语言语音合成模型。

### 方言支持

涵盖 18+ 种中文方言/口音，包括：
- **闽南话（Minnan）** — 与潮汕话同属闽南语分支
- 广东话、四川话、东北话、上海话、天津话等

通过 **Instruct 模式** 控制方言，支持指令如语言、方言、情感、速度、音量等。

### 模型版本

| 模型 | 大小 | 说明 |
|------|------|------|
| Fun-CosyVoice3-0.5B | 0.5B | 最新版，支持 18 方言 + 9 语言 |
| CosyVoice-300M-Instruct | 300M | 支持指令控制方言 |
| CosyVoice-300M-SFT | 300M | 基础推理版 |

### 部署选项

| 方式 | 需求 | 说明 |
|------|------|------|
| 本地推理 | GPU/CPU | CPU 极慢，建议 GPU |
| HuggingFace API | API Key | 可能有推理 API 可用 |
| ModelScope API | 注册 | 阿里平台，CosyVoice 官方渠道 |
| 阿里云百炼 | 付费 | Aliyun 商业 API 服务 |

### 使用方法（Instruct 模式）

```python
from modelscope.pipelines import pipeline
from modelscope.utils.constant import Tasks

inference = pipeline(Tasks.text_to_speech, 
                     'iic/CosyVoice-300M-Instruct',
                     device='cuda:0')

# 用 instruct_text 指定方言
result = inference('这条河很脏，不知道怎么回事。', 
                   instruct_text='用闽南话')
```

### 注意事项

- 潮汕话 ≠ 闽南话（Hokkien）。CosyVoice 标注支持的是"闽南话"（Minnan），即福建/台湾闽南语。潮汕话是闽南语的一个分支（潮汕片），与闽南语共享约 50% 词汇，但发音、声调、部分用词有差异。CosyVoice 的实际潮汕话效果**未经确认**，需实测。
- 若 CosyVoice 的闽南话不完全匹配潮汕话，可考虑 **GPT-SoVITS 语音克隆**方案：找潮汕话母语者的录音样本进行零样本克隆。

### 参考资料

- CosyVoice GitHub: https://github.com/FunAudioLLM/CosyVoice
- ModelScope: https://www.modelscope.cn/models/iic/CosyVoice-300M-Instruct
- HuggingFace: https://huggingface.co/FunAudioLLM/Fun-CosyVoice3-0.5B-2512
