#!/usr/bin/env python3
"""
braille_servo_test.py — Braille keyboard tester with servo output
==================================================================
On launch:
  1. Arduino moves ALL 6 servos UP together (blue on screen)
  2. Arduino moves ALL 6 servos DOWN together
  3. Arduino moves each servo UP and DOWN one by one (green on screen)
  4. Screen unlocks — press a–z to test each Braille letter

Press a–z  →  correct Braille dots raise for 0.5s, then all go back down
Press ESC  →  quit

Servo physical layout (confirmed via servo_test.py):
    [1] [2]   top row     →  Braille dots [1] [4]
    [3] [4]   middle row  →  Braille dots [2] [5]
    [5] [6]   bottom row  →  Braille dots [3] [6]
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

# Grade 1 Braille — dots active per letter (standard dot numbering 1-6)
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

# Physical servo order: which Braille dot each servo index (0-5) controls.
# Servos are wired left→right, top→bottom: positions 1,2,3,4,5,6
# Braille dots run down left column then right: dot1=top-left, dot4=top-right,
#   dot2=mid-left, dot5=mid-right, dot3=bot-left, dot6=bot-right
_SERVO_DOT_ORDER = [1, 2, 3, 4, 5, 6]  # sequential: servo 0→dot1, 1→dot2, 2→dot3, 3→dot4, 4→dot5, 5→dot6

# Braille dot → which servo circle to light (for the on-screen display)
# dot1→circle1, dot2→circle3, dot3→circle5, dot4→circle2, dot5→circle4, dot6→circle6
_DOT_TO_SERVO = {1: 1, 2: 3, 3: 5, 4: 2, 5: 4, 6: 6}

SERVO_GRID = {
    1: (0, 0), 2: (0, 1),
    3: (1, 0), 4: (1, 1),
    5: (2, 0), 6: (2, 1),
}

SERVO_POSITIONS = {
    1: "top-left",  2: "top-right",
    3: "mid-left",  4: "mid-right",
    5: "bot-left",  6: "bot-right",
}

R   = 40
PAD = 20
CW  = PAD + (R * 2 + PAD) * 2
CH  = PAD + (R * 2 + PAD) * 3


def dots_to_pattern(dots: list[int]) -> str:
    """Convert active Braille dot list to 6-char binary string in physical servo order."""
    return ''.join('1' if d in dots else '0' for d in _SERVO_DOT_ORDER)


def init_serial():
    if not _SERIAL_LIB:
        print("[Serial] pyserial not installed.")
        return None
    try:
        ser = serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=2)
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


class BrailleServoTestApp(tk.Tk):
    def __init__(self, ser):
        super().__init__()
        self.ser = ser
        self._last_key_time = 0.0
        self._ready = False

        self.title("Braille Servo Test — press a–z")
        self.resizable(False, False)
        self.configure(bg="#1a1a2e")

        self._build_ui()

        if ser:
            threading.Thread(target=self._listen_startup, daemon=True).start()
            self.after(15000, self._startup_timeout)
        else:
            self._ready = True
            self._status_var.set("No Arduino — display only")
            self._sub_var.set("Keyboard active. Press a–z.")

        self.bind("<Key>", self._on_key)
        self.bind("<Escape>", lambda _: self._quit())
        self.protocol("WM_DELETE_WINDOW", self._quit)

    # ── UI ──────────────────────────────────────────────────────

    def _build_ui(self):
        bg = "#1a1a2e"

        tk.Label(self, text="Braille Servo Test",
                 font=("Helvetica", 18, "bold"), fg="#eee", bg=bg).pack(pady=(16, 2))
        tk.Label(self, text="Press a–z  •  ESC = quit",
                 font=("Helvetica", 11), fg="#666", bg=bg).pack(pady=(0, 6))

        connected = self.ser is not None
        tk.Label(self,
                 text=f"Arduino: {'CONNECTED  (' + SERIAL_PORT + ')' if connected else 'NOT CONNECTED — display only'}",
                 font=("Helvetica", 10, "bold"),
                 fg="#2ecc71" if connected else "#e67e22", bg=bg).pack(pady=(0, 12))

        # Braille cell grid (numbered 1-6 in physical servo order)
        self._canvas = tk.Canvas(self, width=CW, height=CH,
                                  bg="#0d0d1a", highlightthickness=0)
        self._canvas.pack()
        self._circles: dict[int, int] = {}
        self._circle_labels: dict[int, int] = {}
        self._draw_grid()

        # Large letter display
        self._letter_var = tk.StringVar(value="—")
        tk.Label(self, textvariable=self._letter_var,
                 font=("Helvetica", 64, "bold"), fg="#fff", bg=bg).pack(pady=(14, 0))

        self._status_var = tk.StringVar(
            value="Running startup check — watch all servos move…" if self.ser else "No Arduino"
        )
        tk.Label(self, textvariable=self._status_var,
                 font=("Helvetica", 16, "bold"), fg="#fff", bg=bg).pack(pady=(4, 2))

        self._sub_var = tk.StringVar(
            value="Waiting for Arduino…" if self.ser else ""
        )
        tk.Label(self, textvariable=self._sub_var,
                 font=("Helvetica", 12), fg="#7fb3f5", bg=bg).pack()

        self._pattern_var = tk.StringVar(value="")
        tk.Label(self, textvariable=self._pattern_var,
                 font=("Courier", 14), fg="#aaa", bg=bg).pack(pady=(4, 20))

    def _draw_grid(self):
        for n in range(1, 7):
            x, y = self._dot_xy(n)
            cid = self._canvas.create_oval(
                x - R, y - R, x + R, y + R,
                fill="#2a2a4a", outline="#555", width=2,
            )
            lid = self._canvas.create_text(
                x, y, text=str(n),
                font=("Helvetica", 20, "bold"), fill="#555",
            )
            self._circles[n] = cid
            self._circle_labels[n] = lid

    def _dot_xy(self, servo: int):
        row, col = SERVO_GRID[servo]
        x = PAD + R + col * (R * 2 + PAD)
        y = PAD + R + row * (R * 2 + PAD)
        return x, y

    def _render(self, active_servos: list[int], color: str = "#f39c12") -> None:
        for n in range(1, 7):
            on = n in active_servos
            self._canvas.itemconfig(self._circles[n],
                                     fill=color if on else "#2a2a4a",
                                     outline="#f1c40f" if on else "#555")
            self._canvas.itemconfig(self._circle_labels[n],
                                     fill="#111" if on else "#555")

    def _dots_to_servos(self, dots: list[int]) -> list[int]:
        """Convert Braille dot numbers to physical servo circle numbers for display."""
        return [_DOT_TO_SERVO[d] for d in dots if d in _DOT_TO_SERVO]

    # ── Startup listener ────────────────────────────────────────

    def _listen_startup(self) -> None:
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
            self._letter_var.set("—")
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
            self._status_var.set("Startup complete — press a–z")
            self._sub_var.set("Each letter raises its Braille dots for 0.5s then goes down.")
            self._pattern_var.set("")

    def _startup_timeout(self) -> None:
        if not self._ready:
            self._ready = True
            self._render([])
            self._status_var.set("Press a–z to test each Braille letter")
            self._sub_var.set("(Upload updated Arduino sketch to see startup animation)")
            print("[Startup] Timeout — keyboard now active")

    # ── Key handler ─────────────────────────────────────────────

    def _on_key(self, event) -> None:
        if not self._ready:
            self._sub_var.set("Wait for startup check to finish…")
            return
        now = time.time()
        if now - self._last_key_time < 0.8:
            return
        self._last_key_time = now

        ch = event.char.lower()
        if ch not in BRAILLE:
            return

        dots = BRAILLE[ch]
        pattern = dots_to_pattern(dots)
        active_servos = self._dots_to_servos(dots)
        dot_str = " ".join(str(d) for d in sorted(dots)) or "none"
        display = ch.upper() if ch != " " else "(sp)"

        # Show UP state
        self._render(active_servos)
        self._letter_var.set(display)
        self._status_var.set(f"'{display}'  —  dots: {dot_str}")
        self._sub_var.set("Holding 0.5s…")
        self._pattern_var.set(f"serial → \"{pattern}\"")

        print(f"[Test] '{ch}'  dots:{dot_str}  pattern:{pattern}")
        send_pattern(pattern, self.ser)

        # Auto-down after 500ms
        self.after(500, lambda: self._bring_down())

    def _bring_down(self) -> None:
        self._render([])
        self._status_var.set("DOWN — ready for next key")
        self._sub_var.set("")
        self._pattern_var.set("serial → \"000000\"")
        send_pattern("000000", self.ser)

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
    print("  Braille Servo Test")
    print("=" * 54)
    ser = init_serial()
    print()
    app = BrailleServoTestApp(ser)
    app.mainloop()


if __name__ == "__main__":
    main()
