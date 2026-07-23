"""
Blackjack — a self-contained Python GUI game built with tkinter.

Rules implemented:
  - Standard 52-card deck (reshuffled when low).
  - Dealer stands on all 17s (including soft 17).
  - Blackjack (natural 21) pays 3:2.
  - Player can Hit, Stand, or Double Down.
  - Betting with a chip bankroll.

Run:  python blackjack.py
"""

import random
import tkinter as tk
try:
    import wallet  # shared credit wallet when launched as a standalone script
except ImportError:  # when imported as part of the betting-shop package
    from education_system.post_18.university_system.modules.domain.commerce.betting.gui.games import wallet
from tkinter import font as tkfont


SUITS = {"spades": "\u2660", "hearts": "\u2665", "diamonds": "\u2666", "clubs": "\u2663"}
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]

# Colors
FELT = "#0b6623"
FELT_DARK = "#08461a"
CARD_FACE = "#fdfdf7"
CARD_BACK = "#1f3a5f"
CARD_BACK_PATTERN = "#2e5686"
RED = "#c0392b"
BLACK = "#1a1a1a"
GOLD = "#f1c40f"

CARD_W, CARD_H = 90, 128


class Card:
    def __init__(self, rank, suit):
        self.rank = rank
        self.suit = suit
        self.face_up = True

    @property
    def value(self):
        if self.rank in ("J", "Q", "K"):
            return 10
        if self.rank == "A":
            return 11
        return int(self.rank)

    @property
    def is_red(self):
        return self.suit in ("hearts", "diamonds")


class Deck:
    def __init__(self, num_decks=1):
        self.num_decks = num_decks
        self.cards = []
        self.shuffle()

    def shuffle(self):
        self.cards = [
            Card(r, s)
            for _ in range(self.num_decks)
            for s in SUITS
            for r in RANKS
        ]
        random.shuffle(self.cards)

    def draw(self):
        if len(self.cards) < 15:
            self.shuffle()
        return self.cards.pop()


def hand_value(cards):
    """Return best hand total, counting aces as 1 or 11."""
    total = sum(c.value for c in cards if c.face_up)
    aces = sum(1 for c in cards if c.rank == "A" and c.face_up)
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total


def is_soft(cards):
    total = sum(c.value for c in cards if c.face_up)
    aces = sum(1 for c in cards if c.rank == "A" and c.face_up)
    return aces > 0 and total <= 21


class BlackjackGame:
    def __init__(self, root):
        self.root = root
        self.root.title("Blackjack")
        self.root.configure(bg=FELT)
        self.root.resizable(False, False)

        self.deck = Deck(num_decks=4)
        self.bankroll = wallet.get_credits()
        self.bet = 0
        self.player = []
        self.dealer = []
        self.in_round = False
        self.player_doubled = False

        self._build_fonts()
        self._build_ui()
        self._set_message("Place your bet to start.")
        self._refresh_stats()

    # ---------- UI construction ----------
    def _build_fonts(self):
        self.f_big = tkfont.Font(family="Helvetica", size=22, weight="bold")
        self.f_med = tkfont.Font(family="Helvetica", size=14, weight="bold")
        self.f_small = tkfont.Font(family="Helvetica", size=11)
        self.f_rank = tkfont.Font(family="Helvetica", size=16, weight="bold")
        self.f_rank_big = tkfont.Font(family="Helvetica", size=34, weight="bold")

    def _build_ui(self):
        # Top status bar
        top = tk.Frame(self.root, bg=FELT_DARK)
        top.pack(fill="x")
        self.lbl_bankroll = tk.Label(top, text="", fg=GOLD, bg=FELT_DARK,
                                     font=self.f_med, padx=14, pady=8)
        self.lbl_bankroll.pack(side="left")
        self.lbl_bet = tk.Label(top, text="", fg="white", bg=FELT_DARK,
                                font=self.f_med, padx=14, pady=8)
        self.lbl_bet.pack(side="right")

        # Table canvas
        self.canvas = tk.Canvas(self.root, width=760, height=460,
                                bg=FELT, highlightthickness=0)
        self.canvas.pack()

        # Message banner
        self.lbl_msg = tk.Label(self.root, text="", fg="white", bg=FELT,
                                font=self.f_med, pady=6)
        self.lbl_msg.pack(fill="x")

        # Betting controls
        bet_bar = tk.Frame(self.root, bg=FELT_DARK)
        bet_bar.pack(fill="x")
        tk.Label(bet_bar, text="Bet:", fg="white", bg=FELT_DARK,
                 font=self.f_small).pack(side="left", padx=(14, 6), pady=8)
        self.chip_buttons = []
        for amount in (5, 25, 100):
            b = tk.Button(bet_bar, text=f"+{amount}", width=5,
                          command=lambda a=amount: self._add_bet(a),
                          bg="#2e5686", fg="white", relief="raised", bd=2,
                          activebackground="#3d6ba5", font=self.f_small)
            b.pack(side="left", padx=3, pady=6)
            self.chip_buttons.append(b)
        self.btn_clear = tk.Button(bet_bar, text="Clear", width=5,
                                   command=self._clear_bet, bg="#7f4a2e",
                                   fg="white", font=self.f_small)
        self.btn_clear.pack(side="left", padx=3)
        tk.Label(bet_bar, text="Set bet:", fg="white", bg=FELT_DARK,
                 font=self.f_small).pack(side="left", padx=(14, 6), pady=8)
        self.bet_var = tk.StringVar(value=str(self.bet))
        self.bet_entry = tk.Entry(bet_bar, textvariable=self.bet_var, width=6,
                                  justify="center", font=self.f_small)
        self.bet_entry.pack(side="left", padx=3, pady=6)
        self.bet_entry.bind("<Return>", lambda e: self.set_bet())
        self.bet_entry.bind("<FocusOut>", lambda e: self.set_bet())

        # Action controls
        action_bar = tk.Frame(self.root, bg=FELT_DARK)
        action_bar.pack(fill="x", pady=(0, 4))
        self.btn_deal = tk.Button(action_bar, text="Deal", width=9,
                                  command=self.deal, bg=GOLD, fg=BLACK,
                                  font=self.f_med, relief="raised", bd=3)
        self.btn_deal.pack(side="left", padx=6, pady=8)
        self.btn_hit = tk.Button(action_bar, text="Hit", width=9,
                                 command=self.hit, font=self.f_med,
                                 bg="#27ae60", fg="white")
        self.btn_hit.pack(side="left", padx=6)
        self.btn_stand = tk.Button(action_bar, text="Stand", width=9,
                                   command=self.stand, font=self.f_med,
                                   bg="#c0392b", fg="white")
        self.btn_stand.pack(side="left", padx=6)
        self.btn_double = tk.Button(action_bar, text="Double", width=9,
                                    command=self.double_down, font=self.f_med,
                                    bg="#8e44ad", fg="white")
        self.btn_double.pack(side="left", padx=6)

        self._set_action_state(betting=True)

    # ---------- Drawing ----------
    def _rounded_rect(self, x, y, w, h, r, **kwargs):
        pts = [
            x + r, y, x + w - r, y, x + w, y, x + w, y + r,
            x + w, y + h - r, x + w, y + h, x + w - r, y + h,
            x + r, y + h, x, y + h, x, y + h - r,
            x, y + r, x, y,
        ]
        return self.canvas.create_polygon(pts, smooth=True, **kwargs)

    def _draw_card(self, card, x, y):
        self._rounded_rect(x, y, CARD_W, CARD_H, 10,
                           fill=CARD_FACE, outline="#c9c9b8", width=2)
        if not card.face_up:
            self._rounded_rect(x + 6, y + 6, CARD_W - 12, CARD_H - 12, 8,
                               fill=CARD_BACK, outline=CARD_BACK_PATTERN, width=2)
            for i in range(y + 14, y + CARD_H - 14, 12):
                self.canvas.create_line(x + 10, i, x + CARD_W - 10, i,
                                        fill=CARD_BACK_PATTERN)
            return

        color = RED if card.is_red else BLACK
        sym = SUITS[card.suit]
        # top-left
        self.canvas.create_text(x + 14, y + 16, text=card.rank,
                                fill=color, font=self.f_rank, anchor="center")
        self.canvas.create_text(x + 14, y + 34, text=sym,
                                fill=color, font=self.f_rank, anchor="center")
        # center pip
        self.canvas.create_text(x + CARD_W / 2, y + CARD_H / 2, text=sym,
                                fill=color, font=self.f_rank_big, anchor="center")
        # bottom-right (inverted feel)
        self.canvas.create_text(x + CARD_W - 14, y + CARD_H - 16, text=card.rank,
                                fill=color, font=self.f_rank, anchor="center")
        self.canvas.create_text(x + CARD_W - 14, y + CARD_H - 34, text=sym,
                                fill=color, font=self.f_rank, anchor="center")

    def _draw_hand(self, cards, y, label, show_value=True):
        self.canvas.create_text(40, y - 26, text=label, anchor="w",
                                fill="white", font=self.f_med)
        start_x = 40
        for i, card in enumerate(cards):
            self._draw_card(card, start_x + i * (CARD_W + 16), y)
        if show_value:
            val = hand_value(cards)
            vis = [c for c in cards if c.face_up]
            if val:
                soft = " (soft)" if is_soft(cards) and len(vis) == len(cards) else ""
                badge = f"{val}{soft}"
                bx = start_x + len(cards) * (CARD_W + 16) + 10
                self.canvas.create_oval(bx, y + 44, bx + 44, y + 88,
                                        fill=FELT_DARK, outline=GOLD, width=2)
                self.canvas.create_text(bx + 22, y + 66, text=str(val),
                                        fill=GOLD, font=self.f_med)

    def _render(self):
        self.canvas.delete("all")
        self._draw_hand(self.dealer, 60, "Dealer")
        self._draw_hand(self.player, 300, "You")

    # ---------- Game flow ----------
    def _add_bet(self, amount):
        if self.in_round:
            return
        if self.bet + amount <= self.bankroll:
            self.bet += amount
            self._refresh_stats()
            self._set_message(f"Bet: {self.bet} chips. Press Deal.")
        else:
            self._set_message("Not enough chips for that bet.")

    def set_bet(self):
        """Set the current bet to an exact amount typed by the player."""
        if self.in_round:
            self.bet_var.set(str(self.bet))
            return
        try:
            val = int(float(self.bet_var.get()))
        except (TypeError, ValueError):
            self.bet_var.set(str(self.bet))
            return
        self.bet = max(0, min(val, self.bankroll))
        self.bet_var.set(str(self.bet))
        self._refresh_stats()

    def _clear_bet(self):
        if self.in_round:
            return
        self.bet = 0
        self._refresh_stats()
        self._set_message("Bet cleared.")

    def deal(self):
        if self.in_round:
            return
        if self.bet <= 0:
            self._set_message("Add some chips to your bet first.")
            return

        self.bankroll -= self.bet
        self.in_round = True
        self.player_doubled = False
        self.player = [self.deck.draw(), self.deck.draw()]
        self.dealer = [self.deck.draw(), self.deck.draw()]
        self.dealer[1].face_up = False  # hole card
        self._render()
        self._refresh_stats()

        player_bj = hand_value(self.player) == 21
        # peek: if dealer shows Ace or ten and has blackjack, settle now
        self.dealer[1].face_up = True
        dealer_bj = hand_value(self.dealer) == 21
        self.dealer[1].face_up = False

        if player_bj or dealer_bj:
            self._reveal_and_settle(natural=player_bj)
            return

        can_double = self.bankroll >= self.bet
        self._set_action_state(betting=False, can_double=can_double)
        self._set_message("Hit, Stand, or Double?")

    def hit(self):
        if not self.in_round:
            return
        self.player.append(self.deck.draw())
        self._render()
        if hand_value(self.player) > 21:
            self._reveal_and_settle()
        else:
            # can't double after hitting
            self._set_action_state(betting=False, can_double=False)

    def double_down(self):
        if not self.in_round or self.bankroll < self.bet:
            return
        self.bankroll -= self.bet
        self.bet *= 2
        self.player_doubled = True
        self.player.append(self.deck.draw())
        self._render()
        self._refresh_stats()
        if hand_value(self.player) > 21:
            self._reveal_and_settle()
        else:
            self.stand()

    def stand(self):
        if not self.in_round:
            return
        self._reveal_and_settle()

    def _dealer_play(self):
        self.dealer[1].face_up = True
        while hand_value(self.dealer) < 17:
            self.dealer.append(self.deck.draw())

    def _reveal_and_settle(self, natural=False):
        self._dealer_play()
        self._render()

        p = hand_value(self.player)
        d = hand_value(self.dealer)
        payout = 0
        msg = ""

        if p > 21:
            msg = f"Bust! You lose {self.bet} chips."
        elif natural and d != 21:
            win = int(self.bet * 1.5)
            payout = self.bet + win
            msg = f"Blackjack! You win {win} chips (3:2)."
        elif d == 21 and len(self.dealer) == 2 and natural:
            payout = self.bet
            msg = "Both blackjack — push."
        elif d == 21 and len(self.dealer) == 2:
            msg = f"Dealer blackjack. You lose {self.bet} chips."
        elif d > 21:
            payout = self.bet * 2
            msg = f"Dealer busts! You win {self.bet} chips."
        elif p > d:
            payout = self.bet * 2
            msg = f"You win {self.bet} chips!"
        elif p < d:
            msg = f"Dealer wins. You lose {self.bet} chips."
        else:
            payout = self.bet
            msg = "Push — your bet is returned."

        self.bankroll += payout
        self.in_round = False
        self.bet = 0
        self._refresh_stats()

        if self.bankroll <= 0:
            msg += "  You're out of credits — buy more from the betting shop."
            wallet.close_game(self.root)

        self._set_message(msg + "  Place a bet for the next hand.")
        self._set_action_state(betting=True)

    # ---------- Helpers ----------
    def _set_action_state(self, betting, can_double=False):
        deal_state = "normal" if betting else "disabled"
        play_state = "disabled" if betting else "normal"
        self.btn_deal.config(state=deal_state)
        self.btn_hit.config(state=play_state)
        self.btn_stand.config(state=play_state)
        self.btn_double.config(state="normal" if (not betting and can_double) else "disabled")
        for b in self.chip_buttons:
            b.config(state="normal" if betting else "disabled")
        self.btn_clear.config(state="normal" if betting else "disabled")

    def _refresh_stats(self):
        wallet.set_credits(self.bankroll)
        self.lbl_bankroll.config(text=f"Chips: {self.bankroll}")
        self.lbl_bet.config(text=f"Current bet: {self.bet}")
        if hasattr(self, "bet_var"):
            self.bet_var.set(str(self.bet))

    def _set_message(self, text):
        self.lbl_msg.config(text=text)


def main():
    root = tk.Tk()
    BlackjackGame(root)
    root.mainloop()


if __name__ == "__main__":
    main()
