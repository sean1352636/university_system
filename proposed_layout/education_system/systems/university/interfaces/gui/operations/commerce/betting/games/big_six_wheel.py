"""
Big Six Money Wheel -- classic vertical money wheel.

Self-contained Tkinter game (standard library only).
Run with:  python big_six_wheel.py

A 54-slot wheel. Bet on a denomination (or the Joker / Star). The wheel spins
and pays fixed odds if the pointer lands on your pick.
  $1 -> 1:1   $2 -> 2:1   $5 -> 5:1   $10 -> 10:1   $20 -> 20:1
  Joker / Star -> 40:1
"""

import math
import random
import tkinter as tk
try:
    import wallet  # shared credit wallet when launched as a standalone script
except ImportError:  # when imported as part of the betting-shop package
    from education_system.systems.university.interfaces.gui.operations.commerce.betting.games import wallet

# slot distribution (totals 54)
COUNTS = {"1": 24, "2": 15, "5": 7, "10": 4, "20": 2, "joker": 1, "star": 1}
ODDS = {"1": 1, "2": 2, "5": 5, "10": 10, "20": 20, "joker": 40, "star": 40}
COLOR = {"1": "#457b9d", "2": "#2a9d8f", "5": "#e9c46a", "10": "#e76f51",
         "20": "#9d4edd", "joker": "#e63946", "star": "#f4a261"}
LABEL = {"1": "1", "2": "2", "5": "5", "10": "10", "20": "20",
         "joker": "J", "star": "\u2605"}

WR = 165
FELT, GOLD = "#0b2a1a", "#e9c46a"
START_CREDITS, MIN_BET = 200, 5


class BigSixWheel:
    def __init__(self, root):
        self.root = root
        root.title("Big Six Money Wheel")
        root.configure(bg=FELT)
        root.resizable(False, False)
        self.credits = wallet.get_credits()
        self.bet = 10
        self.pick = tk.StringVar(value="1")
        self.offset = 0.0
        self.busy = False
        # build the fixed slot arrangement for this session
        self.slots = []
        for k, n in COUNTS.items():
            self.slots += [k] * n
        random.shuffle(self.slots)
        self._build()
        self.draw_wheel()
        self.refresh()

    def _build(self):
        f = tk.Frame(self.root, bg=FELT, padx=18, pady=12)
        f.pack()
        tk.Label(f, text="BIG SIX MONEY WHEEL", bg=FELT, fg=GOLD,
                 font=("Helvetica", 18, "bold")).pack()
        self.wheel = tk.Canvas(f, width=WR * 2 + 20, height=WR * 2 + 30,
                               bg=FELT, highlightthickness=0)
        self.wheel.pack(pady=6)
        self.msg = tk.Label(f, text="Pick a slot and spin!", bg=FELT, fg="white",
                            font=("Helvetica", 12, "bold"))
        self.msg.pack()

        sel = tk.Frame(f, bg=FELT, pady=6)
        sel.pack()
        for k in ["1", "2", "5", "10", "20", "joker", "star"]:
            tk.Radiobutton(sel, text=f"{LABEL[k]}\n{ODDS[k]}:1", value=k,
                           variable=self.pick, indicatoron=False, width=5, height=2,
                           font=("Helvetica", 10, "bold"), bg=COLOR[k], fg="white",
                           selectcolor="#111", bd=0).pack(side="left", padx=3)

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
        self.spin_btn = tk.Button(f, text="SPIN", command=self.spin, width=16,
                                  font=("Helvetica", 14, "bold"), bg="#1b7a4b",
                                  fg="white", activebackground=GOLD, bd=0, pady=8,
                                  cursor="hand2")
        self.spin_btn.pack(pady=6)

    def draw_wheel(self, highlight=None):
        c = self.wheel
        c.delete("all")
        cx = cy = WR + 10
        n = len(self.slots)
        seg = 360 / n
        for i, key in enumerate(self.slots):
            start = i * seg + self.offset
            hot = highlight is not None and i == highlight
            c.create_arc(cx - WR, cy - WR, cx + WR, cy + WR, start=start,
                         extent=seg, fill=COLOR[key],
                         outline=GOLD if hot else "#fff", width=3 if hot else 1,
                         style="pieslice")
            mid = math.radians(start + seg / 2)
            tx = cx + math.cos(mid) * WR * 0.82
            ty = cy - math.sin(mid) * WR * 0.82
            c.create_text(tx, ty, text=LABEL[key], fill="white",
                          font=("Helvetica", 9, "bold"))
        c.create_oval(cx - 16, cy - 16, cx + 16, cy + 16, fill="#222", outline=GOLD,
                      width=2)
        c.create_polygon(cx - 12, 4, cx + 12, 4, cx, 30, fill=GOLD, outline="#222")

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

    def spin(self):
        if self.busy:
            return
        if self.credits < self.bet:
            self.msg.config(text="Not enough credits.")
            return
        self.credits -= self.bet
        self.busy = True
        self.spin_btn.config(state="disabled")
        self.msg.config(text="Spinning...", fg="white")
        self.refresh()
        target = random.randrange(len(self.slots))
        n = len(self.slots)
        seg = 360 / n
        base = (90 - (target * seg + seg / 2)) % 360
        self._final = base + 360 * 4
        self._t, self._N, self._target = 0, 48, target
        self._anim()

    def _anim(self):
        t = self._t / self._N
        self.offset = self._final * (1 - (1 - t) ** 3)
        self.draw_wheel()
        if self._t < self._N:
            self._t += 1
            self.root.after(34, self._anim)
        else:
            self.offset %= 360
            self.draw_wheel(highlight=self._target)
            self._settle()

    def _settle(self):
        key = self.slots[self._target]
        pick = self.pick.get()
        if key == pick:
            win = self.bet * ODDS[key] + self.bet   # odds plus stake back
            self.credits += win
            self.msg.config(text=f"Landed {LABEL[key]} \u2014 WIN {win}!", fg=GOLD)
        else:
            self.msg.config(text=f"Landed {LABEL[key]}. You had {LABEL[pick]}.",
                            fg="white")
        if self.credits < MIN_BET:
            self.msg.config(text="Out of credits \u2014 buy more credits!")
            wallet.close_game(self.root)
        self.bet = min(self.bet, self.credits)
        self.refresh()
        self.busy = False
        self.spin_btn.config(state="normal")


def main():
    root = tk.Tk()
    BigSixWheel(root)
    root.mainloop()


if __name__ == "__main__":
    main()
