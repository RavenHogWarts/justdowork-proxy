import tkinter as tk
from tkinter import font


class Calculator(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Calculator")
        self.resizable(False, False)
        self.configure(bg="#1e1e2e")

        # Color palette
        self.colors = {
            "bg": "#1e1e2e",
            "display_bg": "#181825",
            "display_fg": "#cdd6f4",
            "num_bg": "#313244",
            "num_fg": "#cdd6f4",
            "num_active": "#45475a",
            "op_bg": "#f9e2af",
            "op_fg": "#1e1e2e",
            "op_active": "#f5d57a",
            "eq_bg": "#a6e3a1",
            "eq_fg": "#1e1e2e",
            "eq_active": "#94d490",
            "clr_bg": "#f38ba8",
            "clr_fg": "#1e1e2e",
            "clr_active": "#e67a97",
        }

        self.expression = ""
        self.display_var = tk.StringVar(value="0")

        self.display_font = font.Font(family="Helvetica", size=28, weight="bold")
        self.btn_font = font.Font(family="Helvetica", size=18, weight="bold")

        self._build_display()
        self._build_buttons()

        # Keyboard bindings
        self.bind("<Key>", self._on_key)

    def _build_display(self):
        frame = tk.Frame(self, bg=self.colors["bg"])
        frame.grid(row=0, column=0, columnspan=4, sticky="nsew",
                   padx=12, pady=(16, 8))

        label = tk.Label(
            frame,
            textvariable=self.display_var,
            anchor="e",
            bg=self.colors["display_bg"],
            fg=self.colors["display_fg"],
            font=self.display_font,
            padx=16,
            pady=24,
        )
        label.pack(fill="both", expand=True)

    def _build_buttons(self):
        # (text, row, col, type, colspan)
        buttons = [
            ("C", 1, 0, "clr", 1), ("⌫", 1, 1, "op", 1),
            ("%", 1, 2, "op", 1), ("/", 1, 3, "op", 1),

            ("7", 2, 0, "num", 1), ("8", 2, 1, "num", 1),
            ("9", 2, 2, "num", 1), ("*", 2, 3, "op", 1),

            ("4", 3, 0, "num", 1), ("5", 3, 1, "num", 1),
            ("6", 3, 2, "num", 1), ("-", 3, 3, "op", 1),

            ("1", 4, 0, "num", 1), ("2", 4, 1, "num", 1),
            ("3", 4, 2, "num", 1), ("+", 4, 3, "op", 1),

            ("0", 5, 0, "num", 2), (".", 5, 2, "num", 1),
            ("=", 5, 3, "eq", 1),
        ]

        for col in range(4):
            self.grid_columnconfigure(col, weight=1, minsize=72)
        for row in range(1, 6):
            self.grid_rowconfigure(row, weight=1, minsize=64)

        style_map = {
            "num": ("num_bg", "num_fg", "num_active"),
            "op": ("op_bg", "op_fg", "op_active"),
            "eq": ("eq_bg", "eq_fg", "eq_active"),
            "clr": ("clr_bg", "clr_fg", "clr_active"),
        }

        for (text, row, col, kind, colspan) in buttons:
            bg, fg, active = style_map[kind]
            btn = tk.Button(
                self,
                text=text,
                font=self.btn_font,
                bg=self.colors[bg],
                fg=self.colors[fg],
                activebackground=self.colors[active],
                activeforeground=self.colors[fg],
                relief="flat",
                bd=0,
                highlightthickness=0,
                cursor="hand2",
                command=lambda t=text: self._on_click(t),
            )
            btn.grid(row=row, column=col, columnspan=colspan,
                     sticky="nsew", padx=5, pady=5)

    def _on_click(self, char):
        if char == "C":
            self.expression = ""
            self.display_var.set("0")
        elif char == "⌫":
            self.expression = self.expression[:-1]
            self.display_var.set(self.expression or "0")
        elif char == "=":
            self._calculate()
        else:
            self.expression += char
            self.display_var.set(self.expression)

    def _calculate(self):
        try:
            # Only allow safe characters
            allowed = set("0123456789+-*/%. ")
            if not self.expression or not set(self.expression) <= allowed:
                raise ValueError
            result = eval(self.expression, {"__builtins__": {}}, {})
            if result == int(result):
                result = int(result)
            self.display_var.set(str(result))
            self.expression = str(result)
        except Exception:
            self.display_var.set("Error")
            self.expression = ""

    def _on_key(self, event):
        key = event.keysym
        char = event.char
        if char in "0123456789+-*/%.":
            self._on_click(char)
        elif key in ("Return", "KP_Enter", "equal"):
            self._on_click("=")
        elif key == "BackSpace":
            self._on_click("⌫")
        elif key in ("Escape", "Delete"):
            self._on_click("C")


if __name__ == "__main__":
    Calculator().mainloop()