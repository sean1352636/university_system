"""
Keno -- lottery-style casino game.

Self-contained Tkinter game (standard library only).
Run with:  python keno.py

Pick up to 10 numbers from 1-80. The game draws 20. Your payout depends on
how many of your picks are drawn ("catches") and how many spots you played.
"""

import random
import tkinter as tk
try:
    import wallet  # shared credit wallet when launched as a standalone script
except ImportError:  # when imported as part of the betting-shop package
    from education_system.post_18.university_system.modules.domain.commerce.betting.gui.games import wallet

# PAYTABLE[spots][catches] = winnings multiplier applied to the bet
PAYTABLE = {
    1:  {1: 3},
    2:  {2: 12},
    3:  {2: 1, 3: 42},
    4:  {2: 1, 3: 4, 4: 120},
    5:  {3: 2, 4: 20, 5: 480},
    6:  {3: 1, 4: 4, 5: 70, 6: 1600},
    7:  {4: 2, 5: 20, 6: 350, 7: 8000},
    8:  {5: 10, 6: 80, 7: 1000, 8: 10000},
    9:  {5: 5, 6: 40, 7: 300, 8: 4000, 9: 20000},
    10: {5: 2, 6: 20, 7: 80, 8: 500, 9: 4000, 10: 50000},
}
MAX_SPOTS = 10
COLS, ROWS = 10, 8
CELL = 50
FELT, GOLD = "#0b1e3a", "#e9c46a"
START_CREDITS, MIN_BET = 200, 5


def payout_multiplier(spots, catches):
    return PAYTABLE.get(spots, {}).get(catches, 0)


class Keno:
    def __init__(self, root):
        self.root = root
        root.title("Keno")
        root.configure(bg=FELT)
        root.resizable(False, False)
        self.credits = wallet.get_credits()
        self.bet = 10
        self.selected = set()
        self.drawn = []
        self.revealed = 0
        self.busy = False
        self._build()
        self.repaint()
        self.refresh()

    def _build(self):
        f = tk.Frame(self.root, bg=FELT, padx=18, pady=12)
        f.pack()
        tk.Label(f, text="K E N O", bg=FELT, fg=GOLD,
                 font=("Helvetica", 22, "bold")).pack()
        self.msg = tk.Label(f, text="Pick up to 10 numbers, then Play.",
                            bg=FELT, fg="white", font=("Helvetica", 12, "bold"))
        self.msg.pack(pady=2)

        self.canvas = tk.Canvas(f, width=COLS * CELL, height=ROWS * CELL,
                                bg="#081428", highlightthickness=0)
        self.canvas.pack(pady=8)
        self.canvas.bind("<Button-1>", self.on_click)

        self.pick_lbl = tk.Label(f, text="", bg=FELT, fg="#9fb3c8",
                                 font=("Helvetica", 10))
        self.pick_lbl.pack()

        ctl = tk.Frame(f, bg=FELT, pady=6)
        ctl.pack()
        tk.Button(ctl, text="Quick Pick", command=self.quick_pick, width=10,
                  font=("Helvetica", 11, "bold"), bg="#3a5a8a", fg="white",
                  bd=0, cursor="hand2").pack(side="left", padx=4)
        tk.Button(ctl, text="Clear", command=self.clear, width=8,
                  font=("Helvetica", 11, "bold"), bg="#555", fg="white",
                  bd=0, cursor="hand2").pack(side="left", padx=4)

        bar = tk.Frame(f, bg=FELT, pady=6)
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
        self.play_btn = tk.Button(f, text="PLAY", command=self.play, width=16,
                                  font=("Helvetica", 14, "bold"), bg="#1b7a4b",
                                  fg="white", activebackground=GOLD, bd=0, pady=8,
                                  cursor="hand2")
        self.play_btn.pack(pady=6)

    def on_click(self, e):
        if self.busy:
            return
        col, row = int(e.x // CELL), int(e.y // CELL)
        if not (0 <= col < COLS and 0 <= row < ROWS):
            return
        num = row * COLS + col + 1
        if num in self.selected:
            self.selected.remove(num)
        elif len(self.selected) < MAX_SPOTS:
            self.selected.add(num)
        else:
            self.msg.config(text=f"Max {MAX_SPOTS} numbers.")
            return
        self.repaint()
        self.update_picklabel()

    def quick_pick(self):
        if self.busy:
            return
        self.selected = set(random.sample(range(1, 81), MAX_SPOTS))
        self.repaint()
        self.update_picklabel()

    def clear(self):
        if self.busy:
            return
        self.selected = set()
        self.drawn = []
        self.revealed = 0
        self.repaint()
        self.update_picklabel()
        self.msg.config(text="Pick up to 10 numbers, then Play.")

    def update_picklabel(self):
        n = len(self.selected)
        if n and n in PAYTABLE:
            tiers = "   ".join(f"{c}\u2192{m}x" for c, m in
                               sorted(PAYTABLE[n].items()))
            self.pick_lbl.config(text=f"{n} spots \u2014 catch: {tiers}")
        else:
            self.pick_lbl.config(text=f"{n} spots selected")

    def repaint(self):
        c = self.canvas
        c.delete("all")
        drawn_set = set(self.drawn[:self.revealed])
        for row in range(ROWS):
            for col in range(COLS):
                num = row * COLS + col + 1
                x, y = col * CELL, row * CELL
                sel = num in self.selected
                hit = num in drawn_set
                if sel and hit:
                    fill, fg = "#2a9d4a", "white"      # caught
                elif hit:
                    fill, fg = GOLD, "#222"            # drawn, not picked
                elif sel:
                    fill, fg = "#2a6fb0", "white"      # picked
                else:
                    fill, fg = "#12294a", "#8fa6c4"
                c.create_rectangle(x + 2, y + 2, x + CELL - 2, y + CELL - 2,
                                   fill=fill, outline="#22344f")
                c.create_text(x + CELL / 2, y + CELL / 2, text=str(num), fill=fg,
                              font=("Helvetica", 13, "bold"))

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

    def play(self):
        if self.busy:
            return
        if not self.selected:
            self.msg.config(text="Pick at least one number.")
            return
        if self.credits < self.bet:
            self.msg.config(text="Not enough credits.")
            return
        self.credits -= self.bet
        self.drawn = random.sample(range(1, 81), 20)
        self.revealed = 0
        self.busy = True
        self.play_btn.config(state="disabled")
        self.msg.config(text="Drawing...", fg="white")
        self.refresh()
        self._reveal()

    def _reveal(self):
        if self.revealed < len(self.drawn):
            self.revealed += 1
            self.repaint()
            self.root.after(120, self._reveal)
        else:
            self._settle()

    def _settle(self):
        catches = len(self.selected & set(self.drawn))
        mult = payout_multiplier(len(self.selected), catches)
        win = self.bet * mult
        if win:
            self.credits += win
            self.msg.config(text=f"{catches} catches \u2014 WIN {win}!", fg=GOLD)
        else:
            self.msg.config(text=f"{catches} catches \u2014 no win.", fg="white")
        if self.credits < MIN_BET:
            self.msg.config(text="Out of credits \u2014 buy more credits!")
            wallet.close_game(self.root)
        self.bet = min(self.bet, self.credits)
        self.refresh()
        self.busy = False
        self.play_btn.config(state="normal")


def main():
    root = tk.Tk()
    Keno(root)
    root.mainloop()


if __name__ == "__main__":
    main()
