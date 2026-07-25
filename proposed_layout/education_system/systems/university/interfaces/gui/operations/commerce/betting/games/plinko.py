"""
Plinko -- arcade-style drop machine.

Self-contained Tkinter game (standard library only).
Run with:  python plinko.py

Set a stake and drop the ball. It bounces down through the pegs and lands in a
slot with a payout multiplier. The middle slots are common and pay little; the
edges are rare and pay big.
"""

import random
import tkinter as tk
try:
    import wallet  # shared credit wallet when launched as a standalone script
except ImportError:  # when imported as part of the betting-shop package
    from education_system.systems.university.interfaces.gui.operations.commerce.betting.games import wallet

ROWS = 12
SLOTS = ROWS + 1                      # 13 slots
# symmetric payout multipliers (index 0..12), tuned to ~94% RTP
MULTS = [15, 5, 2, 1.3, 1.1, 0.9, 0.4, 0.9, 1.1, 1.3, 2, 5, 15]

CWp = 42
TOP = 40
ROW_H = 26
BALL_R = 7
FELT, GOLD = "#0a1226", "#e9c46a"
START_CREDITS, MIN_BET = 200, 5


def slot_color(m):
    if m >= 4:
        return "#e63946"
    if m >= 1.2:
        return "#e9c46a"
    if m >= 1.0:
        return "#2a9d8f"
    return "#3a5a8a"


class Plinko:
    def __init__(self, root):
        self.root = root
        root.title("Plinko")
        root.configure(bg=FELT)
        root.resizable(False, False)
        self.credits = wallet.get_credits()
        self.bet = 20
        self.busy = False
        self.width = CWp * SLOTS
        self.slot_h = 34
        self.height = TOP + ROWS * ROW_H + self.slot_h + 10
        self._build()
        self.draw_board()
        self.refresh()

    def _build(self):
        f = tk.Frame(self.root, bg=FELT, padx=18, pady=12)
        f.pack()
        tk.Label(f, text="P L I N K O", bg=FELT, fg=GOLD,
                 font=("Helvetica", 22, "bold")).pack()
        self.canvas = tk.Canvas(f, width=self.width, height=self.height,
                                bg="#060a18", highlightthickness=0)
        self.canvas.pack(pady=8)
        self.msg = tk.Label(f, text="Set a stake and drop!", bg=FELT, fg="white",
                            font=("Helvetica", 12, "bold"))
        self.msg.pack()

        bar = tk.Frame(f, bg=FELT, pady=8)
        bar.pack()
        self.cr_lbl = tk.Label(bar, text="", bg=FELT, fg="white",
                               font=("Helvetica", 13, "bold"))
        self.cr_lbl.pack(side="left", padx=8)
        tk.Button(bar, text="\u2212", width=3, command=lambda: self.chg(-MIN_BET),
                  font=("Helvetica", 11, "bold"), bg="#333", fg="white",
                  bd=0).pack(side="left")
        tk.Label(bar, text="Stake:", bg=FELT, fg=GOLD,
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
        self.drop_btn = tk.Button(f, text="DROP", command=self.drop, width=16,
                                  font=("Helvetica", 14, "bold"), bg="#1b7a4b",
                                  fg="white", activebackground=GOLD, bd=0, pady=8,
                                  cursor="hand2")
        self.drop_btn.pack(pady=6)

    def draw_board(self, ball=None, landed=None):
        c = self.canvas
        c.delete("all")
        # pegs
        for r in range(ROWS):
            y = TOP + r * ROW_H
            offset = 0.5 if r % 2 else 0.0
            n = SLOTS if r % 2 else SLOTS + 1
            for i in range(n):
                x = (i + offset) * CWp
                if 0 <= x <= self.width:
                    c.create_oval(x - 2, y - 2, x + 2, y + 2, fill="#5a6b95",
                                  outline="")
        # slots
        y0 = TOP + ROWS * ROW_H
        for i in range(SLOTS):
            x = i * CWp
            hot = landed == i
            c.create_rectangle(x + 2, y0, x + CWp - 2, y0 + self.slot_h,
                               fill=slot_color(MULTS[i]),
                               outline=GOLD if hot else "#222",
                               width=3 if hot else 1)
            m = MULTS[i]
            txt = f"{m:g}x"
            c.create_text(x + CWp / 2, y0 + self.slot_h / 2, text=txt,
                          fill="#111", font=("Helvetica", 9, "bold"))
        # ball
        if ball is not None:
            bx, by = ball
            c.create_oval(bx - BALL_R, by - BALL_R, bx + BALL_R, by + BALL_R,
                          fill=GOLD, outline="#fff", width=2)

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

    def drop(self):
        if self.busy:
            return
        if self.credits < self.bet:
            self.msg.config(text="Not enough credits.")
            return
        self.credits -= self.bet
        self.busy = True
        self.drop_btn.config(state="disabled")
        self.msg.config(text="Dropping...", fg="white")
        self.refresh()

        # decide the path: ROWS left/right moves; slot = number of rights
        self.moves = [random.choice((0, 1)) for _ in range(ROWS)]
        self.slot = sum(self.moves)
        # build the pixel path
        x = self.width / 2
        self.path = [(x, TOP - ROW_H)]
        for r in range(ROWS):
            x += (0.5 if self.moves[r] else -0.5) * CWp
            self.path.append((x, TOP + r * ROW_H))
        # final settle into slot centre
        self.path.append(((self.slot + 0.5) * CWp, TOP + ROWS * ROW_H - 4))
        self._step = 0
        self._animate()

    def _animate(self):
        if self._step < len(self.path):
            self.draw_board(ball=self.path[self._step])
            self._step += 1
            self.root.after(70, self._animate)
        else:
            self._settle()

    def _settle(self):
        mult = MULTS[self.slot]
        win = int(round(self.bet * mult))
        self.credits += win
        self.draw_board(ball=self.path[-1], landed=self.slot)
        net = win - self.bet
        self.msg.config(text=f"Landed {mult:g}x \u2014 won {win} "
                             f"({'+' if net >= 0 else ''}{net}).",
                        fg=GOLD if net >= 0 else "white")
        if self.credits < MIN_BET:
            self.msg.config(text="Out of credits \u2014 buy more credits!")
            wallet.close_game(self.root)
        self.bet = min(self.bet, self.credits)
        self.refresh()
        self.busy = False
        self.drop_btn.config(state="normal")


def main():
    root = tk.Tk()
    Plinko(root)
    root.mainloop()


if __name__ == "__main__":
    main()
