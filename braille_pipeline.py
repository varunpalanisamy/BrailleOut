#!/usr/bin/env python3
"""
braille_pipeline.py  —  HackDavis 2026 AI Braille Display
==========================================================
Full pipeline: webcam → Gemini Vision OCR → Claude cleanup → Braille display → Arduino → TTS

INSTALL (Python packages):
    pip install opencv-python google-generativeai anthropic pyserial pyttsx3 requests

ENVIRONMENT VARIABLES (optional — can also hardcode below):
    export ANTHROPIC_API_KEY="sk-ant-..."
    export GEMINI_API_KEY="AIza..."
    export ELEVENLABS_API_KEY="..."

ARDUINO:
    Run  ls /dev/cu.*  to find your port, then set SERIAL_PORT below.
    Sketch should read serial lines like "101010\n" and drive 6 servos.
"""

import os
import sys
import time
import threading
import subprocess
import tempfile
import tkinter as tk

import base64

import cv2
import google.generativeai as genai
import anthropic

try:
    import serial
    _SERIAL_LIB = True
except ImportError:
    _SERIAL_LIB = False

# ============================================================
#  CONFIGURATION — edit these
# ============================================================
ANTHROPIC_API_KEY   = os.getenv("ANTHROPIC_API_KEY", "")
GEMINI_API_KEY      = os.getenv("GEMINI_API_KEY", "")
GEMINI_VISION_MODEL = "gemini-2.0-flash"
ELEVENLABS_API_KEY  = os.getenv("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = "EXAVITQu4vr4xnSDxMaL"    # Rachel — natural female
SERIAL_PORT         = "/dev/cu.usbmodem14101"     # change to match your Arduino
SERIAL_BAUD         = 9600
CLAUDE_MODEL        = "claude-sonnet-4-6"         # note: "claude-sonnet-4-20250514" is deprecated
WEBCAM_INDEX        = 0

SYSTEM_PROMPT = (
    "You are a text cleanup assistant. The user will send you raw OCR text "
    "extracted from a webcam image. Clean up any OCR errors, fix spelling, "
    "remove gibberish characters, and return only the cleaned plain text. "
    "Nothing else."
)

# ============================================================
#  BRAILLE LOOKUP TABLE — Grade 1
#  Dots 1,2,3 = left column top→bottom; 4,5,6 = right column top→bottom
# ============================================================
BRAILLE: dict[str, list[int]] = {
    'a': [1],            'b': [1, 2],         'c': [1, 4],
    'd': [1, 4, 5],      'e': [1, 5],          'f': [1, 2, 4],
    'g': [1, 2, 4, 5],   'h': [1, 2, 5],       'i': [2, 4],
    'j': [2, 4, 5],      'k': [1, 3],           'l': [1, 2, 3],
    'm': [1, 3, 4],      'n': [1, 3, 4, 5],    'o': [1, 3, 5],
    'p': [1, 2, 3, 4],   'q': [1, 2, 3, 4, 5], 'r': [1, 2, 3, 5],
    's': [2, 3, 4],      't': [2, 3, 4, 5],     'u': [1, 3, 6],
    'v': [1, 2, 3, 6],   'w': [2, 4, 5, 6],     'x': [1, 3, 4, 6],
    'y': [1, 3, 4, 5, 6],'z': [1, 3, 5, 6],
    ' ': [],
}


def dots_to_pattern(dots: list[int]) -> str:
    """[1,4] → '100100'  (bit i=1 means dot i is raised)"""
    return ''.join('1' if d in dots else '0' for d in range(1, 7))


# ============================================================
#  STEP 1 — Webcam capture
# ============================================================

def capture_frame():
    print("\n[Step 1] Webcam opening… press SPACE to capture, Q to quit.")
    cap = cv2.VideoCapture(WEBCAM_INDEX)
    if not cap.isOpened():
        print("[Step 1] ERROR: cannot open webcam.")
        sys.exit(1)

    frame = None
    while True:
        ok, f = cap.read()
        if not ok:
            continue
        cv2.imshow("Braille Camera — SPACE to capture | Q to quit", f)
        key = cv2.waitKey(1) & 0xFF
        if key == ord(' '):
            frame = f.copy()
            print("[Step 1] Frame captured.")
            break
        elif key == ord('q'):
            cap.release()
            cv2.destroyAllWindows()
            sys.exit(0)

    cap.release()
    cv2.destroyAllWindows()
    return frame


# ============================================================
#  STEP 2 — OCR
# ============================================================

def ocr_frame(frame) -> str:
    print("\n[Step 2] Sending image to Gemini Vision for OCR…")
    _, buf = cv2.imencode(".jpg", frame)
    image_part = {
        "mime_type": "image/jpeg",
        "data": base64.b64encode(buf.tobytes()).decode(),
    }
    genai.configure(api_key=GEMINI_API_KEY or None)
    model = genai.GenerativeModel(GEMINI_VISION_MODEL)
    try:
        response = model.generate_content([
            image_part,
            "Extract all text visible in this image. Return the raw text only — no commentary, no formatting, no markdown.",
        ])
        raw = response.text.strip()
    except Exception as e:
        print(f"[Step 2] Gemini error: {e}")
        raw = ""
    print(f"[Step 2] Gemini OCR result:\n{raw or '(empty)'}\n")
    return raw


# ============================================================
#  STEP 3 — Claude cleanup (system prompt cached)
# ============================================================

def clean_text_with_claude(raw_text: str) -> str:
    print("[Step 3] Sending to Claude for cleanup…")
    if not raw_text.strip():
        print("[Step 3] Nothing to clean.")
        return ""

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY or None)
    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    # Static system prompt → cache it so repeated runs are cheaper
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": raw_text}],
        )
        cleaned = response.content[0].text.strip()
        print(f"[Step 3] Cleaned: {cleaned!r}")
        cr = getattr(response.usage, "cache_read_input_tokens", 0)
        cw = getattr(response.usage, "cache_creation_input_tokens", 0)
        if cr or cw:
            print(f"[Step 3] Prompt cache — read: {cr} tok, write: {cw} tok")
        return cleaned
    except anthropic.APIError as e:
        print(f"[Step 3] Claude error: {e}  — falling back to raw OCR text.")
        return raw_text.strip()


# ============================================================
#  STEP 6 — Serial output to Arduino
# ============================================================

def init_serial():
    if not _SERIAL_LIB:
        print("[Serial] pyserial not installed. Skipping.")
        return None
    try:
        ser = serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=1)
        time.sleep(2)  # wait for Arduino bootloader
        print(f"[Serial] Connected: {SERIAL_PORT} @ {SERIAL_BAUD} baud.")
        return ser
    except Exception as e:
        print(f"[Serial] No Arduino found ({e}). Serial disabled.")
        return None


def send_to_arduino(pattern: str, ser) -> None:
    if ser is None:
        return
    def _send():
        try:
            ser.write((pattern + "\n").encode())
        except Exception as ex:
            print(f"[Serial] Write error: {ex}")
    threading.Thread(target=_send, daemon=True).start()


# ============================================================
#  STEP 7 — Voice output
#  Priority: ElevenLabs → pyttsx3 → macOS say
# ============================================================

def _speak_elevenlabs(text: str) -> bool:
    if not ELEVENLABS_API_KEY:
        return False
    try:
        import requests
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
        resp = requests.post(
            url,
            headers={"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"},
            json={
                "text": text,
                "model_id": "eleven_monolingual_v1",
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.75},
            },
            timeout=10,
        )
        if resp.status_code == 200:
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                f.write(resp.content)
                tmp = f.name
            subprocess.Popen(["afplay", tmp])
            return True
        print(f"[TTS] ElevenLabs {resp.status_code}: {resp.text[:80]}")
    except Exception as e:
        print(f"[TTS] ElevenLabs error: {e}")
    return False


def _speak_pyttsx3(text: str) -> bool:
    try:
        import pyttsx3
        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()
        return True
    except Exception as e:
        print(f"[TTS] pyttsx3 error: {e}")
    return False


def _speak_say(text: str) -> None:
    try:
        subprocess.Popen(["say", text])
    except Exception:
        pass


def speak_async(text: str) -> None:
    def _run():
        if _speak_elevenlabs(text):
            return
        if _speak_pyttsx3(text):
            return
        _speak_say(text)
    threading.Thread(target=_run, daemon=True).start()


# ============================================================
#  STEP 5 — tkinter Braille cell display
# ============================================================

_DOT_POS = {
    1: (0, 0), 4: (0, 1),
    2: (1, 0), 5: (1, 1),
    3: (2, 0), 6: (2, 1),
}
_R   = 30   # dot radius px
_PAD = 16   # padding px
_CW  = _PAD + (_R * 2 + _PAD) * 2
_CH  = _PAD + (_R * 2 + _PAD) * 3


class BrailleDisplay(tk.Tk):
    def __init__(self, letters: list[str], ser):
        super().__init__()
        self.letters = letters
        self.ser = ser
        self.idx = -1

        self.title("HackDavis Braille Display")
        self.resizable(False, False)
        self.configure(bg="#f5f5f0")

        tk.Label(self, text="HackDavis Braille Display",
                 font=("Helvetica", 16, "bold"), bg="#f5f5f0").pack(pady=(14, 0))
        tk.Label(self, text="SPACE → next letter   ESC → quit",
                 font=("Helvetica", 11), fg="#888", bg="#f5f5f0").pack(pady=(2, 12))

        self.canvas = tk.Canvas(self, width=_CW, height=_CH,
                                bg="#fff", highlightthickness=2,
                                highlightbackground="#ccc")
        self.canvas.pack(padx=40)

        self.letter_var = tk.StringVar(value="—")
        tk.Label(self, textvariable=self.letter_var,
                 font=("Helvetica", 60, "bold"), bg="#f5f5f0").pack(pady=(14, 2))

        self.info_var = tk.StringVar(value="press SPACE to begin")
        tk.Label(self, textvariable=self.info_var,
                 font=("Helvetica", 11), fg="#888", bg="#f5f5f0").pack()

        self.prog_var = tk.StringVar(value=f"0 / {len(letters)} letters")
        tk.Label(self, textvariable=self.prog_var,
                 font=("Helvetica", 10), fg="#bbb", bg="#f5f5f0").pack(pady=(4, 20))

        self._ovals: dict[int, int] = {}
        self._draw_cell()

        self.bind("<space>", self._advance)
        self.bind("<Escape>", lambda _: self.destroy())

    def _dot_xy(self, dot: int) -> tuple[int, int]:
        row, col = _DOT_POS[dot]
        x = _PAD + _R + col * (_R * 2 + _PAD)
        y = _PAD + _R + row * (_R * 2 + _PAD)
        return x, y

    def _draw_cell(self) -> None:
        self.canvas.delete("all")
        self._ovals.clear()
        for dot in range(1, 7):
            x, y = self._dot_xy(dot)
            oid = self.canvas.create_oval(
                x - _R, y - _R, x + _R, y + _R,
                fill="#fff", outline="#333", width=2,
            )
            self._ovals[dot] = oid

    def _render(self, active: list[int]) -> None:
        for dot, oid in self._ovals.items():
            self.canvas.itemconfig(oid, fill="#111" if dot in active else "#fff")

    def _advance(self, _=None) -> None:
        self.idx += 1
        if self.idx >= len(self.letters):
            self.letter_var.set("✓")
            self.info_var.set("All letters displayed.")
            self._render([])
            return

        ch = self.letters[self.idx]
        dots = BRAILLE.get(ch, [])
        pattern = dots_to_pattern(dots)
        dot_str = " ".join(str(d) for d in sorted(dots)) or "none"

        self._render(dots)
        self.letter_var.set(ch.upper() if ch != " " else "(sp)")
        self.info_var.set(f"dots: {dot_str}   pattern: {pattern}")
        self.prog_var.set(f"{self.idx + 1} / {len(self.letters)} letters")

        # Terminal
        print(f"[Display] '{ch}'  dots:{dot_str}  pattern:{pattern}")

        # Arduino
        send_to_arduino(pattern, self.ser)

        # TTS
        speak_async("space" if ch == " " else ch)


# ============================================================
#  MAIN
# ============================================================

def main():
    # Step 1 — capture
    frame = capture_frame()

    # Step 2 — OCR
    raw_text = ocr_frame(frame)

    # Step 3 — Claude cleanup
    cleaned = clean_text_with_claude(raw_text)

    # Build letter queue (only displayable chars)
    letters = [ch for ch in cleaned.lower() if ch in BRAILLE]
    if not letters:
        print("\n[Pipeline] No displayable characters in cleaned text. Exiting.")
        sys.exit(0)
    print(f"\n[Pipeline] Letter queue ({len(letters)}): {' '.join(letters)}\n")

    # Step 6 — serial
    ser = init_serial()

    # Step 5 — display (blocks until window closes)
    print("[Step 5] Braille window open. Press SPACE to start, ESC to quit.")
    app = BrailleDisplay(letters, ser)
    app.mainloop()

    if ser:
        ser.close()
    print("\n[Pipeline] Complete.")


if __name__ == "__main__":
    main()
