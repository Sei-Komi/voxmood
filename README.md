# VoxMood 🎤

**Voice emotion analysis sidecar for AI agents.**

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

## Quick Start (3 steps)

### 1. Install

```bash
git clone https://github.com/Sei-Komi/voxmood.git
cd voxmood
pip install aiohttp
```

### 2. Configure

Get a [DashScope API key](https://dashscope.aliyuncs.com/) (free tier available) and set it:

```bash
export VOXMOOD_API_KEY="sk-your-key-here"
```

Or create a `.env` file:

```
VOXMOOD_API_KEY=sk-your-key-here
```

### 3. Run

```bash
python voxmood.py
```

Point your STT client at `http://localhost:9233` instead of the original API endpoint. That's it.

## How It Works

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

## Configuration

All settings via environment variables:

| Variable | Default | Description |
|---|---|---|
| `VOXMOOD_API_KEY` | *(required)* | DashScope API key |
| `VOXMOOD_PORT` | `9233` | Proxy listen port |
| `VOXMOOD_UPSTREAM_URL` | `https://dashscope-intl.aliyuncs.com/compatible-mode/v1` | Upstream STT API base URL |
| `VOXMOOD_MODEL` | `qwen-omni-turbo` | Multimodal model for analysis |
| `VOXMOOD_LANGUAGE` | `zh` | Analysis language (`zh`/`en`/`ja`) |
| `VOXMOOD_OUTPUT` | `/tmp/voxmood_analysis.json` | Where to write analysis results |
| `VOXMOOD_CACHE_DIR` | `/tmp/voxmood_cache` | Audio file cache directory |
| `VOXMOOD_MAX_CACHE` | `50` | Max cached audio files |

## Output Format

```json
{
  "timestamp": 1718510400.123,
  "iso_time": "2026-06-16 10:00:00",
  "analysis": "1. 情绪：撒娇\n2. 语气：温柔\n3. 语速：慢\n4. 音量：轻声\n5. 特殊特征：拖长音、尾音上扬\n6. 声线特征：气声偏重、声音发甜\n7. 说话人语气温柔带撒娇，心情愉悦放松",
  "audio_file": "/tmp/voxmood_cache/voice_1718510400123.mp3",
  "audio_size_bytes": 15234,
  "model": "qwen-omni-turbo",
  "language": "zh"
}
```

## Use Cases

- **AI companions** — understand emotional context behind voice messages, not just words
- **Voice journaling** — track mood patterns over time through voice tone analysis
- **Customer service** — detect frustration, confusion, or satisfaction in real-time
- **Language learning** — analyze pronunciation confidence and speaking patterns
- **Accessibility** — add emotional context to voice-to-text for deaf/HoH users

## Using with Other STT Providers

VoxMood works with any OpenAI-compatible STT API. To use with OpenAI's Whisper:

```bash
export VOXMOOD_UPSTREAM_URL="https://api.openai.com/v1"
export VOXMOOD_API_KEY="sk-your-openai-key"
export VOXMOOD_MODEL="gpt-4o-audio-preview"
```

## Health Check

```bash
curl http://localhost:9233/health
```

Returns proxy status and the latest analysis result.

## Requirements

- Python 3.8+
- `aiohttp` (`pip install aiohttp`)
- A DashScope API key (or any OpenAI-compatible multimodal API)

## Why "VoxMood"?

*Vox* (Latin: voice) + *Mood*. Because transcripts are lossy — they strip away tone, pace, volume, and texture. VoxMood puts that information back.

## License

MIT

---

Built by [Sei-Komi](https://github.com/Sei-Komi) · Born from the need to hear what text can't say.
