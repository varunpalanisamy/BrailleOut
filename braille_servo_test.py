#!/usr/bin/env python3
"""
braille_servo_test.py  —  HackDavis 2026
=========================================
Press a–z on the keyboard:
  • Braille cell lights up on screen
  • 6-char binary pattern sent over serial to Arduino → 6 servos move

Run:
    python3 braille_servo_test.py

No API keys needed. Just the Arduino plugged in via USB.
"""

import time
import threading
import tkinter as tk

try:
    import serial
    _SERIAL_LIB = True
except ImportError:
    _SERIAL_LIB = False

# ── Config ────────────────────────────────────────────────────
SERIAL_PORT = "/dev/cu.usbmodem1051DB2BD6802"   # run: ls /dev/cu.*  to find yours
SERIAL_BAUD = 9600
# ─────────────────────────────────────────────────────────────

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

DOT_POS = {
    1: (0, 0), 4: (0, 1),
    2: (1, 0), 5: (1, 1),
    3: (2, 0), 6: (2, 1),
}

R   = 36
PAD = 18
CW  = PAD + (R * 2 + PAD) * 2
CH  = PAD + (R * 2 + PAD) * 3


def dots_to_pattern(dots: list[int]) -> str:
    return ''.join('1' if d in dots else '0' for d in range(1, 7))


def init_serial():
    if not _SERIAL_LIB:
        print("[Serial] pyserial not installed — run: pip install pyserial")
        return None
    try:
        ser = serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=1)
        time.sleep(2)   # wait for Arduino bootloader
        print(f"[Serial] Connected: {SERIAL_PORT} @ {SERIAL_BAUD} baud")
        return ser
    except Exception as e:
        print(f"[Serial] Could not connect ({e})")
        print(f"[Serial] Check SERIAL_PORT at top of file — run: ls /dev/cu.*")
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


class BrailleTestApp(tk.Tk):
    def __init__(self, ser):
        super().__init__()
        self.ser = ser
        self._last_key_time = 0.0   # debounce: ignore key-repeat during Arduino reset
        self.title("Braille Servo Test — press a–z")
        self.resizable(False, False)
        self.configure(bg="#f5f5f0")

        # Title
        tk.Label(self, text="Braille Servo Tester",
                 font=("Helvetica", 17, "bold"), bg="#f5f5f0").pack(pady=(14, 2))
        tk.Label(self, text="Press any letter key (a–z)  •  SPACE = clear  •  ESC = quit",
                 font=("Helvetica", 11), fg="#888", bg="#f5f5f0").pack(pady=(0, 10))

        # Arduino status badge
        status_txt = f"Arduino: connected ({SERIAL_PORT})" if ser else "Arduino: NOT connected (running in display-only mode)"
        status_col = "#27ae60" if ser else "#e67e22"
        tk.Label(self, text=status_txt, font=("Helvetica", 10, "bold"),
                 fg=status_col, bg="#f5f5f0").pack(pady=(0, 12))

        # Braille cell canvas
        self._canvas = tk.Canvas(self, width=CW, height=CH,
                                  bg="#fff", highlightthickness=2,
                                  highlightbackground="#ccc")
        self._canvas.pack(padx=50)
        self._ovals: dict[int, int] = {}
        self._draw_cell()

        # Large letter display
        self._letter_var = tk.StringVar(value="—")
        tk.Label(self, textvariable=self._letter_var,
                 font=("Helvetica", 72, "bold"), bg="#f5f5f0").pack(pady=(12, 0))

        # Dots + pattern info
        self._info_var = tk.StringVar(value="")
        tk.Label(self, textvariable=self._info_var,
                 font=("Helvetica", 12), fg="#555", bg="#f5f5f0").pack()

        # Pattern binary string
        self._pattern_var = tk.StringVar(value="")
        tk.Label(self, textvariable=self._pattern_var,
                 font=("Courier", 16, "bold"), fg="#222", bg="#f5f5f0").pack(pady=(4, 20))

        self.bind("<Key>", self._on_key)
        self.bind("<Escape>", lambda _: self.destroy())
        self.protocol("WM_DELETE_WINDOW", self._quit)

    def _dot_xy(self, dot: int) -> tuple[int, int]:
        row, col = DOT_POS[dot]
        x = PAD + R + col * (R * 2 + PAD)
        y = PAD + R + row * (R * 2 + PAD)
        return x, y

    def _draw_cell(self) -> None:
        self._canvas.delete("all")
        self._ovals.clear()
        for dot in range(1, 7):
            x, y = self._dot_xy(dot)
            # Draw dot number label (small, grey)
            self._canvas.create_text(x, y - R - 6, text=str(dot),
                                      font=("Helvetica", 8), fill="#bbb")
            oid = self._canvas.create_oval(
                x - R, y - R, x + R, y + R,
                fill="#fff", outline="#333", width=2,
            )
            self._ovals[dot] = oid

    def _render(self, active: list[int]) -> None:
        for dot, oid in self._ovals.items():
            self._canvas.itemconfig(oid, fill="#111" if dot in active else "#fff")

    def _on_key(self, event) -> None:
        now = time.time()
        if now - self._last_key_time < 0.5:   # block repeat during Arduino reset+raise
            return
        self._last_key_time = now
        ch = event.char.lower()
        if ch == " ":
            self._show(ch, [])
            return
        if ch not in BRAILLE:
            return
        self._show(ch, BRAILLE[ch])

    def _show(self, ch: str, dots: list[int]) -> None:
        pattern = dots_to_pattern(dots)
        dot_str = " ".join(str(d) for d in sorted(dots)) or "none"
        display  = ch.upper() if ch not in (" ", "") else "(sp)"

        # Step 1 on screen: clear all dots (mirrors Arduino reset phase)
        self._render([])
        self._letter_var.set("↓")
        self._info_var.set("resetting…")
        self._pattern_var.set("")
        self.update()

        # Step 2 on screen: show active dots after ~350ms (matches Arduino delay)
        self.after(380, lambda: self._finish_show(display, dots, dot_str, pattern))

        print(f"[Key] '{ch}'  dots:{dot_str}  pattern:{pattern}")
        send_pattern(pattern, self.ser)

    def _finish_show(self, display: str, dots: list[int], dot_str: str, pattern: str) -> None:
        self._render(dots)
        self._letter_var.set(display)
        self._info_var.set(f"dots active: {dot_str}")
        self._pattern_var.set(f"serial → \"{pattern}\"")

    def _quit(self) -> None:
        if self.ser:
            try:
                send_pattern("000000", self.ser)
                time.sleep(0.1)
                self.ser.close()
            except Exception:
                pass
        self.destroy()


def main():
    print("=" * 50)
    print("  HackDavis — Braille Servo Test")
    print("=" * 50)
    ser = init_serial()
    print()
    app = BrailleTestApp(ser)
    app.mainloop()


if __name__ == "__main__":
    main()
