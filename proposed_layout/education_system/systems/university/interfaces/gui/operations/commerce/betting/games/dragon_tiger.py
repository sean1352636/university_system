"""
Dragon Tiger -- fast electronic card game.

Self-contained Tkinter game (standard library only).
Run with:  python dragon_tiger.py

One card to Dragon, one to Tiger. Bet on which is higher, or on a Tie. Highest
card wins (Ace low, King high). Dragon/Tiger pay 1:1; Tie pays 8:1 (and your
Dragon/Tiger stake is half-lost on a tie, as in most casinos).
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

CARD_W, CARD_H = 120, 168
FELT, GOLD = "#3a0a12", "#e9c46a"
START_CREDITS, MIN_BET = 200, 5


class DragonTiger:
    def __init__(self, root):
        self.root = root
        root.title("Dragon Tiger")
        root.configure(bg=FELT)
        root.resizable(False, False)
        self.credits = wallet.get_credits()
        self.bet = 20
        self.choice = tk.StringVar(value="dragon")
        self.busy = False
        self._build()
        self.render(None, None)
        self.refresh()

    def _build(self):
        f = tk.Frame(self.root, bg=FELT, padx=20, pady=14)
        f.pack()
        tk.Label(f, text="\U0001f409  DRAGON  vs  TIGER  \U0001f405".replace(
            "\U0001f409", "").replace("\U0001f405", ""), bg=FELT, fg=GOLD,
            font=("Helvetica", 20, "bold")).pack()

        row = tk.Frame(f, bg=FELT)
        row.pack(pady=8)
        dcol = tk.Frame(row, bg=FELT)
        dcol.pack(side="left", padx=20)
        tk.Label(dcol, text="DRAGON", bg=FELT, fg="#ff7b7b",
                 font=("Helvetica", 14, "bold")).pack()
        self.dragon_c = tk.Canvas(dcol, width=CARD_W, height=CARD_H, bg=FELT,
                                  highlightthickness=0)
        self.dragon_c.pack()
        tcol = tk.Frame(row, bg=FELT)
        tcol.pack(side="left", padx=20)
        tk.Label(tcol, text="TIGER", bg=FELT, fg="#ffcf7b",
                 font=("Helvetica", 14, "bold")).pack()
        self.tiger_c = tk.Canvas(tcol, width=CARD_W, height=CARD_H, bg=FELT,
                                 highlightthickness=0)
        self.tiger_c.pack()

        self.msg = tk.Label(f, text="Choose a side and deal.", bg=FELT, fg="white",
                            font=("Helvetica", 13, "bold"))
        self.msg.pack(pady=4)

        sel = tk.Frame(f, bg=FELT, pady=4)
        sel.pack()
        for key, txt, col in [("dragon", "DRAGON 1:1", "#9b2226"),
                              ("tie", "TIE 8:1", "#2a6f4a"),
                              ("tiger", "TIGER 1:1", "#b5651d")]:
            tk.Radiobutton(sel, text=txt, value=key, variable=self.choice,
                           indicatoron=False, width=12, height=2,
                           font=("Helvetica", 11, "bold"), bg=col, fg="white",
                           selectcolor="#111", bd=0).pack(side="left", padx=4)

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
        self.deal_btn = tk.Button(f, text="DEAL", command=self.deal, width=16,
                                  font=("Helvetica", 14, "bold"), bg="#1b7a4b",
                                  fg="white", activebackground=GOLD, bd=0, pady=8,
                                  cursor="hand2")
        self.deal_btn.pack(pady=6)

    def _draw(self, canvas, card):
        canvas.delete("all")
        if card is None:
            canvas.create_rectangle(4, 4, CARD_W - 4, CARD_H - 4, fill="#1d1030",
                                    outline=GOLD, width=2)
            canvas.create_text(CARD_W / 2, CARD_H / 2, text="?", fill=GOLD,
                               font=("Helvetica", 40, "bold"))
            return
        canvas.create_rectangle(4, 4, CARD_W - 4, CARD_H - 4, fill="white",
                                outline="#222", width=2)
        rank, suit = card
        color = "#c0392b" if suit in RED else "#111"
        rs = RANK_STR[rank]
        canvas.create_text(20, 22, text=rs, fill=color,
                           font=("Helvetica", 20, "bold"))
        canvas.create_text(20, 46, text=suit, fill=color, font=("Helvetica", 18))
        canvas.create_text(CARD_W / 2, CARD_H / 2, text=suit, fill=color,
                           font=("Helvetica", 52, "bold"))

    def render(self, d, t):
        self._draw(self.dragon_c, d)
        self._draw(self.tiger_c, t)

    def chg(self, delta):
        if self.busy:
            return
        self.bet = max(MIN_BET, min(max(self.credits, MIN_BET), self.bet + delta))
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

    def deal(self):
        if self.busy:
            return
        if self.credits < self.bet:
            self.msg.config(text="Not enough credits.")
            return
        self.credits -= self.bet
        self.busy = True
        self.deal_btn.config(state="disabled")
        self.refresh()
        deck = [(r, s) for s in SUITS for r in RANKS]
        random.shuffle(deck)
        self.dcard, self.tcard = deck.pop(), deck.pop()
        self.render(None, None)
        self.msg.config(text="Dealing...", fg="white")
        self.root.after(400, lambda: (self._draw(self.dragon_c, self.dcard),
                                      self.msg.config(text="Dragon...")))
        self.root.after(900, lambda: (self._draw(self.tiger_c, self.tcard),
                                      self._settle()))

    def _settle(self):
        d, t = self.dcard[0], self.tcard[0]
        choice = self.choice.get()
        if d > t:
            outcome = "dragon"
        elif t > d:
            outcome = "tiger"
        else:
            outcome = "tie"

        if outcome == "tie":
            if choice == "tie":
                win = self.bet * 8 + self.bet
                self.credits += win
                self.msg.config(text=f"TIE! Win {self.bet * 8}.", fg=GOLD)
            else:
                # half the side stake is returned on a tie
                self.credits += self.bet // 2
                self.msg.config(text=f"Tie \u2014 half your {choice} bet returned.",
                                fg="white")
        elif choice == outcome:
            win = self.bet * 2
            self.credits += win
            self.msg.config(text=f"{outcome.title()} wins \u2014 you win "
                                 f"{self.bet}!", fg=GOLD)
        else:
            self.msg.config(text=f"{outcome.title()} wins. You lose.", fg="white")

        if self.credits < MIN_BET:
            self.msg.config(text="Out of credits \u2014 buy more credits!")
            wallet.close_game(self.root)
        self.bet = min(self.bet, self.credits)
        self.refresh()
        self.busy = False
        self.deal_btn.config(state="normal")


def main():
    root = tk.Tk()
    DragonTiger(root)
    root.mainloop()


if __name__ == "__main__":
    main()
