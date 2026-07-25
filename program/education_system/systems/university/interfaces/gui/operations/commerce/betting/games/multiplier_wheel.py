"""
Multiplier Wheel -- a single-spin gamble on your stake.

Self-contained Tkinter game (standard library only).
Run with:  python multiplier_wheel.py

Set a stake and spin. The wheel lands on a return multiplier: 0x means you
lose the stake, otherwise you get stake x multiplier back. About a 94% return
overall, so the house keeps a small edge.
"""

import math
import random
import tkinter as tk
try:
    import wallet  # shared credit wallet when launched as a standalone script
except ImportError:  # when imported as part of the betting-shop package
    from education_system.systems.university.interfaces.gui.operations.commerce.betting.games import wallet

# 16 segments -- expected multiplier 15/16 = 0.9375
SEGMENTS = [0, 1, 0, 2, 0, 0, 3, 0, 1, 0, 2, 0, 1, 0, 5, 0]
SEG_COLOR = {0: "#5a5a6e", 1: "#457b9d", 2: "#2a9d8f", 3: "#e9c46a", 5: "#e63946"}

WR = 160
FELT, GOLD = "#141830", "#e9c46a"
START_CREDITS, MIN_BET = 200, 5


class MultiplierWheel:
    def __init__(self, root):
        self.root = root
        root.title("Multiplier Wheel")
        root.configure(bg=FELT)
        root.resizable(False, False)
        self.credits = wallet.get_credits()
        self.bet = 20
        self.offset = 0.0
        self.busy = False
        self._build()
        self.draw_wheel()
        self.refresh()

    def _build(self):
        f = tk.Frame(self.root, bg=FELT, padx=18, pady=12)
        f.pack()
        tk.Label(f, text="MULTIPLIER WHEEL", bg=FELT, fg=GOLD,
                 font=("Helvetica", 18, "bold")).pack()
        self.wheel = tk.Canvas(f, width=WR * 2 + 20, height=WR * 2 + 30,
                               bg=FELT, highlightthickness=0)
        self.wheel.pack(pady=6)
        self.msg = tk.Label(f, text="Set your stake and spin!", bg=FELT,
                            fg="white", font=("Helvetica", 12, "bold"))
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
                                  font=("Helvetica", 14, "bold"), bg="#7b2cbf",
                                  fg="white", activebackground=GOLD, bd=0, pady=8,
                                  cursor="hand2")
        self.spin_btn.pack(pady=6)

    def draw_wheel(self, highlight=None):
        c = self.wheel
        c.delete("all")
        cx = cy = WR + 10
        n = len(SEGMENTS)
        seg = 360 / n
        for i, mult in enumerate(SEGMENTS):
            start = i * seg + self.offset
            hot = highlight is not None and i == highlight
            c.create_arc(cx - WR, cy - WR, cx + WR, cy + WR, start=start,
                         extent=seg, fill=SEG_COLOR[mult],
                         outline=GOLD if hot else "#fff", width=4 if hot else 1,
                         style="pieslice")
            mid = math.radians(start + seg / 2)
            tx = cx + math.cos(mid) * WR * 0.74
            ty = cy - math.sin(mid) * WR * 0.74
            txt = "LOSE" if mult == 0 else f"x{mult}"
            c.create_text(tx, ty, text=txt, fill="white",
                          font=("Helvetica", 11, "bold"))
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
        target = random.randrange(len(SEGMENTS))
        n = len(SEGMENTS)
        seg = 360 / n
        base = (90 - (target * seg + seg / 2)) % 360
        self._final = base + 360 * 4
        self._t, self._N, self._target = 0, 46, target
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
        mult = SEGMENTS[self._target]
        win = self.bet * mult
        if win:
            self.credits += win
            self.msg.config(text=f"x{mult} \u2014 WIN {win}!", fg=GOLD)
        else:
            self.msg.config(text="LOSE \u2014 no return this spin.", fg="white")
        if self.credits < MIN_BET:
            self.msg.config(text="Out of credits \u2014 buy more credits!")
            wallet.close_game(self.root)
        self.bet = min(self.bet, self.credits)
        self.refresh()
        self.busy = False
        self.spin_btn.config(state="normal")


def main():
    root = tk.Tk()
    MultiplierWheel(root)
    root.mainloop()


if __name__ == "__main__":
    main()
