"""Per-user credit wallet for the betting-shop arcade games.

Every game in this package reads its starting balance from, and writes every
balance change back to, this persisted wallet. Balances are keyed by user
account, so credits belong to whoever is logged in rather than to the machine:
what you finish blackjack with is what roulette starts with *for that user*.
Buying credits (from the betting shop GUI or the in-game top-up) increases the
signed-in user's balance.

Which user a call applies to is resolved in this order:

1. an explicit ``user=`` argument (the betting-shop GUI passes ``self.user_id``);
2. the ``ARCADE_USER`` environment variable (the launcher sets this on each
   game subprocess so the game inherits the logged-in user);
3. a shared ``_default`` bucket, used when a game is run standalone with no
   user context.

The balances are persisted to ``wallet.json`` next to this module so they
survive across separately-launched game processes. Reads and writes hit the
file each call so concurrently-open games observe each other's balance. This is
a local dev store; it is not safe against simultaneous read-modify-write races
between two processes writing at the exact same instant (last writer wins).
"""

import json
import os
import threading
from datetime import datetime

_HERE = os.path.dirname(os.path.abspath(__file__))
WALLET_PATH = os.path.join(_HERE, "wallet.json")

# Rolling log of arcade plays (balance changes) shared across game processes.
HISTORY_PATH = os.path.join(_HERE, "wallet_history.json")
MAX_HISTORY = 200

# Environment variable the launcher sets so the wallet can tag each balance
# change with the name of the game that caused it.
GAME_ENV_VAR = "ARCADE_GAME"

# Environment variable the launcher sets so a game subprocess knows which
# logged-in user account its credits belong to.
USER_ENV_VAR = "ARCADE_USER"

# Bucket used when no user account can be resolved (e.g. a game launched
# standalone, outside the betting-shop GUI).
DEFAULT_USER = "_default"

# Credits granted the very first time a user's wallet is used (before any
# purchase).
DEFAULT_STARTING_CREDITS = 1000

_lock = threading.Lock()


def _current_user(user=None):
    """Resolve which account a wallet operation applies to.

    Prefers an explicit ``user`` argument, then the ``ARCADE_USER`` environment
    variable, then the shared :data:`DEFAULT_USER` bucket. Always returns a
    non-empty string usable as a storage key.
    """
    if user is not None and str(user) != "":
        return str(user)
    env_user = os.environ.get(USER_ENV_VAR)
    if env_user:
        return str(env_user)
    return DEFAULT_USER


def _read_all():
    """Return ``{user_id: credits}`` for every account, or ``{}`` if unreadable.

    Transparently migrates the legacy single-balance format
    (``{"credits": N}``) into the shared :data:`DEFAULT_USER` bucket so older
    wallet files keep working.
    """
    try:
        with open(WALLET_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    users = data.get("users")
    if isinstance(users, dict):
        balances = {}
        for uid, credits in users.items():
            try:
                balances[str(uid)] = int(credits)
            except (ValueError, TypeError):
                continue
        return balances
    # Legacy format: a single shared balance under "credits".
    if "credits" in data:
        try:
            return {DEFAULT_USER: int(data["credits"])}
        except (ValueError, TypeError):
            return {}
    return {}


def _write_all(balances):
    """Atomically persist the full ``{user_id: credits}`` map (each >= 0)."""
    clean = {str(uid): max(0, int(credits)) for uid, credits in balances.items()}
    tmp = WALLET_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"users": clean}, fh)
    os.replace(tmp, WALLET_PATH)
    return clean


def get_credits(user=None):
    """Return the current credit balance for ``user`` (or the resolved account).

    On a user's first ever use their wallet is seeded with
    ``DEFAULT_STARTING_CREDITS``.
    """
    uid = _current_user(user)
    with _lock:
        balances = _read_all()
        if uid not in balances:
            balances[uid] = DEFAULT_STARTING_CREDITS
            _write_all(balances)
            return DEFAULT_STARTING_CREDITS
        return balances[uid]


def _read_history():
    """Return the stored play history (newest last), or [] if unreadable."""
    try:
        with open(HISTORY_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
            return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def _record_play(old, new, uid):
    """Append a play entry for a balance change made by a running game.

    Only balance changes that happen inside a launched game process (where the
    launcher has set ``GAME_ENV_VAR``) and that actually move the balance are
    recorded, so buying/cashing out credits from the GUI is not logged as a
    game play. Entries are tagged with ``uid`` so each account sees only its
    own plays.
    """
    game = os.environ.get(GAME_ENV_VAR)
    if not game or old is None or new == old:
        return
    entry = {
        "game": game,
        "user": uid,
        "change": new - old,
        "balance": new,
        "played_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    history = _read_history()
    history.append(entry)
    history = history[-MAX_HISTORY:]
    tmp = HISTORY_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(history, fh)
    os.replace(tmp, HISTORY_PATH)


def get_history(limit=50, user=None):
    """Return recent arcade plays for ``user``, newest first (up to ``limit``).

    Legacy entries recorded before per-user tagging (no ``user`` field) are
    treated as belonging to the shared :data:`DEFAULT_USER` bucket.
    """
    uid = _current_user(user)
    with _lock:
        history = _read_history()
    mine = [e for e in history if str(e.get("user", DEFAULT_USER)) == uid]
    return list(reversed(mine[-limit:]))


def close_game(window, delay_ms=3000, message="Out of credits — closing…"):
    """Auto-close a game window once the player has run out of credits.

    Called from a game's out-of-credits branch (a point where no further bet is
    possible). The window title is updated and the window is destroyed after a
    short delay so the player can read the final result before it closes; since
    each game owns its own Tk root, destroying it ends that game's process.

    Idempotent: repeated calls only schedule the close once.
    """
    if window is None or getattr(window, "_arcade_closing", False):
        return
    try:
        window._arcade_closing = True
        try:
            window.title(message)
        except Exception:
            pass
        window.after(int(delay_ms), window.destroy)
    except Exception:
        pass


def set_credits(value, user=None):
    """Overwrite ``user``'s balance with ``value`` (clamped to >= 0).

    Records a play-history entry when the change originates from a running
    game (see :func:`_record_play`).
    """
    uid = _current_user(user)
    with _lock:
        balances = _read_all()
        old = balances.get(uid)
        new = max(0, int(value))
        balances[uid] = new
        _write_all(balances)
        _record_play(old, new, uid)
        return new


def buy_credits(amount, user=None):
    """Add ``amount`` credits to ``user``'s balance and return the new total.

    Raises ``ValueError`` if ``amount`` is not a positive number.
    """
    amount = int(amount)
    if amount <= 0:
        raise ValueError("Credit amount must be positive")
    uid = _current_user(user)
    with _lock:
        balances = _read_all()
        balance = balances.get(uid, 0)
        balances[uid] = balance + amount
        _write_all(balances)
        return balances[uid]
