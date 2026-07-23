"""
Classic Slot -- 3 reels, single payline.

Self-contained Tkinter game (standard library only).
Run with:  python classic_slot.py

Match three symbols on the centre line. Two hearts pay a small consolation,
one heart pays your bet back. Sevens are the jackpot.
"""

import random
import tkinter as tk
try:
    import wallet  # shared credit wallet when launched as a standalone script
except ImportError:  # when imported as part of the betting-shop package
    from education_system.post_18.university_system.modules.domain.commerce.betting.gui.games import wallet

# name -> (glyph, colour, font size)
SYM = {
    "seven":   ("7",   "#e63946", 46),
    "bar":     ("BAR", "#1d3557", 22),
    "star":    ("\u2605", "#e9c46a", 44),
    "diamond": ("\u25c6", "#2aa9c9", 42),
    "heart":   ("\u2665", "#e63946", 42),
    "club":    ("\u2663", "#2a9d4a", 42),
}
# reel strip -- repetition controls probability (sevens are rare)
STRIP = (["club"] * 6 + ["heart"] * 6 + ["diamond"] * 4 +
         ["star"] * 3 + ["bar"] * 2 + ["seven"] * 1)
PAYOUT = {"seven": 100, "bar": 40, "star": 20, "diamond": 12, "heart": 8, "club": 5}

COLS, ROWS = 3, 3
CELL, GAP = 100, 10
FELT, GOLD = "#0b1e3a", "#e9c46a"
START_CREDITS, MIN_BET = 200, 5


class ClassicSlot:
    def __init__(self, root):
        self.root = root
        root.title("Classic Slot \u2014 777")
        root.configure(bg=FELT)
        root.resizable(False, False)
        self.credits = wallet.get_credits()
        self.bet = 25
        self.stops = [0, 0, 0]
        self.win_cells = set()
        self.busy = False
        self._build()
        self.render()
        self.refresh()

    def _build(self):
        f = tk.Frame(self.root, bg=FELT, padx=20, pady=16)
        f.pack()
        tk.Label(f, text="\u2605 CLASSIC SLOT \u2605", bg=FELT, fg=GOLD,
                 font=("Helvetica", 20, "bold")).pack()
        w = COLS * CELL + (COLS + 1) * GAP
        h = ROWS * CELL + (ROWS + 1) * GAP
        self.canvas = tk.Canvas(f, width=w, height=h, bg="#081428",
                                highlightthickness=0)
        self.canvas.pack(pady=10)
        self.msg = tk.Label(f, text="", bg=FELT, fg="white",
                            font=("Helvetica", 13, "bold"))
        self.msg.pack()
        tk.Label(f, text="777=100x  BAR=40x  \u2605=20x  \u25c6=12x  "
                 "\u2665=8x  \u2663=5x  (per bet)", bg=FELT, fg="#9fb3c8",
                 font=("Helvetica", 9)).pack(pady=2)

        bar = tk.Frame(f, bg=FELT, pady=8)
        bar.pack()
        self.cr_lbl = tk.Label(bar, text="", bg=FELT, fg="white",
                               font=("Helvetica", 13, "bold"))
        self.cr_lbl.pack(side="left", padx=10)
        tk.Button(bar, text="\u2212", width=3, command=lambda: self.chg(-MIN_BET),
                  font=("Helvetica", 12, "bold"), bg="#333", fg="white",
                  bd=0).pack(side="left")
        tk.Label(bar, text="Bet:", bg=FELT, fg=GOLD,
                 font=("Helvetica", 13, "bold")).pack(side="left", padx=(6, 2))
        self.bet_var = tk.StringVar()
        self.bet_entry = tk.Entry(bar, textvariable=self.bet_var, width=6,
                                  justify="center", font=("Helvetica", 13, "bold"),
                                  bg="#0d2846", fg=GOLD, insertbackground=GOLD,
                                  relief="flat", bd=2)
        self.bet_entry.pack(side="left")
        self.bet_entry.bind("<Return>", lambda e: self.set_bet())
        self.bet_entry.bind("<FocusOut>", lambda e: self.set_bet())
        tk.Button(bar, text="+", width=3, command=lambda: self.chg(MIN_BET),
                  font=("Helvetica", 12, "bold"), bg="#333", fg="white",
                  bd=0).pack(side="left")
        self.spin_btn = tk.Button(f, text="SPIN", command=self.spin, width=16,
                                  font=("Helvetica", 15, "bold"), bg="#1b7a4b",
                                  fg="white", activebackground=GOLD, bd=0, pady=8,
                                  cursor="hand2")
        self.spin_btn.pack(pady=6)

    def draw_cell(self, col, row, sym, win=False, payline=False):
        x = GAP + col * (CELL + GAP)
        y = GAP + row * (CELL + GAP)
        bg = "#fff6d5" if payline else "white"
        outline = GOLD if win else "#22344f"
        self.canvas.create_rectangle(x, y, x + CELL, y + CELL, fill=bg,
                                     outline=outline, width=4 if win else 2)
        g, color, size = SYM[sym]
        self.canvas.create_text(x + CELL / 2, y + CELL / 2, text=g, fill=color,
                                 font=("Helvetica", size, "bold"))

    def render(self):
        self.canvas.delete("all")
        for col in range(COLS):
            for row in range(ROWS):
                sym = STRIP[(self.stops[col] + row - 1) % len(STRIP)]
                self.draw_cell(col, row, sym, win=(col, row) in self.win_cells,
                               payline=(row == 1))

    def chg(self, d):
        if self.busy:
            return
        self.bet = max(MIN_BET, min(max(self.credits, MIN_BET), self.bet + d))
        self.refresh()

    def set_bet(self):
        """Set the bet to the amount typed into the entry box.

        Reuses ``chg`` so the same clamping (and busy guard) applies; any
        invalid entry is simply ignored and the box reverts to the real bet.
        """
        try:
            self.chg(int(float(self.bet_var.get())) - self.bet)
        except (TypeError, ValueError):
            pass
        self.bet_var.set(str(self.bet))

    def refresh(self):
        wallet.set_credits(self.credits)
        self.cr_lbl.config(text=f"Credits: {self.credits}")
        self.bet_var.set(str(self.bet))

    def spin(self):
        if self.busy:
            return
        if self.credits < self.bet:
            self.msg.config(text="Not enough credits.")
            return
        self.credits -= self.bet
        self.win_cells = set()
        self.msg.config(text="")
        self.final = [random.randrange(len(STRIP)) for _ in range(COLS)]
        self.ticks = [10 + c * 6 for c in range(COLS)]
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
            self.root.after(55, self._animate)
        else:
            self._settle()

    def _settle(self):
        line = [STRIP[self.final[c]] for c in range(COLS)]
        hearts = line.count("heart")
        if line[0] == line[1] == line[2]:
            mult = PAYOUT[line[0]]
            self.win_cells = {(0, 1), (1, 1), (2, 1)}
            label = f"Three {SYM[line[0]][0]}!"
        elif hearts == 2:
            mult, label = 2, "Two hearts"
            self.win_cells = {(c, 1) for c in range(COLS) if line[c] == "heart"}
        elif hearts == 1:
            mult, label = 1, "One heart"
            self.win_cells = {(c, 1) for c in range(COLS) if line[c] == "heart"}
        else:
            mult, label = 0, None

        if mult:
            win = self.bet * mult
            self.credits += win
            self.msg.config(text=f"{label}  \u2014  WIN {win}!", fg=GOLD)
        else:
            self.msg.config(text="No win. Spin again!", fg="white")

        self.render()
        if self.credits < MIN_BET:
            self.msg.config(text="Out of credits \u2014 buy more credits to keep playing!")
            wallet.close_game(self.root)
        self.bet = min(self.bet, self.credits)
        self.refresh()
        self.busy = False
        self.spin_btn.config(state="normal")


def main():
    root = tk.Tk()
    ClassicSlot(root)
    root.mainloop()


if __name__ == "__main__":
    main()
