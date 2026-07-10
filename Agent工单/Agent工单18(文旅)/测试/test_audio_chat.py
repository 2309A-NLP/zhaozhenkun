"""工单18：语音与音频接口测试脚本，负责验证语音问答接口是否可用。"""
import io
import json
import wave
from urllib import request, parse

BASE_URL = "http://127.0.0.1:5050"

def build_wav_bytes() -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(16000)
        wav_file.writeframes(b"\x00\x00" * 8000)
    return buffer.getvalue()

def post_audio(session_id: str) -> dict:
    boundary = "----HermesBoundary123456"
    body = []
    for key, value in {"session_id": session_id, "language": "zh"}.items():
        body.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"\r\n\r\n{value}\r\n".encode())
    body.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"audio\"; filename=\"voice.wav\"\r\nContent-Type: audio/wav\r\n\r\n".encode())
    body.append(build_wav_bytes())
    body.append(f"\r\n--{boundary}--\r\n".encode())
    data = b"".join(body)
    req = request.Request(f"{BASE_URL}/api/chat/audio", data=data, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}, method="POST")
    with request.urlopen(req) as response:
        return json.loads(response.read().decode("utf-8"))

def post_json(url: str, payload: dict) -> dict:
    req = request.Request(url, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
    with request.urlopen(req) as response:
        return json.loads(response.read().decode("utf-8"))

if __name__ == "__main__":
    session = post_json(f"{BASE_URL}/api/session/create", {})
    print(json.dumps(post_audio(session["session_id"]), ensure_ascii=False, indent=2))
