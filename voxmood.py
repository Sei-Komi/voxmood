#!/usr/bin/env python3
"""VoxMood — Voice Emotion Analysis Sidecar

A transparent proxy that sits between your app and any OpenAI-compatible
Speech-to-Text API. It intercepts voice audio, forwards the ASR request
as-is, and asynchronously runs paralinguistic analysis via a multimodal
LLM (Qwen-Omni by default).

Your app gets the transcript back with zero latency overhead.
Meanwhile, VoxMood writes a JSON analysis file that your app can read
to understand *how* something was said, not just *what* was said.

Usage:
    pip install aiohttp
    export VOXMOOD_API_KEY="your-dashscope-api-key"
    python voxmood.py

    # Point your STT client at http://localhost:9233 instead of the real API.
"""

import asyncio
import json
import os
import sys
import time
import base64
from pathlib import Path

try:
    import aiohttp
    from aiohttp import web, ClientSession
except ImportError:
    print("Missing dependency. Run: pip install aiohttp")
    sys.exit(1)

# --- Configuration (env vars or .env file) ---

UPSTREAM_URL = os.environ.get(
    "VOXMOOD_UPSTREAM_URL",
    "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
)
API_KEY = os.environ.get("VOXMOOD_API_KEY", "")
ANALYSIS_MODEL = os.environ.get("VOXMOOD_MODEL", "qwen-omni-turbo")
PORT = int(os.environ.get("VOXMOOD_PORT", "9233"))
ANALYSIS_OUTPUT = Path(os.environ.get("VOXMOOD_OUTPUT", "/tmp/voxmood_analysis.json"))
CACHE_DIR = Path(os.environ.get("VOXMOOD_CACHE_DIR", "/tmp/voxmood_cache"))
MAX_CACHE_FILES = int(os.environ.get("VOXMOOD_MAX_CACHE", "50"))
LANGUAGE = os.environ.get("VOXMOOD_LANGUAGE", "zh")

CACHE_DIR.mkdir(exist_ok=True)

if not API_KEY:
    for env_file in [Path(".env"), Path.home() / ".voxmood.env"]:
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                line = line.strip()
                if line.startswith("VOXMOOD_API_KEY="):
                    API_KEY = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
            if API_KEY:
                break

# --- Analysis prompts by language ---

PROMPTS = {
    "zh": (
        "分析这段语音的副语言特征。用中文简洁回答，每项一行：\n"
        "1. 情绪：从以下选一个最贴切的（平静/开心/兴奋/撒娇/俏皮/好奇/无聊/疲惫/难过/生气/害羞/焦虑/委屈）\n"
        "2. 语气：一两个词（如：轻快/慵懒/认真/俏皮/温柔/急促/犹豫/随意/正常）\n"
        "3. 语速：快/中/慢\n"
        "4. 音量：大/中/小/轻声\n"
        "5. 特殊特征：如有笑声/叹气/停顿/声音发抖/鼻音重/哭腔/拖长音/尾音上扬/嘟嘴音。没有就写'无'\n"
        "6. 声线特征：描述音色质感（如：气声偏重/鼻音明显/嗓音清亮/沙哑/声音发甜/声线细软）\n"
        "7. 一句话总结说话人此刻的状态和可能的心情\n"
        "只输出分析结果，不要重复问题。"
    ),
    "en": (
        "Analyze the paralinguistic features of this voice clip. Answer concisely, one line per item:\n"
        "1. Emotion: pick the closest (calm/happy/excited/playful/curious/bored/tired/sad/angry/shy/anxious/hurt)\n"
        "2. Tone: one or two words (e.g. cheerful/lazy/serious/playful/gentle/rushed/hesitant/casual/neutral)\n"
        "3. Speed: fast/medium/slow\n"
        "4. Volume: loud/medium/soft/whisper\n"
        "5. Notable features: laughter/sigh/pause/trembling/nasal/crying/drawl/rising intonation. Write 'none' if absent\n"
        "6. Voice texture: describe the timbre (e.g. breathy/nasal/clear/raspy/sweet/thin/resonant)\n"
        "7. One sentence summarizing the speaker's current state and likely mood\n"
        "Output only the analysis, do not repeat the questions."
    ),
    "ja": (
        "この音声のパラ言語特徴を分析してください。各項目1行で簡潔に：\n"
        "1. 感情：最も近いもの（平静/嬉しい/興奮/甘え/いたずら/好奇心/退屈/疲れ/悲しい/怒り/恥ずかしい/不安/悔しい）\n"
        "2. 口調：1-2語（例：軽快/だるい/真剣/いたずら/優しい/急ぎ/ためらい/カジュアル/普通）\n"
        "3. 速度：速い/普通/遅い\n"
        "4. 音量：大/中/小/ささやき\n"
        "5. 特徴：笑い/ため息/間/震え/鼻声/泣き/引き伸ばし/語尾上がり。なければ'なし'\n"
        "6. 声質：音色（例：息混じり/鼻声/透明/かすれ/甘い/細い/響く）\n"
        "7. 話者の状態と心情を一文で\n"
        "分析結果のみ出力。"
    ),
}


async def analyze_voice(audio_path: Path):
    """Send audio to multimodal LLM for paralinguistic analysis."""
    try:
        audio_bytes = audio_path.read_bytes()
        audio_b64 = base64.b64encode(audio_bytes).decode()

        ext = audio_path.suffix.lstrip(".")
        mime_map = {
            "mp3": "audio/mp3", "ogg": "audio/ogg", "wav": "audio/wav",
            "m4a": "audio/mp4", "amr": "audio/amr", "webm": "audio/webm",
        }
        mime = mime_map.get(ext, "audio/mpeg")
        data_uri = f"data:{mime};base64,{audio_b64}"

        prompt = PROMPTS.get(LANGUAGE, PROMPTS["en"])

        payload = {
            "model": ANALYSIS_MODEL,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "input_audio", "input_audio": {"data": data_uri, "format": ext}},
                    {"type": "text", "text": prompt},
                ],
            }],
            "stream": False,
            "modalities": ["text"],
        }

        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        }

        async with ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            async with session.post(
                f"{UPSTREAM_URL}/chat/completions", json=payload, headers=headers
            ) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    analysis_text = result["choices"][0]["message"]["content"]
                    analysis = {
                        "timestamp": time.time(),
                        "iso_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                        "analysis": analysis_text,
                        "audio_file": str(audio_path),
                        "audio_size_bytes": len(audio_bytes),
                        "model": ANALYSIS_MODEL,
                        "language": LANGUAGE,
                    }
                    ANALYSIS_OUTPUT.write_text(json.dumps(analysis, ensure_ascii=False, indent=2))
                    print(f"[voxmood] ✓ {analysis_text[:80]}...")
                    return analysis
                else:
                    error = await resp.text()
                    print(f"[voxmood] ✗ API {resp.status}: {error[:200]}")
                    return None
    except Exception as e:
        print(f"[voxmood] ✗ analysis failed: {e}")
        return None


async def handle_chat_completions(request: web.Request):
    """Proxy /chat/completions — intercept audio, forward everything."""
    raw_body = await request.read()

    audio_path = None
    try:
        body = json.loads(raw_body)
        for msg in body.get("messages", []):
            content = msg.get("content")
            if not isinstance(content, list):
                continue
            for part in content:
                if part.get("type") == "input_audio":
                    audio_uri = part.get("input_audio", {}).get("data", "")
                    if audio_uri and "base64," in audio_uri:
                        b64 = audio_uri.split("base64,", 1)[1]
                        audio_bytes = base64.b64decode(b64)
                        ts = int(time.time() * 1000)
                        audio_path = CACHE_DIR / f"voice_{ts}.mp3"
                        audio_path.write_bytes(audio_bytes)
                        print(f"[voxmood] 🎤 intercepted {len(audio_bytes)} bytes")
                    break
    except (json.JSONDecodeError, KeyError, TypeError):
        pass

    auth = request.headers.get("Authorization", f"Bearer {API_KEY}")
    headers = {"Authorization": auth, "Content-Type": "application/json"}

    try:
        async with ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
            async with session.post(
                f"{UPSTREAM_URL}/chat/completions", data=raw_body, headers=headers
            ) as resp:
                resp_body = await resp.read()
                resp_headers = dict(resp.headers)
                for h in ("Transfer-Encoding", "Content-Encoding"):
                    resp_headers.pop(h, None)
                result = web.Response(body=resp_body, status=resp.status, headers=resp_headers)
    except Exception as e:
        print(f"[voxmood] upstream error: {e}")
        return web.json_response(
            {"error": {"message": str(e), "type": "proxy_error"}}, status=502
        )

    if audio_path and audio_path.exists():
        asyncio.create_task(analyze_voice(audio_path))

    return result


async def handle_health(request: web.Request):
    """Health check — also returns the latest analysis if available."""
    latest = None
    if ANALYSIS_OUTPUT.exists():
        try:
            latest = json.loads(ANALYSIS_OUTPUT.read_text())
        except Exception:
            pass

    return web.json_response({
        "status": "ok",
        "port": PORT,
        "model": ANALYSIS_MODEL,
        "language": LANGUAGE,
        "upstream": UPSTREAM_URL,
        "cached_files": len(list(CACHE_DIR.glob("voice_*"))),
        "latest_analysis": latest,
    })


async def handle_catchall(request: web.Request):
    """Forward any other API calls transparently."""
    path = request.path
    raw_body = await request.read()
    if path.startswith("/v1/"):
        path = path[3:]

    headers = dict(request.headers)
    headers.pop("Host", None)

    try:
        async with ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            async with session.request(
                request.method, f"{UPSTREAM_URL}{path}",
                data=raw_body if raw_body else None, headers=headers,
            ) as resp:
                resp_body = await resp.read()
                resp_headers = dict(resp.headers)
                for h in ("Transfer-Encoding", "Content-Encoding"):
                    resp_headers.pop(h, None)
                return web.Response(body=resp_body, status=resp.status, headers=resp_headers)
    except Exception as e:
        return web.json_response(
            {"error": {"message": str(e), "type": "proxy_error"}}, status=502
        )


def cleanup_cache():
    files = sorted(CACHE_DIR.glob("voice_*"), key=lambda f: f.stat().st_mtime)
    for f in files[:-MAX_CACHE_FILES]:
        f.unlink(missing_ok=True)


async def periodic_cleanup():
    while True:
        await asyncio.sleep(3600)
        cleanup_cache()


async def on_startup(app):
    asyncio.create_task(periodic_cleanup())


def main():
    if not API_KEY:
        print("[voxmood] ✗ No API key found.")
        print("[voxmood]   Set VOXMOOD_API_KEY env var or create .env file.")
        sys.exit(1)

    app = web.Application()
    app.on_startup.append(on_startup)
    app.router.add_post("/v1/chat/completions", handle_chat_completions)
    app.router.add_post("/chat/completions", handle_chat_completions)
    app.router.add_get("/health", handle_health)
    app.router.add_route("*", "/{path:.*}", handle_catchall)

    print(f"[voxmood] Voice emotion sidecar starting")
    print(f"[voxmood] Port: {PORT}")
    print(f"[voxmood] Upstream: {UPSTREAM_URL}")
    print(f"[voxmood] Model: {ANALYSIS_MODEL}")
    print(f"[voxmood] Language: {LANGUAGE}")
    print(f"[voxmood] Output: {ANALYSIS_OUTPUT}")
    web.run_app(app, port=PORT, print=lambda msg: print(f"[voxmood] {msg}"))


if __name__ == "__main__":
    main()
