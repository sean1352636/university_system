"""
Wheel Bonus Slot -- 3 reels, single payline, with a spinning BONUS WHEEL.

Self-contained Tkinter game (standard library only).
Run with:  python wheel_bonus_slot.py

Match three on the centre line for normal wins. Land three B (bonus) symbols
to launch the wheel, which spins and lands on a multiplier of your bet.
"""

import math
import random
import tkinter as tk
try:
    import wallet  # shared credit wallet when launched as a standalone script
except ImportError:  # when imported as part of the betting-shop package
    from education_system.systems.university.interfaces.gui.operations.commerce.betting.games import wallet

SYM = {
    "bonus": ("B", "#ff006e", 40),   # triggers the wheel
    "seven": ("7", "#e63946", 44),
    "star":  ("\u2605", "#e9c46a", 42),
    "bell":  ("\u25c6", "#2aa9c9", 42),
    "heart": ("\u2665", "#e63946", 42),
    "club":  ("\u2663", "#2a9d4a", 42),
}
STRIP = (["club"] * 7 + ["heart"] * 6 + ["bell"] * 5 + ["star"] * 3 +
         ["seven"] * 2 + ["bonus"] * 1)
PAYOUT = {"seven": 50, "star": 25, "bell": 14, "heart": 8, "club": 5}
WHEEL_PRIZES = [2, 5, 3, 8, 4, 10, 6, 25]     # multipliers of the bet
WHEEL_COLORS = ["#e76f51", "#2a9d8f", "#e9c46a", "#264653",
                "#f4a261", "#457b9d", "#e5989b", "#7b2cbf"]

COLS, ROWS = 3, 3
CELL, GAP = 100, 10
WHEEL_R = 120
FELT, GOLD = "#10233a", "#e9c46a"
START_CREDITS, MIN_BET = 200, 5


class WheelBonusSlot:
    def __init__(self, root):
        self.root = root
        root.title("Wheel Bonus Slot")
        root.configure(bg=FELT)
        root.resizable(False, False)
        self.credits = wallet.get_credits()
        self.bet = 25
        self.stops = [0, 0, 0]
        self.win_cells = set()
        self.busy = False
        self.wheel_offset = 0.0
        self._build()
        self.render()
        self.draw_wheel()
        self.refresh()

    def _build(self):
        f = tk.Frame(self.root, bg=FELT, padx=20, pady=14)
        f.pack()
        tk.Label(f, text="\u2605 WHEEL BONUS \u2605", bg=FELT, fg=GOLD,
                 font=("Helvetica", 19, "bold")).pack()
        body = tk.Frame(f, bg=FELT)
        body.pack()

        left = tk.Frame(body, bg=FELT)
        left.pack(side="left", padx=8)
        w = COLS * CELL + (COLS + 1) * GAP
        h = ROWS * CELL + (ROWS + 1) * GAP
        self.canvas = tk.Canvas(left, width=w, height=h, bg="#081428",
                                highlightthickness=0)
        self.canvas.pack()

        right = tk.Frame(body, bg=FELT)
        right.pack(side="left", padx=8)
        self.wheel = tk.Canvas(right, width=WHEEL_R * 2 + 20,
                               height=WHEEL_R * 2 + 20, bg=FELT,
                               highlightthickness=0)
        self.wheel.pack()

        self.msg = tk.Label(f, text="Land 3 B to spin the wheel!", bg=FELT,
                            fg="white", font=("Helvetica", 13, "bold"))
        self.msg.pack(pady=4)
        tk.Label(f, text="777=50x  \u2605=25x  \u25c6=14x  \u2665=8x  \u2663=5x",
                 bg=FELT, fg="#9fb3c8", font=("Helvetica", 9)).pack()

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
                                  font=("Helvetica", 14, "bold"), bg="#1b7a4b",
                                  fg="white", activebackground=GOLD, bd=0, pady=8,
                                  cursor="hand2")
        self.spin_btn.pack(pady=6)

    # ---- reels -----------------------------------------------------------
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
                outline = GOLD if win else "#22344f"
                self.canvas.create_rectangle(x, y, x + CELL, y + CELL, fill=bg,
                                             outline=outline, width=4 if win else 2)
                g, color, size = SYM[self._sym_at(col, row)]
                self.canvas.create_text(x + CELL / 2, y + CELL / 2, text=g,
                                         fill=color, font=("Helvetica", size, "bold"))

    # ---- wheel -----------------------------------------------------------
    def draw_wheel(self, highlight=None):
        c = self.wheel
        c.delete("all")
        cx = cy = WHEEL_R + 10
        n = len(WHEEL_PRIZES)
        seg = 360 / n
        for i, mult in enumerate(WHEEL_PRIZES):
            start = i * seg + self.wheel_offset
            c.create_arc(cx - WHEEL_R, cy - WHEEL_R, cx + WHEEL_R, cy + WHEEL_R,
                         start=start, extent=seg, fill=WHEEL_COLORS[i % len(WHEEL_COLORS)],
                         outline="#fff", width=2, style="pieslice")
            mid = math.radians(start + seg / 2)
            tx = cx + math.cos(mid) * WHEEL_R * 0.62
            ty = cy - math.sin(mid) * WHEEL_R * 0.62
            c.create_text(tx, ty, text=f"x{mult}", fill="white",
                          font=("Helvetica", 13, "bold"))
        c.create_oval(cx - 18, cy - 18, cx + 18, cy + 18, fill="#222", outline=GOLD,
                      width=2)
        # pointer at top pointing down
        c.create_polygon(cx - 12, 6, cx + 12, 6, cx, 30, fill=GOLD, outline="#222")

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

    # ---- spin ------------------------------------------------------------
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
        if line[0] == line[1] == line[2] == "bonus":
            self.win_cells = {(c, 1) for c in range(COLS)}
            self.render()
            self.msg.config(text="BONUS! Spinning the wheel...", fg=GOLD)
            self._spin_wheel()
            return
        if line[0] == line[1] == line[2] and line[0] in PAYOUT:
            win = self.bet * PAYOUT[line[0]]
            self.credits += win
            self.win_cells = {(c, 1) for c in range(COLS)}
            self.msg.config(text=f"Three {SYM[line[0]][0]}  \u2014  WIN {win}!",
                            fg=GOLD)
        else:
            self.msg.config(text="No win. Spin again!", fg="white")
        self.render()
        self._finish()

    # ---- bonus wheel spin ------------------------------------------------
    def _spin_wheel(self):
        n = len(WHEEL_PRIZES)
        seg = 360 / n
        target = random.randrange(n)
        # offset that puts target's centre under the top pointer (90 degrees)
        base = (90 - (target * seg + seg / 2)) % 360
        self._wheel_final = base + 360 * 4      # extra full turns
        self._wheel_target = target
        self._wheel_frame = 0
        self._wheel_frames = 48
        self._animate_wheel()

    def _animate_wheel(self):
        t = self._wheel_frame / self._wheel_frames
        ease = 1 - (1 - t) ** 3                  # ease-out
        self.wheel_offset = self._wheel_final * ease
        self.draw_wheel()
        if self._wheel_frame < self._wheel_frames:
            self._wheel_frame += 1
            self.root.after(35, self._animate_wheel)
        else:
            self.wheel_offset %= 360
            self.draw_wheel()
            mult = WHEEL_PRIZES[self._wheel_target]
            win = self.bet * mult
            self.credits += win
            self.msg.config(text=f"Wheel landed on x{mult}  \u2014  WIN {win}!",
                            fg=GOLD)
            self._finish()

    def _finish(self):
        if self.credits < MIN_BET:
            self.msg.config(text="Out of credits \u2014 buy more credits!")
            wallet.close_game(self.root)
        self.bet = min(self.bet, self.credits)
        self.refresh()
        self.busy = False
        self.spin_btn.config(state="normal")


def main():
    root = tk.Tk()
    WheelBonusSlot(root)
    root.mainloop()


if __name__ == "__main__":
    main()
