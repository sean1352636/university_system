"""
Video Poker -- Jacks or Better.

Self-contained Tkinter game (standard library only).
Run with:  python video_poker.py

Draw five cards, HOLD the ones you want (click them), then Draw to replace the
rest. You're paid on the standard Jacks-or-Better table -- a pair of Jacks or
higher is the minimum paying hand.
"""

import random
import tkinter as tk
try:
    import wallet  # shared credit wallet when launched as a standalone script
except ImportError:  # when imported as part of the betting-shop package
    from education_system.post_18.university_system.modules.domain.commerce.betting.gui.games import wallet
from collections import Counter

SUITS = ["\u2660", "\u2665", "\u2666", "\u2663"]
RED = {"\u2665", "\u2666"}
RANKS = list(range(2, 15))
RANK_STR = {**{n: str(n) for n in range(2, 11)}, 11: "J", 12: "Q", 13: "K", 14: "A"}

# hand key -> (name, payout per coin for bets 1..5)
PAYTABLE = [
    ("Royal Flush",     [250, 500, 750, 1000, 4000]),
    ("Straight Flush",  [50, 100, 150, 200, 250]),
    ("Four of a Kind",  [25, 50, 75, 100, 125]),
    ("Full House",      [9, 18, 27, 36, 45]),
    ("Flush",           [6, 12, 18, 24, 30]),
    ("Straight",        [4, 8, 12, 16, 20]),
    ("Three of a Kind", [3, 6, 9, 12, 15]),
    ("Two Pair",        [2, 4, 6, 8, 10]),
    ("Jacks or Better", [1, 2, 3, 4, 5]),
]
PAYINDEX = {name: i for i, (name, _) in enumerate(PAYTABLE)}

CARD_W, CARD_H = 92, 128
FELT, GOLD = "#0b2a3a", "#e9c46a"
START_CREDITS = 200


def straight_high(ranks):
    s = set(ranks)
    if len(s) != 5:
        return None
    hi, lo = max(s), min(s)
    if hi - lo == 4:
        return hi
    if s == {14, 2, 3, 4, 5}:
        return 5
    return None


def rank_hand(hand):
    """Return the paytable name for a hand, or None if it doesn't pay."""
    ranks = [c[0] for c in hand]
    suits = [c[1] for c in hand]
    counts = Counter(ranks)
    shape = sorted(counts.values(), reverse=True)
    is_flush = len(set(suits)) == 1
    sh = straight_high(ranks)

    if sh and is_flush:
        return "Royal Flush" if sh == 14 else "Straight Flush"
    if shape[0] == 4:
        return "Four of a Kind"
    if shape == [3, 2]:
        return "Full House"
    if is_flush:
        return "Flush"
    if sh:
        return "Straight"
    if shape[0] == 3:
        return "Three of a Kind"
    if shape[:2] == [2, 2]:
        return "Two Pair"
    if shape[0] == 2:
        pair_rank = next(r for r, n in counts.items() if n == 2)
        if pair_rank >= 11 or pair_rank == 14:   # J,Q,K,A
            return "Jacks or Better"
    return None


class VideoPoker:
    def __init__(self, root):
        self.root = root
        root.title("Video Poker \u2014 Jacks or Better")
        root.configure(bg=FELT)
        root.resizable(False, False)
        self.credits = wallet.get_credits()
        self.bet = 5
        self.phase = "deal"          # deal | draw
        self.hand = [(2, SUITS[0])] * 5
        self.held = [False] * 5
        self._build()
        self.render()
        self.refresh()

    def _build(self):
        f = tk.Frame(self.root, bg=FELT, padx=18, pady=12)
        f.pack()
        tk.Label(f, text="VIDEO POKER \u2014 Jacks or Better", bg=FELT, fg=GOLD,
                 font=("Helvetica", 17, "bold")).pack()
        self.pay_frame = tk.Frame(f, bg="#08202c")
        self.pay_frame.pack(pady=6, fill="x")
        self._build_paytable()

        row = tk.Frame(f, bg=FELT)
        row.pack(pady=8)
        self.card_canvases = []
        for i in range(5):
            c = tk.Canvas(row, width=CARD_W, height=CARD_H + 20, bg=FELT,
                          highlightthickness=0)
            c.pack(side="left", padx=5)
            c.bind("<Button-1>", lambda e, idx=i: self.toggle_hold(idx))
            self.card_canvases.append(c)

        self.msg = tk.Label(f, text="Press Deal to start.", bg=FELT, fg="white",
                            font=("Helvetica", 13, "bold"))
        self.msg.pack()

        bar = tk.Frame(f, bg=FELT, pady=8)
        bar.pack()
        self.cr_lbl = tk.Label(bar, text="", bg=FELT, fg="white",
                               font=("Helvetica", 13, "bold"))
        self.cr_lbl.pack(side="left", padx=8)
        tk.Button(bar, text="Bet \u2212", command=lambda: self.chg(-1),
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
        tk.Button(bar, text="Bet +", command=lambda: self.chg(1),
                  font=("Helvetica", 11, "bold"), bg="#333", fg="white",
                  bd=0).pack(side="left")
        self.action_btn = tk.Button(f, text="DEAL", command=self.action, width=16,
                                    font=("Helvetica", 14, "bold"), bg="#1b7a4b",
                                    fg="white", activebackground=GOLD, bd=0, pady=8,
                                    cursor="hand2")
        self.action_btn.pack(pady=6)

    def _build_paytable(self):
        for w in self.pay_frame.winfo_children():
            w.destroy()
        for r, (name, pays) in enumerate(PAYTABLE):
            fg = GOLD if self.bet - 1 == 0 else "white"
            tk.Label(self.pay_frame, text=name, bg="#08202c", fg="#cfe3ee",
                     font=("Helvetica", 9, "bold"), anchor="w", width=16).grid(
                row=r, column=0, sticky="w", padx=4)
            for b in range(5):
                sel = (b == self.bet - 1)
                tk.Label(self.pay_frame, text=str(pays[b]), bg="#0f3547" if sel
                         else "#08202c", fg=GOLD if sel else "#9fc0cf",
                         font=("Helvetica", 9, "bold"), width=5).grid(
                    row=r, column=b + 1, padx=1)

    def _draw_card(self, canvas, card, held=False, face=True):
        canvas.delete("all")
        y0 = 18
        if held:
            canvas.create_text(CARD_W / 2, 9, text="HELD", fill=GOLD,
                               font=("Helvetica", 9, "bold"))
        if not face:
            canvas.create_rectangle(3, y0, CARD_W - 3, CARD_H + 14, fill="#1d3a63",
                                    outline="#222")
            return
        canvas.create_rectangle(3, y0, CARD_W - 3, CARD_H + 14, fill="white",
                                outline="#222")
        rank, suit = card
        color = "#c0392b" if suit in RED else "#111"
        rs = RANK_STR[rank]
        canvas.create_text(16, y0 + 16, text=rs, fill=color,
                           font=("Helvetica", 14, "bold"))
        canvas.create_text(16, y0 + 34, text=suit, fill=color,
                           font=("Helvetica", 13))
        canvas.create_text(CARD_W / 2, y0 + CARD_H / 2, text=suit, fill=color,
                           font=("Helvetica", 32, "bold"))
        if held:
            canvas.create_rectangle(3, y0, CARD_W - 3, CARD_H + 14, outline=GOLD,
                                    width=3)

    def render(self):
        for i in range(5):
            self._draw_card(self.card_canvases[i], self.hand[i], self.held[i])

    def toggle_hold(self, idx):
        if self.phase != "draw":
            return
        self.held[idx] = not self.held[idx]
        self.render()

    def chg(self, d):
        if self.phase == "draw":
            return
        self.bet = max(1, min(5, self.bet + d))
        self._build_paytable()
        self.refresh()

    def set_bet(self):
        """Set the coin bet (1-5) to the amount typed into the entry box."""
        try:
            self.chg(int(float(self.bet_var.get())) - self.bet)
        except (TypeError, ValueError):
            pass
        self.bet_var.set(str(self.bet))

    def refresh(self):
        wallet.set_credits(self.credits)
        self.cr_lbl.config(text=f"Credits: {self.credits}")
        self.bet_var.set(str(self.bet))

    def action(self):
        if self.phase == "deal":
            if self.credits < self.bet:
                self.msg.config(text="Not enough credits.")
                return
            self.credits -= self.bet
            self.deck = [(r, s) for s in SUITS for r in RANKS]
            random.shuffle(self.deck)
            self.hand = [self.deck.pop() for _ in range(5)]
            self.held = [False] * 5
            self.phase = "draw"
            self.action_btn.config(text="DRAW")
            self.msg.config(text="Hold cards, then Draw.", fg="white")
            self.render()
            self.refresh()
        else:
            for i in range(5):
                if not self.held[i]:
                    self.hand[i] = self.deck.pop()
            self.render()
            name = rank_hand(self.hand)
            if name:
                pay = PAYTABLE[PAYINDEX[name]][1][self.bet - 1]
                self.credits += pay
                self.msg.config(text=f"{name}!  Win {pay}.", fg=GOLD)
            else:
                self.msg.config(text="No paying hand. Deal again.", fg="white")
            self.phase = "deal"
            self.action_btn.config(text="DEAL")
            if self.credits < 1:
                self.msg.config(text="Out of credits \u2014 buy more credits!")
                wallet.close_game(self.root)
            self.bet = min(self.bet, max(1, self.credits))
            self._build_paytable()
            self.refresh()


def main():
    root = tk.Tk()
    VideoPoker(root)
    root.mainloop()


if __name__ == "__main__":
    main()
