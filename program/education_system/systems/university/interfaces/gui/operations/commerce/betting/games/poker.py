"""
Five Card Draw Poker -- heads-up against the computer.

A self-contained Tkinter GUI game. Requires only the Python standard library.
Run with:  python poker.py

Rules implemented:
  * Heads-up (you vs. the computer), fixed-limit betting.
  * Each hand: both players ante, get 5 cards, bet, draw, bet again, showdown.
  * Standard poker hand rankings (high card up to straight/royal flush).
  * The computer draws sensibly and bets/bluffs based on hand strength.
"""

import random
import tkinter as tk
try:
    import wallet  # shared credit wallet when launched as a standalone script
except ImportError:  # when imported as part of the betting-shop package
    from education_system.systems.university.interfaces.gui.operations.commerce.betting.games import wallet
from collections import Counter

# ---------------------------------------------------------------------------
# Cards & hand evaluation  (no Tkinter here -- pure logic, easy to test)
# ---------------------------------------------------------------------------

SUITS = ["\u2660", "\u2665", "\u2666", "\u2663"]  # spade heart diamond club
RED_SUITS = {"\u2665", "\u2666"}
RANKS = list(range(2, 15))  # 2..14, where 11=J 12=Q 13=K 14=A

RANK_STR = {**{n: str(n) for n in range(2, 11)}, 11: "J", 12: "Q", 13: "K", 14: "A"}
RANK_NAME = {2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six", 7: "Seven",
             8: "Eight", 9: "Nine", 10: "Ten", 11: "Jack", 12: "Queen",
             13: "King", 14: "Ace"}
RANK_PLURAL = {2: "Twos", 3: "Threes", 4: "Fours", 5: "Fives", 6: "Sixes",
               7: "Sevens", 8: "Eights", 9: "Nines", 10: "Tens", 11: "Jacks",
               12: "Queens", 13: "Kings", 14: "Aces"}

# Hand categories (higher is better)
HIGH, PAIR, TWO_PAIR, THREE, STRAIGHT, FLUSH, FULL_HOUSE, FOUR, STR_FLUSH = range(9)


def make_deck():
    return [(r, s) for s in SUITS for r in RANKS]


def straight_high(ranks):
    """Return the high card of a straight, or None. Handles the wheel (A-2-3-4-5)."""
    s = set(ranks)
    if len(s) != 5:
        return None
    hi, lo = max(s), min(s)
    if hi - lo == 4:
        return hi
    if s == {14, 2, 3, 4, 5}:  # ace-low straight
        return 5
    return None


def analyze(hand):
    """Analyze a 5-card hand.

    Returns a dict with:
      key  -- a comparable tuple; bigger key == better hand
      name -- human readable description
    """
    ranks = sorted((c[0] for c in hand), reverse=True)
    suits = [c[1] for c in hand]
    counts = Counter(ranks)
    # groups sorted by (count, rank) descending -> pairs/trips first
    groups = sorted(counts.items(), key=lambda kv: (kv[1], kv[0]), reverse=True)
    shape = [g[1] for g in groups]           # e.g. [3, 2] for a full house
    by_group = [g[0] for g in groups]         # ranks in group order
    is_flush = len(set(suits)) == 1
    sh = straight_high(ranks)

    if sh and is_flush:
        cat, tb = STR_FLUSH, (sh,)
        name = "Royal Flush" if sh == 14 else f"{RANK_NAME[sh]}-high Straight Flush"
    elif shape[0] == 4:
        quad, kick = by_group[0], by_group[1]
        cat, tb = FOUR, (quad, kick)
        name = f"Four of a Kind, {RANK_PLURAL[quad]}"
    elif shape[:2] == [3, 2]:
        trip, pair = by_group[0], by_group[1]
        cat, tb = FULL_HOUSE, (trip, pair)
        name = f"Full House, {RANK_PLURAL[trip]} full of {RANK_PLURAL[pair]}"
    elif is_flush:
        cat, tb = FLUSH, tuple(ranks)
        name = f"{RANK_NAME[ranks[0]]}-high Flush"
    elif sh:
        cat, tb = STRAIGHT, (sh,)
        name = f"{RANK_NAME[sh]}-high Straight"
    elif shape[0] == 3:
        trip = by_group[0]
        kickers = sorted(by_group[1:], reverse=True)
        cat, tb = THREE, (trip, *kickers)
        name = f"Three of a Kind, {RANK_PLURAL[trip]}"
    elif shape[:2] == [2, 2]:
        hp, lp = sorted(by_group[:2], reverse=True)
        kick = by_group[2]
        cat, tb = TWO_PAIR, (hp, lp, kick)
        name = f"Two Pair, {RANK_PLURAL[hp]} and {RANK_PLURAL[lp]}"
    elif shape[0] == 2:
        pair = by_group[0]
        kickers = sorted(by_group[1:], reverse=True)
        cat, tb = PAIR, (pair, *kickers)
        name = f"Pair of {RANK_PLURAL[pair]}"
    else:
        cat, tb = HIGH, tuple(ranks)
        name = f"{RANK_NAME[ranks[0]]} High"

    return {"key": (cat, *tb), "category": cat, "name": name}


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

CARD_W, CARD_H = 84, 118
FELT = "#0b6b3a"
FELT_DARK = "#075229"
GOLD = "#e9c46a"
CARD_BACK = "#1d3a63"

START_CHIPS = 500
ANTE = 10
BET_SIZE = 20
MAX_RAISES = 3


class PokerGame:
    def __init__(self, root):
        self.root = root
        root.title("Five Card Draw \u2014 vs. Computer")
        root.configure(bg=FELT)
        root.resizable(False, False)

        self.player_chips = wallet.get_credits()
        self.ai_chips = START_CHIPS

        # Hand state (populated once a hand is dealt). Initialised here so an
        # immediate match_over -> render (e.g. starting with too few credits to
        # ante) does not reference cards that have not been dealt yet.
        self.player_hand = []
        self.ai_hand = []
        self.held = [False] * 5
        self.reveal_ai = False
        self.pot = 0
        self.phase = "idle"

        self._build_ui()
        self.new_match()

    # ---- UI construction -------------------------------------------------
    def _build_ui(self):
        f = tk.Frame(self.root, bg=FELT, padx=18, pady=14)
        f.pack()

        # Computer area
        top = tk.Frame(f, bg=FELT)
        top.pack(fill="x")
        self.ai_chip_lbl = tk.Label(top, text="", bg=FELT, fg="white",
                                    font=("Helvetica", 13, "bold"))
        self.ai_chip_lbl.pack(side="left")
        self.ai_hand_lbl = tk.Label(top, text="", bg=FELT, fg=GOLD,
                                    font=("Helvetica", 12, "italic"))
        self.ai_hand_lbl.pack(side="right")

        self.ai_cards = self._card_row(f)

        # Middle: pot + message log
        mid = tk.Frame(f, bg=FELT_DARK, padx=12, pady=8)
        mid.pack(fill="x", pady=10)
        self.pot_lbl = tk.Label(mid, text="", bg=FELT_DARK, fg=GOLD,
                                font=("Helvetica", 16, "bold"))
        self.pot_lbl.pack()
        self.log_box = tk.Text(mid, height=4, width=52, bg=FELT_DARK, fg="white",
                               bd=0, font=("Helvetica", 10), state="disabled",
                               highlightthickness=0, wrap="word")
        self.log_box.pack()

        # Player cards
        self.player_cards = self._card_row(f)
        for i, c in enumerate(self.player_cards):
            c.bind("<Button-1>", lambda e, idx=i: self.toggle_hold(idx))

        bottom = tk.Frame(f, bg=FELT)
        bottom.pack(fill="x")
        self.player_hand_lbl = tk.Label(bottom, text="", bg=FELT, fg=GOLD,
                                        font=("Helvetica", 12, "italic"))
        self.player_hand_lbl.pack(side="right")
        self.player_chip_lbl = tk.Label(bottom, text="", bg=FELT, fg="white",
                                        font=("Helvetica", 13, "bold"))
        self.player_chip_lbl.pack(side="left")

        # Action buttons
        self.action_frame = tk.Frame(f, bg=FELT, pady=8)
        self.action_frame.pack()

    def _card_row(self, parent):
        row = tk.Frame(parent, bg=FELT)
        row.pack(pady=4)
        canvases = []
        for _ in range(5):
            c = tk.Canvas(row, width=CARD_W, height=CARD_H + 16, bg=FELT,
                          highlightthickness=0)
            c.pack(side="left", padx=5)
            canvases.append(c)
        return canvases

    # ---- Card drawing ----------------------------------------------------
    def _draw_card(self, canvas, card, face_up=True, held=False):
        canvas.delete("all")
        y0 = 16  # leave room above for the HOLD tag
        if held:
            canvas.create_text(CARD_W / 2, 8, text="HOLD", fill=GOLD,
                               font=("Helvetica", 9, "bold"))
        if face_up:
            canvas.create_rectangle(3, y0, CARD_W - 3, CARD_H + 12,
                                    fill="white", outline="#222", width=1)
            rank, suit = card
            color = "#c0392b" if suit in RED_SUITS else "#111"
            rs = RANK_STR[rank]
            canvas.create_text(15, y0 + 14, text=rs, fill=color,
                               font=("Helvetica", 13, "bold"))
            canvas.create_text(15, y0 + 30, text=suit, fill=color,
                               font=("Helvetica", 12))
            canvas.create_text(CARD_W / 2, y0 + CARD_H / 2, text=suit, fill=color,
                               font=("Helvetica", 30, "bold"))
            canvas.create_text(CARD_W - 15, CARD_H + 12 - 14, text=rs, fill=color,
                               font=("Helvetica", 13, "bold"))
        else:
            canvas.create_rectangle(3, y0, CARD_W - 3, CARD_H + 12,
                                    fill=CARD_BACK, outline="#222", width=1)
            for gx in range(14, CARD_W - 8, 12):
                canvas.create_line(gx, y0 + 4, gx, CARD_H + 8, fill="#33578f")
            for gy in range(y0 + 8, CARD_H + 10, 12):
                canvas.create_line(8, gy, CARD_W - 8, gy, fill="#33578f")
        if held:
            canvas.create_rectangle(3, y0, CARD_W - 3, CARD_H + 12,
                                    outline=GOLD, width=3)

    # ---- Match / hand lifecycle -----------------------------------------
    def new_match(self):
        self.player_chips = wallet.get_credits()
        self.ai_chips = START_CHIPS
        self.log_clear()
        self.log("Welcome! You and the computer each start with "
                 f"{START_CHIPS} chips.")
        self.deal_new_hand()

    def deal_new_hand(self):
        if self.player_chips < ANTE or self.ai_chips < ANTE:
            self.match_over()
            return

        self.deck = make_deck()
        random.shuffle(self.deck)
        self.player_hand = [self.deck.pop() for _ in range(5)]
        self.ai_hand = [self.deck.pop() for _ in range(5)]
        self.held = [False] * 5
        self.reveal_ai = False
        self.pot = 0
        self.committed = {"player": 0, "ai": 0}
        self.raise_count = 0
        self.phase = "bet1"

        # antes
        self._to_pot("player", ANTE)
        self._to_pot("ai", ANTE)
        self.log(f"\u2014 New hand \u2014 both ante {ANTE}.")

        self.render()
        self.update_actions()  # player acts first

    # ---- Chip helpers ----------------------------------------------------
    def _to_pot(self, who, amount):
        """Move up to `amount` chips from a player into the pot. Returns actual."""
        stack = self.player_chips if who == "player" else self.ai_chips
        actual = max(0, min(amount, stack))
        if who == "player":
            self.player_chips -= actual
        else:
            self.ai_chips -= actual
        self.pot += actual
        return actual

    def contribute(self, who, amount):
        actual = self._to_pot(who, amount)
        self.committed[who] += actual

    def to_call(self, who):
        level = max(self.committed.values())
        return level - self.committed[who]

    # ---- Player betting actions -----------------------------------------
    def player_check(self):
        self.log("You check.")
        self.ai_bet_step()

    def player_bet(self):
        self.contribute("player", BET_SIZE)
        self.raise_count += 1
        self.log(f"You bet {BET_SIZE}.")
        self.render()
        self.ai_bet_step()

    def player_call(self):
        amt = self.to_call("player")
        self.contribute("player", amt)
        self.log(f"You call {amt}.")
        self.render()
        self.end_betting_round()

    def player_raise(self):
        amt = self.to_call("player") + BET_SIZE
        self.contribute("player", amt)
        self.raise_count += 1
        self.log(f"You raise {BET_SIZE}.")
        self.render()
        self.ai_bet_step()

    def player_fold(self):
        self.log("You fold.")
        self.finish_hand(winner="ai")

    # ---- Computer betting ------------------------------------------------
    def ai_betting_action(self, to_call):
        cat = analyze(self.ai_hand)["category"]
        strong = cat >= TWO_PAIR      # two pair or better
        medium = cat == PAIR
        r = random.random()

        if to_call == 0:  # option to check or bet
            if strong:
                return ("bet", BET_SIZE) if r < 0.80 else ("check", 0)
            if medium:
                return ("bet", BET_SIZE) if r < 0.40 else ("check", 0)
            return ("bet", BET_SIZE) if r < 0.15 else ("check", 0)  # bluff sometimes
        else:            # facing a bet
            can_raise = self.raise_count < MAX_RAISES and self.ai_chips > 0
            if strong:
                if can_raise and r < 0.5:
                    return ("raise", BET_SIZE)
                return ("call", to_call)
            if medium:
                return ("call", to_call) if r < 0.70 else ("fold", 0)
            return ("call", to_call) if r < 0.20 else ("fold", 0)  # occasional bluff-catch

    def ai_bet_step(self):
        tc = self.to_call("ai")
        act, _ = self.ai_betting_action(tc)

        if act == "fold":
            self.log("Computer folds.")
            self.finish_hand(winner="player")
            return
        if act == "check":
            self.log("Computer checks.")
            self.end_betting_round()
            return
        if act == "call":
            self.contribute("ai", tc)
            self.log(f"Computer calls {tc}.")
            self.render()
            self.end_betting_round()
            return
        # bet or raise
        self.contribute("ai", tc + BET_SIZE)
        self.raise_count += 1
        self.log(f"Computer {'bets' if act == 'bet' else 'raises'} {BET_SIZE}.")
        self.render()
        self.update_actions()  # back to the player to respond

    def end_betting_round(self):
        if self.phase == "bet1":
            self.enter_draw()
        else:  # bet2
            self.finish_hand()

    # ---- Draw phase ------------------------------------------------------
    def enter_draw(self):
        self.phase = "draw"
        self.raise_count = 0
        self.committed = {"player": 0, "ai": 0}
        self.log("Draw phase: click cards to HOLD, then press Draw.")
        self.render()
        self.update_actions()

    def toggle_hold(self, idx):
        if self.phase != "draw":
            return
        self.held[idx] = not self.held[idx]
        self.render()

    def do_draw(self):
        # replace the player's non-held cards
        drawn = 0
        for i in range(5):
            if not self.held[i]:
                self.player_hand[i] = self.deck.pop()
                drawn += 1
        self.log(f"You draw {drawn} card{'s' if drawn != 1 else ''}.")

        self.ai_draw()

        self.phase = "bet2"
        self.render()
        self.log("Final betting round.")
        self.update_actions()

    def ai_draw(self):
        info = analyze(self.ai_hand)
        cat = info["category"]
        hand = self.ai_hand
        ranks = [c[0] for c in hand]
        suits = [c[1] for c in hand]
        counts = Counter(ranks)

        if cat in (STRAIGHT, FLUSH, FULL_HOUSE, STR_FLUSH):
            keep = set(range(5))                       # made hand, stand pat
        elif cat == FOUR:
            keep = {i for i in range(5) if counts[hand[i][0]] == 4}
        elif cat in (THREE, TWO_PAIR, PAIR):
            keep = {i for i in range(5) if counts[hand[i][0]] >= 2}
        else:  # high card: chase a flush/straight draw or hold high cards
            suit_counts = Counter(suits)
            flush_suit = next((s for s, n in suit_counts.items() if n >= 4), None)
            if flush_suit:
                keep = {i for i in range(5) if hand[i][1] == flush_suit}
            else:
                keep = self._four_to_straight(ranks)
                if not keep:
                    order = sorted(range(5), key=lambda i: hand[i][0], reverse=True)
                    highs = [i for i in order if hand[i][0] >= 11]
                    keep = set(highs[:2]) if highs else {order[0]}

        drawn = 0
        for i in range(5):
            if i not in keep:
                self.ai_hand[i] = self.deck.pop()
                drawn += 1
        self.log(f"Computer draws {drawn} card{'s' if drawn != 1 else ''}.")

    @staticmethod
    def _four_to_straight(ranks):
        """Return indices of 4 cards forming an open/one-gap straight draw, else set()."""
        best = set()
        uniq = sorted(set(ranks))
        for i in range(len(uniq)):
            for j in range(i, len(uniq)):
                window = [r for r in uniq if uniq[i] <= r <= uniq[j]]
                if uniq[j] - uniq[i] <= 4 and len(window) >= 4:
                    idxs = set()
                    used = set()
                    for r in window:
                        for k, rr in enumerate(ranks):
                            if rr == r and k not in used:
                                idxs.add(k)
                                used.add(k)
                                break
                    if len(idxs) >= 4 and len(idxs) > len(best):
                        best = set(list(idxs)[:4]) if len(idxs) > 4 else idxs
        return best

    # ---- Showdown / results ---------------------------------------------
    def finish_hand(self, winner=None):
        self.phase = "showdown"
        self.reveal_ai = True

        if winner == "ai":
            self.ai_chips += self.pot
            self.log(f"Computer wins {self.pot} chips.")
        elif winner == "player":
            self.player_chips += self.pot
            self.log(f"You win {self.pot} chips!")
        else:
            pk = analyze(self.player_hand)
            ak = analyze(self.ai_hand)
            self.log(f"You: {pk['name']}.  Computer: {ak['name']}.")
            if pk["key"] > ak["key"]:
                self.player_chips += self.pot
                self.log(f"You win {self.pot} chips with {pk['name']}!")
            elif pk["key"] < ak["key"]:
                self.ai_chips += self.pot
                self.log(f"Computer wins {self.pot} with {ak['name']}.")
            else:
                half = self.pot // 2
                self.player_chips += self.pot - half
                self.ai_chips += half
                self.log(f"Split pot! Each takes about {half}.")

        self.pot = 0
        self.render()
        self.update_actions()

    def match_over(self):
        self.phase = "gameover"
        self.reveal_ai = True
        if self.player_chips >= self.ai_chips:
            self.log("You've bankrupted the computer. You win the match!")
        else:
            self.log("You're out of chips. The computer wins the match.")
            wallet.close_game(self.root)
        self.render()
        self.update_actions()

    # ---- Rendering -------------------------------------------------------
    def render(self):
        wallet.set_credits(self.player_chips)
        has_hands = len(self.player_hand) == 5 and len(self.ai_hand) == 5
        if has_hands:
            for i in range(5):
                self._draw_card(self.ai_cards[i], self.ai_hand[i],
                                face_up=self.reveal_ai)
                self._draw_card(self.player_cards[i], self.player_hand[i],
                                face_up=True, held=self.held[i] and self.phase == "draw")

        self.ai_chip_lbl.config(text=f"Computer:  {self.ai_chips} chips")
        self.player_chip_lbl.config(text=f"You:  {self.player_chips} chips")
        self.pot_lbl.config(text=f"POT:  {self.pot}")

        if has_hands and self.phase in ("showdown", "gameover"):
            self.ai_hand_lbl.config(text=analyze(self.ai_hand)["name"])
        else:
            self.ai_hand_lbl.config(text="")
        self.player_hand_lbl.config(text=analyze(self.player_hand)["name"] if has_hands else "")

    def update_actions(self):
        for w in self.action_frame.winfo_children():
            w.destroy()

        def btn(text, cmd, color="#2d6a4f"):
            b = tk.Button(self.action_frame, text=text, command=cmd,
                          font=("Helvetica", 12, "bold"), width=12,
                          bg=color, fg="white", activebackground=GOLD,
                          bd=0, padx=6, pady=6, cursor="hand2")
            b.pack(side="left", padx=6)
            return b

        if self.phase in ("bet1", "bet2"):
            tc = self.to_call("player")
            if tc == 0:
                btn("Check", self.player_check)
                if self.player_chips > 0:
                    btn(f"Bet {BET_SIZE}", self.player_bet, "#1b7a4b")
            else:
                btn(f"Call {tc}", self.player_call, "#1b7a4b")
                if self.raise_count < MAX_RAISES and self.player_chips > tc:
                    btn(f"Raise {BET_SIZE}", self.player_raise, "#1b7a4b")
                btn("Fold", self.player_fold, "#9b2226")
        elif self.phase == "draw":
            btn("Draw", self.do_draw, "#1b7a4b")
        elif self.phase == "showdown":
            btn("Next Hand", self.deal_new_hand, "#1b7a4b")
        elif self.phase == "gameover":
            btn("New Match", self.new_match, "#1b7a4b")

    # ---- Message log -----------------------------------------------------
    def log(self, msg):
        self.log_box.config(state="normal")
        self.log_box.insert("end", msg + "\n")
        self.log_box.see("end")
        # keep it from growing without bound
        lines = int(self.log_box.index("end-1c").split(".")[0])
        if lines > 200:
            self.log_box.delete("1.0", "50.0")
        self.log_box.config(state="disabled")

    def log_clear(self):
        self.log_box.config(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.config(state="disabled")


def main():
    root = tk.Tk()
    PokerGame(root)
    root.mainloop()


if __name__ == "__main__":
    main()
