"""
Target Wheel -- choose how much of the wheel you cover.

Self-contained Tkinter game (standard library only).
Run with:  python target_wheel.py

The wheel has 24 numbered slots. Choose how many adjacent slots to cover
(1-12): fewer slots = longer odds, more slots = shorter odds. The overall
return is about 94% whatever you choose, so pick your own risk level.
"""

import math
import random
import tkinter as tk
try:
    import wallet  # shared credit wallet when launched as a standalone script
except ImportError:  # when imported as part of the betting-shop package
    from education_system.post_18.university_system.modules.domain.commerce.betting.gui.games import wallet

N_SLOTS = 24
RTP = 0.94
WR = 165
FELT, GOLD = "#132a1c", "#e9c46a"
START_CREDITS, MIN_BET = 200, 5


def return_multiplier(covered):
    """Total return per unit stake on a win (includes stake)."""
    return (N_SLOTS / covered) * RTP


class TargetWheel:
    def __init__(self, root):
        self.root = root
        root.title("Target Wheel")
        root.configure(bg=FELT)
        root.resizable(False, False)
        self.credits = wallet.get_credits()
        self.bet = 10
        self.covered = 6
        self.start_slot = 0            # first covered slot index
        self.offset = 0.0
        self.busy = False
        self._build()
        self.draw_wheel()
        self.refresh()

    def _build(self):
        f = tk.Frame(self.root, bg=FELT, padx=18, pady=10)
        f.pack()
        tk.Label(f, text="TARGET WHEEL", bg=FELT, fg=GOLD,
                 font=("Helvetica", 18, "bold")).pack()
        self.wheel = tk.Canvas(f, width=WR * 2 + 20, height=WR * 2 + 30,
                               bg=FELT, highlightthickness=0)
        self.wheel.pack(pady=4)
        self.msg = tk.Label(f, text="Choose your coverage and spin!", bg=FELT,
                            fg="white", font=("Helvetica", 12, "bold"))
        self.msg.pack()

        cov = tk.Frame(f, bg=FELT, pady=4)
        cov.pack()
        tk.Label(cov, text="Cover:", bg=FELT, fg="white",
                 font=("Helvetica", 12, "bold")).pack(side="left")
        tk.Button(cov, text="\u2212", width=3, command=lambda: self.cover(-1),
                  font=("Helvetica", 11, "bold"), bg="#333", fg="white",
                  bd=0).pack(side="left")
        self.cov_lbl = tk.Label(cov, text="", bg=FELT, fg=GOLD, width=20,
                                font=("Helvetica", 12, "bold"))
        self.cov_lbl.pack(side="left")
        tk.Button(cov, text="+", width=3, command=lambda: self.cover(1),
                  font=("Helvetica", 11, "bold"), bg="#333", fg="white",
                  bd=0).pack(side="left")
        tk.Button(cov, text="Move", width=6, command=self.move_arc,
                  font=("Helvetica", 10, "bold"), bg="#3a5a8a", fg="white",
                  bd=0).pack(side="left", padx=6)

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

    def covered_set(self):
        return {(self.start_slot + k) % N_SLOTS for k in range(self.covered)}

    def draw_wheel(self, landed=None):
        c = self.wheel
        c.delete("all")
        cx = cy = WR + 10
        seg = 360 / N_SLOTS
        cov = self.covered_set()
        for i in range(N_SLOTS):
            start = i * seg + self.offset
            in_arc = i in cov
            if landed is not None and i == landed:
                fill = "#e9c46a"
            elif in_arc:
                fill = "#2a9d4a"
            else:
                fill = "#1d3a2a" if i % 2 == 0 else "#163022"
            c.create_arc(cx - WR, cy - WR, cx + WR, cy + WR, start=start,
                         extent=seg, fill=fill,
                         outline=GOLD if in_arc else "#fff",
                         width=3 if in_arc else 1, style="pieslice")
            mid = math.radians(start + seg / 2)
            tx = cx + math.cos(mid) * WR * 0.82
            ty = cy - math.sin(mid) * WR * 0.82
            c.create_text(tx, ty, text=str(i + 1), fill="white",
                          font=("Helvetica", 9, "bold"))
        c.create_oval(cx - 16, cy - 16, cx + 16, cy + 16, fill="#222", outline=GOLD,
                      width=2)
        c.create_polygon(cx - 12, 4, cx + 12, 4, cx, 30, fill=GOLD, outline="#222")

    def cover(self, d):
        if self.busy:
            return
        self.covered = max(1, min(12, self.covered + d))
        self.draw_wheel()
        self.refresh()

    def move_arc(self):
        if self.busy:
            return
        self.start_slot = (self.start_slot + 1) % N_SLOTS
        self.draw_wheel()

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
        ret = return_multiplier(self.covered)
        self.cov_lbl.config(text=f"{self.covered}/24  (pays {ret:.2f}x)")

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
        target = random.randrange(N_SLOTS)
        seg = 360 / N_SLOTS
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
            self.draw_wheel(landed=self._target)
            self._settle()

    def _settle(self):
        if self._target in self.covered_set():
            win = round(self.bet * return_multiplier(self.covered))
            self.credits += win
            self.msg.config(text=f"Landed {self._target + 1} \u2014 WIN {win}!",
                            fg=GOLD)
        else:
            self.msg.config(text=f"Landed {self._target + 1} \u2014 missed.",
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
    TargetWheel(root)
    root.mainloop()


if __name__ == "__main__":
    main()
