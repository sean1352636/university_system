"""
Fruit Machine -- 3 reels with HOLD and NUDGE features (UK-style).

Self-contained Tkinter game (standard library only).
Run with:  python fruit_machine.py

After some losing spins the machine offers a feature:
  * HOLD  -- click reels to hold them, then press SPIN for a FREE respin.
  * NUDGE -- click a reel to nudge it down one symbol; try to line up a win.
Match three on the centre line to win.
"""

import random
import tkinter as tk
try:
    import wallet  # shared credit wallet when launched as a standalone script
except ImportError:  # when imported as part of the betting-shop package
    from education_system.post_18.university_system.modules.domain.commerce.betting.gui.games import wallet

SYM = {
    "seven": ("7",   "#e63946", 44),
    "bar":   ("BAR", "#1d3557", 22),
    "bell":  ("\u25c6", "#e9c46a", 42),
    "plum":  ("\u2665", "#c1121f", 42),
    "lemon": ("\u25cf", "#f4d35e", 42),
    "cherry": ("\u2663", "#2a9d4a", 42),
}
STRIP = (["cherry"] * 6 + ["lemon"] * 5 + ["plum"] * 5 + ["bell"] * 4 +
         ["bar"] * 2 + ["seven"] * 1)
PAYOUT = {"seven": 60, "bar": 30, "bell": 16, "plum": 10, "lemon": 8, "cherry": 5}

COLS, ROWS = 3, 3
CELL, GAP = 100, 10
FELT, GOLD = "#12263a", "#e9c46a"
START_CREDITS, MIN_BET = 200, 5


class FruitMachine:
    def __init__(self, root):
        self.root = root
        root.title("Fruit Machine \u2014 Hold & Nudge")
        root.configure(bg=FELT)
        root.resizable(False, False)
        self.credits = wallet.get_credits()
        self.bet = 20
        self.stops = [0, 0, 0]
        self.held = [False, False, False]
        self.mode = "idle"        # idle | hold | nudge
        self.nudges = 0
        self.busy = False
        self.win_cells = set()
        self._build()
        self.render()
        self.refresh()

    def _build(self):
        f = tk.Frame(self.root, bg=FELT, padx=20, pady=16)
        f.pack()
        tk.Label(f, text="\u2605 FRUIT MACHINE \u2605", bg=FELT, fg=GOLD,
                 font=("Helvetica", 19, "bold")).pack()
        w = COLS * CELL + (COLS + 1) * GAP
        h = ROWS * CELL + (ROWS + 1) * GAP
        self.canvas = tk.Canvas(f, width=w, height=h, bg="#081428",
                                highlightthickness=0)
        self.canvas.pack(pady=8)
        self.canvas.bind("<Button-1>", self.on_click)
        self.hold_lbls = []
        hl = tk.Frame(f, bg=FELT)
        hl.pack()
        for _ in range(COLS):
            lb = tk.Label(hl, text="", bg=FELT, fg=GOLD, width=12,
                          font=("Helvetica", 10, "bold"))
            lb.pack(side="left", padx=4)
            self.hold_lbls.append(lb)
        self.msg = tk.Label(f, text="", bg=FELT, fg="white",
                            font=("Helvetica", 13, "bold"))
        self.msg.pack(pady=2)
        tk.Label(f, text="777=60x  BAR=30x  \u25c6=16x  \u2665=10x  "
                 "\u25cf=8x  \u2663=5x", bg=FELT, fg="#9fb3c8",
                 font=("Helvetica", 9)).pack()

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

        btns = tk.Frame(f, bg=FELT, pady=6)
        btns.pack()
        self.spin_btn = tk.Button(btns, text="SPIN", command=self.spin, width=12,
                                  font=("Helvetica", 14, "bold"), bg="#1b7a4b",
                                  fg="white", activebackground=GOLD, bd=0, pady=8,
                                  cursor="hand2")
        self.spin_btn.pack(side="left", padx=6)
        self.done_btn = tk.Button(btns, text="COLLECT", command=self.finish_nudge,
                                  width=12, font=("Helvetica", 14, "bold"),
                                  bg="#555", fg="white", activebackground=GOLD,
                                  bd=0, pady=8, cursor="hand2", state="disabled")
        self.done_btn.pack(side="left", padx=6)

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
                if self.held[col]:
                    bg = "#d8f3dc"
                outline = GOLD if win else "#22344f"
                self.canvas.create_rectangle(x, y, x + CELL, y + CELL, fill=bg,
                                             outline=outline, width=4 if win else 2)
                g, color, size = SYM[self._sym_at(col, row)]
                self.canvas.create_text(x + CELL / 2, y + CELL / 2, text=g,
                                         fill=color, font=("Helvetica", size, "bold"))
        for c in range(COLS):
            if self.mode == "hold":
                self.hold_lbls[c].config(text="HELD" if self.held[c] else "hold?")
            elif self.mode == "nudge":
                self.hold_lbls[c].config(text="nudge \u2193")
            else:
                self.hold_lbls[c].config(text="")

    def on_click(self, event):
        if self.busy:
            return
        col = int(event.x // (CELL + GAP))
        if col < 0 or col >= COLS:
            return
        if self.mode == "hold":
            self.held[col] = not self.held[col]
            self.render()
        elif self.mode == "nudge" and self.nudges > 0:
            self.stops[col] = (self.stops[col] + 1) % len(STRIP)
            self.nudges -= 1
            self.render()
            self.msg.config(text=f"Nudges left: {self.nudges}")
            if self.nudges == 0:
                self.finish_nudge()

    def chg(self, d):
        if self.busy or self.mode != "idle":
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
        free = self.mode == "hold"
        if not free:
            if self.credits < self.bet:
                self.msg.config(text="Not enough credits.")
                return
            self.credits -= self.bet
            self.held = [False, False, False]
        self.win_cells = set()
        self.mode = "idle"
        self.msg.config(text="Free respin!" if free else "")
        self.final = [self.stops[c] if self.held[c]
                      else random.randrange(len(STRIP)) for c in range(COLS)]
        self.ticks = [0 if self.held[c] else 10 + c * 6 for c in range(COLS)]
        self.busy = True
        self.spin_btn.config(state="disabled")
        self.done_btn.config(state="disabled")
        self.refresh()
        self._animate(free)

    def _animate(self, free):
        running = False
        for c in range(COLS):
            if self.ticks[c] > 0:
                self.ticks[c] -= 1
                self.stops[c] = (self.final[c] if self.ticks[c] == 0
                                 else random.randrange(len(STRIP)))
                running = True
        self.render()
        if running:
            self.root.after(55, self._animate, free)
        else:
            self._settle(free)

    def _payline_win(self):
        line = [self._sym_at(c, 1) for c in range(COLS)]
        if line[0] == line[1] == line[2]:
            return PAYOUT[line[0]], line[0]
        if line.count("cherry") == 2:
            return 2, "cherry2"
        if line.count("cherry") == 1:
            return 1, "cherry1"
        return 0, None

    def _settle(self, free):
        mult, what = self._payline_win()
        if mult:
            win = self.bet * mult
            self.credits += win
            self.win_cells = {(c, 1) for c in range(COLS)}
            self.msg.config(text=f"WIN {win}!", fg=GOLD)
            self._end_turn()
            return
        # no win -> maybe a feature (only after a paid spin, not a free respin)
        r = random.random()
        if not free and r < 0.30:
            self.mode = "hold"
            self.msg.config(text="HOLD offered! Click reels to hold, then SPIN.",
                            fg=GOLD)
            self.render()
            self._enable_idle_controls()
        elif not free and r < 0.48:
            self.mode = "nudge"
            self.nudges = random.randint(1, 3)
            self.msg.config(text=f"{self.nudges} NUDGES! Click a reel to nudge.",
                            fg=GOLD)
            self.render()
            self.busy = False
            self.done_btn.config(state="normal")
        else:
            self.msg.config(text="No win. Spin again!", fg="white")
            self._end_turn()

    def finish_nudge(self):
        if self.mode != "nudge":
            return
        self.mode = "idle"
        self.nudges = 0
        mult, what = self._payline_win()
        if mult:
            win = self.bet * mult
            self.credits += win
            self.win_cells = {(c, 1) for c in range(COLS)}
            self.msg.config(text=f"Nudge WIN {win}!", fg=GOLD)
        else:
            self.msg.config(text="No win from nudges.", fg="white")
        self._end_turn()

    def _enable_idle_controls(self):
        self.busy = False
        self.spin_btn.config(state="normal")

    def _end_turn(self):
        self.render()
        if self.credits < MIN_BET:
            self.msg.config(text="Out of credits \u2014 buy more credits!")
            wallet.close_game(self.root)
        self.bet = min(self.bet, self.credits)
        self.refresh()
        self.busy = False
        self.mode = "idle"
        self.spin_btn.config(state="normal")
        self.done_btn.config(state="disabled")


def main():
    root = tk.Tk()
    FruitMachine(root)
    root.mainloop()


if __name__ == "__main__":
    main()
