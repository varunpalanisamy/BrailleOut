"""
Lightweight Flask API server for the Braille web frontend.
Run with: python api_server.py
Runs on port 5001 so it doesn't conflict with anything else.
"""

import os
# Must be set before torch / whisper / opencv import to prevent semaphore leaks
# and segfaults caused by PyTorch's internal thread pools colliding with Flask threads.
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

import re
import json
import base64
import collections
import html as html_lib
import threading
import time
import cv2
from flask import Flask, jsonify, request, Response, stream_with_context
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

# ── Arduino serial ──────────────────────────────────────────────
SERIAL_BAUD = 9600
_ser = None
_ser_lock = threading.Lock()
_serial_warned = False

try:
    import serial as _serial_mod
    from serial.tools import list_ports as _list_ports
    _SERIAL_LIB = True
except ImportError:
    _SERIAL_LIB = False
    print("[Serial] pyserial not installed — Arduino output disabled")

def _find_arduino_port() -> str | None:
    """Return the first port that looks like an Arduino, or None."""
    for port in _list_ports.comports():
        desc = (port.description or '').lower()
        mfr  = (port.manufacturer or '').lower()
        if any(k in desc or k in mfr for k in ('arduino', 'usbmodem', 'ch340', 'cp210', 'ftdi')):
            return port.device
    return None

def _get_serial():
    global _ser, _serial_warned
    if not _SERIAL_LIB:
        return None
    with _ser_lock:
        if _ser is None or not _ser.isOpen():
            port = _find_arduino_port()
            if port is None:
                if not _serial_warned:
                    print("[Serial] No Arduino found — braille hardware disabled")
                    _serial_warned = True
                return None
            try:
                _ser = _serial_mod.Serial(port, SERIAL_BAUD, timeout=1)
                time.sleep(2)
                _serial_warned = False
                print(f"[Serial] Connected: {port}")
            except Exception as e:
                if not _serial_warned:
                    print(f"[Serial] Could not connect to {port}: {e}")
                    _serial_warned = True
                _ser = None
    return _ser

def _send_to_arduino(pattern: str):
    ser = _get_serial()
    if ser is None:
        return
    def _go():
        try:
            with _ser_lock:
                ser.write((pattern + "\n").encode())
        except Exception as ex:
            print(f"[Serial] Write error: {ex}")
    threading.Thread(target=_go, daemon=True).start()

@app.route("/api/send-pattern", methods=["POST"])
def send_pattern():
    data = request.get_json(force=True)
    pattern = data.get("pattern", "000000")
    if len(pattern) != 6 or not all(c in "01" for c in pattern):
        return jsonify({"error": "pattern must be 6 binary chars"}), 400
    _send_to_arduino(pattern)
    # Pulse: bring all pins back down after 300 ms
    threading.Timer(0.3, lambda: _send_to_arduino("000000")).start()
    return jsonify({"ok": True, "pattern": pattern})

@app.route("/api/arduino-status")
def arduino_status():
    ser = _get_serial()
    return jsonify({"connected": ser is not None})

# ── Webcam ──────────────────────────────────────────────────────────────────
import contextlib

@contextlib.contextmanager
def _silence_cv():
    """Redirect stderr at the fd level to suppress OpenCV's probe warnings."""
    devnull_fd = os.open(os.devnull, os.O_WRONLY)
    saved = os.dup(2)
    try:
        os.dup2(devnull_fd, 2)
        yield
    finally:
        os.dup2(saved, 2)
        os.close(saved)
        os.close(devnull_fd)

def _autodetect_camera() -> int:
    for i in range(5):
        with _silence_cv():
            cap = cv2.VideoCapture(i)
            ok, _ = cap.read() if cap.isOpened() else (False, None)
            cap.release()
        if ok:
            print(f"[Camera] Auto-detected camera at index {i}")
            return i
    print("[Camera] No camera detected — defaulting to index 0")
    return 0

_webcam_index = _autodetect_camera()
_cap: cv2.VideoCapture | None = None
_cap_lock = threading.Lock()


def _get_cap() -> cv2.VideoCapture:
    global _cap
    if _cap is None or not _cap.isOpened():
        _cap = cv2.VideoCapture(_webcam_index)
    return _cap


def _release_cap():
    global _cap
    if _cap is not None:
        try:
            _cap.release()
        except Exception:
            pass
        _cap = None


def _read_frame():
    with _cap_lock:
        cap = _get_cap()
        ok, frame = cap.read()
    return ok, frame if ok else None


@app.route("/api/cameras")
def list_cameras():
    available = []
    for i in range(10):
        if i == _webcam_index and _cap is not None and _cap.isOpened():
            label = "Built-in" if i == 0 else f"Camera {i}"
            available.append({"index": i, "label": label})
            continue
        with _silence_cv():
            cap = cv2.VideoCapture(i, cv2.CAP_AVFOUNDATION)
            opened = cap.isOpened()
            if not opened:
                cap.release()
                cap = cv2.VideoCapture(i)
                opened = cap.isOpened()
            cap.release()
        if opened:
            label = "Built-in" if i == 0 else f"Camera {i}"
            available.append({"index": i, "label": label})
    return jsonify({"cameras": available, "active": _webcam_index})


@app.route("/api/set-camera", methods=["POST"])
def set_camera():
    global _webcam_index
    data = request.get_json(force=True)
    idx = data.get("index")
    if not isinstance(idx, int):
        return jsonify({"error": "index must be an integer"}), 400
    with _cap_lock:
        _release_cap()
        _webcam_index = idx
    return jsonify({"ok": True, "active": _webcam_index})


def _mjpeg_stream():
    while True:
        ok, frame = _read_frame()
        if not ok:
            time.sleep(0.05)
            continue
        _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n\r\n" +
            buf.tobytes() +
            b"\r\n"
        )


@app.route("/api/video-feed")
def video_feed():
    return Response(_mjpeg_stream(), mimetype="multipart/x-mixed-replace; boundary=frame")



def extract_video_id(url: str) -> str | None:
    patterns = [
        r"(?:v=)([a-zA-Z0-9_-]{11})",
        r"(?:youtu\.be/)([a-zA-Z0-9_-]{11})",
        r"(?:embed/)([a-zA-Z0-9_-]{11})",
        r"(?:shorts/)([a-zA-Z0-9_-]{11})",
    ]
    for pattern in patterns:
        m = re.search(pattern, url)
        if m:
            return m.group(1)
    return None


@app.route("/api/transcript")
def get_transcript():
    url = request.args.get("url", "").strip()
    if not url:
        return jsonify({"error": "No URL provided"}), 400

    video_id = extract_video_id(url)
    if not video_id:
        return jsonify({"error": "Could not extract video ID — paste the full YouTube URL"}), 400

    try:
        import http.cookiejar
        import requests as req_mod
        from youtube_transcript_api import YouTubeTranscriptApi
        cookies_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cookies.txt")
        if os.path.exists(cookies_path):
            session = req_mod.Session()
            jar = http.cookiejar.MozillaCookieJar(cookies_path)
            jar.load(ignore_discard=True, ignore_expires=True)
            session.cookies = jar
            api = YouTubeTranscriptApi(http_client=session)
        else:
            api = YouTubeTranscriptApi()
        transcript = api.fetch(video_id)
        raw = " ".join(snippet.text for snippet in transcript)
        text = html_lib.unescape(raw)
        return jsonify({"text": text, "video_id": video_id})
    except Exception as exc:
        msg = str(exc)
        if "blocked" in msg.lower() or "ip" in msg.lower():
            return jsonify({"error": "Your IP is temporarily blocked by YouTube. Switch to a different network (e.g. phone hotspot) and try again."}), 500
        return jsonify({"error": msg}), 500


@app.route("/api/capture", methods=["POST"])
def capture():
    ok, frame = _read_frame()
    if not ok or frame is None:
        return jsonify({"error": "Could not read frame from webcam"}), 500
    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
    image_b64 = base64.b64encode(buf.tobytes()).decode()
    try:
        from google import genai
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[{
                "parts": [
                    {"text": "Extract ONLY the text visible in this image. Return just the raw text with no explanation. If no text is visible, return an empty string."},
                    {"inline_data": {"mime_type": "image/jpeg", "data": image_b64}},
                ]
            }],
        )
        return jsonify({"text": (response.text or "").strip()})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/process-image", methods=["POST"])
def process_image():
    try:
        data = request.get_json(force=True)
        image_b64: str = data.get("image", "")
        if "," in image_b64:
            image_b64 = image_b64.split(",", 1)[1]

        from google import genai

        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                {
                    "parts": [
                        {
                            "text": (
                                "Extract ONLY the text visible in this image. "
                                "Return just the raw text with no explanation. "
                                "If no text is visible, return an empty string."
                            )
                        },
                        {
                            "inline_data": {
                                "mime_type": "image/jpeg",
                                "data": image_b64,
                            }
                        },
                    ]
                }
            ],
        )
        return jsonify({"text": (response.text or "").strip()})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


_last_snap: bytes | None = None
_last_snap_lock = threading.Lock()

# ── Temporal memory (last 3 Gemma summaries) ────────────────────
_frame_history: collections.deque = collections.deque(maxlen=3)
_frame_history_lock = threading.Lock()

# Stop retrying the minimal prompt after 3 consecutive empty responses
_empty_streak = 0
_MAX_RETRY_STREAK = 3

# ── Gemma system prompt + mode parsing ──────────────────────────
_GEMMA_SYSTEM = ""  # instructions folded into the user turn for better compliance

_MODE_DELAYS = {"TEXT": 1.5, "SCENE": 0.8, "PERSON": 1.2}

_MODE_FALLBACKS = {"TEXT": "text visible", "SCENE": "scene ahead", "PERSON": "person present"}

def _parse_gemma_output(raw: str):
    """Return (mode, clean_text, delay) from Gemma's tagged output."""
    text = raw.strip()
    # Primary: colon format "scene: busy coffee shop"
    m = re.search(r'\b(text|scene|person)\s*:\s*([^\n]+)', text, re.IGNORECASE)
    if m:
        mode = m.group(1).upper()
        desc = m.group(2).strip().rstrip(".,!?;:\"'").lower()
        clean = ' '.join(desc.split()[:8])
    else:
        # Fallback: bracket format "[SCENE] something"
        m2 = re.search(r'\[(text|scene|person)\]\s*([^\n]*)', text, re.IGNORECASE)
        if m2:
            mode = m2.group(1).upper()
            desc = m2.group(2).strip().rstrip(".,!?;:\"'").lower()
            clean = ' '.join(desc.split()[:8])
        else:
            # No recognised format — use the first line verbatim (better than canned phrase)
            mode = "SCENE"
            first_line = text.split('\n')[0].strip().rstrip(".,!?;:\"'").lower()
            clean = ' '.join(first_line.split()[:8])
    if not clean:
        clean = _MODE_FALLBACKS.get(mode, "nothing detected")
    return mode, clean, _MODE_DELAYS.get(mode, 1.5)

@app.route("/api/snap", methods=["POST"])
def snap():
    """Step 1: grab a frame instantly and store it. Returns a thumbnail so the
    frontend can show a preview while Gemma processes in the background."""
    global _last_snap
    ok, frame = _read_frame()
    if not ok or frame is None:
        return jsonify({"error": "Could not read frame from webcam"}), 500
    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
    with _last_snap_lock:
        _last_snap = buf.tobytes()
    thumbnail = base64.b64encode(_last_snap).decode()
    return jsonify({"ok": True, "thumbnail": thumbnail})


@app.route("/api/gemma-stream", methods=["POST"])
def gemma_stream():
    """
    Streaming SSE endpoint combining Features 1-3, 5, and 6.
    Accepts optional JSON body: { audio_transcript: "..." }
    Yields SSE tokens as they arrive from Ollama, then a final done event
    with mode (TEXT/SCENE/PERSON), clean text, and suggested pacing delay.
    """
    body = request.get_json(force=True, silent=True) or {}

    image_b64 = (body.get("image_b64") or "").strip()
    if not image_b64:
        with _last_snap_lock:
            snap_bytes = _last_snap
        if snap_bytes is None:
            def _err():
                yield "data: " + json.dumps({"error": "No frame snapped yet — call /api/snap first"}) + "\n\n"
            return Response(stream_with_context(_err()), mimetype="text/event-stream")
        image_b64 = base64.b64encode(snap_bytes).decode()

    with _frame_history_lock:
        history_list = list(_frame_history)

    user_content = (
        "Describe the most important thing in this image using exactly one of these:\n"
        "  text: <quote the words exactly> — use when readable text or signs are visible\n"
        "  person: <3-5 word description> — use when a person is the main subject\n"
        "  scene: <3-5 word description> — use for everything else\n"
        "Choose whichever fits best. Examples:\n"
        "  'text: stop'  'text: push to open'  'person: woman smiling'  'scene: kitchen counter'\n"
        "One line only. Never leave the description blank."
    )
    if history_list:
        prev_str = ", ".join(f"'{h}'" for h in history_list[-2:])
        user_content += f"\nContext — previously seen: {prev_str}."

    def _generate():
        import ollama
        full_text = ""
        try:
            messages = []
            if _GEMMA_SYSTEM:
                messages.append({"role": "system", "content": _GEMMA_SYSTEM})
            messages.append({"role": "user", "content": user_content, "images": [image_b64]})
            stream = ollama.chat(
                model="gemma4:e4b",
                messages=messages,
                stream=True,
                options={"temperature": 0.1, "num_predict": 60},
            )
            for chunk in stream:
                token = chunk["message"]["content"]
                full_text += token
                yield "data: " + json.dumps({"token": token}) + "\n\n"

            print(f"[Gemma] raw output: {repr(full_text)}")

            # Empty response — retry once with a simpler prompt, unless we've
            # had too many consecutive empties (dark room / bad lighting).
            global _empty_streak
            if not full_text.strip():
                if _empty_streak < _MAX_RETRY_STREAK:
                    print(f"[Gemma] Empty (streak {_empty_streak + 1}) — retrying with minimal prompt…")
                    try:
                        retry = ollama.chat(
                            model="gemma4:e4b",
                            messages=[{"role": "user", "content": "Is there any text in this image? If yes, say 'text:' then quote it. Otherwise describe in 5 words.", "images": [image_b64]}],
                            options={"temperature": 0.3, "num_predict": 30},
                        )
                        full_text = retry["message"]["content"]
                        print(f"[Gemma] retry output: {repr(full_text)}")
                    except Exception:
                        pass
                else:
                    print(f"[Gemma] Empty streak {_empty_streak} — skipping retry")
                _empty_streak += 1
            else:
                _empty_streak = 0  # reset on any successful response

            mode, clean_text, delay = _parse_gemma_output(full_text)
            with _frame_history_lock:
                if clean_text and clean_text not in _MODE_FALLBACKS.values():
                    _frame_history.append(clean_text)

            yield "data: " + json.dumps({
                "done": True,
                "text": clean_text,
                "mode": mode,
                "delay": delay,
            }) + "\n\n"
        except Exception as exc:
            yield "data: " + json.dumps({"error": str(exc)}) + "\n\n"

    return Response(
        stream_with_context(_generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.route("/api/gemma-process", methods=["POST"])
def gemma_process():
    """Step 2 fallback: run Gemma 4 on the last snapped frame (non-streaming). Takes 10-40s."""
    with _last_snap_lock:
        snap_bytes = _last_snap
    if snap_bytes is None:
        return jsonify({"error": "No frame snapped yet — call /api/snap first"}), 400
    image_b64 = base64.b64encode(snap_bytes).decode()
    try:
        import ollama
        resp = ollama.chat(
            model="gemma4:e4b",
            messages=[
                {"role": "system", "content": _GEMMA_SYSTEM},
                {
                    "role": "user",
                    "content": "What is the most important information in this image? Reply with [TEXT], [SCENE], or [PERSON] tag followed by 5 words or fewer.",
                    "images": [image_b64],
                },
            ],
            options={"temperature": 0.1, "num_predict": 30},
        )
        mode, clean_text, delay = _parse_gemma_output(resp["message"]["content"])
        with _frame_history_lock:
            if clean_text and clean_text not in _MODE_FALLBACKS.values():
                _frame_history.append(clean_text)
        return jsonify({"text": clean_text, "mode": mode, "delay": delay})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@app.route("/api/gemma-capture", methods=["POST"])
def gemma_capture():
    """Legacy single-step endpoint (kept for compatibility)."""
    ok, frame = _read_frame()
    if not ok or frame is None:
        return jsonify({"error": "Could not read frame from webcam"}), 500
    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    image_b64 = base64.b64encode(buf.tobytes()).decode()
    try:
        import ollama
        resp = ollama.chat(
            model="gemma4:e4b",
            messages=[
                {"role": "system", "content": _GEMMA_SYSTEM},
                {
                    "role": "user",
                    "content": "What is the most important information in this image? 5 words or fewer.",
                    "images": [image_b64],
                },
            ],
            options={"temperature": 0.1, "num_predict": 30},
        )
        text = resp["message"]["content"].strip().lower().rstrip(".,!?;:\"'").strip()
        return jsonify({"text": text})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500




if __name__ == "__main__":
    print("Starting Braille API server on http://localhost:5001")
    app.run(port=5001, debug=True, use_reloader=False, threaded=True)
