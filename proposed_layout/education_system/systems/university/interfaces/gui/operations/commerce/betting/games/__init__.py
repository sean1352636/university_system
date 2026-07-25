"""Standalone casino/arcade games for the betting shop GUI.

Each module in this package is a self-contained tkinter game with its own
``main()`` entry point and Tk window. They are launched from the betting shop
casino tab as separate subprocesses so each game keeps its own event loop and
bankroll, fully isolated from the main betting application.
"""

import os
import subprocess
import sys

from . import wallet

# Directory holding the game scripts (this package's directory).
GAMES_DIR = os.path.dirname(os.path.abspath(__file__))

# Registry of games: (module_filename, display label), grouped roughly by type.
# Ordering here drives the button layout on the casino tab.
GAMES = [
    # Card & table games
    ("blackjack.py", "Blackjack"),
    ("video_blackjack.py", "Video Blackjack"),
    ("poker.py", "Poker"),
    ("video_poker.py", "Video Poker"),
    ("baccarat.py", "Baccarat"),
    ("dragon_tiger.py", "Dragon Tiger"),
    ("hi_lo.py", "Hi-Lo"),
    ("craps.py", "Craps"),
    # Roulette
    ("roulette.py", "Roulette"),
    ("electronic_roulette.py", "Electronic Roulette"),
    # Slots
    ("classic_slot.py", "Classic Slot"),
    ("fruit_machine.py", "Fruit Machine"),
    ("multiline_slot.py", "Multiline Slot"),
    ("progressive_slot.py", "Progressive Slot"),
    ("space_slot.py", "Space Slot"),
    ("wheel_bonus_slot.py", "Wheel Bonus Slot"),
    # Wheels
    ("big_six_wheel.py", "Big Six Wheel"),
    ("bonus_prize_wheel.py", "Bonus Prize Wheel"),
    ("color_wheel.py", "Color Wheel"),
    ("dual_wheel.py", "Dual Wheel"),
    ("multiplier_wheel.py", "Multiplier Wheel"),
    ("target_wheel.py", "Target Wheel"),
    # Number & misc games
    ("bingo.py", "Bingo"),
    ("keno.py", "Keno"),
    ("plinko.py", "Plinko"),
    ("sportsbook.py", "Sportsbook"),
]


def launch_game(filename, game_name=None, user=None):
    """Launch a game module in its own window as a separate process.

    Runs the game script with the current Python interpreter. Each game owns
    its own Tk root and mainloop, so it runs independently of the betting shop
    GUI. ``game_name`` (the display label) is passed to the child via the
    ``ARCADE_GAME`` environment variable so the wallet can tag the play history
    it records. ``user`` (the logged-in account id) is passed via the
    ``ARCADE_USER`` environment variable so the game plays against that user's
    credit balance rather than a shared one. Returns the ``subprocess.Popen``
    handle.

    Raises ``FileNotFoundError`` if the game script does not exist.
    """
    path = os.path.join(GAMES_DIR, filename)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"Game not found: {filename}")
    env = dict(os.environ)
    env[wallet.GAME_ENV_VAR] = game_name or filename
    if user is not None and str(user) != "":
        env[wallet.USER_ENV_VAR] = str(user)
    return subprocess.Popen([sys.executable, path], env=env)  # noqa: S603
