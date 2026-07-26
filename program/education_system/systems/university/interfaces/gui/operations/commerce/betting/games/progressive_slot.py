"""
Progressive Jackpot Slot -- 3 reels, single payline, growing jackpot.

Self-contained Tkinter game (standard library only).
Run with:  python progressive_slot.py

Every spin feeds a small slice of your bet into the JACKPOT meter. Land three
\u2605 stars on the centre line to win the whole jackpot, which then reseeds.
Other combos pay normal fixed multiples of your bet.
"""

import random
import tkinter as tk
try:
    import wallet  # shared credit wallet when launched as a standalone script
except ImportError:  # when imported as part of the betting-shop package
    from education_system.systems.university.interfaces.gui.operations.commerce.betting.games import wallet

SYM = {
    "jackpot": ("\u2605", "#e9c46a", 46),   # the progressive symbol
    "seven":   ("7",   "#e63946", 44),
    "bar":     ("BAR", "#1d3557", 22),
    "bell":    ("\u25c6", "#2aa9c9", 42),
    "heart":   ("\u2665", "#e63946", 42),
    "club":    ("\u2663", "#2a9d4a", 42),
}
STRIP = (["club"] * 7 + ["heart"] * 6 + ["bell"] * 5 + ["bar"] * 3 +
         ["seven"] * 2 + ["jackpot"] * 1)
PAYOUT = {"seven": 50, "bar": 25, "bell": 14, "heart": 8, "club": 5}
JACKPOT_SEED = 1000
CONTRIB = 0.05          # 5% of each bet feeds the jackpot

COLS, ROWS = 3, 3
CELL, GAP = 100, 10
FELT, GOLD = "#1a1030", "#e9c46a"
START_CREDITS, MIN_BET = 200, 5


class ProgressiveSlot:
    def __init__(self, root):
        self.root = root
        root.title("Progressive Jackpot Slot")
        root.configure(bg=FELT)
        root.resizable(False, False)
        self.credits = wallet.get_credits()
        self.bet = 25
        self.jackpot = JACKPOT_SEED
        self.jackpot_shown = JACKPOT_SEED
        self.stops = [0, 0, 0]
        self.win_cells = set()
        self.busy = False
        self._build()
        self.render()
        self.refresh()
        self._animate_jackpot()

    def _build(self):
        f = tk.Frame(self.root, bg=FELT, padx=20, pady=14)
        f.pack()
        self.jp_lbl = tk.Label(f, text="", bg="#2a1650", fg=GOLD,
                               font=("Helvetica", 24, "bold"), padx=20, pady=6)
        self.jp_lbl.pack(fill="x", pady=(0, 8))
        tk.Label(f, text="Land \u2605 \u2605 \u2605 to win the JACKPOT",
                 bg=FELT, fg="#cbb6ff", font=("Helvetica", 11, "bold")).pack()
        w = COLS * CELL + (COLS + 1) * GAP
        h = ROWS * CELL + (ROWS + 1) * GAP
        self.canvas = tk.Canvas(f, width=w, height=h, bg="#0e0820",
                                highlightthickness=0)
        self.canvas.pack(pady=8)
        self.msg = tk.Label(f, text="", bg=FELT, fg="white",
                            font=("Helvetica", 13, "bold"))
        self.msg.pack()
        tk.Label(f, text="777=50x  BAR=25x  \u25c6=14x  \u2665=8x  \u2663=5x",
                 bg=FELT, fg="#9f8fc8", font=("Helvetica", 9)).pack(pady=2)

        bar = tk.Frame(f, bg=FELT, pady=8)
        bar.pack()
        self.cr_lbl = tk.Label(bar, text="", bg=FELT, fg="white",
                               font=("Helvetica", 13, "bold"))
        self.cr_lbl.pack(side="left", padx=8)
        tk.Button(bar, text="\u2212", width=3, command=lambda: self.chg(-MIN_BET),
                  font=("Helvetica", 11, "bold"), bg="#333", fg="white",
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
                  font=("Helvetica", 11, "bold"), bg="#333", fg="white",
                  bd=0).pack(side="left")
        self.spin_btn = tk.Button(f, text="SPIN", command=self.spin, width=16,
                                  font=("Helvetica", 14, "bold"), bg="#7b2cbf",
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
                win = (col, row) in self.win_cells
                bg = "#fff6d5" if row == 1 else "white"
                outline = GOLD if win else "#3a2a5a"
                self.canvas.create_rectangle(x, y, x + CELL, y + CELL, fill=bg,
                                             outline=outline, width=4 if win else 2)
                g, color, size = SYM[self._sym_at(col, row)]
                self.canvas.create_text(x + CELL / 2, y + CELL / 2, text=g,
                                         fill=color, font=("Helvetica", size, "bold"))

    def _animate_jackpot(self):
        if self.jackpot_shown < self.jackpot:
            step = max(1, (self.jackpot - self.jackpot_shown) // 8)
            self.jackpot_shown = min(self.jackpot, self.jackpot_shown + step)
        elif self.jackpot_shown > self.jackpot:
            self.jackpot_shown = self.jackpot
        self.jp_lbl.config(text=f"JACKPOT   {self.jackpot_shown:,}")
        self.root.after(60, self._animate_jackpot)

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
        self.jackpot += int(self.bet * CONTRIB)
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
        if line[0] == line[1] == line[2] == "jackpot":
            win = self.jackpot
            self.credits += win
            self.win_cells = {(c, 1) for c in range(COLS)}
            self.msg.config(text=f"\u2605 JACKPOT! You win {win:,}! \u2605", fg=GOLD)
            self.jackpot = JACKPOT_SEED
        elif line[0] == line[1] == line[2] and line[0] in PAYOUT:
            win = self.bet * PAYOUT[line[0]]
            self.credits += win
            self.win_cells = {(c, 1) for c in range(COLS)}
            self.msg.config(text=f"Three {SYM[line[0]][0]}  \u2014  WIN {win}!",
                            fg=GOLD)
        elif line.count("jackpot") == 2:
            win = self.bet * 5
            self.credits += win
            self.win_cells = {(c, 1) for c in range(COLS) if line[c] == "jackpot"}
            self.msg.config(text=f"Two \u2605  \u2014  WIN {win}!", fg=GOLD)
        else:
            self.msg.config(text="No win. Spin again!", fg="white")
        self.render()
        if self.credits < MIN_BET:
            self.msg.config(text="Out of credits \u2014 buy more credits!")
            wallet.close_game(self.root)
        self.bet = min(self.bet, self.credits)
        self.refresh()
        self.busy = False
        self.spin_btn.config(state="normal")


def main():
    root = tk.Tk()
    ProgressiveSlot(root)
    root.mainloop()


if __name__ == "__main__":
    main()
