# VoxMood 🎤

**语音情绪分析中间件 | Voice emotion analysis sidecar**

[中文](#中文) | [English](#english)

---

## 中文

VoxMood 是一个透明代理，插在你的应用和语音转文字 API（Qwen / OpenAI 等）之间。它拦截语音，正常转发转写请求（零延迟），同时异步分析说话人的**情绪、语气、语速、音量、声线**。

> 转录只告诉你**说了什么**，VoxMood 告诉你**怎么说的**。

```
你的应用 → VoxMood (localhost:9233) → 语音转文字 API
                 |
                 └→ 异步情绪分析 → /tmp/voxmood_analysis.json
```

### 分析维度

| 维度 | 示例 |
|---|---|
| 情绪 | 平静 / 开心 / 撒娇 / 难过 / 焦虑 / 委屈 ... |
| 语气 | 轻快 / 慵懒 / 温柔 / 急促 / 犹豫 ... |
| 语速 & 音量 | 快 / 中 / 慢，大 / 轻声 / 耳语 |
| 声线特征 | 气声偏重 / 嗓音清亮 / 沙哑 / 声音发甜 / 鼻音明显 ... |
| 特殊特征 | 笑声 / 叹气 / 拖长音 / 尾音上扬 / 哭腔 ... |

### 三步上手

**1. 安装**

```bash
git clone https://github.com/Sei-Komi/voxmood.git
cd voxmood
pip install aiohttp
```

**2. 配置**

去 [DashScope](https://dashscope.aliyuncs.com/) 申请 API key（有免费额度），然后：

```bash
export VOXMOOD_API_KEY="sk-你的key"
```

或者创建 `.env` 文件：

```
VOXMOOD_API_KEY=sk-你的key
```

**3. 启动**

```bash
python voxmood.py
```

把你的语音转文字客户端指向 `http://localhost:9233`，搞定。

### 原理

```
┌─────────┐    音频    ┌──────────┐    音频    ┌──────────┐
│ 你的应用  │ ───────→ │ VoxMood  │ ───────→ │ 转写 API  │
│          │ ←─────── │  (代理)   │ ←─────── │          │
└─────────┘   转写文本  └────┬─────┘  转写文本  └──────────┘
                            │
                            │ 异步（不增加延迟）
                            ▼
                    ┌──────────────┐
                    │ 多模态大模型   │
                    │ (Qwen-Omni)  │
                    └──────┬───────┘
                           │
                           ▼
                 /tmp/voxmood_analysis.json
```

1. 你的应用照常发送语音消息给 VoxMood（API 格式不变）
2. VoxMood 原样转发给上游转写 API，**立即返回**转写结果
3. 后台异步将音频发给多模态大模型做情绪分析
4. 分析结果写入 JSON 文件，你的应用随时可读

**零延迟** — 代理在分析完成前就已返回转写结果。

### 输出示例

```json
{
  "timestamp": 1718510400.123,
  "iso_time": "2026-06-16 10:00:00",
  "analysis": "1. 情绪：撒娇\n2. 语气：温柔\n3. 语速：慢\n4. 音量：轻声\n5. 特殊特征：拖长音、尾音上扬\n6. 声线特征：气声偏重、声音发甜\n7. 说话人语气温柔带撒娇，心情愉悦放松",
  "model": "qwen-omni-turbo",
  "language": "zh"
}
```

### 使用场景

- **AI 伴侣 / AI Agent** — 让你的 AI 不只读文字，还能感受语气
- **语音日记** — 追踪情绪变化
- **客服系统** — 实时检测用户情绪
- **语言学习** — 分析口语表达信心和模式
- **无障碍** — 为听障用户补充情绪上下文

### 配置项

所有配置通过环境变量设置：

| 变量 | 默认值 | 说明 |
|---|---|---|
| `VOXMOOD_API_KEY` | *(必填)* | DashScope API key |
| `VOXMOOD_PORT` | `9233` | 代理端口 |
| `VOXMOOD_UPSTREAM_URL` | `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` | 上游转写 API |
| `VOXMOOD_MODEL` | `qwen-omni-turbo` | 分析用多模态模型 |
| `VOXMOOD_LANGUAGE` | `zh` | 分析语言（`zh` / `en` / `ja`） |
| `VOXMOOD_OUTPUT` | `/tmp/voxmood_analysis.json` | 分析结果输出路径 |

### 其他转写服务

VoxMood 兼容所有 OpenAI 格式的转写 API。用 OpenAI Whisper：

```bash
export VOXMOOD_UPSTREAM_URL="https://api.openai.com/v1"
export VOXMOOD_API_KEY="sk-你的openai-key"
export VOXMOOD_MODEL="gpt-4o-audio-preview"
```

### 依赖

- Python 3.8+
- `aiohttp`（`pip install aiohttp`）
- DashScope API key（或任何 OpenAI 兼容的多模态 API）

---

## English

VoxMood is a transparent proxy that sits between your app and any OpenAI-compatible Speech-to-Text API. It intercepts voice audio, forwards the STT request with zero added latency, and asynchronously analyzes *how* something was said — not just *what* was said.

```
Your App → VoxMood (localhost:9233) → STT API (Qwen/OpenAI/etc.)
                |
                └→ async emotion analysis → /tmp/voxmood_analysis.json
```

Your app gets the transcript back instantly. In the background, VoxMood runs the audio through a multimodal LLM to extract:

- **Emotion** — calm, happy, excited, sad, angry, shy, anxious...
- **Tone** — cheerful, lazy, serious, gentle, rushed, hesitant...
- **Speed & Volume** — fast/medium/slow, loud/soft/whisper
- **Voice texture** — breathy, nasal, clear, raspy, sweet, resonant...
- **Notable features** — laughter, sighs, pauses, trembling, drawl, rising intonation...

### Quick Start (3 steps)

**1. Install**

```bash
git clone https://github.com/Sei-Komi/voxmood.git
cd voxmood
pip install aiohttp
```

**2. Configure**

Get a [DashScope API key](https://dashscope.aliyuncs.com/) (free tier available) and set it:

```bash
export VOXMOOD_API_KEY="sk-your-key-here"
```

Or create a `.env` file:

```
VOXMOOD_API_KEY=sk-your-key-here
```

**3. Run**

```bash
python voxmood.py
```

Point your STT client at `http://localhost:9233` instead of the original API endpoint. That's it.

### How It Works

```
┌─────────┐    audio    ┌──────────┐    audio    ┌──────────┐
│ Your App │ ─────────→ │ VoxMood  │ ─────────→ │ STT API  │
│          │ ←───────── │ (proxy)  │ ←───────── │          │
└─────────┘  transcript └────┬─────┘  transcript └──────────┘
                             │
                             │ async (no delay)
                             ▼
                     ┌───────────────┐
                     │ Multimodal LLM │
                     │ (Qwen-Omni)   │
                     └───────┬───────┘
                             │
                             ▼
                   /tmp/voxmood_analysis.json
```

1. Your app sends a voice message to VoxMood (same API format as before)
2. VoxMood forwards it to the upstream STT API and returns the transcript immediately
3. In the background, VoxMood sends the audio to a multimodal LLM for emotion analysis
4. The analysis result is written to a JSON file your app can read

**Zero latency overhead** — the proxy response is returned before the analysis completes.

### Output Format

```json
{
  "timestamp": 1718510400.123,
  "iso_time": "2026-06-16 10:00:00",
  "analysis": "1. Emotion: playful\n2. Tone: gentle\n3. Speed: slow\n4. Volume: soft\n5. Notable: drawl, rising intonation\n6. Texture: breathy, sweet\n7. Speaker sounds relaxed and affectionate",
  "model": "qwen-omni-turbo",
  "language": "en"
}
```

### Use Cases

- **AI companions** — understand emotional context behind voice messages, not just words
- **Voice journaling** — track mood patterns over time through voice tone analysis
- **Customer service** — detect frustration, confusion, or satisfaction in real-time
- **Language learning** — analyze pronunciation confidence and speaking patterns
- **Accessibility** — add emotional context to voice-to-text for deaf/HoH users

### Configuration

All settings via environment variables:

| Variable | Default | Description |
|---|---|---|
| `VOXMOOD_API_KEY` | *(required)* | DashScope API key |
| `VOXMOOD_PORT` | `9233` | Proxy listen port |
| `VOXMOOD_UPSTREAM_URL` | `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` | Upstream STT API base URL |
| `VOXMOOD_MODEL` | `qwen-omni-turbo` | Multimodal model for analysis |
| `VOXMOOD_LANGUAGE` | `zh` | Analysis language (`zh`/`en`/`ja`) |
| `VOXMOOD_OUTPUT` | `/tmp/voxmood_analysis.json` | Where to write analysis results |

### Using with Other STT Providers

VoxMood works with any OpenAI-compatible STT API. To use with OpenAI's Whisper:

```bash
export VOXMOOD_UPSTREAM_URL="https://api.openai.com/v1"
export VOXMOOD_API_KEY="sk-your-openai-key"
export VOXMOOD_MODEL="gpt-4o-audio-preview"
```

### Health Check

```bash
curl http://localhost:9233/health
```

### Requirements

- Python 3.8+
- `aiohttp` (`pip install aiohttp`)
- A DashScope API key (or any OpenAI-compatible multimodal API)

---

## Why "VoxMood"?

*Vox* (Latin: voice) + *Mood*. Because transcripts are lossy — they strip away tone, pace, volume, and texture. VoxMood puts that information back.

## License

MIT

---

Built by [Sei-Komi](https://github.com/Sei-Komi) · Born from the need to hear what text can't say.
