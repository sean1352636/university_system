"""
Electronic Roulette -- single-zero (European) roulette.

Self-contained Tkinter game (standard library only).
Run with:  python electronic_roulette.py

Click numbers on the board to place straight-up bets (35:1), or use the outside
buttons for Red/Black/Odd/Even/Low/High (1:1) and the Dozens (2:1). Stack as
many chips as you like, then Spin. Zero loses all outside/dozen bets.
"""

import random
import tkinter as tk
try:
    import wallet  # shared credit wallet when launched as a standalone script
except ImportError:  # when imported as part of the betting-shop package
    from education_system.post_18.university_system.modules.domain.commerce.betting.gui.games import wallet

RED_NUMBERS = {1, 3, 5, 7, 9, 12, 14, 16, 18, 19, 21, 23, 25, 27, 30, 32, 34, 36}
FELT, GOLD = "#0a3d1e", "#e9c46a"
CW, CH = 46, 46
START_CREDITS, MIN_BET = 300, 5


def color_of(n):
    if n == 0:
        return "green"
    return "red" if n in RED_NUMBERS else "black"


def settle(number, bets):
    """bets: dict key->amount. Returns total return (stake included on wins)."""
    ret = 0
    for key, amt in bets.items():
        kind = key[0]
        if kind == "straight":
            if number == key[1]:
                ret += amt * 36
        elif kind == "red":
            if number != 0 and color_of(number) == "red":
                ret += amt * 2
        elif kind == "black":
            if number != 0 and color_of(number) == "black":
                ret += amt * 2
        elif kind == "odd":
            if number != 0 and number % 2 == 1:
                ret += amt * 2
        elif kind == "even":
            if number != 0 and number % 2 == 0:
                ret += amt * 2
        elif kind == "low":
            if 1 <= number <= 18:
                ret += amt * 2
        elif kind == "high":
            if 19 <= number <= 36:
                ret += amt * 2
        elif kind == "dozen":
            d = key[1]
            if number != 0 and (d - 1) * 12 + 1 <= number <= d * 12:
                ret += amt * 3
    return ret


class Roulette:
    def __init__(self, root):
        self.root = root
        root.title("Electronic Roulette")
        root.configure(bg=FELT)
        root.resizable(False, False)
        self.credits = wallet.get_credits()
        self.stake = 5
        self.bets = {}
        self.busy = False
        self._build()
        self.refresh()

    def _build(self):
        f = tk.Frame(self.root, bg=FELT, padx=16, pady=12)
        f.pack()
        tk.Label(f, text="ELECTRONIC ROULETTE", bg=FELT, fg=GOLD,
                 font=("Helvetica", 18, "bold")).pack()

        self.result_lbl = tk.Label(f, text="\u2014", bg="#062a14", fg=GOLD,
                                   font=("Helvetica", 22, "bold"), width=6)
        self.result_lbl.pack(pady=4)

        # board: 0 + 12x3 grid
        self.board = tk.Canvas(f, width=CW * 13 + 4, height=CH * 3 + 4, bg=FELT,
                               highlightthickness=0)
        self.board.pack(pady=6)
        self.board.bind("<Button-1>", self.on_board)
        self._draw_board()

        # outside bets
        out = tk.Frame(f, bg=FELT)
        out.pack(pady=4)
        specs = [("red", "RED"), ("black", "BLACK"), ("odd", "ODD"),
                 ("even", "EVEN"), ("low", "1-18"), ("high", "19-36")]
        for key, txt in specs:
            bg = "#c1121f" if key == "red" else "#1d1d1d" if key == "black" else "#20563a"
            tk.Button(out, text=txt, width=7, font=("Helvetica", 10, "bold"),
                      bg=bg, fg="white", bd=0, cursor="hand2",
                      command=lambda k=key: self.place((k,))).pack(side="left",
                                                                   padx=2)
        dz = tk.Frame(f, bg=FELT)
        dz.pack(pady=2)
        for d, txt in [(1, "1st 12"), (2, "2nd 12"), (3, "3rd 12")]:
            tk.Button(dz, text=f"{txt} (2:1)", width=10,
                      font=("Helvetica", 10, "bold"), bg="#20563a", fg="white",
                      bd=0, cursor="hand2",
                      command=lambda d=d: self.place(("dozen", d))).pack(
                side="left", padx=3)

        self.slip_lbl = tk.Label(f, text="No bets.", bg=FELT, fg="#bfe3cf",
                                 font=("Helvetica", 10), wraplength=600,
                                 justify="left")
        self.slip_lbl.pack(pady=4)

        bar = tk.Frame(f, bg=FELT, pady=6)
        bar.pack()
        self.cr_lbl = tk.Label(bar, text="", bg=FELT, fg="white",
                               font=("Helvetica", 13, "bold"))
        self.cr_lbl.pack(side="left", padx=8)
        tk.Label(bar, text="Chip:", bg=FELT, fg="white",
                 font=("Helvetica", 11)).pack(side="left")
        tk.Button(bar, text="\u2212", width=3, command=lambda: self.chg(-MIN_BET),
                  font=("Helvetica", 11, "bold"), bg="#333", fg="white",
                  bd=0).pack(side="left")
        self.stake_var = tk.StringVar()
        self.stake_entry = tk.Entry(bar, textvariable=self.stake_var, width=6,
                                    justify="center", font=("Helvetica", 13, "bold"),
                                    bg="#0d2846", fg=GOLD, insertbackground=GOLD,
                                    relief="flat", bd=2)
        self.stake_entry.pack(side="left")
        self.stake_entry.bind("<Return>", lambda e: self.set_bet())
        self.stake_entry.bind("<FocusOut>", lambda e: self.set_bet())
        tk.Button(bar, text="+", width=3, command=lambda: self.chg(MIN_BET),
                  font=("Helvetica", 11, "bold"), bg="#333", fg="white",
                  bd=0).pack(side="left")

        btns = tk.Frame(f, bg=FELT, pady=6)
        btns.pack()
        self.spin_btn = tk.Button(btns, text="SPIN", command=self.spin, width=12,
                                  font=("Helvetica", 14, "bold"), bg="#1b7a4b",
                                  fg="white", bd=0, pady=6, cursor="hand2")
        self.spin_btn.pack(side="left", padx=6)
        tk.Button(btns, text="Clear", command=self.clear, width=10,
                  font=("Helvetica", 14, "bold"), bg="#555", fg="white", bd=0,
                  pady=6, cursor="hand2").pack(side="left", padx=6)

    def _num_at(self, row, col):
        # col 0..11, row 0(top)..2(bottom)
        return col * 3 + (3 - row)

    def _draw_board(self, landed=None):
        c = self.board
        c.delete("all")
        # zero cell (full height, leftmost)
        c.create_rectangle(2, 2, 2 + CW, 2 + CH * 3, fill="#2a9d4a",
                           outline=GOLD if landed == 0 else "#fff",
                           width=3 if landed == 0 else 1)
        c.create_text(2 + CW / 2, 2 + CH * 1.5, text="0", fill="white",
                      font=("Helvetica", 16, "bold"))
        for col in range(12):
            for row in range(3):
                n = self._num_at(row, col)
                x = 2 + CW + col * CW
                y = 2 + row * CH
                fill = "#c1121f" if color_of(n) == "red" else "#1d1d1d"
                hot = landed == n
                c.create_rectangle(x, y, x + CW, y + CH, fill=fill,
                                   outline=GOLD if hot else "#fff",
                                   width=3 if hot else 1)
                c.create_text(x + CW / 2, y + CH / 2, text=str(n), fill="white",
                              font=("Helvetica", 12, "bold"))
                amt = self.bets.get(("straight", n))
                if amt:
                    c.create_oval(x + CW - 20, y + 4, x + CW - 4, y + 20,
                                  fill=GOLD, outline="#222")
                    c.create_text(x + CW - 12, y + 12, text=str(amt), fill="#222",
                                  font=("Helvetica", 7, "bold"))

    def on_board(self, e):
        if self.busy:
            return
        if e.x < 2 + CW:               # zero column
            self.place(("straight", 0))
            return
        col = int((e.x - 2 - CW) // CW)
        row = int((e.y - 2) // CH)
        if 0 <= col < 12 and 0 <= row < 3:
            self.place(("straight", self._num_at(row, col)))

    def place(self, key):
        if self.busy:
            return
        if self.credits < self.stake:
            self.slip_lbl.config(text="Not enough credits for that chip.")
            return
        self.credits -= self.stake
        self.bets[key] = self.bets.get(key, 0) + self.stake
        self._draw_board()
        self.refresh()

    def clear(self):
        if self.busy:
            return
        self.credits += sum(self.bets.values())
        self.bets = {}
        self._draw_board()
        self.refresh()

    def chg(self, d):
        if self.busy:
            return
        self.stake = max(MIN_BET, min(max(self.credits, MIN_BET), self.stake + d))
        self.refresh()

    def set_bet(self):
        """Set the chip stake to the amount typed into the entry box."""
        try:
            self.chg(int(float(self.stake_var.get())) - self.stake)
        except (TypeError, ValueError):
            pass
        self.stake_var.set(str(self.stake))

    def refresh(self):
        wallet.set_credits(self.credits)
        self.cr_lbl.config(text=f"Credits: {self.credits}")
        self.stake_var.set(str(self.stake))
        if self.bets:
            total = sum(self.bets.values())
            names = []
            for key, amt in self.bets.items():
                label = key[0] if key[0] != "straight" else f"#{key[1]}"
                if key[0] == "dozen":
                    label = f"dozen{key[1]}"
                names.append(f"{label}:{amt}")
            self.slip_lbl.config(text=f"Bets ({total}):  " + "  ".join(names))
        else:
            self.slip_lbl.config(text="No bets.")

    def spin(self):
        if self.busy:
            return
        if not self.bets:
            self.slip_lbl.config(text="Place a bet first.")
            return
        self.busy = True
        self.spin_btn.config(state="disabled")
        self._final = random.randint(0, 36)
        self._ticks = 22
        self._tick()

    def _tick(self):
        if self._ticks > 0:
            n = random.randint(0, 36)
            self.result_lbl.config(text=str(n), fg="white")
            self._ticks -= 1
            self.root.after(60 + (22 - self._ticks) * 6, self._tick)
        else:
            n = self._final
            col = {"red": "#ff6b6b", "black": "#cfd8dc", "green": "#7CFC98"}[color_of(n)]
            self.result_lbl.config(text=str(n), fg=col)
            self._draw_board(landed=n)
            self._settle(n)

    def _settle(self, number):
        ret = settle(number, self.bets)
        staked = sum(self.bets.values())
        self.credits += ret
        net = ret - staked
        cname = color_of(number)
        if ret > 0:
            self.slip_lbl.config(
                text=f"{number} {cname} \u2014 returned {ret} "
                     f"({'+' if net >= 0 else ''}{net}).")
        else:
            self.slip_lbl.config(text=f"{number} {cname} \u2014 no win ({net}).")
        self.bets = {}
        if self.credits < MIN_BET:
            self.slip_lbl.config(text=f"{number} {cname}. Out of credits \u2014 "
                                      f"buy more credits!")
            wallet.close_game(self.root)
        self.stake = min(self.stake, max(MIN_BET, self.credits))
        self.refresh()
        self.busy = False
        self.spin_btn.config(state="normal")


def main():
    root = tk.Tk()
    Roulette(root)
    root.mainloop()


if __name__ == "__main__":
    main()
