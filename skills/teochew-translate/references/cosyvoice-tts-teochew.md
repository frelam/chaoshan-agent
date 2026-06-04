# 潮汕话 TTS 语音合成方案

调查日期: 2026-06-04 (updated 2026-06-04: added bracket phoneme format, CPU deployment guide, actual deployment verified)

## 方案概览

| 方案 | 类型 | 效果预期 | 部署难度 |
|------|------|---------|---------|
| CosyVoice 3.0 闽南话模式 | 多方言 TTS | 漳州腔闽南语≈潮汕话的70% | 中（需下载模型或云API） |
| Edge/OpenAI TTS + Peng'im | 拼音读法 | 入声字不准，但有音 | 低（直接使用内置工具） |
| GPT-SoVITS | 语音克隆 | ⛔ 不适合潮汕话（见下文） | 高 |
| teochew-g2p + 通用TTS | G2P → 拼音TTS | 同Edge方案 | 中 |

---

## 方案一：CosyVoice 3.0（推荐首选测试）

**阿里通义实验室** 出品，基于 LLM 的多语言语音合成模型。

### 方言支持

涵盖 18+ 种中文方言/口音，包括：
- **闽南话（Minnan）** — 据用户确认，该模型使用的闽南话为 **漳州腔**
- 广东话、四川话、东北话、上海话、天津话等

### 漳州腔 vs 潮汕话

| 维度 | 漳州腔闽南语 | 潮汕话 | 差距评估 |
|------|------------|--------|---------|
| 语系分支 | 闽南语漳州片 | 闽南语潮汕片 | 同属闽南语，音系根基相同 |
| 词汇重叠 | ~60-70% | 100% | 基础词汇互通度高 |
| 声调系统 | 7 声调 | 8 声调 | 潮汕多一个阳上调 |
| 声母 | 无 retroflex | 有 retroflex | 部分字读音差异明显 |
| 日常感 | 漳州/台湾腔 | 潮汕腔 | 母语者可分辨，非母语者觉得"差不多" |

**结论**：能出"闽南语味道"，但不是正宗潮汕话。可作为替代方案，适合非严格要求场景。

### 模型版本

| 模型 | 大小 | 说明 |
|------|------|------|
| Fun-CosyVoice3-0.5B | 0.5B | 最新版，支持 18 方言 + 9 语言 |
| CosyVoice-300M-Instruct | 300M | 支持指令控制方言，实测可用 |
| CosyVoice-300M-SFT | 300M | 基础推理版 |

### 部署选项

| 方式 | 需求 | 说明 |
|------|------|------|
| 本地推理 (GPU) | NVIDIA 显卡（4GB+ 显存） | ✅ 推荐，速度快 |
| 本地推理 (CPU) | 15GB+ 内存 | ❌ 慢但可用，无需 GPU |
| HF Space 在线 Demo | 浏览器 | ✅ 免费，即时测试 |
| ModelScope API | 注册 | 阿里平台，CosyVoice 官方渠道 |
| 阿里云百炼 | 付费 | Aliyun 商业 API 服务 |

### 本地 CPU 部署步骤

适用于无 GPU 环境。已在 Hermes 主机（15GB RAM, 8核 CPU）上实测通过。

#### 1. 安装依赖

```bash
pip install modelscope funasr
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
pip install matcha-tts pyworld onnx onnxruntime pypinyin g2p_en
```

**注意：torch/torchaudio/torchvision 版本必须匹配。** 实测稳定组合：
- torch 2.7.0+cpu
- torchvision 0.22.0+cpu
- torchaudio 2.7.0+cpu

如果后续安装其他包（如 matcha-tts）引入了不兼容的 torchvision，卸掉重装。

**PIL 版本**：系统 PIL 可能过旧（缺 `Image.Resampling`），升级到最新：
```bash
pip install --upgrade Pillow
```

#### 2. 下载模型

先用 modelscope 下载约 5.5GB 模型：

```python
from modelscope import snapshot_download
model_dir = snapshot_download('iic/CosyVoice-300M-Instruct')
print(f'模型下载到: {model_dir}')
# ~/.cache/modelscope/hub/models/iic/CosyVoice-300M-Instruct/
```

模型文件组成：

| 文件 | 大小 | 用途 |
|------|------|------|
| llm.pt | 1.16GB | 语言模型主权重 |
| llm.llm.fp32.zip | 1.47GB | 语言模型 FP32 备份 |
| llm.llm.fp16.zip | 772MB | 语言模型 FP16 版本 |
| speech_tokenizer_v1.onnx | 499MB | 语音 tokenizer |
| flow.pt | 401MB | 流匹配模型 |
| flow.decoder.estimator.fp32.onnx | 314MB | 解码器 ONNX |
| flow.encoder.fp32.zip / fp16.zip | 99MB/60MB | 编码器 |
| llm.text_encoder.fp32.zip / fp16.zip | 354MB/197MB | 文本编码器 |
| hift.pt | 79MB | HiFi-GAN 声码器 |
| campplus.onnx | 27MB | 说话人嵌入 |

**注意**：后台下载时务必用 `/usr/bin/python3` 显式指定 Python，否则 background process 可能找不到 modelscope 或其他 pip 包。

#### 3. 克隆代码仓库

PyPI 包 `cosyvoice` 不完整（缺少 cosyvoice.utils/cli 等核心模块），**必须从 GitHub 克隆**：

```bash
git clone --depth 1 https://github.com/FunAudioLLM/CosyVoice.git ~/CosyVoice
```

推理时需将 CosyVoice 仓库加入 Python path。

#### 4. 推理测试

**WARNING: modelscope.pipelines 对 CosyVoice 不可用！** 以下方式会失败：
- `pipeline(Tasks.text_to_speech, 'iic/CosyVoice-300M-Instruct')` 报错 `Unrecognized model (missing model_type key)`
- 原因是 transformers pipeline 不认识 CosyVoice 的 config.json 结构

**正确做法**：使用 CosyVoice 官方 GitHub 仓库的 `cosyvoice.cli` 模块。

```python
import sys, os
sys.path.insert(0, os.path.expanduser("~/CosyVoice"))

import torch
import torchaudio
from cosyvoice.cli.cosyvoice import CosyVoice

model_dir = os.path.expanduser("~/.cache/modelscope/hub/models/iic/CosyVoice-300M-Instruct")

# NO device 参数！类构造函数自动检测 CUDA/CPU
# load_jit=False 对 CPU 推理必设（JIT 需要 CUDA）
model = CosyVoice(model_dir, load_jit=False, fp16=False)

# Instruct 模式: tts_text + spk_id + instruct_text
# tts_text — 要朗读的文字（中文普通话）
# spk_id — 说话人（如 "中文男"、"中文女"）
# instruct_text — 方言/风格指令（如 "用闽南话说"）
for result in model.inference_instruct(
    tts_text="热到已经融化了，都不想理我，没有胃口",
    spk_id="中文男",
    instruct_text="用闽南话说",
    stream=False
):
    torchaudio.save("output.wav", result['tts_speech'], model.sample_rate)
```

**也可用 CosyVoiceTTS 封装类**（部分功能但 API 更简单）：

```python
from cosyvoice.api import CosyVoiceTTS
tts = CosyVoiceTTS(
    model_cache_dir='checkpoints/cosyvoice',
    device='cpu',
    model_type='instruct',
)
for result in tts.tts_instruct('热到已经融化了，都不想理我，没有胃口',
                                spk_id='中文男',
                                return_format='wav'):
    torchaudio.save('out.wav', result, 22050)
```

注意：`CosyVoiceTTS` 会额外下载 CosyVoice-300M-SFT 和 CosyVoice-ttsfrd 模型，以及 HuggingFace 的 voice-pkg（约 1GB+）。

#### 5. CPU 性能基准（实测）

| 指标 | 值 |
|------|----|
| 模型加载 | ~14秒 |
| 5秒音频生成 | ~33秒 |
| RTF (实时率) | ~6.5x |
| 最长等待 | ~48秒总耗时 |
| 内存峰值 | ~8GB |
| 磁盘占用 | ~5.5GB |

RTF = 6.5x 意味着生成 1 分钟音频约需 6.5 分钟 CPU 推理，**可用但不可实时**。如需更快，建议 GPU。

#### 常见部署陷阱

| 问题 | 原因 | 解决 |
|------|------|------|
| `PIL.Image has no attribute Resampling` | 系统 PIL 版本过旧 | `pip install --upgrade Pillow` |
| `Unrecognized model / missing model_type` | 试图用 transformers pipeline 加载 | 改用 CosyVoice 类的 CLI 模块 |
| `No module named 'cosyvoice.utils'` | PyPI 包 cosyvoice 不完整 | 从 GitHub 克隆完整仓库 |
| `CosyVoice.__init__() got unexpected keyword 'device'` | 类构造参数无 device | 去掉 device 参数，自动检测 |
| `RuntimeError: operator torchvision::nms does not exist` | torchvision 与 torch 版本不匹配 | 匹配版本重装（见上文） |
| `undefined symbol: torch_library_impl` | torchaudio 与 torch 版本不匹配 | 匹配版本重装 |
| 模型下载超时 (600s+) | 模型 5.5GB | 用 background=True 后台下载 |
| 后台下载报 ModuleNotFoundError | 背景进程 Python 路径不同 | 用 /usr/bin/python3 显式指定 |

### 与 teochew-translate 技能集成架构

```
用户输入潮汕话
     │
     ▼
[teochew-translate] → 翻译成普通话
     │
     ▼
[CosyVoice 闽南话指令] → 用闽南话读出普通话文字
     │
     ▼
语音输出（漳州腔闽南语）
```

### 使用方法（Instruct 模式）

```python
# 正确方式：使用 CosyVoice 官方仓库的 CLI 模块
# 需在 CosyVoice 仓库根目录运行
from cosyvoice.cli.cosyvoice import CosyVoice
import torchaudio

model = CosyVoice(
    '/path/to/CosyVoice-300M-Instruct',
    device='cuda:0',       # 或 'cpu'
)

# 注意：输入是普通话文字，通过 instruct_text 指定方言
output = model.inference_instruct(
    '这条河很脏，不知道怎么回事。',
    '中文男',            # 说话人 ID
    '用闽南话说',        # 方言指令
    stream=False,
)
for result in output:
    torchaudio.save('out.wav', result['tts_speech'], 22050)
```

### 快速测试（无需安装）

打开 HF Space：https://huggingface.co/spaces/FunAudioLLM/Fun-CosyVoice3-0.5B
1. 输入普通话文字
2. 在 Instruct 框填 "用闽南话说"
3. 听效果

### 音素输入格式（Bracket Phoneme Format）

CosyVoice 支持音素级精确发音控制，使用 `[]` 括号包裹每个音素/音节。灵感来自 CosyVoice 官方范例：

```
"Her handwriting is [M][AY0][N][UW1][T]并且很整洁，说明她[h][ào]干净。"
```

每条 `[]` 内的内容代表一个发音单元，可以是：
- **英文字母** — 按字母发音读（如 `[M]`、`[T]`）
- **国际音标** — 按 IPA 读（如 `[AY0]`、`[UW1]`）
- **中文拼音声韵母** — 按拼音读（如 `[h]`、`[ào]`）
- **自定义拼音** — 包括潮州拼音音节

#### 潮汕话音素格式规则

1. **有声母的字**：拆成 `[声母][韵母+声调]`
   例：热 → `[r][uah8]`，到 → `[g][ao3]`，来 → `[l][ai5]`

2. **零声母的字**：整个音节放一个括号
   例：烊 → `[ionn5]`，唔 → `[m6]`，下 → `[ê7]`

3. **带声母的零声母**：仍拆两段
   例：我 → `[ua2]`（但习惯拆成 `[u][a2]` 可更精确）

4. **双字母声母**：整体作为一个声母标记
   例：无 → `[bh][o5]`

5. **标点符号**：按原样保留（逗号、句号、空格等）

#### 例：热到烊去，连来睬我一下都无，食唔落

**纯括号格式（推荐用于 CosyVoice 输入）**：
```
[r][uah8][g][ao3][ionn5][k][e3]，[l][iêng5][l][ai5][c][ai2][ua2][z][êg8][ê7][d][ou1][bh][o5]，[z][iah8][m6][l][oh8]
```

**注意**：输入时不要包含汉字，只保留括号和标点。中文文本和音素括号混用会导致 CosyVoice 发音冲突。

#### 关键限制
- **漳州腔 vs 潮汕话**：CosyVoice 的闽南话模式是漳州腔，发潮州拼音时声调会有偏差（潮汕话8个声调，漳州腔7个）
- **入声验证**：-h/-b/-g 结尾的入声字（如 ruah8、ziah8、loh8）在 CosyVoice 中是否短促准确，需实测确认

---

## 方案二：Edge/OpenAI TTS + Peng'im（现有方案）

详见 SKILL.md 的 TTS 章节。适用于快速出音，质量一般。

---

## 方案三：GPT-SoVITS ⛔ 不适合潮汕话

**关键限制**：GPT-SoVITS 虽然能克隆音色（声线、音质），但**发音依赖内置音素表**。它支持的音素只覆盖：
- 中文普通话
- 英文
- 日文
- 韩文
- 粤语

**潮汕话不在其音素表中**。即使提供了潮汕话母语者的录音作为 reference：
- 克隆的是那个人的"嗓音特性"
- 但读出来的发音仍然是用普通话/粤语音素去拼的
- 结果就是 **"普通话腔的潮汕话"**，发音严重失真

**结论**：不适合潮汕话 TTS，除非重新训练音素层（需要大量潮汕话标注数据）。

---

## 方案四：teochew-g2p + 通用TTS

GitHub 项目 https://github.com/p1an-lin-jung/teochew-g2p （62★）
- 功能：汉字 → 潮州拼音（G2P）
- 可以配合 Edge/OpenAI TTS，将潮汕话汉字转成拼音后朗读
- 效果同现有 Edge TTS 方案（入声字不准）

---

## 完整管线：ASR → 翻译 → TTS

参见 `references/teochew-asr-pipeline.md` 获取详细的 ASR 评测日志和待测模型列表。

管线目标：潮汕话语音 → ASR（待解决）→ teochew-translate（已有）→ TTS（此处评估的方案之一）

## 结论与建议

1. **首选测试**：打开 HF Space 试 CosyVoice 的闽南话模式，评估它离正宗潮汕话差多远
2. **如果可接受**：本地部署 CosyVoice-300M-Instruct，集成到 teochew-translate 技能
3. **如果不可接受**：目前没有成熟的潮汕话专用 TTS，需等待相关模型出现
