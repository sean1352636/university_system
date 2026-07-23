"""
Bonus Prize Wheel -- push-your-luck accumulator wheel.

Self-contained Tkinter game (standard library only).
Run with:  python bonus_prize_wheel.py

Pay an entry to start a round. Each spin adds a prize to your BANK. DOUBLE
doubles the bank and lets you keep going; BUST wipes the bank and ends the
round. Press COLLECT any time to bank your winnings into credits.
"""

import math
import random
import tkinter as tk
try:
    import wallet  # shared credit wallet when launched as a standalone script
except ImportError:  # when imported as part of the betting-shop package
    from education_system.post_18.university_system.modules.domain.commerce.betting.gui.games import wallet

# segment kinds: ("prize", n) adds n*bet ; "double" ; "bust"
SEGMENTS = [("prize", 5), ("bust", 0), ("prize", 8), ("double", 0),
            ("prize", 3), ("bust", 0), ("prize", 15), ("prize", 5),
            ("double", 0), ("prize", 3), ("bust", 0), ("prize", 25)]
KIND_COLOR = {"prize": "#2a9d8f", "double": "#e9c46a", "bust": "#e63946"}

WR = 160
FELT, GOLD = "#241035", "#e9c46a"
START_CREDITS, MIN_BET = 200, 5


class BonusPrizeWheel:
    def __init__(self, root):
        self.root = root
        root.title("Bonus Prize Wheel")
        root.configure(bg=FELT)
        root.resizable(False, False)
        self.credits = wallet.get_credits()
        self.bet = 10
        self.offset = 0.0
        self.busy = False
        self.in_round = False
        self.bank = 0
        self._build()
        self.draw_wheel()
        self.refresh()

    def _build(self):
        f = tk.Frame(self.root, bg=FELT, padx=18, pady=12)
        f.pack()
        tk.Label(f, text="BONUS PRIZE WHEEL", bg=FELT, fg=GOLD,
                 font=("Helvetica", 18, "bold")).pack()
        self.bank_lbl = tk.Label(f, text="", bg="#3a1a55", fg=GOLD,
                                 font=("Helvetica", 15, "bold"), padx=16, pady=4)
        self.bank_lbl.pack(pady=4)
        self.wheel = tk.Canvas(f, width=WR * 2 + 20, height=WR * 2 + 30,
                               bg=FELT, highlightthickness=0)
        self.wheel.pack(pady=4)
        self.msg = tk.Label(f, text="Press Start to buy in and spin!", bg=FELT,
                            fg="white", font=("Helvetica", 12, "bold"))
        self.msg.pack()

        bar = tk.Frame(f, bg=FELT, pady=6)
        bar.pack()
        self.cr_lbl = tk.Label(bar, text="", bg=FELT, fg="white",
                               font=("Helvetica", 13, "bold"))
        self.cr_lbl.pack(side="left", padx=8)
        tk.Button(bar, text="\u2212", width=3, command=lambda: self.chg(-MIN_BET),
                  font=("Helvetica", 11, "bold"), bg="#333", fg="white",
                  bd=0).pack(side="left")
        tk.Label(bar, text="Entry:", bg=FELT, fg=GOLD,
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
        self.spin_btn = tk.Button(btns, text="START", command=self.spin, width=12,
                                  font=("Helvetica", 14, "bold"), bg="#7b2cbf",
                                  fg="white", activebackground=GOLD, bd=0, pady=8,
                                  cursor="hand2")
        self.spin_btn.pack(side="left", padx=6)
        self.collect_btn = tk.Button(btns, text="COLLECT", command=self.collect,
                                     width=12, font=("Helvetica", 14, "bold"),
                                     bg="#1b7a4b", fg="white", activebackground=GOLD,
                                     bd=0, pady=8, cursor="hand2", state="disabled")
        self.collect_btn.pack(side="left", padx=6)

    def draw_wheel(self, highlight=None):
        c = self.wheel
        c.delete("all")
        cx = cy = WR + 10
        n = len(SEGMENTS)
        seg = 360 / n
        for i, (kind, val) in enumerate(SEGMENTS):
            start = i * seg + self.offset
            hot = highlight is not None and i == highlight
            c.create_arc(cx - WR, cy - WR, cx + WR, cy + WR, start=start,
                         extent=seg, fill=KIND_COLOR[kind],
                         outline=GOLD if hot else "#fff", width=4 if hot else 1,
                         style="pieslice")
            mid = math.radians(start + seg / 2)
            tx = cx + math.cos(mid) * WR * 0.72
            ty = cy - math.sin(mid) * WR * 0.72
            txt = {"double": "DBL", "bust": "BUST"}.get(kind, f"+{val}x")
            c.create_text(tx, ty, text=txt, fill="white",
                          font=("Helvetica", 10, "bold"))
        c.create_oval(cx - 16, cy - 16, cx + 16, cy + 16, fill="#222", outline=GOLD,
                      width=2)
        c.create_polygon(cx - 12, 4, cx + 12, 4, cx, 30, fill=GOLD, outline="#222")

    def chg(self, d):
        if self.busy or self.in_round:
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
        self.bank_lbl.config(text=f"BANK: {self.bank}")

    def spin(self):
        if self.busy:
            return
        if not self.in_round:
            if self.credits < self.bet:
                self.msg.config(text="Not enough credits.")
                return
            self.credits -= self.bet
            self.in_round = True
            self.bank = 0
            self.spin_btn.config(text="SPIN AGAIN")
        self.busy = True
        self.spin_btn.config(state="disabled")
        self.collect_btn.config(state="disabled")
        self.msg.config(text="Spinning...", fg="white")
        self.refresh()
        target = random.randrange(len(SEGMENTS))
        n = len(SEGMENTS)
        seg = 360 / n
        base = (90 - (target * seg + seg / 2)) % 360
        self._final = base + 360 * 4
        self._t, self._N, self._target = 0, 44, target
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
        kind, val = SEGMENTS[self._target]
        self.busy = False
        if kind == "bust":
            self.bank = 0
            self.in_round = False
            self.msg.config(text="BUST! The bank is gone.", fg="#ff8080")
            self.spin_btn.config(text="START", state="normal")
            self.collect_btn.config(state="disabled")
        elif kind == "double":
            self.bank *= 2
            self.msg.config(text=f"DOUBLE! Bank is now {self.bank}.", fg=GOLD)
            self.spin_btn.config(state="normal")
            self.collect_btn.config(state="normal")
        else:
            self.bank += self.bet * val
            self.msg.config(text=f"+{val}x \u2014 bank {self.bank}. Spin or collect?",
                            fg=GOLD)
            self.spin_btn.config(state="normal")
            self.collect_btn.config(state="normal")
        if self.credits < MIN_BET and not self.in_round:
            self.msg.config(text="Out of credits \u2014 buy more credits!")
            wallet.close_game(self.root)
        self.bet = min(self.bet, self.credits) if not self.in_round else self.bet
        self.refresh()

    def collect(self):
        if self.busy or not self.in_round:
            return
        self.credits += self.bank
        self.msg.config(text=f"Collected {self.bank} credits!", fg=GOLD)
        self.bank = 0
        self.in_round = False
        self.spin_btn.config(text="START", state="normal")
        self.collect_btn.config(state="disabled")
        self.bet = min(self.bet, max(MIN_BET, self.credits))
        self.refresh()


def main():
    root = tk.Tk()
    BonusPrizeWheel(root)
    root.mainloop()


if __name__ == "__main__":
    main()
