#!/usr/bin/env python3
"""Quick test for VoxMood — verifies the proxy starts and can analyze audio.

Usage:
    # 1. Start VoxMood in another terminal:
    #    python voxmood.py
    #
    # 2. Run this test:
    #    python test_voxmood.py
    #
    # Or test with your own audio file:
    #    python test_voxmood.py /path/to/voice.mp3
"""

import asyncio
import base64
import json
import sys
from pathlib import Path

try:
    import aiohttp
except ImportError:
    print("Run: pip install aiohttp")
    sys.exit(1)

VOXMOOD_URL = "http://localhost:9233"


async def test_health():
    """Test 1: health check."""
    print("\n[Test 1] Health check...", end=" ")
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as s:
            async with s.get(f"{VOXMOOD_URL}/health") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print(f"OK — model: {data.get('model')}, language: {data.get('language')}")
                    return True
                else:
                    print(f"FAIL — status {resp.status}")
                    return False
    except aiohttp.ClientConnectorError:
        print("FAIL — cannot connect. Is VoxMood running on port 9233?")
        return False


async def test_audio_analysis(audio_path: str | None = None):
    """Test 2: send audio and check analysis."""
    print("\n[Test 2] Audio analysis...", end=" ")

    if audio_path and Path(audio_path).exists():
        audio_bytes = Path(audio_path).read_bytes()
        ext = Path(audio_path).suffix.lstrip(".")
        print(f"(using {audio_path}, {len(audio_bytes)} bytes)")
    else:
        print("(generating 1s silent test tone)")
        audio_bytes = generate_test_audio()
        ext = "wav"

    audio_b64 = base64.b64encode(audio_bytes).decode()
    mime = {"mp3": "audio/mp3", "ogg": "audio/ogg", "wav": "audio/wav",
            "m4a": "audio/mp4"}.get(ext, "audio/mpeg")

    payload = {
        "model": "qwen-audio-turbo",
        "messages": [{
            "role": "user",
            "content": [
                {
                    "type": "input_audio",
                    "input_audio": {"data": f"data:{mime};base64,{audio_b64}", "format": ext}
                },
                {"type": "text", "text": "transcribe this audio"}
            ]
        }]
    }

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as s:
            async with s.post(
                f"{VOXMOOD_URL}/v1/chat/completions",
                json=payload,
                headers={"Content-Type": "application/json"}
            ) as resp:
                status = resp.status
                body = await resp.text()

                if status in (200, 401, 400):
                    print(f"Proxy forwarded OK (upstream returned {status})")
                    if status == 200:
                        print(f"  Transcript: {json.loads(body).get('choices', [{}])[0].get('message', {}).get('content', '?')[:100]}")
                else:
                    print(f"Unexpected status: {status}")
                    print(f"  Body: {body[:200]}")

    except Exception as e:
        print(f"FAIL — {e}")
        return False

    print("\n  Waiting 5s for async analysis...", end=" ", flush=True)
    await asyncio.sleep(5)

    analysis_file = Path("/tmp/voxmood_analysis.json")
    if analysis_file.exists():
        analysis = json.loads(analysis_file.read_text())
        print("OK!")
        print(f"\n  === Analysis Result ===")
        print(f"  Time: {analysis.get('iso_time')}")
        print(f"  Model: {analysis.get('model')}")
        for line in analysis.get("analysis", "").split("\n"):
            print(f"  {line}")
        return True
    else:
        print("No analysis file found (might still be processing)")
        return False


def generate_test_audio():
    """Generate a minimal valid WAV file (1s silence) for testing."""
    import struct
    sample_rate = 16000
    duration = 1
    n_samples = sample_rate * duration
    header = struct.pack('<4sI4s', b'RIFF', 36 + n_samples * 2, b'WAVE')
    fmt = struct.pack('<4sIHHIIHH', b'fmt ', 16, 1, 1, sample_rate, sample_rate * 2, 2, 16)
    data_header = struct.pack('<4sI', b'data', n_samples * 2)
    samples = b'\x00\x00' * n_samples
    return header + fmt + data_header + samples


async def main():
    print("=" * 50)
    print("VoxMood Test Suite")
    print("=" * 50)

    audio_path = sys.argv[1] if len(sys.argv) > 1 else None

    ok = await test_health()
    if not ok:
        print("\nVoxMood is not running. Start it first:")
        print("  python voxmood.py")
        return

    await test_audio_analysis(audio_path)

    print("\n" + "=" * 50)
    print("Tests complete!")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
