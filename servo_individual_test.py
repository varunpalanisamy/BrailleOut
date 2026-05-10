#!/usr/bin/env python3
"""
servo_individual_test.py  —  HackDavis 2026
============================================
Press 1–6 to fire a single servo (dot position).
Press 0 to reset all servos.
ESC to quit.

Run:
    python3 servo_individual_test.py
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

DOT_POS = {
    1: (0, 0), 4: (0, 1),
    2: (1, 0), 5: (1, 1),
    3: (2, 0), 6: (2, 1),
}

R   = 36
PAD = 18
CW  = PAD + (R * 2 + PAD) * 2
CH  = PAD + (R * 2 + PAD) * 3


_SERVO_DOT_ORDER = [1, 2, 3, 4, 5, 6]  # sequential: servo 0→dot1, 1→dot2, 2→dot3, 3→dot4, 4→dot5, 5→dot6

def dots_to_pattern(active: list[int]) -> str:
    return ''.join('1' if d in active else '0' for d in _SERVO_DOT_ORDER)


def init_serial():
    if not _SERIAL_LIB:
        print("[Serial] pyserial not installed — run: pip install pyserial")
        return None
    try:
        ser = serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=1)
        time.sleep(2)
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


class ServoTestApp(tk.Tk):
    def __init__(self, ser):
        super().__init__()
        self.ser = ser
        self._active: list[int] = []
        self.title("Individual Servo Test — press 1–6")
        self.resizable(False, False)
        self.configure(bg="#f5f5f0")

        tk.Label(self, text="Individual Servo Tester",
                 font=("Helvetica", 17, "bold"), bg="#f5f5f0").pack(pady=(14, 2))
        tk.Label(self, text="Press 1–6 to trigger a single servo  •  0 = reset all  •  ESC = quit",
                 font=("Helvetica", 11), fg="#888", bg="#f5f5f0").pack(pady=(0, 10))

        status_txt = f"Arduino: connected ({SERIAL_PORT})" if ser else "Arduino: NOT connected (display-only mode)"
        status_col = "#27ae60" if ser else "#e67e22"
        tk.Label(self, text=status_txt, font=("Helvetica", 10, "bold"),
                 fg=status_col, bg="#f5f5f0").pack(pady=(0, 12))

        self._canvas = tk.Canvas(self, width=CW, height=CH,
                                  bg="#fff", highlightthickness=2,
                                  highlightbackground="#ccc")
        self._canvas.pack(padx=50)
        self._ovals: dict[int, int] = {}
        self._draw_cell()

        self._dot_var = tk.StringVar(value="—")
        tk.Label(self, textvariable=self._dot_var,
                 font=("Helvetica", 72, "bold"), bg="#f5f5f0").pack(pady=(12, 0))

        self._info_var = tk.StringVar(value="press a number key")
        tk.Label(self, textvariable=self._info_var,
                 font=("Helvetica", 12), fg="#555", bg="#f5f5f0").pack()

        self._pattern_var = tk.StringVar(value="")
        tk.Label(self, textvariable=self._pattern_var,
                 font=("Courier", 16, "bold"), fg="#222", bg="#f5f5f0").pack(pady=(4, 20))

        self.bind("<Key>", self._on_key)
        self.bind("<Escape>", lambda _: self._quit())
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
            self._canvas.create_text(x, y, text=str(dot),
                                      font=("Helvetica", 14, "bold"), fill="#bbb",
                                      tags=f"label_{dot}")
            oid = self._canvas.create_oval(
                x - R, y - R, x + R, y + R,
                fill="#fff", outline="#333", width=2,
            )
            self._ovals[dot] = oid
            # Dot number label on top of oval
            self._canvas.create_text(x, y, text=str(dot),
                                      font=("Helvetica", 14, "bold"), fill="#999")

    def _render(self, active: list[int]) -> None:
        for dot, oid in self._ovals.items():
            self._canvas.itemconfig(oid, fill="#f39c12" if dot in active else "#fff")

    def _on_key(self, event) -> None:
        ch = event.char
        if ch == "0":
            self._fire([])
            return
        if ch in "123456":
            self._fire([int(ch)])

    def _fire(self, dots: list[int]) -> None:
        self._active = dots
        pattern = dots_to_pattern(dots)

        self._render([])
        self._dot_var.set("↓")
        self._info_var.set("resetting…")
        self._pattern_var.set("")
        self.update()

        self.after(380, lambda: self._finish(dots, pattern))
        print(f"[Servo] dots:{sorted(dots) or 'none'}  pattern:{pattern}")
        send_pattern(pattern, self.ser)

    def _finish(self, dots: list[int], pattern: str) -> None:
        self._render(dots)
        if not dots:
            self._dot_var.set("0")
            self._info_var.set("all servos reset")
        else:
            self._dot_var.set(str(dots[0]))
            self._info_var.set(f"dot {dots[0]} active  (position: row {DOT_POS[dots[0]][0]+1}, col {DOT_POS[dots[0]][1]+1})")
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
    print("  HackDavis — Individual Servo Test")
    print("=" * 50)
    ser = init_serial()
    print()
    app = ServoTestApp(ser)
    app.mainloop()


if __name__ == "__main__":
    main()
