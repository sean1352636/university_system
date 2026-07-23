"""
Dual Wheel -- two concentric wheels spin together.

Self-contained Tkinter game (standard library only).
Run with:  python dual_wheel.py

The inner wheel gives a base value, the outer ring gives a multiplier. Your
win is stake x inner x outer (a 0 on the inner wheel means no win). Both wheels
are read at the top pointer.
"""

import math
import random
import tkinter as tk
try:
    import wallet  # shared credit wallet when launched as a standalone script
except ImportError:  # when imported as part of the betting-shop package
    from education_system.post_18.university_system.modules.domain.commerce.betting.gui.games import wallet

INNER = [0, 1, 1, 2, 0, 1, 2, 1]          # E = 8/8 = 1.0 ... with zeros below
INNER = [0, 0, 0, 0, 1, 2, 1, 1]          # E = 5/8 = 0.625
OUTER = [1, 2, 1, 1, 3, 1]                 # E = 9/6 = 1.5   -> product ~0.9375
INNER_COLOR = {0: "#5a5a6e", 1: "#457b9d", 2: "#2a9d8f"}
OUTER_COLOR = {1: "#264653", 2: "#e9c46a", 3: "#e63946"}

R_OUT, R_IN = 165, 100
FELT, GOLD = "#0e2233", "#e9c46a"
START_CREDITS, MIN_BET = 200, 5


class DualWheel:
    def __init__(self, root):
        self.root = root
        root.title("Dual Wheel")
        root.configure(bg=FELT)
        root.resizable(False, False)
        self.credits = wallet.get_credits()
        self.bet = 20
        self.off_in = 0.0
        self.off_out = 0.0
        self.busy = False
        self._build()
        self.draw_wheel()
        self.refresh()

    def _build(self):
        f = tk.Frame(self.root, bg=FELT, padx=18, pady=12)
        f.pack()
        tk.Label(f, text="DUAL WHEEL", bg=FELT, fg=GOLD,
                 font=("Helvetica", 18, "bold")).pack()
        tk.Label(f, text="win = stake \u00d7 inner value \u00d7 outer multiplier",
                 bg=FELT, fg="#9fb3c8", font=("Helvetica", 10)).pack()
        self.wheel = tk.Canvas(f, width=R_OUT * 2 + 20, height=R_OUT * 2 + 30,
                               bg=FELT, highlightthickness=0)
        self.wheel.pack(pady=6)
        self.msg = tk.Label(f, text="Set a stake and spin!", bg=FELT, fg="white",
                            font=("Helvetica", 12, "bold"))
        self.msg.pack()

        bar = tk.Frame(f, bg=FELT, pady=8)
        bar.pack()
        self.cr_lbl = tk.Label(bar, text="", bg=FELT, fg="white",
                               font=("Helvetica", 13, "bold"))
        self.cr_lbl.pack(side="left", padx=8)
        tk.Button(bar, text="\u2212", width=3, command=lambda: self.chg(-MIN_BET),
                  font=("Helvetica", 11, "bold"), bg="#333", fg="white",
                  bd=0).pack(side="left")
        tk.Label(bar, text="Stake:", bg=FELT, fg=GOLD,
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

    def draw_wheel(self, hi_in=None, hi_out=None):
        c = self.wheel
        c.delete("all")
        cx = cy = R_OUT + 10
        # outer ring
        no = len(OUTER)
        so = 360 / no
        for i, m in enumerate(OUTER):
            start = i * so + self.off_out
            hot = hi_out is not None and i == hi_out
            c.create_arc(cx - R_OUT, cy - R_OUT, cx + R_OUT, cy + R_OUT, start=start,
                         extent=so, fill=OUTER_COLOR[m],
                         outline=GOLD if hot else "#fff", width=4 if hot else 1,
                         style="pieslice")
            mid = math.radians(start + so / 2)
            tx = cx + math.cos(mid) * (R_OUT + R_IN) / 2 * 1.05
            ty = cy - math.sin(mid) * (R_OUT + R_IN) / 2 * 1.05
            c.create_text(tx, ty, text=f"x{m}", fill="white",
                          font=("Helvetica", 11, "bold"))
        # inner disk on top
        ni = len(INNER)
        si = 360 / ni
        for i, v in enumerate(INNER):
            start = i * si + self.off_in
            hot = hi_in is not None and i == hi_in
            c.create_arc(cx - R_IN, cy - R_IN, cx + R_IN, cy + R_IN, start=start,
                         extent=si, fill=INNER_COLOR[v],
                         outline=GOLD if hot else "#fff", width=4 if hot else 1,
                         style="pieslice")
            mid = math.radians(start + si / 2)
            tx = cx + math.cos(mid) * R_IN * 0.6
            ty = cy - math.sin(mid) * R_IN * 0.6
            c.create_text(tx, ty, text=("0" if v == 0 else str(v)), fill="white",
                          font=("Helvetica", 12, "bold"))
        c.create_oval(cx - 14, cy - 14, cx + 14, cy + 14, fill="#222", outline=GOLD,
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
        self._ti = random.randrange(len(INNER))
        self._to = random.randrange(len(OUTER))
        si, so = 360 / len(INNER), 360 / len(OUTER)
        self._fin_in = (90 - (self._ti * si + si / 2)) % 360 + 360 * 4
        self._fin_out = (90 - (self._to * so + so / 2)) % 360 + 360 * 3
        self._t, self._N = 0, 50
        self._anim()

    def _anim(self):
        t = self._t / self._N
        ease = 1 - (1 - t) ** 3
        self.off_in = self._fin_in * ease
        self.off_out = self._fin_out * ease
        self.draw_wheel()
        if self._t < self._N:
            self._t += 1
            self.root.after(32, self._anim)
        else:
            self.off_in %= 360
            self.off_out %= 360
            self.draw_wheel(hi_in=self._ti, hi_out=self._to)
            self._settle()

    def _settle(self):
        v = INNER[self._ti]
        m = OUTER[self._to]
        win = self.bet * v * m
        if win:
            self.credits += win
            self.msg.config(text=f"{v} \u00d7 x{m} \u2014 WIN {win}!", fg=GOLD)
        else:
            self.msg.config(text=f"Inner 0 \u00d7 x{m} \u2014 no win.", fg="white")
        if self.credits < MIN_BET:
            self.msg.config(text="Out of credits \u2014 buy more credits!")
            wallet.close_game(self.root)
        self.bet = min(self.bet, self.credits)
        self.refresh()
        self.busy = False
        self.spin_btn.config(state="normal")


def main():
    root = tk.Tk()
    DualWheel(root)
    root.mainloop()


if __name__ == "__main__":
    main()
