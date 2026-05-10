#!/usr/bin/env python3
"""
servo_test.py — Individual servo tester
========================================
Press 1–6  →  only that one servo moves up, all others go down.
Press 0    →  all servos go down (full reset).
Press ESC  →  quit.

Servo positions in the Braille cell:
    [1] [2]
    [3] [4]
    [5] [6]

Use this to confirm each servo is wired to the correct physical position.
"""

import time
import threading
import tkinter as tk

try:
    import serial
    _SERIAL_LIB = True
except ImportError:
    _SERIAL_LIB = False

SERIAL_PORT = "/dev/cu.usbmodem1051DB2BD6802"
SERIAL_BAUD = 9600

# Dot layout as the user labeled them (left→right, top→bottom)
# Position in pattern string = servo index (0-based)
# Servo 1 → index 0, Servo 2 → index 1, ... Servo 6 → index 5
SERVO_POSITIONS = {
    1: "top-left",
    2: "top-right",
    3: "mid-left",
    4: "mid-right",
    5: "bot-left",
    6: "bot-right",
}

# Grid coords for drawing (row, col)
SERVO_GRID = {
    1: (0, 0),
    2: (0, 1),
    3: (1, 0),
    4: (1, 1),
    5: (2, 0),
    6: (2, 1),
}

R   = 40
PAD = 20
CW  = PAD + (R * 2 + PAD) * 2
CH  = PAD + (R * 2 + PAD) * 3


def make_pattern(servo_num: int) -> str:
    """servo_num 1-6 → 6-char pattern with only that servo active. 0 = all down."""
    return ''.join('1' if i == servo_num - 1 else '0' for i in range(6))


def init_serial():
    if not _SERIAL_LIB:
        print("[Serial] pyserial not installed.")
        return None
    try:
        ser = serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=1)
        time.sleep(2)
        print(f"[Serial] Connected: {SERIAL_PORT}")
        return ser
    except Exception as e:
        print(f"[Serial] Could not connect: {e}")
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
        self._active = 0          # which servo is currently up (0 = none)
        self._last_key_time = 0.0

        self.title("Servo Individual Test — press 1–6")
        self.resizable(False, False)
        self.configure(bg="#1a1a2e")

        self._build_ui()

        for i in range(7):           # 0–6
            self.bind(str(i), self._on_key)
        self.bind("<Escape>", lambda _: self._quit())
        self.protocol("WM_DELETE_WINDOW", self._quit)

    def _build_ui(self):
        bg = "#1a1a2e"
        tk.Label(self, text="Servo Individual Test",
                 font=("Helvetica", 18, "bold"), fg="#eee", bg=bg).pack(pady=(16, 2))
        tk.Label(self, text="Press 1–6 to activate one servo   •   0 = all down   •   ESC = quit",
                 font=("Helvetica", 11), fg="#888", bg=bg).pack(pady=(0, 4))

        connected = self.ser is not None
        tk.Label(self,
                 text=f"Arduino: {'CONNECTED' if connected else 'NOT CONNECTED — display only'}",
                 font=("Helvetica", 10, "bold"),
                 fg="#2ecc71" if connected else "#e67e22", bg=bg).pack(pady=(0, 14))

        # 2×3 grid of servo indicators
        grid_frame = tk.Frame(self, bg=bg)
        grid_frame.pack()

        self._canvas = tk.Canvas(grid_frame, width=CW, height=CH,
                                  bg="#0d0d1a", highlightthickness=0)
        self._canvas.pack()
        self._circles: dict[int, int] = {}
        self._labels: dict[int, int] = {}
        self._draw_grid()

        # Big status label
        self._status_var = tk.StringVar(value="Press a number key")
        tk.Label(self, textvariable=self._status_var,
                 font=("Helvetica", 22, "bold"), fg="#fff", bg=bg).pack(pady=(18, 4))

        self._pattern_var = tk.StringVar(value="pattern: ——————")
        tk.Label(self, textvariable=self._pattern_var,
                 font=("Courier", 15), fg="#aaa", bg=bg).pack()

        self._pos_var = tk.StringVar(value="")
        tk.Label(self, textvariable=self._pos_var,
                 font=("Helvetica", 13), fg="#7fb3f5", bg=bg).pack(pady=(4, 20))

    def _dot_xy(self, servo: int):
        row, col = SERVO_GRID[servo]
        x = PAD + R + col * (R * 2 + PAD)
        y = PAD + R + row * (R * 2 + PAD)
        return x, y

    def _draw_grid(self):
        for n in range(1, 7):
            x, y = self._dot_xy(n)
            cid = self._canvas.create_oval(
                x - R, y - R, x + R, y + R,
                fill="#2a2a4a", outline="#555", width=2,
            )
            lid = self._canvas.create_text(
                x, y, text=str(n),
                font=("Helvetica", 22, "bold"), fill="#666",
            )
            self._circles[n] = cid
            self._labels[n] = lid

    def _render(self, active: int):
        for n in range(1, 7):
            on = (n == active)
            self._canvas.itemconfig(self._circles[n],
                                     fill="#f39c12" if on else "#2a2a4a",
                                     outline="#f1c40f" if on else "#555")
            self._canvas.itemconfig(self._labels[n],
                                     fill="#111" if on else "#666")

    def _on_key(self, event):
        now = time.time()
        if now - self._last_key_time < 0.15:
            return
        self._last_key_time = now

        try:
            n = int(event.char)
        except ValueError:
            return

        pattern = make_pattern(n)
        self._active = n
        self._render(n)

        if n == 0:
            self._status_var.set("ALL DOWN — reset")
            self._pattern_var.set(f"pattern: {pattern}")
            self._pos_var.set("")
        else:
            pos = SERVO_POSITIONS[n]
            self._status_var.set(f"Servo {n} → UP")
            self._pattern_var.set(f"pattern: {pattern}")
            self._pos_var.set(f"position: {pos}")

        print(f"[Test] Servo {n}  pattern={pattern}")
        send_pattern(pattern, self.ser)

    def _quit(self):
        if self.ser:
            try:
                send_pattern("000000", self.ser)
                time.sleep(0.15)
                self.ser.close()
            except Exception:
                pass
        self.destroy()


def main():
    print("=" * 50)
    print("  Servo Individual Test")
    print("=" * 50)
    ser = init_serial()
    print()
    app = ServoTestApp(ser)
    app.mainloop()


if __name__ == "__main__":
    main()
