"""
Bingo -- 75-ball casino bingo.

Self-contained Tkinter game (standard library only).
Run with:  python bingo.py

Buy a card, press Play, and balls are called automatically. Your card daubs
itself. Complete any LINE (row, column, or diagonal) to win -- the fewer balls
it takes, the bigger the payout. The centre square is a free space.
"""

import random
import tkinter as tk
try:
    import wallet  # shared credit wallet when launched as a standalone script
except ImportError:  # when imported as part of the betting-shop package
    from education_system.post_18.university_system.modules.domain.commerce.betting.gui.games import wallet

COLS = [("B", 1, 15), ("I", 16, 30), ("N", 31, 45), ("G", 46, 60), ("O", 61, 75)]
CELL = 72
CAP = 42                       # give up if no line by this many calls
# payout multiplier by number of calls taken to hit the first line
# (calibrated to the real distribution: ~52% hit rate, ~92% RTP)
PAY_TIERS = [(24, 6), (32, 2), (42, 1)]   # (<= calls, multiplier)
FELT, GOLD = "#0e2038", "#e9c46a"
START_CREDITS, MIN_BET = 200, 5


def line_payout(calls):
    for limit, mult in PAY_TIERS:
        if calls <= limit:
            return mult
    return 0


def make_card():
    """Return card[5][5] of numbers (centre = 0 for FREE)."""
    card = [[0] * 5 for _ in range(5)]
    for col, (_, lo, hi) in enumerate(COLS):
        nums = random.sample(range(lo, hi + 1), 5)
        for row in range(5):
            card[row][col] = nums[row]
    card[2][2] = 0  # free space
    return card


def has_line(daub):
    for r in range(5):
        if all(daub[r]):
            return True
    for c in range(5):
        if all(daub[r][c] for r in range(5)):
            return True
    if all(daub[i][i] for i in range(5)):
        return True
    if all(daub[i][4 - i] for i in range(5)):
        return True
    return False


class Bingo:
    def __init__(self, root):
        self.root = root
        root.title("Bingo \u2014 75 ball")
        root.configure(bg=FELT)
        root.resizable(False, False)
        self.credits = wallet.get_credits()
        self.bet = 10
        self.busy = False
        self._new_card()
        self._build()
        self.render()
        self.refresh()

    def _new_card(self):
        self.card = make_card()
        self.daub = [[False] * 5 for _ in range(5)]
        self.daub[2][2] = True
        self.pool = random.sample(range(1, 76), 75)
        self.calls = 0
        self.current = None
        self.won = False

    def _build(self):
        f = tk.Frame(self.root, bg=FELT, padx=18, pady=12)
        f.pack()
        tk.Label(f, text="B I N G O", bg=FELT, fg=GOLD,
                 font=("Helvetica", 22, "bold")).pack()

        top = tk.Frame(f, bg=FELT)
        top.pack(pady=6)
        self.ball_lbl = tk.Label(top, text="\u2014", bg="#2a1650", fg=GOLD,
                                 width=4, font=("Helvetica", 30, "bold"))
        self.ball_lbl.pack(side="left", padx=10)
        info = tk.Frame(top, bg=FELT)
        info.pack(side="left")
        self.calls_lbl = tk.Label(info, text="", bg=FELT, fg="white",
                                  font=("Helvetica", 12, "bold"))
        self.calls_lbl.pack(anchor="w")
        self.recent_lbl = tk.Label(info, text="", bg=FELT, fg="#9fb3c8",
                                   font=("Helvetica", 10), width=30, anchor="w",
                                   justify="left")
        self.recent_lbl.pack(anchor="w")

        w = 5 * CELL
        self.canvas = tk.Canvas(f, width=w, height=CELL + 5 * CELL, bg="#081428",
                                highlightthickness=0)
        self.canvas.pack(pady=8)

        self.msg = tk.Label(f, text="Buy a card and press Play!", bg=FELT,
                            fg="white", font=("Helvetica", 12, "bold"))
        self.msg.pack()
        tk.Label(f, text="Line in \u226424 calls = 6x  \u2022  \u226432 = 2x  "
                 "\u2022  \u226442 = 1x  \u2022  slower = no win", bg=FELT,
                 fg="#9fb3c8", font=("Helvetica", 9)).pack(pady=2)

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

        btns = tk.Frame(f, bg=FELT, pady=6)
        btns.pack()
        self.play_btn = tk.Button(btns, text="PLAY", command=self.play, width=12,
                                  font=("Helvetica", 14, "bold"), bg="#1b7a4b",
                                  fg="white", activebackground=GOLD, bd=0, pady=8,
                                  cursor="hand2")
        self.play_btn.pack(side="left", padx=6)
        self.new_btn = tk.Button(btns, text="New Card", command=self.new_card,
                                 width=12, font=("Helvetica", 14, "bold"),
                                 bg="#3a5a8a", fg="white", activebackground=GOLD,
                                 bd=0, pady=8, cursor="hand2")
        self.new_btn.pack(side="left", padx=6)

    def render(self):
        c = self.canvas
        c.delete("all")
        # header
        for col, (letter, _, _) in enumerate(COLS):
            x = col * CELL
            c.create_rectangle(x, 0, x + CELL, CELL, fill="#7b2cbf", outline="#fff")
            c.create_text(x + CELL / 2, CELL / 2, text=letter, fill="white",
                          font=("Helvetica", 26, "bold"))
        # cells
        for row in range(5):
            for col in range(5):
                x, y = col * CELL, CELL + row * CELL
                num = self.card[row][col]
                free = (row == 2 and col == 2)
                daubed = self.daub[row][col]
                if free:
                    fill, fg, txt = "#e9c46a", "#222", "FREE"
                elif daubed:
                    fill, fg, txt = "#2a9d4a", "white", str(num)
                else:
                    fill, fg, txt = "white", "#111", str(num)
                c.create_rectangle(x + 2, y + 2, x + CELL - 2, y + CELL - 2,
                                   fill=fill, outline="#22344f")
                c.create_text(x + CELL / 2, y + CELL / 2, text=txt, fill=fg,
                              font=("Helvetica", 16 if not free else 12, "bold"))

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
        self.calls_lbl.config(text=f"Calls: {self.calls}")

    def new_card(self):
        if self.busy:
            return
        self._new_card()
        self.ball_lbl.config(text="\u2014")
        self.recent_lbl.config(text="")
        self.render()
        self.refresh()
        self.msg.config(text="New card ready. Press Play!", fg="white")

    def play(self):
        if self.busy:
            return
        if self.credits < self.bet:
            self.msg.config(text="Not enough credits.")
            return
        # fresh card if the previous round already finished
        if self.calls > 0:
            self._new_card()
            self.render()
        self.credits -= self.bet
        self.busy = True
        self.play_btn.config(state="disabled")
        self.new_btn.config(state="disabled")
        self.msg.config(text="Calling numbers...", fg="white")
        self.refresh()
        self._recent = []
        self._call()

    def _call(self):
        if has_line(self.daub):
            self._settle(won=True)
            return
        if self.calls >= CAP or not self.pool:
            self._settle(won=False)
            return
        n = self.pool.pop()
        self.calls += 1
        self.current = n
        col = (n - 1) // 15
        for row in range(5):
            if self.card[row][col] == n:
                self.daub[row][col] = True
        letter = COLS[col][0]
        self.ball_lbl.config(text=f"{letter}{n}")
        self._recent = ([f"{letter}{n}"] + self._recent)[:8]
        self.recent_lbl.config(text="Recent: " + "  ".join(self._recent))
        self.render()
        self.refresh()
        self.root.after(170, self._call)

    def _settle(self, won):
        if won:
            mult = line_payout(self.calls)
            win = self.bet * mult
            if win:
                self.credits += win
                self.msg.config(text=f"BINGO in {self.calls} calls \u2014 "
                                     f"WIN {win}! ({mult}x)", fg=GOLD)
            else:
                self.msg.config(text=f"Line in {self.calls} calls \u2014 too "
                                     f"slow, no payout.", fg="white")
        else:
            self.msg.config(text="No line in time. Better luck next card.",
                            fg="white")
        if self.credits < MIN_BET:
            self.msg.config(text="Out of credits \u2014 buy more credits!")
            wallet.close_game(self.root)
        self.bet = min(self.bet, self.credits)
        self.refresh()
        self.busy = False
        self.play_btn.config(state="normal")
        self.new_btn.config(state="normal")


def main():
    root = tk.Tk()
    Bingo(root)
    root.mainloop()


if __name__ == "__main__":
    main()
