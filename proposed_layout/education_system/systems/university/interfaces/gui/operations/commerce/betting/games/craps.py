"""
Craps -- casino-style GUI dice game.

A self-contained Tkinter game. Requires only the Python standard library.
Run with:  python craps.py

Bets supported:
  PASS LINE   -- come-out: win on 7/11, lose on 2/3/12; else a point is set.
                 point phase: roll the point to win, roll a 7 to lose.  1:1
  DON'T PASS  -- the reverse. Come-out: win 2/3, lose 7/11, push 12.
                 point phase: 7 before the point wins.               1:1
  FIELD       -- one-roll bet. Wins on 2,3,4,9,10,11,12 (2 & 12 pay 2:1);
                 loses on 5,6,7,8.

Pass / Don't Pass can only be placed on the come-out roll. Field can be
placed before any roll.
"""

import random
import tkinter as tk
try:
    import wallet  # shared credit wallet when launched as a standalone script
except ImportError:  # when imported as part of the betting-shop package
    from education_system.systems.university.interfaces.gui.operations.commerce.betting.games import wallet

# ---------------------------------------------------------------------------
# Dice logic (pure, testable)
# ---------------------------------------------------------------------------

def roll_dice():
    return random.randint(1, 6), random.randint(1, 6)


def field_payout(total):
    """Return profit multiplier for a 1-unit field bet, or -1 for a loss."""
    if total in (2, 12):
        return 2      # pays 2:1
    if total in (3, 4, 9, 10, 11):
        return 1      # pays 1:1
    return -1         # 5,6,7,8 lose


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

FELT = "#0b6b3a"
FELT_DARK = "#075229"
GOLD = "#e9c46a"
DIE_SIZE = 88

START_CHIPS = 500
MIN_BET = 5


class CrapsGame:
    def __init__(self, root):
        self.root = root
        root.title("Craps")
        root.configure(bg=FELT)
        root.resizable(False, False)

        self.chips = wallet.get_credits()
        self.bet_amount = 25
        self.point = None                 # None on the come-out roll
        self.bets = {"pass": 0, "dont": 0, "field": 0}
        self.busy = False

        self._build_ui()
        self.refresh()
        self.log("Come-out roll. Place a bet, then Roll the dice.")

    # ---- UI --------------------------------------------------------------
    def _build_ui(self):
        f = tk.Frame(self.root, bg=FELT, padx=20, pady=16)
        f.pack()

        # point indicator
        self.point_lbl = tk.Label(f, text="", bg=FELT, fg=GOLD,
                                  font=("Helvetica", 15, "bold"))
        self.point_lbl.pack()

        # dice
        dice = tk.Frame(f, bg=FELT)
        dice.pack(pady=10)
        self.die1 = tk.Canvas(dice, width=DIE_SIZE, height=DIE_SIZE, bg=FELT,
                              highlightthickness=0)
        self.die1.pack(side="left", padx=10)
        self.die2 = tk.Canvas(dice, width=DIE_SIZE, height=DIE_SIZE, bg=FELT,
                              highlightthickness=0)
        self.die2.pack(side="left", padx=10)
        self._draw_die(self.die1, 1)
        self._draw_die(self.die2, 1)

        # centre panel
        mid = tk.Frame(f, bg=FELT_DARK, padx=12, pady=8)
        mid.pack(fill="x", pady=8)
        self.total_lbl = tk.Label(mid, text="", bg=FELT_DARK, fg=GOLD,
                                  font=("Helvetica", 15, "bold"))
        self.total_lbl.pack()
        self.log_box = tk.Text(mid, height=3, width=54, bg=FELT_DARK, fg="white",
                               bd=0, font=("Helvetica", 10), state="disabled",
                               highlightthickness=0, wrap="word")
        self.log_box.pack()

        # bet spots
        spots = tk.Frame(f, bg=FELT, pady=6)
        spots.pack()
        self.spot_lbls = {}
        specs = [("pass", "PASS LINE", "#1b6fb3"),
                 ("dont", "DON'T PASS", "#9b2226"),
                 ("field", "FIELD", "#6a4c93")]
        for key, label, color in specs:
            col = tk.Frame(spots, bg=FELT)
            col.pack(side="left", padx=8)
            tk.Button(col, text=label, width=12, height=2,
                      font=("Helvetica", 11, "bold"), bg=color, fg="white",
                      activebackground=GOLD, bd=0, cursor="hand2",
                      command=lambda k=key: self.place_bet(k)).pack()
            lbl = tk.Label(col, text="0", bg=FELT, fg=GOLD,
                           font=("Helvetica", 12, "bold"))
            lbl.pack()
            self.spot_lbls[key] = lbl

        # amount + chips
        amt = tk.Frame(f, bg=FELT, pady=6)
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

        # actions
        act = tk.Frame(f, bg=FELT, pady=10)
        act.pack()
        self.roll_btn = tk.Button(act, text="Roll Dice", command=self.roll,
                                  font=("Helvetica", 13, "bold"), width=14,
                                  bg="#1b7a4b", fg="white", activebackground=GOLD,
                                  bd=0, pady=6, cursor="hand2")
        self.roll_btn.pack(side="left", padx=6)
        self.clear_btn = tk.Button(act, text="Clear Bets", command=self.clear_bets,
                                   font=("Helvetica", 13, "bold"), width=12,
                                   bg="#555", fg="white", activebackground=GOLD,
                                   bd=0, pady=6, cursor="hand2")
        self.clear_btn.pack(side="left", padx=6)

    # ---- dice drawing ----------------------------------------------------
    def _draw_die(self, canvas, value):
        canvas.delete("all")
        s = DIE_SIZE
        canvas.create_rectangle(6, 6, s - 6, s - 6, fill="white", outline="#222",
                                width=2)
        r = 8
        # pip positions on a 3x3 grid
        lo, mid, hi = s * 0.30, s * 0.5, s * 0.70
        pips = {
            1: [(mid, mid)],
            2: [(lo, lo), (hi, hi)],
            3: [(lo, lo), (mid, mid), (hi, hi)],
            4: [(lo, lo), (hi, lo), (lo, hi), (hi, hi)],
            5: [(lo, lo), (hi, lo), (mid, mid), (lo, hi), (hi, hi)],
            6: [(lo, lo), (hi, lo), (lo, mid), (hi, mid), (lo, hi), (hi, hi)],
        }[value]
        for x, y in pips:
            canvas.create_oval(x - r, y - r, x + r, y + r, fill="#111", outline="")

    # ---- betting ---------------------------------------------------------
    def change_bet(self, delta):
        if self.busy:
            return
        self.bet_amount = max(MIN_BET, self.bet_amount + delta)
        self.refresh()

    def set_bet(self):
        """Set the bet to the amount typed into the entry box."""
        try:
            self.change_bet(int(float(self.bet_var.get())) - self.bet_amount)
        except (TypeError, ValueError):
            pass
        self.bet_var.set(str(self.bet_amount))

    def place_bet(self, key):
        if self.busy:
            return
        if key in ("pass", "dont") and self.point is not None:
            self.log("Line bets can only be placed on the come-out roll.")
            return
        if self.bet_amount > self.chips:
            self.log("Not enough chips for that bet.")
            return
        self.chips -= self.bet_amount
        self.bets[key] += self.bet_amount
        self.refresh()

    def clear_bets(self):
        if self.busy:
            return
        # refund field always; refund line bets only on the come-out
        refundable = ["field"]
        if self.point is None:
            refundable += ["pass", "dont"]
        for k in refundable:
            self.chips += self.bets[k]
            self.bets[k] = 0
        self.refresh()

    def refresh(self):
        wallet.set_credits(self.chips)
        self.chip_lbl.config(text=f"Chips: {self.chips}")
        self.bet_var.set(str(self.bet_amount))
        for k, lbl in self.spot_lbls.items():
            lbl.config(text=str(self.bets[k]))
        if self.point is None:
            self.point_lbl.config(text="COME-OUT ROLL  \u2022  point OFF")
        else:
            self.point_lbl.config(text=f"POINT IS {self.point}  \u2022  ON")

    # ---- rolling ---------------------------------------------------------
    def roll(self):
        if self.busy:
            return
        if sum(self.bets.values()) == 0:
            self.log("Place at least one bet before rolling.")
            return
        self.busy = True
        self.roll_btn.config(state="disabled")
        self.clear_btn.config(state="disabled")
        self._final = roll_dice()
        self._tumble(0)

    def _tumble(self, n):
        # quick shuffle animation before settling on the real result
        if n < 8:
            self._draw_die(self.die1, random.randint(1, 6))
            self._draw_die(self.die2, random.randint(1, 6))
            self.root.after(60, lambda: self._tumble(n + 1))
        else:
            d1, d2 = self._final
            self._draw_die(self.die1, d1)
            self._draw_die(self.die2, d2)
            self.total_lbl.config(text=f"Rolled {d1} + {d2} = {d1 + d2}")
            self._resolve(d1 + d2)

    def _resolve(self, total):
        msgs = []

        # 1) Field is a one-roll bet, resolved every roll
        if self.bets["field"] > 0:
            fb = self.bets["field"]
            mult = field_payout(total)
            if mult > 0:
                self.chips += fb + fb * mult
                extra = " (2:1)" if total in (2, 12) else ""
                msgs.append(f"Field wins {fb * mult}{extra}.")
            else:
                msgs.append(f"Field loses {fb}.")
            self.bets["field"] = 0

        # 2) Line bets
        if self.point is None:
            # come-out roll
            if total in (7, 11):
                self._pay_line(pass_wins=True, msgs=msgs, tag="natural")
            elif total in (2, 3):
                self._pay_line(pass_wins=False, dont_push=False, msgs=msgs,
                               tag="craps")
            elif total == 12:
                self._pay_line(pass_wins=False, dont_push=True, msgs=msgs,
                               tag="craps (12)")
            else:
                self.point = total
                msgs.append(f"Point is set to {total}. Roll it again "
                            f"before a 7.")
        else:
            # point phase
            if total == self.point:
                self._pay_line(pass_wins=True, msgs=msgs, tag="point made")
                self.point = None
            elif total == 7:
                self._pay_line(pass_wins=False, dont_push=False, msgs=msgs,
                               tag="seven out")
                self.point = None
            else:
                msgs.append("No decision \u2014 roll again.")

        self.log("  ".join(msgs))

        if self.chips < MIN_BET and sum(self.bets.values()) == 0:
            self.log("Out of chips \u2014 buy more credits to keep playing.")
            wallet.close_game(self.root)
            self.point = None
        self.bet_amount = max(MIN_BET, min(self.bet_amount, max(self.chips, MIN_BET)))

        self.refresh()
        self.busy = False
        self.roll_btn.config(state="normal")
        self.clear_btn.config(state="normal")

    def _pay_line(self, pass_wins, msgs, tag, dont_push=False):
        """Settle pass and don't-pass bets. Bets are cleared when resolved."""
        pb, db = self.bets["pass"], self.bets["dont"]
        if pb > 0:
            if pass_wins:
                self.chips += pb * 2
                msgs.append(f"Pass line wins {pb} ({tag}).")
            else:
                msgs.append(f"Pass line loses {pb} ({tag}).")
            self.bets["pass"] = 0
        if db > 0:
            if dont_push:
                self.chips += db
                msgs.append(f"Don't Pass pushes ({tag}).")
            elif pass_wins:
                msgs.append(f"Don't Pass loses {db} ({tag}).")
            else:
                self.chips += db * 2
                msgs.append(f"Don't Pass wins {db} ({tag}).")
            self.bets["dont"] = 0

    # ---- log -------------------------------------------------------------
    def log(self, msg):
        self.log_box.config(state="normal")
        self.log_box.insert("end", msg + "\n")
        self.log_box.see("end")
        self.log_box.config(state="disabled")


def main():
    root = tk.Tk()
    CrapsGame(root)
    root.mainloop()


if __name__ == "__main__":
    main()
