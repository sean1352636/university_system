"""
Video Blackjack -- electronic blackjack against the dealer.

Self-contained Tkinter game (standard library only).
Run with:  python video_blackjack.py

Hit or Stand (and Double on your first two cards). Dealer draws to 17. Blackjack
pays 3:2, other wins pay even money. Dealer stands on all 17s.
"""

import random
import tkinter as tk
try:
    import wallet  # shared credit wallet when launched as a standalone script
except ImportError:  # when imported as part of the betting-shop package
    from education_system.systems.university.interfaces.gui.operations.commerce.betting.games import wallet

SUITS = ["\u2660", "\u2665", "\u2666", "\u2663"]
RED = {"\u2665", "\u2666"}
RANKS = list(range(2, 15))
RANK_STR = {**{n: str(n) for n in range(2, 11)}, 11: "J", 12: "Q", 13: "K", 14: "A"}

CARD_W, CARD_H = 82, 116
FELT, GOLD = "#0b5a2a", "#e9c46a"
START_CREDITS, MIN_BET = 200, 5


def card_value(rank):
    if rank >= 11 and rank <= 13:
        return 10
    if rank == 14:
        return 11
    return rank


def hand_total(cards):
    total = sum(card_value(r) for r, _ in cards)
    aces = sum(1 for r, _ in cards if r == 14)
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total


def is_blackjack(cards):
    return len(cards) == 2 and hand_total(cards) == 21


class VideoBlackjack:
    def __init__(self, root):
        self.root = root
        root.title("Video Blackjack")
        root.configure(bg=FELT)
        root.resizable(False, False)
        self.credits = wallet.get_credits()
        self.bet = 20
        self.phase = "bet"           # bet | player | done
        self.player = []
        self.dealer = []
        self._build()
        self.render()
        self.refresh()

    def _build(self):
        f = tk.Frame(self.root, bg=FELT, padx=18, pady=12)
        f.pack()
        tk.Label(f, text="VIDEO BLACKJACK", bg=FELT, fg=GOLD,
                 font=("Helvetica", 18, "bold")).pack()
        tk.Label(f, text="Dealer", bg=FELT, fg="white",
                 font=("Helvetica", 12, "bold")).pack()
        self.dealer_total = tk.Label(f, text="", bg=FELT, fg=GOLD,
                                     font=("Helvetica", 12, "bold"))
        self.dealer_total.pack()
        self.dealer_row = self._card_row(f)
        mid = tk.Frame(f, bg="#074420", padx=10, pady=6)
        mid.pack(fill="x", pady=8)
        self.msg = tk.Label(mid, text="Place a bet and deal.", bg="#074420",
                            fg=GOLD, font=("Helvetica", 13, "bold"))
        self.msg.pack()
        self.player_row = self._card_row(f)
        self.player_total = tk.Label(f, text="", bg=FELT, fg=GOLD,
                                     font=("Helvetica", 12, "bold"))
        self.player_total.pack()
        tk.Label(f, text="You", bg=FELT, fg="white",
                 font=("Helvetica", 12, "bold")).pack()

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
        self.deal_btn = tk.Button(btns, text="DEAL", command=self.deal, width=9,
                                  font=("Helvetica", 13, "bold"), bg="#1b7a4b",
                                  fg="white", bd=0, pady=6, cursor="hand2")
        self.deal_btn.pack(side="left", padx=4)
        self.hit_btn = tk.Button(btns, text="HIT", command=self.hit, width=8,
                                 font=("Helvetica", 13, "bold"), bg="#3a5a8a",
                                 fg="white", bd=0, pady=6, cursor="hand2",
                                 state="disabled")
        self.hit_btn.pack(side="left", padx=4)
        self.stand_btn = tk.Button(btns, text="STAND", command=self.stand, width=8,
                                   font=("Helvetica", 13, "bold"), bg="#9b2226",
                                   fg="white", bd=0, pady=6, cursor="hand2",
                                   state="disabled")
        self.stand_btn.pack(side="left", padx=4)
        self.double_btn = tk.Button(btns, text="DOUBLE", command=self.double,
                                    width=8, font=("Helvetica", 13, "bold"),
                                    bg="#7b2cbf", fg="white", bd=0, pady=6,
                                    cursor="hand2", state="disabled")
        self.double_btn.pack(side="left", padx=4)

    def _card_row(self, parent):
        row = tk.Frame(parent, bg=FELT)
        row.pack(pady=4)
        cvs = []
        for _ in range(6):
            c = tk.Canvas(row, width=CARD_W, height=CARD_H, bg=FELT,
                          highlightthickness=0)
            c.pack(side="left", padx=3)
            cvs.append(c)
        return cvs

    def _draw_card(self, canvas, card, face=True):
        canvas.delete("all")
        if card is None:
            return
        if not face:
            canvas.create_rectangle(3, 3, CARD_W - 3, CARD_H - 3, fill="#1d3a63",
                                    outline="#222")
            for gx in range(12, CARD_W - 8, 12):
                canvas.create_line(gx, 8, gx, CARD_H - 8, fill="#33578f")
            return
        canvas.create_rectangle(3, 3, CARD_W - 3, CARD_H - 3, fill="white",
                                outline="#222")
        rank, suit = card
        color = "#c0392b" if suit in RED else "#111"
        rs = RANK_STR[rank]
        canvas.create_text(14, 15, text=rs, fill=color,
                           font=("Helvetica", 13, "bold"))
        canvas.create_text(14, 31, text=suit, fill=color, font=("Helvetica", 12))
        canvas.create_text(CARD_W / 2, CARD_H / 2, text=suit, fill=color,
                           font=("Helvetica", 28, "bold"))

    def render(self, hide_hole=False):
        for i in range(6):
            self._draw_card(self.dealer_row[i],
                            self.dealer[i] if i < len(self.dealer) else None,
                            face=not (hide_hole and i == 1))
            self._draw_card(self.player_row[i],
                            self.player[i] if i < len(self.player) else None)
        if hide_hole:
            up = card_value(self.dealer[0][0]) if self.dealer else 0
            self.dealer_total.config(text=f"Showing {up}")
        else:
            self.dealer_total.config(
                text=f"Total {hand_total(self.dealer)}" if self.dealer else "")
        self.player_total.config(
            text=f"Total {hand_total(self.player)}" if self.player else "")

    def chg(self, d):
        if self.phase != "bet":
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

    def _btns(self, deal, hit, stand, double):
        self.deal_btn.config(state="normal" if deal else "disabled")
        self.hit_btn.config(state="normal" if hit else "disabled")
        self.stand_btn.config(state="normal" if stand else "disabled")
        self.double_btn.config(state="normal" if double else "disabled")

    def deal(self):
        if self.credits < self.bet:
            self.msg.config(text="Not enough credits.")
            return
        self.credits -= self.bet
        self.doubled = False
        self.deck = [(r, s) for s in SUITS for r in RANKS]
        random.shuffle(self.deck)
        self.player = [self.deck.pop(), self.deck.pop()]
        self.dealer = [self.deck.pop(), self.deck.pop()]
        self.phase = "player"
        self.refresh()
        if is_blackjack(self.player) or is_blackjack(self.dealer):
            self.finish()
            return
        self.render(hide_hole=True)
        self.msg.config(text="Hit, Stand, or Double?", fg=GOLD)
        can_double = self.credits >= self.bet
        self._btns(False, True, True, can_double)

    def hit(self):
        self.player.append(self.deck.pop())
        self.render(hide_hole=True)
        if hand_total(self.player) > 21:
            self.finish()
        else:
            self._btns(False, True, True, False)

    def double(self):
        if self.credits < self.bet:
            return
        self.credits -= self.bet
        self.doubled = True
        self.player.append(self.deck.pop())
        self.refresh()
        self.finish()

    def stand(self):
        self.finish()

    def finish(self):
        self.phase = "done"
        self._btns(True, False, False, False)
        # dealer plays if player not busted and no naturals shortcut
        pbj = is_blackjack(self.player)
        dbj = is_blackjack(self.dealer)
        pt = hand_total(self.player)
        if pt <= 21 and not pbj and not dbj:
            while hand_total(self.dealer) < 17:
                self.dealer.append(self.deck.pop())
        self.render(hide_hole=False)
        dt = hand_total(self.dealer)
        stake = self.bet * (2 if self.doubled else 1)

        if pbj and not dbj:
            win = int(self.bet * 2.5)         # 3:2 plus stake back
            self.credits += win
            result = f"Blackjack! Win {win - self.bet}."
        elif dbj and not pbj:
            result = "Dealer blackjack. You lose."
        elif pbj and dbj:
            self.credits += self.bet
            result = "Both blackjack \u2014 push."
        elif pt > 21:
            result = f"Bust at {pt}. You lose."
        elif dt > 21:
            self.credits += stake * 2
            result = f"Dealer busts at {dt}. You win {stake}!"
        elif pt > dt:
            self.credits += stake * 2
            result = f"{pt} beats {dt}. You win {stake}!"
        elif pt < dt:
            result = f"{dt} beats {pt}. You lose."
        else:
            self.credits += stake
            result = f"Push on {pt}."

        self.msg.config(text=result, fg=GOLD)
        self.phase = "bet"
        if self.credits < MIN_BET:
            self.msg.config(text=result + "  (Out of credits \u2014 buy more credits!)")
            wallet.close_game(self.root)
        self.bet = min(self.bet, self.credits)
        self.refresh()


def main():
    root = tk.Tk()
    VideoBlackjack(root)
    root.mainloop()


if __name__ == "__main__":
    main()
