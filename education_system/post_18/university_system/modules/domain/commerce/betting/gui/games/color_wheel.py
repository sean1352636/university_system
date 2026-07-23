"""
Color Wheel -- bet on colours or a single number.

Self-contained Tkinter game (standard library only).
Run with:  python color_wheel.py

A 20-slot wheel: 9 red, 9 black, 2 green. Bet Red or Black (1:1), Green (9:1),
or a single number 1-18 (17:1). The pointer decides.
"""

import math
import random
import tkinter as tk
try:
    import wallet  # shared credit wallet when launched as a standalone script
except ImportError:  # when imported as part of the betting-shop package
    from education_system.post_18.university_system.modules.domain.commerce.betting.gui.games import wallet

# build 20 slots: numbers 1..18 alternating red/black, plus two greens (0, 00)
SLOTS = []
for i in range(1, 19):
    SLOTS.append((str(i), "red" if i % 2 == 1 else "black"))
SLOTS.insert(0, ("0", "green"))
SLOTS.append(("00", "green"))          # total 20
COLOR_HEX = {"red": "#c1121f", "black": "#1d1d1d", "green": "#2a9d4a"}

WR = 165
FELT, GOLD = "#0b2233", "#e9c46a"
START_CREDITS, MIN_BET = 200, 5


def payout(bet_kind, bet_num, slot):
    """Return winnings multiplier (total return incl. stake) for a hit, else 0."""
    label, color = slot
    if bet_kind == "color":
        if color == bet_num:                     # bet_num holds the colour
            return 10 if color == "green" else 2  # green 9:1 -> return 10x; color 1:1 -> 2x
        return 0
    if bet_kind == "number":
        return 18 if label == bet_num else 0     # 17:1 -> return 18x
    return 0


class ColorWheel:
    def __init__(self, root):
        self.root = root
        root.title("Color Wheel")
        root.configure(bg=FELT)
        root.resizable(False, False)
        self.credits = wallet.get_credits()
        self.bet = 10
        self.offset = 0.0
        self.busy = False
        self.bet_kind = tk.StringVar(value="color")
        self.bet_color = tk.StringVar(value="red")
        self.bet_number = tk.StringVar(value="1")
        self._build()
        self.draw_wheel()
        self.refresh()

    def _build(self):
        f = tk.Frame(self.root, bg=FELT, padx=18, pady=10)
        f.pack()
        tk.Label(f, text="COLOR WHEEL", bg=FELT, fg=GOLD,
                 font=("Helvetica", 18, "bold")).pack()
        self.wheel = tk.Canvas(f, width=WR * 2 + 20, height=WR * 2 + 30,
                               bg=FELT, highlightthickness=0)
        self.wheel.pack(pady=4)
        self.msg = tk.Label(f, text="Place a bet and spin!", bg=FELT, fg="white",
                            font=("Helvetica", 12, "bold"))
        self.msg.pack()

        # colour bets
        crow = tk.Frame(f, bg=FELT, pady=4)
        crow.pack()
        for col, txt in [("red", "RED 1:1"), ("black", "BLACK 1:1"),
                         ("green", "GREEN 9:1")]:
            tk.Radiobutton(crow, text=txt, value=col, variable=self.bet_color,
                           command=lambda: self.bet_kind.set("color"),
                           indicatoron=False, width=10, height=1,
                           font=("Helvetica", 10, "bold"), bg=COLOR_HEX[col],
                           fg="white", selectcolor="#111", bd=0).pack(side="left",
                                                                      padx=3)
        # number bet
        nrow = tk.Frame(f, bg=FELT, pady=4)
        nrow.pack()
        tk.Radiobutton(nrow, text="Number (17:1):", value="number",
                       variable=self.bet_kind, bg=FELT, fg="white",
                       selectcolor="#111", font=("Helvetica", 10, "bold"),
                       activebackground=FELT).pack(side="left")
        self.num_menu = tk.OptionMenu(nrow, self.bet_number,
                                      *[str(i) for i in range(1, 19)])
        self.num_menu.config(bg="#333", fg="white", font=("Helvetica", 10, "bold"),
                             width=4, highlightthickness=0)
        self.num_menu.pack(side="left", padx=4)
        tk.Radiobutton(nrow, text="Colour bet", value="color",
                       variable=self.bet_kind, bg=FELT, fg="white",
                       selectcolor="#111", font=("Helvetica", 10, "bold"),
                       activebackground=FELT).pack(side="left", padx=6)

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
        n = len(SLOTS)
        seg = 360 / n
        for i, (label, color) in enumerate(SLOTS):
            start = i * seg + self.offset
            hot = highlight is not None and i == highlight
            c.create_arc(cx - WR, cy - WR, cx + WR, cy + WR, start=start,
                         extent=seg, fill=COLOR_HEX[color],
                         outline=GOLD if hot else "#fff", width=4 if hot else 1,
                         style="pieslice")
            mid = math.radians(start + seg / 2)
            tx = cx + math.cos(mid) * WR * 0.8
            ty = cy - math.sin(mid) * WR * 0.8
            c.create_text(tx, ty, text=label, fill="white",
                          font=("Helvetica", 10, "bold"))
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
        target = random.randrange(len(SLOTS))
        n = len(SLOTS)
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
        slot = SLOTS[self._target]
        kind = self.bet_kind.get()
        bet_num = self.bet_color.get() if kind == "color" else self.bet_number.get()
        mult = payout(kind, bet_num, slot)
        if mult:
            win = self.bet * mult
            self.credits += win
            self.msg.config(text=f"Landed {slot[0]} ({slot[1]}) \u2014 WIN {win}!",
                            fg=GOLD)
        else:
            self.msg.config(text=f"Landed {slot[0]} ({slot[1]}). No win.",
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
    ColorWheel(root)
    root.mainloop()


if __name__ == "__main__":
    main()
