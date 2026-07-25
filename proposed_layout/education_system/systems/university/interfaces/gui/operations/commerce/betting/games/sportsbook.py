"""
Sportsbook -- casino sports-betting area.

Self-contained Tkinter game (standard library only).
Run with:  python sportsbook.py

Browse a slate of (fictional) matches with decimal odds, tap outcomes to add
them to your bet slip, set a stake, and place your bets. Each match is then
simulated from its true probabilities (the quoted odds carry a small house
margin) and your winning singles pay stake x odds.
"""

import random
import tkinter as tk
try:
    import wallet  # shared credit wallet when launched as a standalone script
except ImportError:  # when imported as part of the betting-shop package
    from education_system.systems.university.interfaces.gui.operations.commerce.betting.games import wallet

FELT, GOLD = "#0c2a1e", "#e9c46a"
START_BALANCE = 500
MARGIN = 0.06                  # bookmaker overround

TEAMS = {
    "Soccer": ["Riverton Rovers", "Kingsport United", "Ashford Athletic",
               "Portside FC", "Hillcrest City", "Marlow Town",
               "Oakvale Wanderers", "Sablewick FC"],
    "Basketball": ["Metro Comets", "Bayline Bolts", "Granite Peaks",
                   "Summit Sharks", "Delta Dragons", "Coastal Current"],
    "Tennis": ["A. Voss", "R. Calder", "M. Ibarra", "T. Fenwick",
               "L. Okonkwo", "S. Petrov", "D. Marchetti", "N. Adeyemi"],
    "Football": ["Crestview Colonels", "Ironside Miners", "Vandergrift Vipers",
                 "Northgate Knights", "Redland Raptors", "Belmont Bruisers"],
}


def make_match(sport):
    teams = random.sample(TEAMS[sport], 2)
    three_way = sport == "Soccer"
    if three_way:
        # true probabilities for home / draw / away
        raw = [random.uniform(0.8, 2.2), random.uniform(0.7, 1.3),
               random.uniform(0.8, 2.2)]
        outcomes = ["home", "draw", "away"]
    else:
        raw = [random.uniform(0.8, 2.4), random.uniform(0.8, 2.4)]
        outcomes = ["home", "away"]
    s = sum(raw)
    true_p = [x / s for x in raw]
    # quoted odds include the margin
    odds = [round(1.0 / (p * (1 + MARGIN)), 2) for p in true_p]
    return {"sport": sport, "home": teams[0], "away": teams[1],
            "outcomes": outcomes, "true_p": true_p, "odds": odds}


def simulate(match):
    """Pick an outcome by true probability; return (outcome, score_str)."""
    outcome = random.choices(match["outcomes"], weights=match["true_p"])[0]
    return outcome, score_line(match, outcome)


def score_line(match, outcome):
    sport = match["sport"]
    h, a = match["home"], match["away"]
    if sport == "Soccer":
        if outcome == "draw":
            g = random.randint(0, 3)
            return f"{h} {g}\u2013{g} {a}"
        hi = random.randint(1, 4)
        lo = random.randint(0, hi - 1)
        return (f"{h} {hi}\u2013{lo} {a}" if outcome == "home"
                else f"{h} {lo}\u2013{hi} {a}")
    if sport == "Basketball":
        win = random.randint(96, 122)
        lose = win - random.randint(1, 18)
        return (f"{h} {win}\u2013{lose} {a}" if outcome == "home"
                else f"{h} {lose}\u2013{win} {a}")
    if sport == "Tennis":
        loser_sets = random.randint(0, 1)
        return (f"{h} 2\u2013{loser_sets} {a}" if outcome == "home"
                else f"{h} {loser_sets}\u20132 {a}")
    # Football
    win = random.choice([17, 20, 21, 24, 27, 28, 31, 34])
    lose = random.choice([3, 7, 10, 13, 14, 17, 20])
    if lose >= win:
        lose = win - 3
    return (f"{h} {win}\u2013{lose} {a}" if outcome == "home"
            else f"{h} {lose}\u2013{win} {a}")


class Sportsbook:
    def __init__(self, root):
        self.root = root
        root.title("Sportsbook")
        root.configure(bg=FELT)
        root.resizable(False, False)
        self.balance = wallet.get_credits()
        self.stake = 25
        self.slip = []          # list of dicts: match, outcome, odds, stake
        self._new_slate()
        self._build()
        self.render_matches()
        self.render_slip()
        self.refresh()

    def _new_slate(self):
        sports = ["Soccer", "Soccer", "Basketball", "Tennis", "Football"]
        self.matches = [make_match(s) for s in sports]

    def _build(self):
        f = tk.Frame(self.root, bg=FELT, padx=16, pady=12)
        f.pack()
        tk.Label(f, text="\u2605 SPORTSBOOK \u2605", bg=FELT, fg=GOLD,
                 font=("Helvetica", 20, "bold")).pack()

        body = tk.Frame(f, bg=FELT)
        body.pack()

        # left: matches
        self.matches_frame = tk.Frame(body, bg=FELT)
        self.matches_frame.pack(side="left", anchor="n", padx=(0, 14))

        # right: bet slip
        right = tk.Frame(body, bg="#0a1f16", padx=10, pady=8)
        right.pack(side="left", anchor="n")
        tk.Label(right, text="BET SLIP", bg="#0a1f16", fg=GOLD,
                 font=("Helvetica", 13, "bold")).pack(anchor="w")
        self.slip_frame = tk.Frame(right, bg="#0a1f16")
        self.slip_frame.pack(fill="x")
        self.slip_total = tk.Label(right, text="", bg="#0a1f16", fg="white",
                                   font=("Helvetica", 11, "bold"), justify="left")
        self.slip_total.pack(anchor="w", pady=4)

        # stake control
        stakebar = tk.Frame(f, bg=FELT, pady=8)
        stakebar.pack()
        self.bal_lbl = tk.Label(stakebar, text="", bg=FELT, fg="white",
                                font=("Helvetica", 13, "bold"))
        self.bal_lbl.pack(side="left", padx=8)
        tk.Label(stakebar, text="Stake:", bg=FELT, fg="white",
                 font=("Helvetica", 11)).pack(side="left")
        tk.Button(stakebar, text="\u2212", width=3, command=lambda: self.chg(-5),
                  font=("Helvetica", 11, "bold"), bg="#333", fg="white",
                  bd=0).pack(side="left")
        self.stake_var = tk.StringVar()
        self.stake_entry = tk.Entry(stakebar, textvariable=self.stake_var, width=6,
                                    justify="center", font=("Helvetica", 13, "bold"),
                                    bg="#0d2846", fg=GOLD, insertbackground=GOLD,
                                    relief="flat", bd=2)
        self.stake_entry.pack(side="left")
        self.stake_entry.bind("<Return>", lambda e: self.set_bet())
        self.stake_entry.bind("<FocusOut>", lambda e: self.set_bet())
        tk.Button(stakebar, text="+", width=3, command=lambda: self.chg(5),
                  font=("Helvetica", 11, "bold"), bg="#333", fg="white",
                  bd=0).pack(side="left")

        btns = tk.Frame(f, bg=FELT, pady=4)
        btns.pack()
        self.place_btn = tk.Button(btns, text="Place Bets", command=self.place,
                                   width=14, font=("Helvetica", 13, "bold"),
                                   bg="#1b7a4b", fg="white", activebackground=GOLD,
                                   bd=0, pady=6, cursor="hand2")
        self.place_btn.pack(side="left", padx=6)
        tk.Button(btns, text="New Slate", command=self.new_slate, width=12,
                  font=("Helvetica", 13, "bold"), bg="#3a5a8a", fg="white",
                  activebackground=GOLD, bd=0, pady=6, cursor="hand2").pack(
            side="left", padx=6)

        self.msg = tk.Label(f, text="Tap an outcome to add it to your slip.",
                            bg=FELT, fg="white", font=("Helvetica", 11, "bold"),
                            wraplength=560, justify="left")
        self.msg.pack(pady=6)

    # ---- matches ---------------------------------------------------------
    def render_matches(self):
        for w in self.matches_frame.winfo_children():
            w.destroy()
        labels3 = ["1", "X", "2"]
        labels2 = ["1", "2"]
        for mi, m in enumerate(self.matches):
            row = tk.Frame(self.matches_frame, bg="#0a1f16", padx=8, pady=6)
            row.pack(fill="x", pady=3)
            tk.Label(row, text=f"[{m['sport']}]  {m['home']}  v  {m['away']}",
                     bg="#0a1f16", fg="white", font=("Helvetica", 11, "bold"),
                     width=40, anchor="w").pack(anchor="w")
            obar = tk.Frame(row, bg="#0a1f16")
            obar.pack(anchor="w", pady=2)
            labels = labels3 if len(m["outcomes"]) == 3 else labels2
            for oi, outcome in enumerate(m["outcomes"]):
                picked = any(s["mi"] == mi and s["outcome"] == outcome
                             for s in self.slip)
                b = tk.Button(
                    obar, text=f"{labels[oi]}  {m['odds'][oi]:.2f}",
                    width=10, font=("Helvetica", 11, "bold"),
                    bg="#e9c46a" if picked else "#16342a",
                    fg="#222" if picked else "white",
                    relief="sunken" if picked else "raised", bd=2, cursor="hand2",
                    command=lambda mi=mi, o=outcome: self.toggle(mi, o))
                b.pack(side="left", padx=3)

    def toggle(self, mi, outcome):
        for i, s in enumerate(self.slip):
            if s["mi"] == mi and s["outcome"] == outcome:
                self.slip.pop(i)
                self.render_matches()
                self.render_slip()
                return
        # replace any existing selection on the same match (one pick per match)
        self.slip = [s for s in self.slip if s["mi"] != mi]
        m = self.matches[mi]
        oi = m["outcomes"].index(outcome)
        self.slip.append({"mi": mi, "outcome": outcome, "odds": m["odds"][oi],
                          "stake": self.stake})
        self.render_matches()
        self.render_slip()

    # ---- slip ------------------------------------------------------------
    def render_slip(self):
        for w in self.slip_frame.winfo_children():
            w.destroy()
        if not self.slip:
            tk.Label(self.slip_frame, text="(empty)", bg="#0a1f16", fg="#7f9c8c",
                     font=("Helvetica", 10, "italic")).pack(anchor="w")
            self.slip_total.config(text="")
            return
        name = {"home": lambda m: m["home"], "away": lambda m: m["away"],
                "draw": lambda m: "Draw"}
        total_stake = ret = 0
        for s in self.slip:
            m = self.matches[s["mi"]]
            pick = name[s["outcome"]](m)
            tk.Label(self.slip_frame,
                     text=f"{pick} @ {s['odds']:.2f}  \u2013 stake {s['stake']}",
                     bg="#0a1f16", fg="white", font=("Helvetica", 10),
                     anchor="w").pack(anchor="w")
            total_stake += s["stake"]
            ret += s["stake"] * s["odds"]
        self.slip_total.config(
            text=f"Total stake: {total_stake}\nPotential return: {ret:.2f}")

    def chg(self, d):
        self.stake = max(5, min(self.balance if self.balance >= 5 else 5,
                                self.stake + d))
        self.refresh()

    def set_bet(self):
        """Set the chip stake to the amount typed into the entry box."""
        try:
            self.chg(int(float(self.stake_var.get())) - self.stake)
        except (TypeError, ValueError):
            pass
        self.stake_var.set(str(self.stake))

    def refresh(self):
        wallet.set_credits(self.balance)
        self.bal_lbl.config(text=f"Balance: {self.balance}")
        self.stake_var.set(str(self.stake))

    def new_slate(self):
        self.slip = []
        self._new_slate()
        self.render_matches()
        self.render_slip()
        self.msg.config(text="New slate loaded. Tap outcomes to bet.", fg="white")

    # ---- settlement ------------------------------------------------------
    def place(self):
        if not self.slip:
            self.msg.config(text="Your bet slip is empty.")
            return
        total_stake = sum(s["stake"] for s in self.slip)
        if total_stake > self.balance:
            self.msg.config(text="Not enough balance for these stakes.")
            return
        self.balance -= total_stake

        # simulate each match that appears in the slip
        results = {}
        for s in self.slip:
            if s["mi"] not in results:
                results[s["mi"]] = simulate(self.matches[s["mi"]])

        lines = []
        total_ret = 0
        for s in self.slip:
            m = self.matches[s["mi"]]
            outcome, score = results[s["mi"]]
            won = outcome == s["outcome"]
            if won:
                ret = round(s["stake"] * s["odds"])
                total_ret += ret
                lines.append(f"\u2705 {score}  (+{ret})")
            else:
                lines.append(f"\u274c {score}")
        self.balance += total_ret

        net = total_ret - total_stake
        head = (f"Returned {total_ret} on {total_stake} staked "
                f"({'+' if net >= 0 else ''}{net}).")
        self.msg.config(text=head + "\n" + "\n".join(dict.fromkeys(lines)),
                        fg=GOLD if net > 0 else "white")

        self.slip = []
        if self.balance < 5:
            self.msg.config(text=head + "\nOut of funds \u2014 buy more credits!")
            wallet.close_game(self.root)
        self._new_slate()
        self.render_matches()
        self.render_slip()
        self.stake = min(self.stake, max(5, self.balance))
        self.refresh()


def main():
    root = tk.Tk()
    Sportsbook(root)
    root.mainloop()


if __name__ == "__main__":
    main()
