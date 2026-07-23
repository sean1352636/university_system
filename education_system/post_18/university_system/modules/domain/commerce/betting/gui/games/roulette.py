"""
European Roulette — a self-contained tkinter GUI game.
Run with:  python roulette.py
Requires only the Python standard library.
"""

import tkinter as tk
try:
    import wallet  # shared credit wallet when launched as a standalone script
except ImportError:  # when imported as part of the betting-shop package
    from education_system.post_18.university_system.modules.domain.commerce.betting.gui.games import wallet
from tkinter import messagebox
import random
import math

# ---------------------------------------------------------------------------
# Roulette constants
# ---------------------------------------------------------------------------
RED_NUMBERS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
BLACK_NUMBERS = {2, 4, 6, 8, 10, 11, 13, 15, 17, 20, 22, 24, 26, 28, 29, 31, 33, 35}

# Order of pockets on a real European wheel (clockwise from 0)
WHEEL_ORDER = [
    0, 32, 15, 19, 4, 21, 2, 25, 17, 34, 6, 27, 13, 36, 11, 30, 8, 23, 10,
    5, 24, 16, 33, 1, 20, 14, 31, 9, 22, 18, 29, 7, 28, 12, 35, 3, 26
]

CHIP_VALUES = [1, 5, 25, 100]
CHIP_COLORS = {1: "#e8e8e8", 5: "#d33636", 25: "#2f8f4e", 100: "#2b2b2b"}

FELT = "#0b6e3a"
FELT_DARK = "#095a30"
GOLD = "#d4af37"


def number_color(n):
    if n == 0:
        return "green"
    return "red" if n in RED_NUMBERS else "black"


# ---------------------------------------------------------------------------
# Bet definitions -- each returns (payout_multiplier, win_predicate)
# payout is "to 1", so a win returns stake * (payout + 1)
# ---------------------------------------------------------------------------
def make_bets():
    bets = {}
    # straight numbers 0-36
    for n in range(0, 37):
        bets[f"num_{n}"] = (35, (lambda x, num=n: x == num))
    # even chance bets
    bets["red"] = (1, lambda x: x in RED_NUMBERS)
    bets["black"] = (1, lambda x: x in BLACK_NUMBERS)
    bets["even"] = (1, lambda x: x != 0 and x % 2 == 0)
    bets["odd"] = (1, lambda x: x % 2 == 1)
    bets["low"] = (1, lambda x: 1 <= x <= 18)
    bets["high"] = (1, lambda x: 19 <= x <= 36)
    # dozens
    bets["dozen_1"] = (2, lambda x: 1 <= x <= 12)
    bets["dozen_2"] = (2, lambda x: 13 <= x <= 24)
    bets["dozen_3"] = (2, lambda x: 25 <= x <= 36)
    # columns
    bets["col_1"] = (2, lambda x: x != 0 and x % 3 == 1)
    bets["col_2"] = (2, lambda x: x != 0 and x % 3 == 2)
    bets["col_3"] = (2, lambda x: x != 0 and x % 3 == 0)
    return bets


BETS = make_bets()


# ---------------------------------------------------------------------------
# Main game
# ---------------------------------------------------------------------------
class Roulette:
    def __init__(self, root):
        self.root = root
        root.title("European Roulette")
        root.configure(bg=FELT_DARK)
        root.resizable(False, False)

        self.balance = wallet.get_credits()
        self.selected_chip = CHIP_VALUES[0]
        self.bets = {}                # bet_key -> amount wagered
        self.bet_widgets = {}         # bet_key -> canvas item id for chip badge
        self.spinning = False
        self.wheel_angle = 0

        self._build_header()
        self._build_wheel()
        self._build_board()
        self._build_chips()
        self._build_controls()
        self._draw_wheel()

    # ---- Header ---------------------------------------------------------
    def _build_header(self):
        header = tk.Frame(self.root, bg=FELT_DARK)
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=12, pady=(12, 4))

        tk.Label(header, text="\u265b  ROULETTE  \u265b", font=("Georgia", 22, "bold"),
                 fg=GOLD, bg=FELT_DARK).pack(side="left")

        self.balance_lbl = tk.Label(header, text=f"Balance: ${self.balance}",
                                    font=("Consolas", 16, "bold"), fg="white", bg=FELT_DARK)
        self.balance_lbl.pack(side="right")

        self.bet_total_lbl = tk.Label(header, text="On table: $0",
                                      font=("Consolas", 12), fg="#cfe8d8", bg=FELT_DARK)
        self.bet_total_lbl.pack(side="right", padx=16)

    # ---- Wheel + result -------------------------------------------------
    def _build_wheel(self):
        left = tk.Frame(self.root, bg=FELT_DARK)
        left.grid(row=1, column=0, padx=12, pady=8, sticky="n")

        self.wheel = tk.Canvas(left, width=300, height=300, bg=FELT_DARK,
                               highlightthickness=0)
        self.wheel.pack()

        self.result_lbl = tk.Label(left, text="Place your bets",
                                   font=("Georgia", 18, "bold"), fg="white",
                                   bg=FELT_DARK, width=16)
        self.result_lbl.pack(pady=6)

        self.msg_lbl = tk.Label(left, text="", font=("Consolas", 12),
                                fg="#cfe8d8", bg=FELT_DARK, width=26, height=2,
                                wraplength=260, justify="center")
        self.msg_lbl.pack()

    def _draw_wheel(self, highlight=None):
        c = self.wheel
        c.delete("all")
        cx, cy, r = 150, 150, 130
        n = len(WHEEL_ORDER)
        step = 360 / n
        for i, num in enumerate(WHEEL_ORDER):
            start = self.wheel_angle + i * step
            col = number_color(num)
            fill = {"green": "#0b8a44", "red": "#c0392b", "black": "#1c1c1c"}[col]
            c.create_arc(cx - r, cy - r, cx + r, cy + r, start=start, extent=step,
                         fill=fill, outline=GOLD, width=1)
            # number text at mid-angle
            mid = math.radians(start + step / 2)
            tx = cx + (r - 16) * math.cos(mid)
            ty = cy - (r - 16) * math.sin(mid)
            c.create_text(tx, ty, text=str(num), fill="white",
                          font=("Arial", 8, "bold"))
        # hub
        c.create_oval(cx - 40, cy - 40, cx + 40, cy + 40, fill="#7a5c1e",
                      outline=GOLD, width=2)
        c.create_text(cx, cy, text="\u2605", fill=GOLD, font=("Arial", 22))
        # pointer at top
        c.create_polygon(cx - 10, 8, cx + 10, 8, cx, 30, fill=GOLD, outline="black")
        if highlight is not None:
            self.result_lbl.config(text=f"  {highlight}  ",
                                   bg={"green": "#0b8a44", "red": "#c0392b",
                                       "black": "#1c1c1c"}[number_color(highlight)])

    # ---- Betting board --------------------------------------------------
    def _build_board(self):
        board = tk.Frame(self.root, bg=FELT)
        board.grid(row=1, column=1, padx=12, pady=8, sticky="n")

        # 0 spanning the left
        self._bet_cell(board, "0", "num_0", 0, 0, rowspan=3, bg="#0b8a44",
                       width=3, height=3)

        # number grid: 3 rows x 12 cols. Top row 3,6,9...; bottom 1,4,7...
        layout = [
            [3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 33, 36],
            [2, 5, 8, 11, 14, 17, 20, 23, 26, 29, 32, 35],
            [1, 4, 7, 10, 13, 16, 19, 22, 25, 28, 31, 34],
        ]
        for r, row in enumerate(layout):
            for cidx, num in enumerate(row):
                bg = "#c0392b" if num in RED_NUMBERS else "#1c1c1c"
                self._bet_cell(board, str(num), f"num_{num}", r, cidx + 1, bg=bg)

        # column bets (2:1) on the right
        for r, key in enumerate(["col_3", "col_2", "col_1"]):
            self._bet_cell(board, "2:1", key, r, 13, bg=FELT_DARK, width=4)

        # dozens
        self._bet_cell(board, "1st 12", "dozen_1", 3, 1, colspan=4, bg=FELT_DARK)
        self._bet_cell(board, "2nd 12", "dozen_2", 3, 5, colspan=4, bg=FELT_DARK)
        self._bet_cell(board, "3rd 12", "dozen_3", 3, 9, colspan=4, bg=FELT_DARK)

        # even-money row
        even_money = [
            ("1-18", "low"), ("EVEN", "even"), ("\u25c6", "red"),
            ("\u25c6", "black"), ("ODD", "odd"), ("19-36", "high"),
        ]
        for i, (label, key) in enumerate(even_money):
            bg = FELT_DARK
            fg = "white"
            if key == "red":
                bg = "#c0392b"
            elif key == "black":
                bg = "#1c1c1c"
            self._bet_cell(board, label, key, 4, 1 + i * 2, colspan=2, bg=bg, fg=fg)

    def _bet_cell(self, parent, text, key, r, col, rowspan=1, colspan=1,
                  bg="#1c1c1c", fg="white", width=2, height=1):
        f = tk.Frame(parent, bg=bg, highlightbackground=GOLD,
                     highlightthickness=1)
        f.grid(row=r, column=col, rowspan=rowspan, columnspan=colspan,
               sticky="nsew", padx=1, pady=1)
        canvas = tk.Canvas(f, bg=bg, highlightthickness=0,
                           width=max(28, 14 * width), height=max(24, 22 * height))
        canvas.pack(fill="both", expand=True)
        canvas.create_text(canvas.winfo_reqwidth() / 2,
                           canvas.winfo_reqheight() / 2,
                           text=text, fill=fg, font=("Arial", 9, "bold"),
                           tags="label")
        for w in (f, canvas):
            w.bind("<Button-1>", lambda e, k=key: self.place_bet(k))
            w.bind("<Button-3>", lambda e, k=key: self.clear_one(k))
        self.bet_widgets[key] = canvas

    # ---- Chip selector --------------------------------------------------
    def _build_chips(self):
        chips = tk.Frame(self.root, bg=FELT_DARK)
        chips.grid(row=2, column=0, columnspan=2, pady=(4, 2))

        tk.Label(chips, text="Chip:", font=("Consolas", 12, "bold"),
                 fg="white", bg=FELT_DARK).pack(side="left", padx=(0, 8))

        self.chip_buttons = {}
        for val in CHIP_VALUES:
            b = tk.Canvas(chips, width=52, height=52, bg=FELT_DARK,
                          highlightthickness=0)
            b.pack(side="left", padx=6)
            self._draw_chip(b, val, selected=(val == self.selected_chip))
            b.bind("<Button-1>", lambda e, v=val: self.select_chip(v))
            self.chip_buttons[val] = b

        tk.Label(chips, text="Custom:", font=("Consolas", 12, "bold"),
                 fg="white", bg=FELT_DARK).pack(side="left", padx=(16, 4))
        self.chip_var = tk.StringVar(value=str(self.selected_chip))
        self.chip_entry = tk.Entry(chips, textvariable=self.chip_var, width=6,
                                   justify="center", font=("Consolas", 12, "bold"))
        self.chip_entry.pack(side="left")
        self.chip_entry.bind("<Return>", lambda e: self.set_chip_amount())
        self.chip_entry.bind("<FocusOut>", lambda e: self.set_chip_amount())

    def _draw_chip(self, canvas, val, selected=False):
        canvas.delete("all")
        col = CHIP_COLORS[val]
        outline = GOLD if selected else "white"
        w = 4 if selected else 2
        canvas.create_oval(6, 6, 46, 46, fill=col, outline=outline, width=w)
        txt_col = "black" if val in (1, 5) else "white"
        canvas.create_text(26, 26, text=f"${val}", fill=txt_col,
                           font=("Arial", 10, "bold"))

    # ---- Controls -------------------------------------------------------
    def _build_controls(self):
        ctrl = tk.Frame(self.root, bg=FELT_DARK)
        ctrl.grid(row=3, column=0, columnspan=2, pady=(4, 14))

        self.spin_btn = tk.Button(ctrl, text="\u25b6 SPIN", font=("Georgia", 14, "bold"),
                                  bg=GOLD, fg="#2b2b2b", width=10, relief="raised",
                                  command=self.spin)
        self.spin_btn.pack(side="left", padx=8)

        tk.Button(ctrl, text="Clear Bets", font=("Georgia", 12),
                  bg="#8a3b2e", fg="white", command=self.clear_all).pack(side="left", padx=8)

        tk.Label(ctrl, text="Left-click a spot to bet  \u2022  Right-click to remove",
                 font=("Consolas", 9), fg="#9fd4b4", bg=FELT_DARK).pack(side="left", padx=12)

    # ---- Chip badge on a bet spot --------------------------------------
    def _refresh_badge(self, key):
        canvas = self.bet_widgets[key]
        canvas.delete("badge")
        amt = self.bets.get(key, 0)
        if amt > 0:
            w = canvas.winfo_reqwidth()
            h = canvas.winfo_reqheight()
            canvas.create_oval(w - 22, h - 20, w - 2, h, fill=GOLD,
                               outline="black", tags="badge")
            canvas.create_text(w - 12, h - 10, text=str(amt),
                               font=("Arial", 7, "bold"), tags="badge")

    # ---- Actions --------------------------------------------------------
    def select_chip(self, val):
        self.selected_chip = val
        for v, b in self.chip_buttons.items():
            self._draw_chip(b, v, selected=(v == val))
        if hasattr(self, "chip_var"):
            self.chip_var.set(str(val))

    def set_chip_amount(self):
        """Set the active chip to a custom positive amount typed by the player."""
        try:
            val = int(float(self.chip_var.get()))
        except (TypeError, ValueError):
            self.chip_var.set(str(self.selected_chip))
            return
        if val < 1:
            self.chip_var.set(str(self.selected_chip))
            return
        self.selected_chip = val
        # Deselect the preset chip buttons since a custom value is now active.
        for v, b in self.chip_buttons.items():
            self._draw_chip(b, v, selected=False)
        self.chip_var.set(str(val))

    def place_bet(self, key):
        if self.spinning:
            return
        if self.selected_chip > self.balance - self._table_total():
            self.msg_lbl.config(text="Not enough balance for that chip.")
            return
        self.bets[key] = self.bets.get(key, 0) + self.selected_chip
        self._refresh_badge(key)
        self._update_labels()

    def clear_one(self, key):
        if self.spinning or key not in self.bets:
            return
        del self.bets[key]
        self._refresh_badge(key)
        self._update_labels()

    def clear_all(self):
        if self.spinning:
            return
        for key in list(self.bets):
            self.bets.pop(key)
            self._refresh_badge(key)
        self._update_labels()

    def _table_total(self):
        return sum(self.bets.values())

    def _update_labels(self):
        wallet.set_credits(self.balance)
        self.balance_lbl.config(text=f"Balance: ${self.balance}")
        self.bet_total_lbl.config(text=f"On table: ${self._table_total()}")

    # ---- Spin -----------------------------------------------------------
    def spin(self):
        if self.spinning:
            return
        if not self.bets:
            self.msg_lbl.config(text="Place at least one bet first.")
            return
        self.spinning = True
        self.spin_btn.config(state="disabled")
        self.msg_lbl.config(text="")
        self.result_lbl.config(bg=FELT_DARK, text="Spinning...")

        result = random.randint(0, 36)
        # find where result sits in the wheel order to land the pointer on it
        idx = WHEEL_ORDER.index(result)
        step = 360 / len(WHEEL_ORDER)
        # pointer is at top (90 deg). Solve final angle so that pocket center hits top.
        target = (90 - (idx * step + step / 2)) % 360
        total_spin = 360 * 5 + target  # 5 full turns for drama
        self._animate_spin(0, total_spin, result)

    def _animate_spin(self, current, total, result, frame=0):
        # ease-out: slow down as we approach total
        remaining = total - current
        speed = max(4, remaining * 0.06)
        current = min(total, current + speed)
        self.wheel_angle = current % 360
        self._draw_wheel()
        if current < total - 0.5:
            self.root.after(16, lambda: self._animate_spin(current, total, result, frame + 1))
        else:
            self.wheel_angle = total % 360
            self._draw_wheel(highlight=result)
            self._settle(result)

    def _settle(self, result):
        col = number_color(result)
        winnings = 0
        winning_keys = []
        for key, amt in self.bets.items():
            payout, pred = BETS[key]
            if pred(result):
                winnings += amt * (payout + 1)
                winning_keys.append(key)

        staked = self._table_total()
        self.balance += winnings - staked
        net = winnings - staked

        color_word = {"green": "Green", "red": "Red", "black": "Black"}[col]
        if net > 0:
            msg = f"{result} {color_word}!  You won ${net}."
            self.msg_lbl.config(fg="#b6f7c8")
        elif net == 0:
            msg = f"{result} {color_word}.  You broke even."
            self.msg_lbl.config(fg="#e8e8b6")
        else:
            msg = f"{result} {color_word}.  You lost ${-net}."
            self.msg_lbl.config(fg="#f7b6b6")
        self.msg_lbl.config(text=msg)

        # clear the table
        for key in list(self.bets):
            self.bets.pop(key)
            self._refresh_badge(key)
        self._update_labels()

        self.spinning = False
        self.spin_btn.config(state="normal")

        if self.balance <= 0:
            messagebox.showinfo("Out of chips",
                                "You're out of credits! Buy more from the betting "
                                "shop to keep playing.")
            wallet.close_game(self.root)


if __name__ == "__main__":
    root = tk.Tk()
    Roulette(root)
    root.mainloop()
