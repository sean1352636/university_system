"""
Multiline Video Slot -- 5 reels x 3 rows, 5 paylines, with a WILD.

Self-contained Tkinter game (standard library only).
Run with:  python multiline_slot.py

Five paylines are evaluated left to right. A line pays when 3+ matching
symbols land on consecutive reels starting from reel 1. WILD substitutes for
any symbol. Total bet = 5 x line bet.
"""

import random
import tkinter as tk
try:
    import wallet  # shared credit wallet when launched as a standalone script
except ImportError:  # when imported as part of the betting-shop package
    from education_system.systems.university.interfaces.gui.operations.commerce.betting.games import wallet

SYM = {
    "wild":    ("W", "#9d4edd", 34),
    "star":    ("\u2605", "#e9c46a", 40),
    "diamond": ("\u25c6", "#2aa9c9", 38),
    "heart":   ("\u2665", "#e63946", 38),
    "spade":   ("\u2660", "#1d3557", 38),
    "club":    ("\u2663", "#2a9d4a", 38),
}
STRIP = (["club"] * 8 + ["spade"] * 7 + ["heart"] * 6 + ["diamond"] * 5 +
         ["star"] * 3 + ["wild"] * 2)
# per-symbol payout (x line bet) for exactly 3 / 4 / 5 in a row
PAYTABLE = {
    "star":    {3: 10, 4: 50, 5: 200},
    "diamond": {3: 8, 4: 40, 5: 150},
    "heart":   {3: 5, 4: 25, 5: 100},
    "spade":   {3: 4, 4: 20, 5: 80},
    "club":    {3: 3, 4: 15, 5: 60},
}
# rows used by each of the 5 paylines (index into 0/1/2 per reel)
LINES = [
    [1, 1, 1, 1, 1],   # middle
    [0, 0, 0, 0, 0],   # top
    [2, 2, 2, 2, 2],   # bottom
    [0, 1, 2, 1, 0],   # V
    [2, 1, 0, 1, 2],   # inverted V
]
LINE_COLORS = ["#e9c46a", "#4ea8de", "#e5989b", "#83c5be", "#f4a261"]

COLS, ROWS = 5, 3
CELL, GAP = 88, 8
FELT, GOLD = "#0b1e3a", "#e9c46a"
START_CREDITS = 300


def evaluate(grid):
    """grid[row][col] of symbol names. Returns list of (line_idx, sym, count, cells)."""
    wins = []
    for li, rows in enumerate(LINES):
        cells = [(rows[c], c) for c in range(COLS)]
        syms = [grid[r][c] for (r, c) in cells]
        # base symbol = first non-wild; all wilds -> treat as star
        base = next((s for s in syms if s != "wild"), "star")
        count = 0
        for s in syms:
            if s == base or s == "wild":
                count += 1
            else:
                break
        if count >= 3 and base in PAYTABLE:
            wins.append((li, base, count, cells[:count]))
    return wins


class MultilineSlot:
    def __init__(self, root):
        self.root = root
        root.title("Multiline Video Slot")
        root.configure(bg=FELT)
        root.resizable(False, False)
        self.credits = wallet.get_credits()
        self.line_bet = 5
        self.stops = [0] * COLS
        self.win_cells = {}
        self.busy = False
        self._build()
        self.render()
        self.refresh()

    def _build(self):
        f = tk.Frame(self.root, bg=FELT, padx=18, pady=14)
        f.pack()
        tk.Label(f, text="VIDEO SLOT \u2014 5 LINES", bg=FELT, fg=GOLD,
                 font=("Helvetica", 19, "bold")).pack()
        w = COLS * CELL + (COLS + 1) * GAP
        h = ROWS * CELL + (ROWS + 1) * GAP
        self.canvas = tk.Canvas(f, width=w, height=h, bg="#081428",
                                highlightthickness=0)
        self.canvas.pack(pady=10)
        self.msg = tk.Label(f, text="", bg=FELT, fg="white",
                            font=("Helvetica", 12, "bold"))
        self.msg.pack()
        tk.Label(f, text="\u2605 200  \u25c6 150  \u2665 100  \u2660 80  "
                 "\u2663 60  (5 on a line)   W = WILD", bg=FELT, fg="#9fb3c8",
                 font=("Helvetica", 9)).pack(pady=2)

        bar = tk.Frame(f, bg=FELT, pady=8)
        bar.pack()
        self.cr_lbl = tk.Label(bar, text="", bg=FELT, fg="white",
                               font=("Helvetica", 12, "bold"))
        self.cr_lbl.pack(side="left", padx=8)
        tk.Button(bar, text="\u2212", width=3, command=lambda: self.chg(-1),
                  font=("Helvetica", 11, "bold"), bg="#333", fg="white",
                  bd=0).pack(side="left")
        tk.Label(bar, text="Line", bg=FELT, fg=GOLD,
                 font=("Helvetica", 12, "bold")).pack(side="left", padx=(6, 2))
        self.bet_var = tk.StringVar()
        self.bet_entry = tk.Entry(bar, textvariable=self.bet_var, width=4,
                                  justify="center", font=("Helvetica", 12, "bold"),
                                  bg="#0d2846", fg=GOLD, insertbackground=GOLD,
                                  relief="flat", bd=2)
        self.bet_entry.pack(side="left")
        self.bet_entry.bind("<Return>", lambda e: self.set_bet())
        self.bet_entry.bind("<FocusOut>", lambda e: self.set_bet())
        self.bet_total_lbl = tk.Label(bar, text="", bg=FELT, fg=GOLD, width=10,
                                      font=("Helvetica", 12, "bold"))
        self.bet_total_lbl.pack(side="left")
        tk.Button(bar, text="+", width=3, command=lambda: self.chg(1),
                  font=("Helvetica", 11, "bold"), bg="#333", fg="white",
                  bd=0).pack(side="left")
        self.spin_btn = tk.Button(f, text="SPIN", command=self.spin, width=16,
                                  font=("Helvetica", 14, "bold"), bg="#1b7a4b",
                                  fg="white", activebackground=GOLD, bd=0, pady=8,
                                  cursor="hand2")
        self.spin_btn.pack(pady=6)

    def _sym_at(self, col, row):
        return STRIP[(self.stops[col] + row - 1) % len(STRIP)]

    def render(self):
        self.canvas.delete("all")
        for col in range(COLS):
            for row in range(ROWS):
                x = GAP + col * (CELL + GAP)
                y = GAP + row * (CELL + GAP)
                hit = self.win_cells.get((col, row))
                outline = hit if hit else "#22344f"
                self.canvas.create_rectangle(x, y, x + CELL, y + CELL, fill="white",
                                             outline=outline, width=4 if hit else 2)
                g, color, size = SYM[self._sym_at(col, row)]
                self.canvas.create_text(x + CELL / 2, y + CELL / 2, text=g,
                                         fill=color, font=("Helvetica", size, "bold"))

    def chg(self, d):
        if self.busy:
            return
        self.line_bet = max(1, min(self.line_bet + d, max(1, self.credits // 5)))
        self.refresh()

    def set_bet(self):
        """Set the per-line bet to the amount typed into the entry box."""
        try:
            self.chg(int(float(self.bet_var.get())) - self.line_bet)
        except (TypeError, ValueError):
            pass
        self.bet_var.set(str(self.line_bet))

    def refresh(self):
        wallet.set_credits(self.credits)
        self.cr_lbl.config(text=f"Credits: {self.credits}")
        self.bet_var.set(str(self.line_bet))
        self.bet_total_lbl.config(text=f"\u00d7 5 = {self.line_bet * 5}")

    def spin(self):
        if self.busy:
            return
        total = self.line_bet * 5
        if self.credits < total:
            self.msg.config(text="Not enough credits.")
            return
        self.credits -= total
        self.win_cells = {}
        self.msg.config(text="")
        self.final = [random.randrange(len(STRIP)) for _ in range(COLS)]
        self.ticks = [12 + c * 5 for c in range(COLS)]
        self.busy = True
        self.spin_btn.config(state="disabled")
        self.refresh()
        self._animate()

    def _animate(self):
        running = False
        for c in range(COLS):
            if self.ticks[c] > 0:
                self.ticks[c] -= 1
                self.stops[c] = (self.final[c] if self.ticks[c] == 0
                                 else random.randrange(len(STRIP)))
                running = True
        self.render()
        if running:
            self.root.after(50, self._animate)
        else:
            self._settle()

    def _settle(self):
        grid = [[STRIP[(self.final[c] + r - 1) % len(STRIP)] for c in range(COLS)]
                for r in range(ROWS)]
        wins = evaluate(grid)
        total_win = 0
        for li, base, count, cells in wins:
            pay = PAYTABLE[base][count] * self.line_bet
            total_win += pay
            for (r, c) in cells:
                self.win_cells[(c, r)] = LINE_COLORS[li]
        if total_win:
            self.credits += total_win
            lines = ", ".join(f"L{li + 1}" for li, *_ in wins)
            self.msg.config(text=f"WIN {total_win}!  ({lines})", fg=GOLD)
        else:
            self.msg.config(text="No win. Spin again!", fg="white")
        self.render()
        if self.credits < 5:
            self.msg.config(text="Out of credits \u2014 buy more credits!")
            wallet.close_game(self.root)
        self.line_bet = min(self.line_bet, max(1, self.credits // 5))
        self.refresh()
        self.busy = False
        self.spin_btn.config(state="normal")


def main():
    root = tk.Tk()
    MultilineSlot(root)
    root.mainloop()


if __name__ == "__main__":
    main()
