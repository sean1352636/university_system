"""
Baccarat (Punto Banco) -- casino-style GUI game.

A self-contained Tkinter game. Requires only the Python standard library.
Run with:  python baccarat.py

You bet on PLAYER, BANKER, or TIE. Two hands are dealt and the standard
third-card ("tableau") rules decide any extra cards. Highest total (mod 10)
wins.

Payouts:
  Player  1 : 1
  Banker  1 : 1  minus 5% commission  (win 0.95x)
  Tie     8 : 1   (Player/Banker bets push on a tie)
"""

import random
import tkinter as tk
try:
    import wallet  # shared credit wallet when launched as a standalone script
except ImportError:  # when imported as part of the betting-shop package
    from education_system.systems.university.interfaces.gui.operations.commerce.betting.games import wallet

# ---------------------------------------------------------------------------
# Cards & baccarat logic (no Tkinter -- pure, testable)
# ---------------------------------------------------------------------------

SUITS = ["\u2660", "\u2665", "\u2666", "\u2663"]
RED_SUITS = {"\u2665", "\u2666"}
RANKS = list(range(2, 15))  # 11=J 12=Q 13=K 14=A
RANK_STR = {**{n: str(n) for n in range(2, 11)}, 11: "J", 12: "Q", 13: "K", 14: "A"}


def make_shoe(n_decks=6):
    shoe = [(r, s) for _ in range(n_decks) for s in SUITS for r in RANKS]
    random.shuffle(shoe)
    return shoe


def card_value(rank):
    """Baccarat pip value: A=1, 2-9 face, 10/J/Q/K = 0."""
    if rank == 14:
        return 1
    if rank >= 10:
        return 0
    return rank


def hand_total(cards):
    return sum(card_value(r) for r, _ in cards) % 10


def play_coup(deck):
    """Deal a full coup following punto-banco rules.

    Returns (reveal_order, player, banker, ptotal, btotal, result)
    where reveal_order is a list of ("P"|"B", card) in dealing sequence and
    result is "player" | "banker" | "tie".
    """
    # Deal order: Player, Banker, Player, Banker
    p1, b1, p2, b2 = deck.pop(), deck.pop(), deck.pop(), deck.pop()
    player = [p1, p2]
    banker = [b1, b2]
    reveal = [("P", p1), ("B", b1), ("P", p2), ("B", b2)]

    pt, bt = hand_total(player), hand_total(banker)
    player_third = None

    # Natural: 8 or 9 on first two cards -> both stand
    if pt < 8 and bt < 8:
        # Player rule
        if pt <= 5:
            player_third = deck.pop()
            player.append(player_third)
            reveal.append(("P", player_third))
            pt = hand_total(player)

        # Banker rule
        draw_banker = False
        if player_third is None:
            draw_banker = bt <= 5
        else:
            v = card_value(player_third[0])  # value of player's 3rd card
            if bt <= 2:
                draw_banker = True
            elif bt == 3:
                draw_banker = v != 8
            elif bt == 4:
                draw_banker = v in (2, 3, 4, 5, 6, 7)
            elif bt == 5:
                draw_banker = v in (4, 5, 6, 7)
            elif bt == 6:
                draw_banker = v in (6, 7)
            else:  # bt == 7
                draw_banker = False

        if draw_banker:
            banker_third = deck.pop()
            banker.append(banker_third)
            reveal.append(("B", banker_third))

    pt, bt = hand_total(player), hand_total(banker)
    if pt > bt:
        result = "player"
    elif bt > pt:
        result = "banker"
    else:
        result = "tie"
    return reveal, player, banker, pt, bt, result


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

CARD_W, CARD_H = 76, 106
FELT = "#0b6b3a"
FELT_DARK = "#075229"
GOLD = "#e9c46a"

START_CHIPS = 500
MIN_BET = 5

BET_TYPES = {
    "player": ("PLAYER", "#1b6fb3"),
    "banker": ("BANKER", "#9b2226"),
    "tie":    ("TIE", "#2d6a4f"),
}


class BaccaratGame:
    def __init__(self, root):
        self.root = root
        root.title("Baccarat \u2014 Punto Banco")
        root.configure(bg=FELT)
        root.resizable(False, False)

        self.chips = wallet.get_credits()
        self.bet_amount = 25
        self.bet_type = tk.StringVar(value="player")
        self.deck = make_shoe()
        self.busy = False

        self._build_ui()
        self.reset_table()
        self.refresh_labels()
        self.log("Place your bet, then press Deal. Good luck!")

    # ---- UI --------------------------------------------------------------
    def _build_ui(self):
        f = tk.Frame(self.root, bg=FELT, padx=18, pady=14)
        f.pack()

        tk.Label(f, text="BANKER", bg=FELT, fg=GOLD,
                 font=("Helvetica", 12, "bold")).pack()
        self.banker_total_lbl = tk.Label(f, text="", bg=FELT, fg="white",
                                         font=("Helvetica", 12, "bold"))
        self.banker_total_lbl.pack()
        self.banker_cards = self._card_row(f)

        # centre panel
        mid = tk.Frame(f, bg=FELT_DARK, padx=12, pady=8)
        mid.pack(fill="x", pady=10)
        self.result_lbl = tk.Label(mid, text="", bg=FELT_DARK, fg=GOLD,
                                   font=("Helvetica", 15, "bold"))
        self.result_lbl.pack()
        self.log_box = tk.Text(mid, height=3, width=54, bg=FELT_DARK, fg="white",
                               bd=0, font=("Helvetica", 10), state="disabled",
                               highlightthickness=0, wrap="word")
        self.log_box.pack()

        self.player_cards = self._card_row(f)
        self.player_total_lbl = tk.Label(f, text="", bg=FELT, fg="white",
                                         font=("Helvetica", 12, "bold"))
        self.player_total_lbl.pack()
        tk.Label(f, text="PLAYER", bg=FELT, fg=GOLD,
                 font=("Helvetica", 12, "bold")).pack()

        # bet-type selector
        betsel = tk.Frame(f, bg=FELT, pady=8)
        betsel.pack()
        for key, (label, color) in BET_TYPES.items():
            payout = {"player": "1:1", "banker": "0.95:1", "tie": "8:1"}[key]
            tk.Radiobutton(betsel, text=f"{label}\n{payout}", value=key,
                           variable=self.bet_type, indicatoron=False, width=10,
                           height=2, font=("Helvetica", 11, "bold"),
                           bg=color, fg="white", selectcolor=GOLD,
                           activebackground=GOLD, bd=0).pack(side="left", padx=6)

        # amount + chips
        amt = tk.Frame(f, bg=FELT, pady=4)
        amt.pack()
        self.chip_lbl = tk.Label(amt, text="", bg=FELT, fg="white",
                                 font=("Helvetica", 13, "bold"))
        self.chip_lbl.pack(side="left", padx=12)
        tk.Button(amt, text="\u2212", command=lambda: self.change_bet(-MIN_BET),
                  width=3, font=("Helvetica", 12, "bold"), bg="#333", fg="white",
                  bd=0).pack(side="left")
        tk.Label(amt, text="Bet:", bg=FELT, fg=GOLD,
                 font=("Helvetica", 13, "bold")).pack(side="left", padx=(6, 2))
        self.bet_var = tk.StringVar()
        self.bet_entry = tk.Entry(amt, textvariable=self.bet_var, width=6,
                                  justify="center", font=("Helvetica", 13, "bold"),
                                  bg="#0d2846", fg=GOLD, insertbackground=GOLD,
                                  relief="flat", bd=2)
        self.bet_entry.pack(side="left")
        self.bet_entry.bind("<Return>", lambda e: self.set_bet())
        self.bet_entry.bind("<FocusOut>", lambda e: self.set_bet())
        tk.Button(amt, text="+", command=lambda: self.change_bet(MIN_BET),
                  width=3, font=("Helvetica", 12, "bold"), bg="#333", fg="white",
                  bd=0).pack(side="left")

        # action buttons
        act = tk.Frame(f, bg=FELT, pady=10)
        act.pack()
        self.deal_btn = tk.Button(act, text="Deal", command=self.deal,
                                  font=("Helvetica", 13, "bold"), width=14,
                                  bg="#1b7a4b", fg="white", activebackground=GOLD,
                                  bd=0, pady=6, cursor="hand2")
        self.deal_btn.pack()

    def _card_row(self, parent):
        row = tk.Frame(parent, bg=FELT)
        row.pack(pady=4)
        cvs = []
        for _ in range(3):  # up to 3 cards per hand
            c = tk.Canvas(row, width=CARD_W, height=CARD_H, bg=FELT,
                          highlightthickness=0)
            c.pack(side="left", padx=5)
            cvs.append(c)
        return cvs

    # ---- card drawing ----------------------------------------------------
    def _draw_card(self, canvas, card):
        canvas.delete("all")
        if card is None:
            canvas.create_rectangle(4, 4, CARD_W - 4, CARD_H - 4, outline="#0a5a30",
                                    dash=(3, 3))
            return
        canvas.create_rectangle(3, 3, CARD_W - 3, CARD_H - 3, fill="white",
                                outline="#222")
        rank, suit = card
        color = "#c0392b" if suit in RED_SUITS else "#111"
        rs = RANK_STR[rank]
        canvas.create_text(14, 15, text=rs, fill=color, font=("Helvetica", 12, "bold"))
        canvas.create_text(14, 30, text=suit, fill=color, font=("Helvetica", 11))
        canvas.create_text(CARD_W / 2, CARD_H / 2, text=suit, fill=color,
                           font=("Helvetica", 26, "bold"))
        canvas.create_text(CARD_W - 14, CARD_H - 15, text=rs, fill=color,
                           font=("Helvetica", 12, "bold"))

    # ---- betting ---------------------------------------------------------
    def change_bet(self, delta):
        if self.busy:
            return
        self.bet_amount = max(MIN_BET, min(self.chips, self.bet_amount + delta))
        self.refresh_labels()

    def set_bet(self):
        """Set the bet to the amount typed into the entry box."""
        try:
            self.change_bet(int(float(self.bet_var.get())) - self.bet_amount)
        except (TypeError, ValueError):
            pass
        self.bet_var.set(str(self.bet_amount))

    def refresh_labels(self):
        wallet.set_credits(self.chips)
        self.chip_lbl.config(text=f"Chips: {self.chips}")
        self.bet_var.set(str(self.bet_amount))

    def reset_table(self):
        self._pcards = [None, None, None]
        self._bcards = [None, None, None]
        for i in range(3):
            self._draw_card(self.player_cards[i], None)
            self._draw_card(self.banker_cards[i], None)
        self.player_total_lbl.config(text="")
        self.banker_total_lbl.config(text="")

    # ---- deal / reveal ---------------------------------------------------
    def deal(self):
        if self.busy:
            return
        if self.bet_amount > self.chips:
            self.log("Not enough chips for that bet.")
            return
        if len(self.deck) < 30:
            self.deck = make_shoe()
            self.log("Shuffling a fresh shoe.")

        self.busy = True
        self.deal_btn.config(state="disabled")
        self.result_lbl.config(text="")
        self.reset_table()

        reveal, player, banker, pt, bt, result = play_coup(self.deck)
        self.final = (player, banker, pt, bt, result)
        self.reveal_queue = reveal
        self._pi = self._bi = 0
        self._reveal_step()

    def _reveal_step(self):
        if not self.reveal_queue:
            self._settle()
            return
        side, card = self.reveal_queue.pop(0)
        if side == "P":
            self._pcards[self._pi] = card
            self._draw_card(self.player_cards[self._pi], card)
            self._pi += 1
            self.player_total_lbl.config(
                text=f"Total: {hand_total([c for c in self._pcards if c])}")
        else:
            self._bcards[self._bi] = card
            self._draw_card(self.banker_cards[self._bi], card)
            self._bi += 1
            self.banker_total_lbl.config(
                text=f"Total: {hand_total([c for c in self._bcards if c])}")
        self.root.after(650, self._reveal_step)

    def _settle(self):
        player, banker, pt, bt, result = self.final
        bet = self.bet_amount
        choice = self.bet_type.get()

        # deduct the stake first
        self.chips -= bet
        net = -bet  # net change including the stake already removed

        if result == "tie":
            if choice == "tie":
                self.chips += bet + bet * 8            # stake back + 8:1
                net = bet * 8
            else:
                self.chips += bet                      # push, stake returned
                net = 0
        else:
            won = (choice == result)
            if choice == "tie":
                won = False
            if won:
                if choice == "banker":
                    winnings = int(round(bet * 0.95))  # 5% commission
                else:
                    winnings = bet
                self.chips += bet + winnings
                net = winnings

        names = {"player": "PLAYER", "banker": "BANKER", "tie": "TIE"}
        headline = {"player": "Player wins", "banker": "Banker wins",
                    "tie": "Tie"}[result]
        self.result_lbl.config(text=f"{headline}   \u2014   {pt} vs {bt}")

        if net > 0:
            self.log(f"{headline} ({pt}\u2013{bt}). You bet {names[choice]} "
                     f"and won {net}.")
        elif net == 0:
            self.log(f"{headline} ({pt}\u2013{bt}). Your {names[choice]} "
                     f"bet pushes.")
        else:
            self.log(f"{headline} ({pt}\u2013{bt}). Your {names[choice]} "
                     f"bet loses {bet}.")

        if self.chips < MIN_BET:
            self.log("You're out of credits! Buy more credits to keep playing.")
            wallet.close_game(self.root)
        self.bet_amount = min(self.bet_amount, self.chips)
        self.refresh_labels()

        self.busy = False
        self.deal_btn.config(state="normal")

    # ---- log -------------------------------------------------------------
    def log(self, msg):
        self.log_box.config(state="normal")
        self.log_box.insert("end", msg + "\n")
        self.log_box.see("end")
        self.log_box.config(state="disabled")


def main():
    root = tk.Tk()
    BaccaratGame(root)
    root.mainloop()


if __name__ == "__main__":
    main()
