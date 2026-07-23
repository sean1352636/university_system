"""
Space Slot -- 5 reels x 3 rows, 243 WAYS to win, WILD + SCATTER free spins.

Self-contained Tkinter game (standard library only).
Run with:  python space_slot.py

There are no fixed lines: any symbol that lands on consecutive reels from the
left (in any row) pays "ways" = the product of how many land on each reel.
  W  = WILD, substitutes for any paying symbol.
  S  = SCATTER: 3+ anywhere award free spins (wins pay double during them).
Bet is in steps of 10.
"""

import random
import tkinter as tk
try:
    import wallet  # shared credit wallet when launched as a standalone script
except ImportError:  # when imported as part of the betting-shop package
    from education_system.post_18.university_system.modules.domain.commerce.betting.gui.games import wallet

SYM = {
    "wild":    ("W", "#c77dff", 34),
    "scatter": ("S", "#48cae4", 34),
    "star":    ("\u2605", "#ffd60a", 40),
    "rocket":  ("\u25b2", "#ff7b00", 38),
    "planet":  ("\u25cf", "#4cc9f0", 38),
    "crystal": ("\u25c6", "#90e0ef", 38),
}
STRIP = (["crystal"] * 8 + ["planet"] * 7 + ["rocket"] * 5 + ["star"] * 3 +
         ["wild"] * 2 + ["scatter"] * 2)
PAYTABLE = {   # per unit (unit = bet / 10), multiplied by ways
    "star":    {3: 5, 4: 20, 5: 100},
    "rocket":  {3: 3, 4: 12, 5: 50},
    "planet":  {3: 2, 4: 8, 5: 30},
    "crystal": {3: 1, 4: 5, 5: 20},
}
FREE_SPINS = {3: 8, 4: 12, 5: 20}

COLS, ROWS = 5, 3
CELL, GAP = 88, 8
FELT, GOLD = "#050b1a", "#ffd60a"
START_CREDITS = 300


def evaluate_ways(grid, unit):
    """grid[row][col]. Returns (total_win, win_cells set, scatter_count)."""
    total = 0
    cells = set()
    scatter = sum(grid[r][c] == "scatter" for r in range(ROWS) for c in range(COLS))
    for base, table in PAYTABLE.items():
        counts = []
        for c in range(COLS):
            n = sum(1 for r in range(ROWS) if grid[r][c] in (base, "wild"))
            counts.append(n)
        run = 0
        for c in range(COLS):
            if counts[c] > 0:
                run += 1
            else:
                break
        if run >= 3:
            ways = 1
            for c in range(run):
                ways *= counts[c]
            total += table[run] * ways * unit
            for c in range(run):
                for r in range(ROWS):
                    if grid[r][c] in (base, "wild"):
                        cells.add((c, r))
    return total, cells, scatter


class SpaceSlot:
    def __init__(self, root):
        self.root = root
        root.title("Space Slot \u2014 243 Ways")
        root.configure(bg=FELT)
        root.resizable(False, False)
        self.credits = wallet.get_credits()
        self.bet = 20
        self.stops = [0] * COLS
        self.win_cells = set()
        self.free_spins = 0
        self.busy = False
        self._build()
        self.render()
        self.refresh()

    def _build(self):
        f = tk.Frame(self.root, bg=FELT, padx=18, pady=14)
        f.pack()
        tk.Label(f, text="\u2726 SPACE SLOT \u2726", bg=FELT, fg=GOLD,
                 font=("Helvetica", 20, "bold")).pack()
        self.free_lbl = tk.Label(f, text="", bg=FELT, fg="#48cae4",
                                 font=("Helvetica", 12, "bold"))
        self.free_lbl.pack()
        w = COLS * CELL + (COLS + 1) * GAP
        h = ROWS * CELL + (ROWS + 1) * GAP
        self.canvas = tk.Canvas(f, width=w, height=h, bg="#020617",
                                highlightthickness=0)
        self.canvas.pack(pady=8)
        self.msg = tk.Label(f, text="", bg=FELT, fg="white",
                            font=("Helvetica", 12, "bold"))
        self.msg.pack()
        tk.Label(f, text="\u2605 rocket planet \u25c6  pay 3+ from left \u2014 "
                 "more symbols = more ways.  W wild  \u2022  S scatter = free spins",
                 bg=FELT, fg="#7f9cc0", font=("Helvetica", 9)).pack(pady=2)

        bar = tk.Frame(f, bg=FELT, pady=8)
        bar.pack()
        self.cr_lbl = tk.Label(bar, text="", bg=FELT, fg="white",
                               font=("Helvetica", 12, "bold"))
        self.cr_lbl.pack(side="left", padx=8)
        tk.Button(bar, text="\u2212", width=3, command=lambda: self.chg(-10),
                  font=("Helvetica", 11, "bold"), bg="#333", fg="white",
                  bd=0).pack(side="left")
        tk.Label(bar, text="Bet:", bg=FELT, fg=GOLD,
                 font=("Helvetica", 12, "bold")).pack(side="left", padx=(6, 2))
        self.bet_var = tk.StringVar()
        self.bet_entry = tk.Entry(bar, textvariable=self.bet_var, width=6,
                                  justify="center", font=("Helvetica", 12, "bold"),
                                  bg="#0d2846", fg=GOLD, insertbackground=GOLD,
                                  relief="flat", bd=2)
        self.bet_entry.pack(side="left")
        self.bet_entry.bind("<Return>", lambda e: self.set_bet())
        self.bet_entry.bind("<FocusOut>", lambda e: self.set_bet())
        tk.Button(bar, text="+", width=3, command=lambda: self.chg(10),
                  font=("Helvetica", 11, "bold"), bg="#333", fg="white",
                  bd=0).pack(side="left")
        self.spin_btn = tk.Button(f, text="SPIN", command=self.spin, width=16,
                                  font=("Helvetica", 14, "bold"), bg="#3a0ca3",
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
                outline = GOLD if win else "#16233d"
                self.canvas.create_rectangle(x, y, x + CELL, y + CELL,
                                             fill="#0b1220" if not win else "#1c2a12",
                                             outline=outline, width=4 if win else 2)
                g, color, size = SYM[self._sym_at(col, row)]
                self.canvas.create_text(x + CELL / 2, y + CELL / 2, text=g,
                                         fill=color, font=("Helvetica", size, "bold"))

    def chg(self, d):
        if self.busy or self.free_spins > 0:
            return
        self.bet = max(10, min(max(self.credits, 10), self.bet + d))
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
        if self.free_spins > 0:
            self.free_lbl.config(text=f"FREE SPINS: {self.free_spins}  (wins x2)")
        else:
            self.free_lbl.config(text="")

    def spin(self):
        if self.busy:
            return
        free = self.free_spins > 0
        if not free:
            if self.credits < self.bet:
                self.msg.config(text="Not enough credits.")
                return
            self.credits -= self.bet
        else:
            self.free_spins -= 1
        self.win_cells = set()
        self.msg.config(text="")
        self.final = [random.randrange(len(STRIP)) for _ in range(COLS)]
        self.ticks = [12 + c * 5 for c in range(COLS)]
        self.busy = True
        self.spin_btn.config(state="disabled")
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
            self.root.after(50, self._animate, free)
        else:
            self._settle(free)

    def _settle(self, free):
        grid = [[STRIP[(self.final[c] + r - 1) % len(STRIP)] for c in range(COLS)]
                for r in range(ROWS)]
        unit = self.bet // 10
        win, cells, scatter = evaluate_ways(grid, unit)
        if free:
            win *= 2
        self.win_cells = cells
        parts = []
        if win:
            self.credits += win
            parts.append(f"WIN {win}!")
        if scatter >= 3:
            add = FREE_SPINS.get(scatter, 20)
            self.free_spins += add
            parts.append(f"{scatter} scatters \u2014 +{add} free spins!")
            for r in range(ROWS):
                for c in range(COLS):
                    if grid[r][c] == "scatter":
                        self.win_cells.add((c, r))
        self.msg.config(text="   ".join(parts) if parts else "No win. Spin again!",
                        fg=GOLD if parts else "white")
        self.render()
        if self.credits < 10 and self.free_spins == 0:
            self.msg.config(text="Out of credits \u2014 buy more credits!")
            wallet.close_game(self.root)
        self.bet = min(self.bet, max(10, self.credits))
        self.refresh()
        self.busy = False
        self.spin_btn.config(state="normal")
        if self.free_spins > 0:
            self.spin_btn.config(text="FREE SPIN")
        else:
            self.spin_btn.config(text="SPIN")


def main():
    root = tk.Tk()
    SpaceSlot(root)
    root.mainloop()


if __name__ == "__main__":
    main()
