#!/usr/bin/env python3
"""
gemma_pipeline.py — Gemma 4 Braille Display Pipeline (Hackathon Build)
=======================================================================
Fully offline, multimodal pipeline:

  Microphone → Whisper (local STT) → ┐
                                       ├─→ Gemma 4 via Ollama → Braille encoder → Arduino
  Webcam     → OpenCV frame        → ┘

No internet. No cloud APIs. No subscriptions.

Setup:
  brew install portaudio          # macOS only (needed by sounddevice)
  pip install ollama sounddevice scipy openai-whisper opencv-python pyserial pillow python-dotenv
  ollama pull gemma4:e4b          # ~3 GB download, runs offline after

Run:
  python gemma_pipeline.py
"""

import os
import sys
import time
import threading
import tempfile
import base64
import tkinter as tk
from tkinter import font as tkfont

import cv2
import numpy as np
from PIL import Image, ImageTk

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

try:
    import sounddevice as sd
    _AUDIO_LIB = True
except ImportError:
    _AUDIO_LIB = False
    print("[Audio] sounddevice not installed — audio input disabled")

try:
    import whisper as _whisper_mod
    _WHISPER_LIB = True
except ImportError:
    _WHISPER_LIB = False
    print("[Whisper] openai-whisper not installed — audio transcription disabled")

try:
    import ollama as _ollama
    _OLLAMA_LIB = True
except ImportError:
    _OLLAMA_LIB = False
    print("[Ollama] ollama package not installed — AI disabled")

try:
    import serial
    _SERIAL_LIB = True
except ImportError:
    _SERIAL_LIB = False

# ── Configuration ─────────────────────────────────────────────────────────────
OLLAMA_MODEL      = "gemma4:e4b"      # swap to gemma4:12b for better quality
WHISPER_MODEL     = "base"            # tiny / base / small  — base is fastest offline
SERIAL_PORT       = "/dev/cu.usbmodem1051DB2BD6802"
SERIAL_BAUD       = 9600
WEBCAM_INDEX      = 0                 # 0 = built-in mac cam, 1 = external USB cam
AUDIO_SAMPLE_RATE = 16000
AUDIO_DURATION    = 6                 # seconds to record per capture
CAM_W, CAM_H      = 480, 360

# Gemma 4 compression prompt — output is fed directly into braille encoder
GEMMA_SYSTEM = (
    "You are an intelligent interpreter for a deaf-blind braille reader. "
    "You receive audio transcripts and/or camera images from their environment. "
    "Your job: distill the most important information into AT MOST 5 words. "
    "Rules: output ONLY the phrase — no explanation, no punctuation except spaces, "
    "lowercase only. If nothing meaningful, output: nothing detected"
)

GEMMA_USER_TEMPLATE = """{audio_section}{vision_section}Output the single most important piece of information as 5 words or fewer."""

# ── Braille lookup table (Grade 1) ────────────────────────────────────────────
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

_DOT_POS = {1: (0, 0), 4: (0, 1), 2: (1, 0), 5: (1, 1), 3: (2, 0), 6: (2, 1)}
_SERVO_ORDER = [1, 2, 3, 4, 5, 6]
_R = 28
_PAD = 14
_CW = _PAD + (_R * 2 + _PAD) * 2
_CH = _PAD + (_R * 2 + _PAD) * 3


def dots_to_pattern(dots: list[int]) -> str:
    return ''.join('1' if d in dots else '0' for d in _SERVO_ORDER)


def text_to_letters(text: str) -> list[str]:
    return [ch for ch in text.lower() if ch in BRAILLE]


# ── Serial / Arduino ──────────────────────────────────────────────────────────
def init_serial():
    if not _SERIAL_LIB:
        return None
    try:
        ser = serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=1)
        time.sleep(2)
        print(f"[Serial] Connected: {SERIAL_PORT} @ {SERIAL_BAUD}")
        return ser
    except Exception as e:
        print(f"[Serial] Not connected ({e})")
        return None


def send_pattern(pattern: str, ser) -> None:
    if ser is None:
        return
    def _go():
        try:
            ser.write((pattern + "\n").encode())
        except Exception as ex:
            print(f"[Serial] Write error: {ex}")
    threading.Thread(target=_go, daemon=True).start()


# ── Whisper (local offline STT) ───────────────────────────────────────────────
_whisper_instance = None
_whisper_lock = threading.Lock()


def _load_whisper():
    global _whisper_instance
    if not _WHISPER_LIB:
        return None
    with _whisper_lock:
        if _whisper_instance is None:
            print(f"[Whisper] Loading '{WHISPER_MODEL}' model (first run may take ~30s)…")
            _whisper_instance = _whisper_mod.load_model(WHISPER_MODEL)
            print("[Whisper] Model ready.")
    return _whisper_instance


def record_audio() -> np.ndarray | None:
    if not _AUDIO_LIB:
        return None
    print(f"[Audio] Recording {AUDIO_DURATION}s…")
    try:
        audio = sd.rec(
            int(AUDIO_DURATION * AUDIO_SAMPLE_RATE),
            samplerate=AUDIO_SAMPLE_RATE,
            channels=1,
            dtype='float32',
        )
        sd.wait()
        print("[Audio] Done.")
        return audio.flatten()
    except Exception as e:
        print(f"[Audio] Record error: {e}")
        return None


def transcribe(audio: np.ndarray) -> str:
    model = _load_whisper()
    if model is None or audio is None:
        return ""
    print("[Whisper] Transcribing…")
    result = model.transcribe(audio, fp16=False, language="en")
    text = result.get("text", "").strip()
    print(f"[Whisper] → {text!r}")
    return text


# ── Gemma 4 via Ollama ────────────────────────────────────────────────────────
def run_gemma(audio_text: str = "", frame=None) -> str:
    """
    Send audio transcript + optional webcam frame to Gemma 4 via Ollama.
    Returns a compressed ≤5-word phrase ready for braille output.
    """
    if not _OLLAMA_LIB:
        return "ollama not installed"

    audio_section = ""
    if audio_text.strip():
        audio_section = f"AUDIO — someone nearby said:\n\"{audio_text}\"\n\n"

    vision_section = ""
    if frame is not None:
        vision_section = "IMAGE — camera currently sees: [attached]\n\n"

    if not audio_section and not vision_section:
        return "no input provided"

    user_content = GEMMA_USER_TEMPLATE.format(
        audio_section=audio_section,
        vision_section=vision_section,
    )

    msg: dict = {
        "role": "user",
        "content": user_content,
    }

    if frame is not None:
        _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        msg["images"] = [base64.b64encode(buf.tobytes()).decode()]

    print(f"[Gemma] Calling {OLLAMA_MODEL}…")
    t0 = time.time()
    try:
        resp = _ollama.chat(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": GEMMA_SYSTEM},
                msg,
            ],
            options={"temperature": 0.1, "num_predict": 30},
        )
        raw = resp["message"]["content"].strip().lower()
        # Remove trailing punctuation Gemma sometimes adds
        output = raw.rstrip(".,!?;:\"'").strip()
        print(f"[Gemma] {time.time()-t0:.1f}s → {output!r}")
        return output
    except Exception as e:
        print(f"[Gemma] ERROR: {e}")
        return f"error contacting ollama"


# ── Main Tkinter App ──────────────────────────────────────────────────────────

class GemmaBrailleApp(tk.Tk):
    def __init__(self, ser):
        super().__init__()
        self.ser = ser
        self.letters: list[str] = []
        self.idx = -1
        self._processing = False
        self._last_frame = None
        self._auto_mode = False
        self._auto_job = None
        self._recording = False

        self.title("Gemma 4 Braille — Offline Multimodal Pipeline")
        self.resizable(False, False)
        self.configure(bg="#0d1117")

        self._build_ui()

        self._cap = cv2.VideoCapture(WEBCAM_INDEX)
        if not self._cap.isOpened():
            self._set_status("ERROR: cannot open webcam.", error=True)
        else:
            self._update_camera()

        # Pre-load Whisper in background so first capture isn't slow
        if _WHISPER_LIB:
            threading.Thread(target=_load_whisper, daemon=True).start()

        self.bind("<space>",  lambda _: self._advance(+1))
        self.bind("<Left>",   lambda _: self._advance(-1))
        self.bind("<Right>",  lambda _: self._advance(+1))
        self.bind("<Escape>", lambda _: self._quit())
        self.protocol("WM_DELETE_WINDOW", self._quit)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        BG    = "#0d1117"
        PANEL = "#161b22"
        ACC   = "#58a6ff"   # blue accent
        GRN   = "#3fb950"
        RED   = "#f85149"
        TXT   = "#e6edf3"
        MUTED = "#8b949e"

        self.configure(bg=BG)

        # ── Title row
        hdr = tk.Frame(self, bg=BG)
        hdr.pack(fill=tk.X, padx=20, pady=(14, 4))
        tk.Label(hdr, text="Gemma 4 Braille Display",
                 font=("Helvetica", 17, "bold"), fg=TXT, bg=BG).pack(side=tk.LEFT)

        model_lbl = f"  ·  {OLLAMA_MODEL}  ·  offline"
        tk.Label(hdr, text=model_lbl, font=("Helvetica", 11), fg=MUTED, bg=BG).pack(side=tk.LEFT, pady=(4, 0))

        arduino_txt = f"Arduino ✓ ({SERIAL_PORT})" if self.ser else "Arduino ✗ (display only)"
        arduino_col = GRN if self.ser else MUTED
        tk.Label(self, text=arduino_txt, font=("Helvetica", 10), fg=arduino_col, bg=BG).pack()

        # ── Main content row
        main = tk.Frame(self, bg=BG)
        main.pack(padx=20, pady=10)

        # Camera feed panel
        cam_panel = tk.Frame(main, bg=PANEL, bd=1, relief=tk.SOLID)
        cam_panel.pack(side=tk.LEFT, padx=(0, 20))
        tk.Label(cam_panel, text="LIVE CAMERA", font=("Helvetica", 9, "bold"),
                 fg=MUTED, bg=PANEL).pack(pady=(6, 0))
        cam_inner = tk.Frame(cam_panel, bg="#000", width=CAM_W, height=CAM_H)
        cam_inner.pack_propagate(False)
        cam_inner.pack(padx=8, pady=(4, 8))
        self._cam_label = tk.Label(cam_inner, bg="#000")
        self._cam_label.pack(fill=tk.BOTH, expand=True)

        # Right panel: braille cell + info
        right = tk.Frame(main, bg=BG)
        right.pack(side=tk.LEFT, anchor=tk.N)

        # Braille cell
        cell_panel = tk.Frame(right, bg=PANEL, bd=1, relief=tk.SOLID)
        cell_panel.pack(fill=tk.X)
        tk.Label(cell_panel, text="BRAILLE CELL", font=("Helvetica", 9, "bold"),
                 fg=MUTED, bg=PANEL).pack(pady=(6, 0))
        self._canvas = tk.Canvas(cell_panel, width=_CW, height=_CH,
                                  bg=PANEL, highlightthickness=0)
        self._canvas.pack(pady=(4, 10), padx=20)
        self._ovals: dict[int, int] = {}
        self._draw_cell()

        # Letter display
        self._letter_var = tk.StringVar(value="—")
        tk.Label(right, textvariable=self._letter_var,
                 font=("Helvetica", 64, "bold"), fg=ACC, bg=BG, width=3).pack(pady=(12, 0))

        self._see_var = tk.StringVar(value="")
        tk.Label(right, textvariable=self._see_var,
                 font=("Helvetica", 12), fg=TXT, bg=BG).pack()

        self._dots_var = tk.StringVar(value="")
        tk.Label(right, textvariable=self._dots_var,
                 font=("Helvetica", 10), fg=MUTED, bg=BG).pack(pady=(2, 0))

        self._prog_var = tk.StringVar(value="—")
        tk.Label(right, textvariable=self._prog_var,
                 font=("Helvetica", 10), fg=MUTED, bg=BG).pack(pady=(4, 0))

        # ── Gemma output display
        out_panel = tk.Frame(self, bg=PANEL, bd=1, relief=tk.SOLID)
        out_panel.pack(fill=tk.X, padx=20, pady=(4, 6))
        tk.Label(out_panel, text="GEMMA 4 OUTPUT", font=("Helvetica", 9, "bold"),
                 fg=MUTED, bg=PANEL).pack(side=tk.LEFT, padx=10, pady=6)
        self._output_var = tk.StringVar(value="(press a capture button to run inference)")
        tk.Label(out_panel, textvariable=self._output_var,
                 font=("Helvetica", 12, "bold"), fg=ACC, bg=PANEL).pack(side=tk.LEFT, padx=4)

        # ── Mode buttons
        mode_row = tk.Frame(self, bg=BG)
        mode_row.pack(pady=6)

        btn_kw = dict(font=("Helvetica", 12, "bold"), relief=tk.FLAT,
                      padx=14, pady=8, cursor="hand2", bd=0)

        self._audio_btn = tk.Button(
            mode_row, text="🎤 LISTEN",
            bg="#21262d", fg="#f0883e", activebackground="#30363d",
            command=self._capture_audio, **btn_kw)
        self._audio_btn.pack(side=tk.LEFT, padx=6)

        self._vision_btn = tk.Button(
            mode_row, text="📷 READ TEXT",
            bg="#21262d", fg=ACC, activebackground="#30363d",
            command=self._capture_vision, **btn_kw)
        self._vision_btn.pack(side=tk.LEFT, padx=6)

        self._both_btn = tk.Button(
            mode_row, text="⚡ LISTEN + READ",
            bg="#21262d", fg=GRN, activebackground="#30363d",
            command=self._capture_both, **btn_kw)
        self._both_btn.pack(side=tk.LEFT, padx=6)

        # ── Nav / auto buttons
        nav_row = tk.Frame(self, bg=BG)
        nav_row.pack(pady=4)

        nav_kw = dict(font=("Helvetica", 11, "bold"), relief=tk.FLAT,
                      padx=12, pady=6, cursor="hand2", bd=0)

        tk.Button(nav_row, text="← PREV", bg="#21262d", fg=TXT,
                  activebackground="#30363d",
                  command=lambda: self._advance(-1), **nav_kw).pack(side=tk.LEFT, padx=4)

        tk.Button(nav_row, text="NEXT →", bg="#21262d", fg=TXT,
                  activebackground="#30363d",
                  command=lambda: self._advance(+1), **nav_kw).pack(side=tk.LEFT, padx=4)

        self._auto_btn = tk.Button(nav_row, text="▶ AUTO",
                                    bg=GRN, fg="#0d1117", activebackground="#2ea043",
                                    command=self._toggle_auto, **nav_kw)
        self._auto_btn.pack(side=tk.LEFT, padx=8)

        # Delay slider
        delay_row = tk.Frame(self, bg=BG)
        delay_row.pack(pady=(2, 4))
        tk.Label(delay_row, text="Speed:", font=("Helvetica", 10), fg=MUTED, bg=BG).pack(side=tk.LEFT)
        self._delay_var = tk.DoubleVar(value=1.2)
        tk.Scale(delay_row, from_=0.4, to=5.0, resolution=0.1,
                 orient=tk.HORIZONTAL, length=180,
                 variable=self._delay_var,
                 bg=BG, fg=TXT, highlightthickness=0,
                 troughcolor="#21262d", activebackground=ACC).pack(side=tk.LEFT, padx=6)
        tk.Label(delay_row, textvariable=self._delay_var,
                 font=("Helvetica", 10), fg=MUTED, bg=BG, width=3).pack(side=tk.LEFT)
        tk.Label(delay_row, text="s/letter", font=("Helvetica", 10), fg=MUTED, bg=BG).pack(side=tk.LEFT)

        # Status bar
        self._status_var = tk.StringVar(value="Ready. Choose a capture mode above.")
        self._status_lbl = tk.Label(self, textvariable=self._status_var,
                                     font=("Helvetica", 10), fg=MUTED, bg=BG,
                                     wraplength=760)
        self._status_lbl.pack(pady=(0, 14))

    # ── Braille cell canvas ───────────────────────────────────────────────────

    def _dot_xy(self, dot: int):
        row, col = _DOT_POS[dot]
        x = _PAD + _R + col * (_R * 2 + _PAD)
        y = _PAD + _R + row * (_R * 2 + _PAD)
        return x, y

    def _draw_cell(self):
        self._canvas.delete("all")
        self._ovals.clear()
        for dot in range(1, 7):
            x, y = self._dot_xy(dot)
            oid = self._canvas.create_oval(
                x - _R, y - _R, x + _R, y + _R,
                fill="#21262d", outline="#30363d", width=2,
            )
            self._ovals[dot] = oid

    def _render_dots(self, active: list[int]):
        for dot, oid in self._ovals.items():
            self._canvas.itemconfig(oid, fill="#58a6ff" if dot in active else "#21262d")

    # ── Live camera feed ──────────────────────────────────────────────────────

    def _update_camera(self):
        ok, frame = self._cap.read()
        if ok:
            self._last_frame = frame
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(rgb).resize((CAM_W, CAM_H), Image.BILINEAR)
            self._tk_img = ImageTk.PhotoImage(img)
            self._cam_label.configure(image=self._tk_img)
        self.after(33, self._update_camera)

    # ── Capture modes ─────────────────────────────────────────────────────────

    def _lock_buttons(self, status: str):
        self._processing = True
        for btn in (self._audio_btn, self._vision_btn, self._both_btn, self._auto_btn):
            btn.configure(state=tk.DISABLED)
        self._set_status(status)

    def _unlock_buttons(self):
        self._processing = False
        for btn in (self._audio_btn, self._vision_btn, self._both_btn, self._auto_btn):
            btn.configure(state=tk.NORMAL)

    def _capture_audio(self):
        if self._processing:
            return
        if not _AUDIO_LIB or not _WHISPER_LIB:
            self._set_status("Audio libraries not installed (sounddevice + openai-whisper required).", error=True)
            return
        self._stop_auto()
        self._lock_buttons(f"Recording {AUDIO_DURATION}s of audio… speak now!")
        threading.Thread(target=self._run_audio_pipeline, daemon=True).start()

    def _capture_vision(self):
        if self._processing:
            return
        if self._last_frame is None:
            self._set_status("No camera frame yet — wait a moment.", error=True)
            return
        self._stop_auto()
        frame = self._last_frame.copy()
        self._lock_buttons("Sending camera frame to Gemma 4…")
        threading.Thread(target=self._run_vision_pipeline, args=(frame,), daemon=True).start()

    def _capture_both(self):
        if self._processing:
            return
        if not _AUDIO_LIB or not _WHISPER_LIB:
            self._set_status("Audio libraries not installed — use READ TEXT instead.", error=True)
            return
        if self._last_frame is None:
            self._set_status("No camera frame yet — wait a moment.", error=True)
            return
        self._stop_auto()
        frame = self._last_frame.copy()
        self._lock_buttons(f"Recording {AUDIO_DURATION}s of audio + capturing frame… speak now!")
        threading.Thread(target=self._run_both_pipeline, args=(frame,), daemon=True).start()

    # ── Pipeline threads ──────────────────────────────────────────────────────

    def _run_audio_pipeline(self):
        try:
            audio = record_audio()
            self.after(0, self._set_status, "Transcribing with Whisper…")
            transcript = transcribe(audio)
            if not transcript:
                self.after(0, self._on_error, "No speech detected — try again.")
                return
            self.after(0, self._set_status, f"Whisper: \"{transcript}\" → Sending to Gemma 4…")
            result = run_gemma(audio_text=transcript, frame=None)
            self.after(0, self._on_result, result, f"Audio: \"{transcript}\"")
        except Exception as e:
            self.after(0, self._on_error, str(e))

    def _run_vision_pipeline(self, frame):
        try:
            self.after(0, self._set_status, "Sending image to Gemma 4…")
            result = run_gemma(audio_text="", frame=frame)
            self.after(0, self._on_result, result, "Vision input")
        except Exception as e:
            self.after(0, self._on_error, str(e))

    def _run_both_pipeline(self, frame):
        try:
            audio = record_audio()
            self.after(0, self._set_status, "Transcribing with Whisper…")
            transcript = transcribe(audio)
            label = f"Audio: \"{transcript}\" + Vision" if transcript else "Vision only (no speech detected)"
            self.after(0, self._set_status, f"{label} → Sending to Gemma 4…")
            result = run_gemma(audio_text=transcript, frame=frame)
            self.after(0, self._on_result, result, label)
        except Exception as e:
            self.after(0, self._on_error, str(e))

    # ── Result / error handlers ───────────────────────────────────────────────

    def _on_result(self, gemma_output: str, source_label: str):
        self._unlock_buttons()
        self._output_var.set(gemma_output)

        letters = text_to_letters(gemma_output)
        if not letters:
            self._set_status(
                f"Gemma said: \"{gemma_output}\" — no displayable braille characters found.",
                error=True,
            )
            return

        self.letters = letters
        self.idx = -1
        word_count = len(gemma_output.split())
        self._prog_var.set(f"0 / {len(letters)} letters")
        self._set_status(
            f"{source_label}  →  Gemma 4: \"{gemma_output}\"  ({word_count} word{'s' if word_count != 1 else ''}, {len(letters)} braille chars) — press NEXT or AUTO"
        )
        self._render_dots([])
        self._letter_var.set("—")
        self._see_var.set("")
        self._dots_var.set("")
        send_pattern("000000", self.ser)
        print(f"\n[Queue] {len(letters)} letters: {' '.join(letters)}\n")

    def _on_error(self, msg: str):
        self._unlock_buttons()
        self._set_status(f"Error: {msg}", error=True)

    # ── Navigation ────────────────────────────────────────────────────────────

    def _advance(self, delta: int):
        if not self.letters:
            self._set_status("Run a capture first.", error=True)
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
        self._see_var.set(f"Letter: {display}")
        self._dots_var.set(f"dots {dot_str}  ·  pattern {pattern}")
        self._prog_var.set(f"{self.idx + 1} / {len(self.letters)}")

        print(f"[Display] '{ch}'  dots:{dot_str}  pattern:{pattern}")
        send_pattern(pattern, self.ser)
        self.after(350, lambda: send_pattern("000000", self.ser))

    # ── Auto mode ─────────────────────────────────────────────────────────────

    def _toggle_auto(self):
        if self._auto_mode:
            self._stop_auto()
        else:
            if not self.letters:
                self._set_status("Run a capture first.", error=True)
                return
            self._auto_mode = True
            self._auto_btn.configure(text="⏹ STOP", bg="#f85149", activebackground="#da3633")
            for btn in (self._audio_btn, self._vision_btn, self._both_btn):
                btn.configure(state=tk.DISABLED)
            self._run_auto()

    def _run_auto(self):
        if not self._auto_mode:
            return
        if self.idx + 1 >= len(self.letters):
            self._stop_auto()
            self._set_status("Auto complete — all letters displayed.")
            return
        self._advance(+1)
        self._auto_job = self.after(int(self._delay_var.get() * 1000), self._run_auto)

    def _stop_auto(self):
        self._auto_mode = False
        self._auto_btn.configure(text="▶ AUTO", bg="#3fb950", activebackground="#2ea043")
        for btn in (self._audio_btn, self._vision_btn, self._both_btn):
            btn.configure(state=tk.NORMAL)
        if self._auto_job:
            self.after_cancel(self._auto_job)
            self._auto_job = None

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _set_status(self, msg: str, error: bool = False):
        self._status_var.set(msg)
        self._status_lbl.configure(fg="#f85149" if error else "#8b949e")

    def _quit(self):
        if self.ser:
            try:
                send_pattern("000000", self.ser)
                time.sleep(0.1)
                self.ser.close()
            except Exception:
                pass
        if self._cap.isOpened():
            self._cap.release()
        self.destroy()


# ── Entry point ───────────────────────────────────────────────────────────────

def _check_deps():
    issues = []
    if not _OLLAMA_LIB:
        issues.append("  ✗ ollama  →  pip install ollama")
    if not _AUDIO_LIB:
        issues.append("  ✗ sounddevice  →  brew install portaudio && pip install sounddevice scipy")
    if not _WHISPER_LIB:
        issues.append("  ✗ openai-whisper  →  pip install openai-whisper")
    if not _SERIAL_LIB:
        issues.append("  ✗ pyserial  →  pip install pyserial  (optional — hardware only)")
    return issues


def print_banner():
    print("=" * 58)
    print("  Gemma 4 Braille Display — Offline Multimodal Pipeline")
    print("=" * 58)
    print(f"  Model    : {OLLAMA_MODEL} via Ollama")
    print(f"  STT      : Whisper '{WHISPER_MODEL}' (offline)")
    print(f"  Webcam   : index {WEBCAM_INDEX}")
    print(f"  Arduino  : {SERIAL_PORT} @ {SERIAL_BAUD}")
    issues = _check_deps()
    if issues:
        print("\n  Missing dependencies:")
        for iss in issues:
            print(f"  {iss}")
    else:
        print("\n  All dependencies OK.")
    print("=" * 58)
    print()


def main():
    print_banner()

    # Verify Ollama is reachable before opening the window
    if _OLLAMA_LIB:
        try:
            models = _ollama.list()
            names = [m["model"] for m in models.get("models", [])]
            if OLLAMA_MODEL not in names and not any(OLLAMA_MODEL in n for n in names):
                print(f"[Ollama] WARNING: '{OLLAMA_MODEL}' not found locally.")
                print(f"         Run:  ollama pull {OLLAMA_MODEL}")
                print(f"         Available: {names}")
        except Exception as e:
            print(f"[Ollama] Cannot reach Ollama daemon: {e}")
            print("         Make sure Ollama is running:  ollama serve")

    ser = init_serial()
    app = GemmaBrailleApp(ser)
    app.mainloop()
    print("\n[Pipeline] Complete.")


if __name__ == "__main__":
    main()
