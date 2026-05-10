#!/usr/bin/env python3
"""
servo_test.py — Individual servo tester with startup health check
=================================================================
On launch:
  1. Arduino moves ALL 6 servos UP together (blue on screen)
  2. Arduino moves ALL 6 servos DOWN together
  3. Arduino moves each servo UP and DOWN one by one (green on screen)
  4. Screen unlocks — press 1–6 to test each servo individually

Press 1–6  →  only that one servo moves up, all others go down
Press 0    →  all servos go down (full reset)
Press ESC  →  quit (all servos return to rest)

Servo positions:
    [1] [2]   ← top row
    [3] [4]   ← middle row
    [5] [6]   ← bottom row
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

SERVO_POSITIONS = {
    1: "top-left",
    2: "top-right",
    3: "mid-left",
    4: "mid-right",
    5: "bot-left",
    6: "bot-right",
}

SERVO_GRID = {
    1: (0, 0), 2: (0, 1),
    3: (1, 0), 4: (1, 1),
    5: (2, 0), 6: (2, 1),
}

R   = 40
PAD = 20
CW  = PAD + (R * 2 + PAD) * 2
CH  = PAD + (R * 2 + PAD) * 3


def make_pattern(servo_num: int) -> str:
    """servo_num 1-6 → only that servo active. 0 = all down."""
    return ''.join('1' if i == servo_num - 1 else '0' for i in range(6))


def init_serial():
    if not _SERIAL_LIB:
        print("[Serial] pyserial not installed.")
        return None
    try:
        # No sleep here — we start reading immediately so we catch startup messages
        ser = serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=2)
        print(f"[Serial] Connected: {SERIAL_PORT}")
        return ser
    except Exception as e:
        print(f"[Serial] Could not connect: {e}")
        print("[Serial] Check that Arduino is plugged in and SERIAL_PORT is correct.")
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
        self._active = 0
        self._last_key_time = 0.0
        self._ready = False     # keyboard locked until startup check finishes

        self.title("Servo Individual Test")
        self.resizable(False, False)
        self.configure(bg="#1a1a2e")

        self._build_ui()

        if ser:
            threading.Thread(target=self._listen_startup, daemon=True).start()
            # Safety unlock if Arduino never sends READY (e.g. old sketch)
            self.after(15000, self._startup_timeout)
        else:
            self._ready = True
            self._status_var.set("No Arduino — display only")
            self._sub_var.set("Keyboard active. Press 1–6.")

        for i in range(7):
            self.bind(str(i), self._on_key)
        self.bind("<Escape>", lambda _: self._quit())
        self.protocol("WM_DELETE_WINDOW", self._quit)

    # ── UI ──────────────────────────────────────────────────────

    def _build_ui(self):
        bg = "#1a1a2e"

        tk.Label(self, text="Servo Individual Test",
                 font=("Helvetica", 18, "bold"), fg="#eee", bg=bg).pack(pady=(16, 2))

        tk.Label(self, text="1–6 = one servo   •   0 = all down   •   ESC = quit",
                 font=("Helvetica", 11), fg="#666", bg=bg).pack(pady=(0, 6))

        connected = self.ser is not None
        tk.Label(self,
                 text=f"Arduino: {'CONNECTED  (' + SERIAL_PORT + ')' if connected else 'NOT CONNECTED — display only'}",
                 font=("Helvetica", 10, "bold"),
                 fg="#2ecc71" if connected else "#e67e22", bg=bg).pack(pady=(0, 12))

        # 2×3 servo grid
        self._canvas = tk.Canvas(self, width=CW, height=CH,
                                  bg="#0d0d1a", highlightthickness=0)
        self._canvas.pack()
        self._circles: dict[int, int] = {}
        self._circle_labels: dict[int, int] = {}
        self._draw_grid()

        # Status text
        self._status_var = tk.StringVar(
            value="Running startup check — watch all servos move…" if self.ser else "No Arduino"
        )
        tk.Label(self, textvariable=self._status_var,
                 font=("Helvetica", 20, "bold"), fg="#fff", bg=bg).pack(pady=(16, 2))

        self._sub_var = tk.StringVar(
            value="Waiting for Arduino…" if self.ser else ""
        )
        tk.Label(self, textvariable=self._sub_var,
                 font=("Helvetica", 13), fg="#7fb3f5", bg=bg).pack()

        self._pattern_var = tk.StringVar(value="")
        tk.Label(self, textvariable=self._pattern_var,
                 font=("Courier", 15), fg="#aaa", bg=bg).pack(pady=(4, 20))

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
            self._circle_labels[n] = lid

    def _dot_xy(self, servo: int):
        row, col = SERVO_GRID[servo]
        x = PAD + R + col * (R * 2 + PAD)
        y = PAD + R + row * (R * 2 + PAD)
        return x, y

    def _render(self, active: list[int], color: str = "#f39c12") -> None:
        for n in range(1, 7):
            on = n in active
            self._canvas.itemconfig(self._circles[n],
                                     fill=color if on else "#2a2a4a",
                                     outline="#f1c40f" if on else "#555")
            self._canvas.itemconfig(self._circle_labels[n],
                                     fill="#111" if on else "#666")

    # ── Startup listener ────────────────────────────────────────

    def _listen_startup(self) -> None:
        """Background thread: read Arduino startup messages and mirror them on screen."""
        try:
            while True:
                raw = self.ser.readline()
                if not raw:
                    continue
                line = raw.decode(errors="ignore").strip()
                if not line:
                    continue
                print(f"[Arduino] {line}")
                self.after(0, self._handle_startup_msg, line)
                if line == "READY":
                    break
        except Exception as e:
            print(f"[Startup listener] {e}")

    def _handle_startup_msg(self, msg: str) -> None:
        if msg == "ALL_UP":
            self._render(list(range(1, 7)), color="#3498db")
            self._status_var.set("All 6 servos UP")
            self._sub_var.set("If any didn't move, it may not be wired correctly.")

        elif msg == "ALL_DOWN":
            self._render([])
            self._status_var.set("All 6 servos DOWN")
            self._sub_var.set("Sequential test starting…")

        elif msg.startswith("SERVO_"):
            try:
                n = int(msg.split("_")[1])
                self._render([n], color="#2ecc71")
                self._status_var.set(f"Testing servo {n}  ({SERVO_POSITIONS[n]})")
                self._sub_var.set("Watch which physical pin moved.")
            except ValueError:
                pass

        elif msg == "READY":
            self._render([])
            self._ready = True
            self._status_var.set("Startup complete — press 1–6")
            self._sub_var.set("Each key moves only that one servo.")
            self._pattern_var.set("")

    def _startup_timeout(self) -> None:
        if not self._ready:
            self._ready = True
            self._render([])
            self._status_var.set("Press 1–6 to test each servo")
            self._sub_var.set("(Tip: upload the updated Arduino sketch to see the startup animation)")
            print("[Startup] Timeout — keyboard now active")

    # ── Key handler ─────────────────────────────────────────────

    def _on_key(self, event) -> None:
        if not self._ready:
            self._sub_var.set("Wait for startup check to finish…")
            return
        now = time.time()
        if now - self._last_key_time < 0.15:
            return
        self._last_key_time = now

        try:
            n = int(event.char)
        except ValueError:
            return

        pattern = make_pattern(n)

        if n == 0:
            self._render([])
            self._status_var.set("ALL DOWN — reset")
            self._sub_var.set("")
            self._pattern_var.set(f"serial → \"{pattern}\"")
        else:
            self._render([n])
            self._status_var.set(f"Servo {n}  ({SERVO_POSITIONS[n]})  →  UP")
            self._sub_var.set("All other servos are DOWN.")
            self._pattern_var.set(f"serial → \"{pattern}\"")

        print(f"[Test] Servo {n}  pattern={pattern}")
        send_pattern(pattern, self.ser)

    # ── Quit ────────────────────────────────────────────────────

    def _quit(self) -> None:
        if self.ser:
            try:
                send_pattern("000000", self.ser)
                time.sleep(0.15)
                self.ser.close()
            except Exception:
                pass
        self.destroy()


def main():
    print("=" * 54)
    print("  Servo Individual Test")
    print("=" * 54)
    ser = init_serial()
    print()
    app = ServoTestApp(ser)
    app.mainloop()


if __name__ == "__main__":
    main()
```
