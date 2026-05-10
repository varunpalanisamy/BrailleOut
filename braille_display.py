import tkinter as tk

# Standard Grade 1 Braille alphabet
# Dot numbering: 1,2,3 = left column top→bottom; 4,5,6 = right column top→bottom
BRAILLE = {
    'a': {1},
    'b': {1, 2},
    'c': {1, 4},
    'd': {1, 4, 5},
    'e': {1, 5},
    'f': {1, 2, 4},
    'g': {1, 2, 4, 5},
    'h': {1, 2, 5},
    'i': {2, 4},
    'j': {2, 4, 5},
    'k': {1, 3},
    'l': {1, 2, 3},
    'm': {1, 3, 4},
    'n': {1, 3, 4, 5},
    'o': {1, 3, 5},
    'p': {1, 2, 3, 4},
    'q': {1, 2, 3, 4, 5},
    'r': {1, 2, 3, 5},
    's': {2, 3, 4},
    't': {2, 3, 4, 5},
    'u': {1, 3, 6},
    'v': {1, 2, 3, 6},
    'w': {2, 4, 5, 6},
    'x': {1, 3, 4, 6},
    'y': {1, 3, 4, 5, 6},
    'z': {1, 3, 5, 6},
}

# Maps dot number → (row, col) in the 3×2 grid
DOT_POSITION = {
    1: (0, 0), 4: (0, 1),
    2: (1, 0), 5: (1, 1),
    3: (2, 0), 6: (2, 1),
}

DOT_RADIUS = 28
PADDING = 18
CELL_W = PADDING + (DOT_RADIUS * 2 + PADDING) * 2
CELL_H = PADDING + (DOT_RADIUS * 2 + PADDING) * 3

COLOR_FILLED = "#1a1a1a"
COLOR_EMPTY  = "#ffffff"
COLOR_OUTLINE = "#222222"


class BrailleDisplay(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Braille Cell Viewer")
        self.resizable(False, False)
        self.configure(bg="#f5f5f5")

        title = tk.Label(self, text="Braille Cell Viewer",
                         font=("Helvetica", 16, "bold"), bg="#f5f5f5")
        title.pack(pady=(16, 0))

        subtitle = tk.Label(self, text="Press a letter key  (a–z)",
                            font=("Helvetica", 11), fg="#666666", bg="#f5f5f5")
        subtitle.pack(pady=(2, 12))

        self.canvas = tk.Canvas(self, width=CELL_W, height=CELL_H,
                                bg="#ffffff", highlightthickness=2,
                                highlightbackground="#cccccc")
        self.canvas.pack(padx=32)

        self.letter_var = tk.StringVar(value="—")
        letter_label = tk.Label(self, textvariable=self.letter_var,
                                font=("Helvetica", 48, "bold"), bg="#f5f5f5")
        letter_label.pack(pady=(14, 4))

        self.dots_label = tk.Label(self, text="dots: —",
                                   font=("Helvetica", 11), fg="#888888", bg="#f5f5f5")
        self.dots_label.pack(pady=(0, 20))

        self._oval_ids = {}
        self._draw_empty_cell()

        self.bind("<Key>", self._on_key)

    def _dot_center(self, dot_num):
        row, col = DOT_POSITION[dot_num]
        x = PADDING + DOT_RADIUS + col * (DOT_RADIUS * 2 + PADDING)
        y = PADDING + DOT_RADIUS + row * (DOT_RADIUS * 2 + PADDING)
        return x, y

    def _draw_empty_cell(self):
        self.canvas.delete("all")
        self._oval_ids.clear()
        for dot in range(1, 7):
            x, y = self._dot_center(dot)
            r = DOT_RADIUS
            oid = self.canvas.create_oval(
                x - r, y - r, x + r, y + r,
                fill=COLOR_EMPTY, outline=COLOR_OUTLINE, width=2
            )
            self._oval_ids[dot] = oid

    def _render(self, active_dots):
        for dot, oid in self._oval_ids.items():
            fill = COLOR_FILLED if dot in active_dots else COLOR_EMPTY
            self.canvas.itemconfig(oid, fill=fill)

    def _on_key(self, event):
        ch = event.char.lower()
        if ch not in BRAILLE:
            return
        active = BRAILLE[ch]
        self._render(active)
        self.letter_var.set(ch.upper())
        dot_str = " ".join(str(d) for d in sorted(active))
        self.dots_label.config(text=f"dots: {dot_str}")


if __name__ == "__main__":
    app = BrailleDisplay()
    app.mainloop()
