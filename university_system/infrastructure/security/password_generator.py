"""
Secure Password Generator

Provides cryptographically secure password generation for the university system.
Uses the secrets module for cryptographically strong random numbers suitable for
managing security-sensitive data like passwords and tokens.
"""

import secrets
import string
from typing import Optional

from university_system.core.i18n import get_text, _


# Character sets for password generation
LOWERCASE = string.ascii_lowercase
UPPERCASE = string.ascii_uppercase
DIGITS = string.digits
SPECIAL = "!@#$%^&*()_+-=[]{}|;:,.<>?"
SPECIAL_SAFE = "!@#$%^&*_+-="  # Subset that's safe for most systems


def generate_secure_password(
    length: int = 16,
    include_uppercase: bool = True,
    include_digits: bool = True,
    include_special: bool = True,
    safe_special_only: bool = True,
    exclude_ambiguous: bool = True,
) -> str:
    """
    Generate a cryptographically secure random password.

    Args:
        length: Password length (minimum 8, default 16)
        include_uppercase: Include uppercase letters (default True)
        include_digits: Include digits (default True)
        include_special: Include special characters (default True)
        safe_special_only: Use only safe special characters (default True)
        exclude_ambiguous: Exclude ambiguous characters like 0, O, l, 1, I (default True)

    Returns:
        A secure random password string

    Raises:
        ValueError: If length is less than 8 or character set is empty

    Example:
        >>> password = generate_secure_password()
        >>> len(password) == 16
        True
        >>> password = generate_secure_password(length=12, include_special=False)
        >>> len(password) == 12
        True
    """
    if length < 8:
        raise ValueError("Password length must be at least 8 characters for security")

    # Build character set
    alphabet = LOWERCASE

    if include_uppercase:
        alphabet += UPPERCASE

    if include_digits:
        alphabet += DIGITS

    if include_special:
        alphabet += SPECIAL_SAFE if safe_special_only else SPECIAL

    # Remove ambiguous characters if requested
    if exclude_ambiguous:
        ambiguous = "0O1lI"
        alphabet = "".join(c for c in alphabet if c not in ambiguous)

    if not alphabet:
        raise ValueError("Character set is empty - adjust parameters")

    # Generate password ensuring at least one of each required type
    required_chars = []

    if include_uppercase:
        upper_chars = "".join(c for c in UPPERCASE if c not in "OI") if exclude_ambiguous else UPPERCASE
        if upper_chars:
            required_chars.append(secrets.choice(upper_chars))

    if include_digits:
        digit_chars = "".join(c for c in DIGITS if c not in "01") if exclude_ambiguous else DIGITS
        if digit_chars:
            required_chars.append(secrets.choice(digit_chars))

    if include_special:
        special_chars = SPECIAL_SAFE if safe_special_only else SPECIAL
        if special_chars:
            required_chars.append(secrets.choice(special_chars))

    # Always include at least one lowercase
    lower_chars = "".join(c for c in LOWERCASE if c not in "l") if exclude_ambiguous else LOWERCASE
    required_chars.append(secrets.choice(lower_chars))

    # Fill remaining length with random characters
    remaining_length = length - len(required_chars)
    password_chars = required_chars + [secrets.choice(alphabet) for _ in range(remaining_length)]

    # Shuffle to avoid predictable positions
    secrets.SystemRandom().shuffle(password_chars)

    return "".join(password_chars)


def generate_simple_password(length: int = 12) -> str:
    """
    Generate a simple but secure password (letters and digits only).

    Useful for systems that don't support special characters.

    Args:
        length: Password length (minimum 8, default 12)

    Returns:
        A secure random password with only letters and digits
    """
    return generate_secure_password(
        length=length,
        include_uppercase=True,
        include_digits=True,
        include_special=False,
        exclude_ambiguous=True,
    )


def generate_passphrase(word_count: int = 4, separator: str = "-") -> str:
    """
    Generate a memorable passphrase using random words.

    Args:
        word_count: Number of words (minimum 4, default 4)
        separator: Word separator (default "-")

    Returns:
        A passphrase like "correct-horse-battery-staple"
    """
    if word_count < 4:
        raise ValueError("Passphrase must have at least 4 words for security")

    # Common English words for passphrases (curated for memorability)
    wordlist = [
        "apple", "arrow", "badge", "beach", "black", "blade", "blank", "blaze",
        "block", "bloom", "board", "boost", "brain", "brand", "brave", "bread",
        "break", "brick", "brief", "bring", "broad", "brown", "brush", "build",
        "burst", "cabin", "cable", "camel", "candy", "cargo", "carry", "catch",
        "cedar", "chain", "chair", "chalk", "charm", "chase", "chess", "chief",
        "child", "china", "chunk", "claim", "class", "clean", "clear", "click",
        "climb", "clock", "close", "cloud", "coach", "coast", "color", "coral",
        "couch", "count", "court", "cover", "craft", "crash", "cream", "creek",
        "crest", "crisp", "cross", "crown", "crush", "curve", "cycle", "dance",
        "denim", "depot", "depth", "diary", "diver", "dizzy", "dodge", "doing",
        "draft", "drain", "drake", "drama", "drank", "drawl", "dream", "dress",
        "drift", "drill", "drink", "drive", "droll", "drool", "drove", "drown",
        "drums", "dwarf", "dwell", "dying", "eager", "eagle", "early", "earth",
        "easel", "eight", "elbow", "elder", "elect", "elite", "ember", "empty",
        "enter", "equal", "equip", "erase", "error", "event", "every", "exact",
        "extra", "fable", "faint", "fairy", "faith", "false", "fancy", "fargo",
        "fault", "feast", "fence", "fever", "fiber", "field", "fifth", "fifty",
        "fight", "final", "first", "flair", "flame", "flash", "flask", "float",
        "flock", "flood", "floor", "flour", "fluid", "flush", "focal", "focus",
        "foggy", "force", "forge", "forma", "forth", "forum", "found", "frame",
        "frank", "fraud", "fresh", "fried", "front", "frost", "fruit", "fungi",
        "fuzzy", "gamma", "gauze", "gavel", "gecko", "geese", "genre", "ghost",
        "giant", "giddy", "given", "gizmo", "glare", "glass", "gleam", "glide",
        "globe", "gloom", "glory", "gloss", "glove", "glyph", "golem", "grace",
        "grade", "grain", "grand", "grant", "grape", "grasp", "grass", "grave",
        "gravy", "graze", "great", "green", "greet", "grief", "grill", "grind",
        "gripe", "groan", "groom", "grope", "gross", "group", "grove", "growl",
        "grown", "guard", "guess", "guide", "guild", "guilt", "guise", "gulch",
        "gumbo", "guppy", "gusto", "gypsy", "habit", "haiku", "hairs", "happy",
        "haven", "hazel", "heart", "heave", "heavy", "hedge", "helix", "hello",
        "hence", "herbs", "hinge", "hippo", "hitch", "hobby", "hoist", "honey",
        "honor", "horse", "hotel", "hound", "house", "human", "humid", "humor",
        "husky", "hyena", "ideal", "image", "inbox", "index", "input", "intro",
        "ionic", "irony", "ivory", "jaunt", "jazzy", "jeans", "jelly", "jewel",
        "jiffy", "joint", "joker", "jolly", "joust", "judge", "juice", "jumbo",
        "jumpy", "karma", "kayak", "kebab", "keeps", "ketch", "kicks", "kinky",
        "kiosk", "kitty", "knack", "knead", "kneel", "knife", "knock", "label",
        "labor", "lager", "lance", "large", "laser", "latch", "laugh", "layer",
        "leach", "learn", "lease", "ledge", "legal", "lemon", "lemur", "level",
        "lever", "light", "lilac", "limbo", "limit", "linen", "liner", "lingo",
        "links", "lions", "liver", "llama", "lobby", "local", "lodge", "lofty",
        "logic", "lotus", "lucky", "lumen", "lunar", "lunch", "lymph", "lyric",
        "macho", "macro", "madly", "magic", "major", "maker", "manor", "maple",
        "march", "marry", "marsh", "match", "mauve", "maxim", "mayor", "mealy",
        "means", "medal", "media", "melon", "mercy", "merge", "merit", "merry",
        "metal", "meter", "midst", "might", "mimic", "mince", "minor", "minus",
        "mirth", "misty", "mixer", "mocha", "modal", "model", "modem", "moist",
        "molar", "money", "month", "moose", "moral", "motor", "motto", "mound",
        "mount", "mouse", "mouth", "movie", "muddy", "mulch", "mummy", "munch",
        "mural", "music", "nasty", "naval", "nerve", "never", "nexus", "niche",
        "night", "nimby", "ninja", "ninth", "noble", "noise", "north", "notch",
        "novel", "nudge", "nurse", "nylon", "oasis", "ocean", "octet", "often",
        "olive", "omega", "onion", "onset", "opera", "optic", "orbit", "order",
        "organ", "other", "ought", "ounce", "outer", "outgo", "overt", "owing",
        "oxide", "ozone", "pagan", "paint", "panda", "panel", "panic", "paper",
        "paris", "party", "pasta", "paste", "patch", "patio", "pause", "peace",
        "peach", "pearl", "pedal", "penny", "perch", "peril", "perky", "pesto",
        "petty", "phase", "phone", "photo", "piano", "piece", "pilot", "pinch",
        "pitch", "pixel", "pizza", "place", "plaid", "plain", "plane", "plant",
        "plate", "plaza", "plead", "pleat", "plier", "pluck", "plumb", "plume",
        "plump", "plunk", "plush", "poach", "point", "poise", "polar", "polka",
        "ponds", "poppy", "porch", "poser", "posse", "pouch", "pound", "power",
        "prank", "prawn", "press", "price", "pride", "prime", "print", "prior",
        "prism", "prize", "probe", "promo", "prone", "prong", "proof", "prose",
        "proud", "prove", "prowl", "proxy", "prune", "psalm", "pudgy", "pulse",
        "punch", "pupil", "puppy", "purge", "purse", "pushy", "qualm", "quark",
        "queen", "query", "quest", "queue", "quick", "quiet", "quilt", "quirk",
        "quota", "quote", "rabbi", "racer", "radar", "radio", "rainy", "raise",
        "rally", "ramen", "ranch", "range", "rapid", "ratio", "razor", "reach",
        "react", "ready", "realm", "rebel", "rebus", "recap", "recur", "refer",
        "rehab", "reign", "relax", "relay", "relic", "remix", "repay", "reply",
        "rerun", "reset", "retro", "rhino", "rhyme", "rider", "ridge", "rifle",
        "right", "rigor", "rinse", "ripen", "risen", "risky", "ritzy", "rival",
        "river", "roast", "robot", "rocky", "rodeo", "rogue", "roman", "roomy",
        "roots", "rough", "round", "route", "rover", "royal", "rumba", "rumor",
        "rupee", "rural", "rusty", "sadly", "safer", "saint", "salad", "salon",
        "salsa", "salty", "sandy", "sauce", "sauna", "savor", "scald", "scale",
        "scalp", "scaly", "scamp", "scant", "scare", "scarf", "scary", "scene",
        "scent", "score", "scorn", "scout", "scram", "scrap", "screw", "scrub",
        "seedy", "sense", "serum", "serve", "setup", "seven", "sewer", "shack",
        "shade", "shake", "shall", "shame", "shank", "shape", "shard", "share",
        "shark", "sharp", "shave", "sheep", "sheer", "sheet", "shelf", "shell",
        "shift", "shine", "shiny", "shire", "shirt", "shock", "shore", "short",
        "shout", "shove", "shown", "showy", "shrew", "shrub", "shrug", "shuck",
        "siege", "sight", "sigma", "silky", "silly", "since", "siren", "sixth",
        "sixty", "skate", "skier", "skill", "skimp", "skirt", "skull", "skunk",
        "slack", "slang", "slant", "slash", "slate", "slave", "sleek", "sleep",
        "sleet", "slice", "slick", "slide", "sling", "slink", "slope", "slosh",
        "sloth", "slump", "slunk", "slurp", "slush", "slyly", "smack", "small",
        "smart", "smash", "smear", "smell", "smelt", "smile", "smirk", "smock",
        "smoke", "snack", "snail", "snake", "snare", "snarl", "sneak", "sneer",
        "snide", "sniff", "snipe", "snoop", "snore", "snort", "snout", "snowy",
        "snuck", "snuff", "soapy", "sober", "soggy", "solar", "solid", "solve",
        "sonar", "sonic", "sooth", "sorry", "sound", "south", "space", "spade",
        "spank", "spare", "spark", "spasm", "spawn", "speak", "spear", "speck",
        "speed", "spell", "spend", "spent", "spicy", "spied", "spiel", "spike",
        "spill", "spine", "spiny", "spiral", "spite", "splat", "split", "spoil",
        "spoke", "spoof", "spook", "spool", "spoon", "sport", "spout", "spray",
        "spree", "sprig", "spunk", "spurn", "spurt", "squad", "squat", "squid",
        "stack", "staff", "stage", "stain", "stair", "stake", "stale", "stalk",
        "stall", "stamp", "stand", "stank", "staph", "stare", "stark", "start",
        "stash", "state", "stave", "stays", "stead", "steak", "steal", "steam",
        "steel", "steep", "steer", "stern", "stick", "stiff", "still", "sting",
        "stink", "stint", "stock", "stoic", "stomp", "stone", "stony", "stood",
        "stool", "stoop", "store", "storm", "story", "stout", "stove", "strap",
        "straw", "stray", "strip", "strut", "stuck", "study", "stuff", "stump",
        "stung", "stunk", "stunt", "style", "sugar", "suite", "sulky", "sunny",
        "super", "surge", "sushi", "swamp", "swank", "swarm", "swear", "sweat",
        "sweep", "sweet", "swell", "swept", "swift", "swill", "swine", "swing",
        "swipe", "swirl", "swish", "swiss", "swoon", "swoop", "sword", "swore",
        "sworn", "swung", "table", "tacit", "tacky", "taint", "taken", "taker",
        "tally", "talon", "tango", "tangy", "taper", "tapir", "tardy", "taste",
        "tasty", "taunt", "tawny", "teach", "teary", "tease", "teddy", "teeth",
        "tempo", "tense", "tenth", "tepid", "terms", "terra", "terse", "thank",
        "theft", "their", "theme", "there", "these", "thick", "thief", "thigh",
        "thing", "think", "third", "thorn", "those", "three", "threw", "throb",
        "throw", "thrum", "thumb", "thump", "tiger", "tight", "tilde", "timer",
        "timid", "tipsy", "titan", "title", "toast", "today", "token", "tonal",
        "tonic", "tooth", "topaz", "topic", "torch", "torso", "total", "totem",
        "touch", "tough", "towel", "tower", "toxic", "trace", "track", "tract",
        "trade", "trail", "train", "trait", "tramp", "trash", "trawl", "tread",
        "treat", "trend", "triad", "trial", "tribe", "trick", "tried", "trill",
        "tripe", "trite", "troll", "troop", "trope", "trout", "trove", "truce",
        "truck", "truly", "trump", "trunk", "truss", "trust", "truth", "tryst",
        "tulip", "tumor", "tuned", "tuner", "tunic", "turbo", "tutor", "twang",
        "tweak", "tweed", "tweet", "twice", "twigs", "twine", "twirl", "twist",
        "tying", "udder", "ultra", "umbra", "uncle", "uncut", "under", "undid",
        "undue", "unfed", "unfit", "unify", "union", "unite", "unity", "until",
        "upper", "upset", "urban", "usage", "usher", "using", "usual", "utter",
        "vague", "valid", "value", "valve", "vapor", "vault", "vaunt", "vegan",
        "venom", "venue", "verge", "verse", "vicar", "video", "vigil", "vigor",
        "vinyl", "viola", "viper", "viral", "virus", "visit", "visor", "vista",
        "vital", "vivid", "vixen", "vocal", "vodka", "vogue", "voice", "voila",
        "vomit", "voted", "voter", "vouch", "vowel", "vying", "wacky", "wader",
        "wafer", "wager", "wages", "wagon", "waist", "waltz", "wanna", "warty",
        "waste", "watch", "water", "waver", "waxen", "weary", "weave", "wedge",
        "weedy", "weigh", "weird", "welch", "welsh", "wench", "wheat", "wheel",
        "where", "which", "while", "whine", "whiny", "whirl", "whisk", "white",
        "whole", "whoop", "whose", "widen", "wider", "widow", "width", "wield",
        "wight", "wince", "winch", "windy", "wiped", "wiper", "wired", "wiser",
        "witch", "witty", "woken", "woman", "women", "woods", "woozy", "wordy",
        "world", "worry", "worse", "worst", "worth", "would", "wound", "woven",
        "wrack", "wrath", "wreak", "wreck", "wrest", "wring", "wrist", "write",
        "wrong", "wrote", "wrung", "yacht", "yearn", "yeast", "yield", "young",
        "yours", "youth", "zebra", "zesty", "zippy", "zones",
    ]

    words = [secrets.choice(wordlist) for _ in range(word_count)]
    return separator.join(words)


def generate_temp_password() -> str:
    """
    Generate a temporary password for initial account setup.

    Returns a moderately strong password suitable for first-time login
    that users should be required to change.

    Returns:
        A 12-character secure password
    """
    return generate_secure_password(
        length=12,
        include_uppercase=True,
        include_digits=True,
        include_special=True,
        safe_special_only=True,
        exclude_ambiguous=True,
    )


def check_password_strength(password: str) -> dict:
    """
    Check the strength of a password.

    Args:
        password: The password to check

    Returns:
        Dictionary with strength score (0-100), level, and suggestions
    """
    score = 0
    suggestions = []

    # Length checks
    if len(password) >= 8:
        score += 20
    else:
        suggestions.append("Use at least 8 characters")

    if len(password) >= 12:
        score += 10

    if len(password) >= 16:
        score += 10

    # Character type checks
    has_lower = any(c in LOWERCASE for c in password)
    has_upper = any(c in UPPERCASE for c in password)
    has_digit = any(c in DIGITS for c in password)
    has_special = any(c in SPECIAL for c in password)

    if has_lower:
        score += 10
    else:
        suggestions.append("Add lowercase letters")

    if has_upper:
        score += 15
    else:
        suggestions.append("Add uppercase letters")

    if has_digit:
        score += 15
    else:
        suggestions.append("Add numbers")

    if has_special:
        score += 20
    else:
        suggestions.append("Add special characters")

    # Pattern checks
    if password.lower() in ["password", "123456", "qwerty", "admin", "letmein"]:
        score = 0
        suggestions = ["Avoid common passwords"]

    # Determine strength level
    if score >= 80:
        level = "strong"
    elif score >= 60:
        level = "medium"
    elif score >= 40:
        level = "weak"
    else:
        level = "very weak"

    return {
        "score": min(score, 100),
        "level": level,
        "suggestions": suggestions,
    }


# Convenience aliases
secure_password = generate_secure_password
simple_password = generate_simple_password
temp_password = generate_temp_password
passphrase = generate_passphrase
