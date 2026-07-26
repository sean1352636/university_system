"""
Hi-Lo -- higher/lower streak betting machine.

Self-contained Tkinter game (standard library only).
Run with:  python hi_lo.py

A card is shown; bet whether the next card is HIGHER or LOWER (Ace low, King
high). Each correct call multiplies your running win -- riskier calls pay more.
Cash out any time; a wrong call (or an exact tie) loses the lot.
"""

import random
import tkinter as tk
try:
    import wallet  # shared credit wallet when launched as a standalone script
except ImportError:  # when imported as part of the betting-shop package
    from education_system.systems.university.interfaces.gui.operations.commerce.betting.games import wallet

SUITS = ["\u2660", "\u2665", "\u2666", "\u2663"]
RED = {"\u2665", "\u2666"}
RANKS = list(range(1, 14))          # 1=Ace low ... 13=King high
RANK_STR = {1: "A", 11: "J", 12: "Q", 13: "K", **{n: str(n) for n in range(2, 11)}}

CARD_W, CARD_H = 150, 210
EDGE = 0.92                          # return factor (house keeps ~8%)
FELT, GOLD = "#1a2438", "#e9c46a"
START_CREDITS, MIN_BET = 200, 5


def prob_higher(v):
    return sum(1 for r in RANKS if r > v) / 13.0


def prob_lower(v):
    return sum(1 for r in RANKS if r < v) / 13.0


def multiplier(p):
    return EDGE / p if p > 0 else 0.0


class HiLo:
    def __init__(self, root):
        self.root = root
        root.title("Hi-Lo")
        root.configure(bg=FELT)
        root.resizable(False, False)
        self.credits = wallet.get_credits()
        self.bet = 20
        self.in_round = False
        self.running = 0.0
        self.current = None
        self.busy = False
        self._build()
        self.render()
        self.refresh()
        self.update_buttons()

    def _build(self):
        f = tk.Frame(self.root, bg=FELT, padx=20, pady=14)
        f.pack()
        tk.Label(f, text="HI - LO", bg=FELT, fg=GOLD,
                 font=("Helvetica", 22, "bold")).pack()
        self.canvas = tk.Canvas(f, width=CARD_W, height=CARD_H, bg=FELT,
                                highlightthickness=0)
        self.canvas.pack(pady=8)
        self.run_lbl = tk.Label(f, text="", bg=FELT, fg=GOLD,
                                font=("Helvetica", 14, "bold"))
        self.run_lbl.pack()
        self.msg = tk.Label(f, text="Set a stake and press Deal.", bg=FELT,
                            fg="white", font=("Helvetica", 12, "bold"))
        self.msg.pack(pady=2)

        guess = tk.Frame(f, bg=FELT, pady=6)
        guess.pack()
        self.high_btn = tk.Button(guess, text="HIGHER", command=lambda:
                                  self.guess("higher"), width=14,
                                  font=("Helvetica", 13, "bold"), bg="#1b7a4b",
                                  fg="white", bd=0, pady=6, cursor="hand2",
                                  state="disabled")
        self.high_btn.pack(side="left", padx=6)
        self.low_btn = tk.Button(guess, text="LOWER", command=lambda:
                                 self.guess("lower"), width=14,
                                 font=("Helvetica", 13, "bold"), bg="#9b2226",
                                 fg="white", bd=0, pady=6, cursor="hand2",
                                 state="disabled")
        self.low_btn.pack(side="left", padx=6)

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
        self.deal_btn = tk.Button(btns, text="DEAL", command=self.deal, width=12,
                                  font=("Helvetica", 13, "bold"), bg="#3a5a8a",
                                  fg="white", bd=0, pady=6, cursor="hand2")
        self.deal_btn.pack(side="left", padx=6)
        self.cash_btn = tk.Button(btns, text="CASH OUT", command=self.cash_out,
                                  width=12, font=("Helvetica", 13, "bold"),
                                  bg="#1b7a4b", fg="white", bd=0, pady=6,
                                  cursor="hand2", state="disabled")
        self.cash_btn.pack(side="left", padx=6)

    def render(self):
        c = self.canvas
        c.delete("all")
        if self.current is None:
            c.create_rectangle(4, 4, CARD_W - 4, CARD_H - 4, fill="#111a2c",
                               outline=GOLD, width=2)
            c.create_text(CARD_W / 2, CARD_H / 2, text="?", fill=GOLD,
                          font=("Helvetica", 50, "bold"))
            return
        c.create_rectangle(4, 4, CARD_W - 4, CARD_H - 4, fill="white",
                           outline="#222", width=2)
        rank, suit = self.current
        color = "#c0392b" if suit in RED else "#111"
        rs = RANK_STR[rank]
        c.create_text(24, 26, text=rs, fill=color, font=("Helvetica", 24, "bold"))
        c.create_text(24, 54, text=suit, fill=color, font=("Helvetica", 20))
        c.create_text(CARD_W / 2, CARD_H / 2, text=suit, fill=color,
                      font=("Helvetica", 66, "bold"))

    def update_buttons(self):
        if not self.in_round or self.current is None:
            self.high_btn.config(state="disabled", text="HIGHER")
            self.low_btn.config(state="disabled", text="LOWER")
            return
        v = self.current[0]
        ph, pl = prob_higher(v), prob_lower(v)
        mh, ml = multiplier(ph), multiplier(pl)
        self.high_btn.config(state="normal" if ph > 0 else "disabled",
                             text=f"HIGHER  x{mh:.2f}" if ph > 0 else "HIGHER \u2014")
        self.low_btn.config(state="normal" if pl > 0 else "disabled",
                            text=f"LOWER  x{ml:.2f}" if pl > 0 else "LOWER \u2014")

    def chg(self, d):
        if self.in_round or self.busy:
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
        if self.in_round:
            self.run_lbl.config(text=f"Running: {int(round(self.running))}")
        else:
            self.run_lbl.config(text="")

    def _draw_card(self):
        return (random.choice(RANKS), random.choice(SUITS))

    def deal(self):
        if self.busy or self.in_round:
            return
        if self.credits < self.bet:
            self.msg.config(text="Not enough credits.")
            return
        self.credits -= self.bet
        self.running = float(self.bet)
        self.in_round = True
        self.current = self._draw_card()
        self.render()
        self.msg.config(text="Higher or lower?", fg="white")
        self.deal_btn.config(state="disabled")
        self.cash_btn.config(state="normal")
        self.update_buttons()
        self.refresh()

    def guess(self, direction):
        if self.busy or not self.in_round:
            return
        v = self.current[0]
        p = prob_higher(v) if direction == "higher" else prob_lower(v)
        mult = multiplier(p)
        nxt = self._draw_card()
        self.busy = True
        self.high_btn.config(state="disabled")
        self.low_btn.config(state="disabled")
        self.current = nxt
        self.render()
        correct = ((direction == "higher" and nxt[0] > v) or
                   (direction == "lower" and nxt[0] < v))
        self.busy = False
        if correct:
            self.running *= mult
            self.msg.config(text=f"Correct! x{mult:.2f}. Cash out or keep going?",
                            fg=GOLD)
            self.cash_btn.config(state="normal")
            self.update_buttons()
        else:
            reason = "tie" if nxt[0] == v else "wrong"
            self.msg.config(text=f"{'Tie' if reason=='tie' else 'Wrong'} \u2014 "
                                 f"you lose {int(round(self.running))}.", fg="#ff9090")
            self._end_round()
        self.refresh()

    def cash_out(self):
        if not self.in_round or self.busy:
            return
        won = int(round(self.running))
        self.credits += won
        self.msg.config(text=f"Cashed out {won} credits!", fg=GOLD)
        self._end_round()
        self.refresh()

    def _end_round(self):
        self.in_round = False
        self.running = 0.0
        self.current = None
        self.render()
        self.deal_btn.config(state="normal")
        self.cash_btn.config(state="disabled")
        self.update_buttons()
        if self.credits < MIN_BET:
            self.msg.config(text="Out of credits \u2014 buy more credits!")
            wallet.close_game(self.root)
        self.bet = min(self.bet, max(MIN_BET, self.credits))


def main():
    root = tk.Tk()
    HiLo(root)
    root.mainloop()


if __name__ == "__main__":
    main()
