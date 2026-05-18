#!/usr/bin/env python3
"""
braille_pipeline.py  —  HackDavis 2026 AI Braille Display
==========================================================
Full pipeline: webcam (live in UI) → Gemini Vision OCR → Claude cleanup → Braille display → Arduino → TTS

INSTALL (Python packages):
    pip install opencv-python Pillow google-generativeai anthropic pyserial pyttsx3 requests python-dotenv

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
import tkinter as tk
from PIL import Image, ImageTk

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import cv2
from google import genai as google_genai
from google.genai import types as genai_types
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
GEMINI_VISION_MODEL = "gemini-2.5-flash"
SERIAL_PORT         = "/dev/cu.usbmodem1051DB2BD6802"     # change to match your Arduino
SERIAL_BAUD         = 9600
CLAUDE_MODEL        = "claude-sonnet-4-6"
WEBCAM_INDEX        = 1                   # external USB webcam (0 = built-in, never use)

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

_DOT_POS = {
    1: (0, 0), 4: (0, 1),
    2: (1, 0), 5: (1, 1),
    3: (2, 0), 6: (2, 1),
}

_R   = 30   # dot radius px
_PAD = 16   # padding px
_CW  = _PAD + (_R * 2 + _PAD) * 2
_CH  = _PAD + (_R * 2 + _PAD) * 3

CAM_W = 480
CAM_H = 360


# Physical servo order matches left→right, top→bottom wiring:
# servo0=top-left(dot1), servo1=top-right(dot4), servo2=mid-left(dot2),
# servo3=mid-right(dot5), servo4=bot-left(dot3), servo5=bot-right(dot6)
_SERVO_DOT_ORDER = [1, 2, 3, 4, 5, 6]  # sequential: servo 0→dot1, 1→dot2, 2→dot3, 3→dot4, 4→dot5, 5→dot6

def dots_to_pattern(dots: list[int]) -> str:
    return ''.join('1' if d in dots else '0' for d in _SERVO_DOT_ORDER)


# ============================================================
#  SERIAL
# ============================================================

def init_serial():
    if not _SERIAL_LIB:
        print("[Serial] pyserial not installed. Skipping.")
        return None
    try:
        ser = serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=1)
        time.sleep(2)  # wait for Arduino bootloader to finish
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
#  TTS — macOS say
# ============================================================

def speak_async(text: str) -> None:
    def _run():
        try:
            subprocess.Popen(["say", text])
        except Exception:
            pass
    threading.Thread(target=_run, daemon=True).start()


# ============================================================
#  OCR + CLEANUP
# ============================================================

def ocr_with_gemma(frame) -> str:
    """Primary OCR path: single local Gemma call replaces Gemini + Claude chain."""
    print("[Step 2-Gemma] Encoding frame and calling Gemma for OCR…")
    try:
        import ollama
        import base64 as _b64
        _, buf = cv2.imencode(".jpg", frame)
        image_b64 = _b64.b64encode(buf.tobytes()).decode()
        t0 = time.time()
        resp = ollama.chat(
            model="gemma4:e4b",
            messages=[
                {
                    "role": "user",
                    "content": "Extract all text visible in this image. Return only the clean text, no commentary, no markdown.",
                    "images": [image_b64],
                }
            ],
            options={"temperature": 0.0, "num_predict": 200},
        )
        raw = resp["message"]["content"].strip()
        print(f"[Step 2-Gemma] Gemma OCR in {time.time()-t0:.1f}s → {raw!r}")
        return raw
    except Exception as e:
        print(f"[Step 2-Gemma] ERROR: {e}")
        return ""


def ocr_frame(frame) -> str:
    print("[Step 2] Encoding frame and calling Gemini Vision…")
    _, buf = cv2.imencode(".jpg", frame)
    image_bytes = buf.tobytes()
    client = google_genai.Client(api_key=GEMINI_API_KEY or None)
    t0 = time.time()
    try:
        response = client.models.generate_content(
            model=GEMINI_VISION_MODEL,
            contents=[
                genai_types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                "Extract all text visible in this image. Return the raw text only — no commentary, no formatting, no markdown.",
            ],
        )
        raw = response.text.strip()
        print(f"[Step 2] Gemini responded in {time.time()-t0:.1f}s")
    except Exception as e:
        print(f"[Step 2] Gemini ERROR: {e}")
        raw = ""
    print(f"[Step 2] Raw OCR:\n--- START ---\n{raw or '(empty)'}\n--- END ---")
    return raw


def clean_text_with_claude(raw_text: str) -> str:
    print("[Step 3] Sending to Claude for text cleanup…")
    if not raw_text.strip():
        print("[Step 3] Nothing to clean — skipping Claude call.")
        return ""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY or None)
    t0 = time.time()
    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            system=[
                {
                    "type": "text",
                    "text": SYSTEM_PROMPT,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": raw_text}],
        )
        cleaned = response.content[0].text.strip()
        print(f"[Step 3] Claude responded in {time.time()-t0:.1f}s → {cleaned!r}")
        cr = getattr(response.usage, "cache_read_input_tokens", 0)
        cw = getattr(response.usage, "cache_creation_input_tokens", 0)
        if cr or cw:
            print(f"[Step 3] Cache — read: {cr} tok, write: {cw} tok")
        return cleaned
    except anthropic.APIError as e:
        print(f"[Step 3] Claude ERROR: {e}")
        return raw_text.strip()


# ============================================================
#  UNIFIED PIPELINE APP
# ============================================================

class BraillePipelineApp(tk.Tk):
    def __init__(self, ser):
        super().__init__()
        self.ser = ser
        self.letters: list[str] = []
        self.idx = -1
        self._processing = False
        self._last_frame = None
        self._auto_mode = False
        self._auto_job = None

        self.title("HackDavis 2026 — AI Braille Display")
        self.resizable(False, False)
        self.configure(bg="#f5f5f0")

        self._build_ui()

        self._cap = cv2.VideoCapture(WEBCAM_INDEX)
        if not self._cap.isOpened():
            self._set_status("ERROR: cannot open webcam.", error=True)
        else:
            self._update_camera()

        self.bind("<space>",  lambda _: self._advance(+1))
        self.bind("<Left>",   lambda _: self._advance(-1))
        self.bind("<Right>",  lambda _: self._advance(+1))
        self.bind("<Escape>", lambda _: self._quit())
        self.protocol("WM_DELETE_WINDOW", self._quit)

    # ---- UI construction ----------------------------------------

    def _build_ui(self):
        bg = "#f5f5f0"

        tk.Label(self, text="HackDavis 2026 — AI Braille Display",
                 font=("Helvetica", 16, "bold"), bg=bg).pack(pady=(12, 2))

        arduino_txt = f"Arduino: connected ({SERIAL_PORT})" if self.ser else "Arduino: not connected (display only)"
        arduino_col = "#27ae60" if self.ser else "#aaa"
        tk.Label(self, text=arduino_txt, font=("Helvetica", 10, "bold"),
                 fg=arduino_col, bg=bg).pack(pady=(0, 4))

        # Top row: live camera | braille cell
        top = tk.Frame(self, bg=bg)
        top.pack(padx=20, pady=8)

        # Camera feed
        cam_frame = tk.Frame(top, bg="#000", width=CAM_W, height=CAM_H)
        cam_frame.pack_propagate(False)
        cam_frame.pack(side=tk.LEFT, padx=(0, 24))
        self._cam_label = tk.Label(cam_frame, bg="#000")
        self._cam_label.pack(fill=tk.BOTH, expand=True)

        # Right: braille cell + letter info
        right = tk.Frame(top, bg=bg)
        right.pack(side=tk.LEFT, anchor=tk.N)

        tk.Label(right, text="Braille Cell",
                 font=("Helvetica", 12, "bold"), bg=bg).pack(pady=(0, 6))

        self._canvas = tk.Canvas(right, width=_CW, height=_CH,
                                  bg="#fff", highlightthickness=2,
                                  highlightbackground="#ccc")
        self._canvas.pack()
        self._ovals: dict[int, int] = {}
        self._draw_cell()

        # Large letter
        self._letter_var = tk.StringVar(value="—")
        tk.Label(right, textvariable=self._letter_var,
                 font=("Helvetica", 60, "bold"), bg=bg, width=4).pack(pady=(10, 0))

        # "I see the letter: K"
        self._see_var = tk.StringVar(value="")
        tk.Label(right, textvariable=self._see_var,
                 font=("Helvetica", 13), fg="#333", bg=bg).pack()

        self._dots_var = tk.StringVar(value="")
        tk.Label(right, textvariable=self._dots_var,
                 font=("Helvetica", 10), fg="#888", bg=bg).pack(pady=(2, 0))

        self._prog_var = tk.StringVar(value="— / — letters")
        tk.Label(right, textvariable=self._prog_var,
                 font=("Helvetica", 10), fg="#bbb", bg=bg).pack(pady=(4, 0))

        # Buttons
        btn_row = tk.Frame(self, bg=bg)
        btn_row.pack(pady=10)

        btn_style = dict(font=("Helvetica", 13, "bold"), relief=tk.FLAT,
                         padx=18, pady=8, cursor="hand2")

        self._capture_btn = tk.Button(btn_row, text="CAPTURE TEXT",
                                       bg="#4a90d9", fg="#fff",
                                       activebackground="#357abd",
                                       command=self._capture, **btn_style)
        self._capture_btn.pack(side=tk.LEFT, padx=8)

        tk.Button(btn_row, text="← PREV",
                  bg="#ddd", fg="#333", activebackground="#bbb",
                  command=lambda: self._advance(-1), **btn_style).pack(side=tk.LEFT, padx=4)

        tk.Button(btn_row, text="NEXT →",
                  bg="#ddd", fg="#333", activebackground="#bbb",
                  command=lambda: self._advance(+1), **btn_style).pack(side=tk.LEFT, padx=4)

        self._auto_btn = tk.Button(btn_row, text="▶ AUTO",
                                    bg="#27ae60", fg="#fff",
                                    activebackground="#1e8449",
                                    command=self._toggle_auto, **btn_style)
        self._auto_btn.pack(side=tk.LEFT, padx=8)

        # Delay slider (0.3s – 5.0s)
        delay_row = tk.Frame(self, bg=bg)
        delay_row.pack(pady=(0, 4))
        tk.Label(delay_row, text="Auto delay:", font=("Helvetica", 11), fg="#555", bg=bg).pack(side=tk.LEFT)
        self._delay_var = tk.DoubleVar(value=0.5)
        self._delay_slider = tk.Scale(delay_row, from_=0.3, to=5.0, resolution=0.1,
                                       orient=tk.HORIZONTAL, length=200,
                                       variable=self._delay_var,
                                       bg=bg, fg="#333", highlightthickness=0,
                                       troughcolor="#ddd")
        self._delay_slider.pack(side=tk.LEFT, padx=6)
        self._delay_label = tk.Label(delay_row, textvariable=self._delay_var,
                                      font=("Helvetica", 11), fg="#555", bg=bg, width=3)
        self._delay_label.pack(side=tk.LEFT)
        tk.Label(delay_row, text="sec", font=("Helvetica", 11), fg="#555", bg=bg).pack(side=tk.LEFT)

        # Status bar
        self._status_var = tk.StringVar(value="Point camera at text, then press CAPTURE TEXT.")
        self._status_label = tk.Label(self, textvariable=self._status_var,
                                       font=("Helvetica", 11), fg="#555",
                                       bg=bg, wraplength=720)
        self._status_label.pack(pady=(0, 14))

    # ---- Braille cell ------------------------------------------

    def _dot_xy(self, dot: int) -> tuple[int, int]:
        row, col = _DOT_POS[dot]
        x = _PAD + _R + col * (_R * 2 + _PAD)
        y = _PAD + _R + row * (_R * 2 + _PAD)
        return x, y

    def _draw_cell(self) -> None:
        self._canvas.delete("all")
        self._ovals.clear()
        for dot in range(1, 7):
            x, y = self._dot_xy(dot)
            oid = self._canvas.create_oval(
                x - _R, y - _R, x + _R, y + _R,
                fill="#fff", outline="#333", width=2,
            )
            self._ovals[dot] = oid

    def _render_dots(self, active: list[int]) -> None:
        for dot, oid in self._ovals.items():
            self._canvas.itemconfig(oid, fill="#111" if dot in active else "#fff")

    # ---- Live camera feed --------------------------------------

    def _update_camera(self) -> None:
        ok, frame = self._cap.read()
        if ok:
            self._last_frame = frame
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(rgb).resize((CAM_W, CAM_H), Image.BILINEAR)
            self._tk_img = ImageTk.PhotoImage(img)
            self._cam_label.configure(image=self._tk_img)
        self.after(30, self._update_camera)

    # ---- Capture + background OCR pipeline ---------------------

    def _capture(self) -> None:
        if self._processing:
            return
        if self._last_frame is None:
            self._set_status("No camera frame yet — wait a moment.", error=True)
            return
        self._stop_auto()
        send_to_arduino("000000", self.ser)
        self._processing = True
        self._capture_btn.configure(state=tk.DISABLED, text="Processing…")
        self._auto_btn.configure(state=tk.DISABLED)
        self._set_status("Sending to Gemma OCR… (30-60s, fully offline)")
        threading.Thread(target=self._process, args=(self._last_frame.copy(),), daemon=True).start()
        # Safety: force-unlock after 45s if thread never returns
        self.after(45000, self._unlock_if_stuck)

    def _process(self, frame) -> None:
        try:
            # Primary: single local Gemma call (free, offline, no API keys)
            cleaned = ocr_with_gemma(frame)
            if not cleaned:
                # Fallback: Gemini OCR → Claude cleanup
                raw = ocr_frame(frame)
                cleaned = clean_text_with_claude(raw)
            letters = [ch for ch in cleaned.lower() if ch in BRAILLE]
            self.after(0, self._on_process_done, letters, cleaned)
        except Exception as e:
            print(f"[Pipeline] ERROR in processing thread: {e}")
            self.after(0, self._on_process_error, str(e))

    def _unlock_if_stuck(self) -> None:
        if self._processing:
            print("[Pipeline] Processing timed out — force-unlocking.")
            self._processing = False
            self._capture_btn.configure(state=tk.NORMAL, text="CAPTURE TEXT")
            self._auto_btn.configure(state=tk.NORMAL)
            self._set_status("OCR timed out — try again.", error=True)

    def _on_process_error(self, msg: str) -> None:
        self._processing = False
        self._capture_btn.configure(state=tk.NORMAL, text="CAPTURE TEXT")
        self._auto_btn.configure(state=tk.NORMAL)
        self._set_status(f"Error: {msg} — try again.", error=True)

    def _on_process_done(self, letters: list[str], cleaned: str) -> None:
        self._processing = False
        self._capture_btn.configure(state=tk.NORMAL, text="CAPTURE TEXT")
        self._auto_btn.configure(state=tk.NORMAL)
        if not letters:
            ocr_preview = repr(cleaned) if cleaned else "(empty)"
            self._set_status(
                f"No displayable text found. OCR saw: {ocr_preview} — try again.",
                error=True,
            )
            return
        self.letters = letters
        self.idx = -1
        self._prog_var.set(f"0 / {len(letters)} letters")
        self._set_status(f"Got {len(letters)} letter(s): {' '.join(letters)}   — press NEXT or SPACE")
        self._render_dots([])
        self._letter_var.set("—")
        self._see_var.set("")
        self._dots_var.set("")
        print(f"\n[Pipeline] Letter queue ({len(letters)}): {' '.join(letters)}\n")

    # ---- Navigation --------------------------------------------

    def _advance(self, delta: int) -> None:
        if not self.letters:
            self._set_status("Capture some text first!", error=True)
            return
        new_idx = self.idx + delta
        if new_idx < 0 or new_idx >= len(self.letters):
            return
        self.idx = new_idx
        ch = self.letters[self.idx]
        dots = BRAILLE.get(ch, [])
        pattern = dots_to_pattern(dots)
        dot_str = " ".join(str(d) for d in sorted(dots)) or "none"
        display = ch.upper() if ch != " " else "(sp)"

        self._render_dots(dots)
        self._letter_var.set(display)
        self._see_var.set(f"I see the letter: {display}")
        self._dots_var.set(f"dots: {dot_str}   pattern: {pattern}")
        self._prog_var.set(f"{self.idx + 1} / {len(self.letters)} letters")

        print(f"[Display] '{ch}'  dots:{dot_str}  pattern:{pattern}")
        send_to_arduino(pattern, self.ser)
        # Pulse: send reset immediately so servo goes up then straight back down
        self.after(300, lambda: send_to_arduino("000000", self.ser))
        speak_async("space" if ch == " " else ch)

    # ---- Auto mode ---------------------------------------------

    def _toggle_auto(self) -> None:
        if self._auto_mode:
            self._stop_auto()
        else:
            if not self.letters:
                self._set_status("Capture some text first!", error=True)
                return
            self._auto_mode = True
            self._auto_btn.configure(text="⏹ STOP", bg="#e74c3c", activebackground="#c0392b")
            self._capture_btn.configure(state=tk.DISABLED)
            self._run_auto()

    def _run_auto(self) -> None:
        if not self._auto_mode:
            return
        if self.idx + 1 >= len(self.letters):
            self._stop_auto()
            self._set_status("Auto complete — all letters displayed.")
            return
        self._advance(+1)
        delay_ms = int(self._delay_var.get() * 1000)
        self._auto_job = self.after(delay_ms, self._run_auto)

    def _stop_auto(self) -> None:
        self._auto_mode = False
        self._auto_btn.configure(text="▶ AUTO", bg="#27ae60", activebackground="#1e8449")
        self._capture_btn.configure(state=tk.NORMAL)
        if self._auto_job:
            self.after_cancel(self._auto_job)
            self._auto_job = None

    # ---- Helpers -----------------------------------------------

    def _set_status(self, msg: str, error: bool = False) -> None:
        self._status_var.set(msg)
        self._status_label.configure(fg="#c0392b" if error else "#555")

    def _quit(self) -> None:
        if self.ser:
            try:
                send_to_arduino("000000", self.ser)
                time.sleep(0.1)
            except Exception:
                pass
        if self._cap.isOpened():
            self._cap.release()
        self.destroy()


# ============================================================
#  MAIN
# ============================================================

def _check(label: str, value: str) -> str:
    return f"  {'✓' if value else '✗'} {label}: {'set' if value else 'MISSING'}"


def print_startup_banner() -> None:
    print("=" * 54)
    print("  HackDavis 2026 — AI Braille Display Pipeline")
    print("=" * 54)
    print("API key status:")
    print(_check("ANTHROPIC_API_KEY  (Claude cleanup) ", ANTHROPIC_API_KEY))
    print(_check("GEMINI_API_KEY     (Vision OCR)     ", GEMINI_API_KEY))
    print(f"\nModels:  Gemini={GEMINI_VISION_MODEL}  Claude={CLAUDE_MODEL}")
    print(f"Serial:  {SERIAL_PORT} @ {SERIAL_BAUD} baud")
    print(f"Webcam:  index {WEBCAM_INDEX}")
    print("=" * 54)
    print()


def main():
    print_startup_banner()
    ser = init_serial()
    app = BraillePipelineApp(ser)
    app.mainloop()
    if ser:
        ser.close()
    print("\n[Pipeline] Complete.")


if __name__ == "__main__":
    main()
