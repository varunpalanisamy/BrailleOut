"""
Lightweight Flask API server for the Braille web frontend.
Run with: python api_server.py
Runs on port 5001 so it doesn't conflict with anything else.
"""

import os
import re
import base64
import html as html_lib
import threading
import time
import cv2
from flask import Flask, jsonify, request, Response
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

# ── Arduino serial ──────────────────────────────────────────────
SERIAL_PORT = "/dev/cu.usbmodem1051DB2BD6802"
SERIAL_BAUD = 9600
_ser = None
_ser_lock = threading.Lock()

try:
    import serial as _serial_mod
    _SERIAL_LIB = True
except ImportError:
    _SERIAL_LIB = False
    print("[Serial] pyserial not installed — Arduino output disabled")

def _get_serial():
    global _ser
    if not _SERIAL_LIB:
        return None
    with _ser_lock:
        if _ser is None or not _ser.isOpen():
            try:
                _ser = _serial_mod.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=1)
                time.sleep(2)
                print(f"[Serial] Connected: {SERIAL_PORT}")
            except Exception as e:
                print(f"[Serial] Could not connect: {e}")
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
def _autodetect_camera() -> int:
    for i in range(5):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            ok, _ = cap.read()
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
        cap = cv2.VideoCapture(i, cv2.CAP_AVFOUNDATION)
        if not cap.isOpened():
            cap = cv2.VideoCapture(i)
        if cap.isOpened():
            label = "Built-in" if i == 0 else f"Camera {i}"
            available.append({"index": i, "label": label})
            cap.release()
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

_GEMMA_SYSTEM = (
    "You are an intelligent interpreter for a deaf-blind braille reader. "
    "You receive camera images from their environment. "
    "Distill the most important information into AT MOST 5 words. "
    "Output ONLY the phrase — no explanation, no punctuation except spaces, lowercase only. "
    "If nothing meaningful is visible, output: nothing detected"
)

@app.route("/api/snap", methods=["POST"])
def snap():
    """Step 1: grab a frame instantly and store it. Returns a thumbnail so the
    frontend can show a preview while Gemma processes in the background."""
    global _last_snap
    ok, frame = _read_frame()
    if not ok or frame is None:
        return jsonify({"error": "Could not read frame from webcam"}), 500
    _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    with _last_snap_lock:
        _last_snap = buf.tobytes()
    thumbnail = base64.b64encode(_last_snap).decode()
    return jsonify({"ok": True, "thumbnail": thumbnail})


@app.route("/api/gemma-process", methods=["POST"])
def gemma_process():
    """Step 2: run Gemma 4 on the last snapped frame. Takes 10-40s."""
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
    app.run(port=5001, debug=True)
