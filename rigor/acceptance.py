LEVELS = ["L0", "L1", "L2", "L3", "L4"]


def normalize_level(level):
    value = str(level or "").upper()
    if value not in LEVELS:
        raise ValueError("acceptance level must be one of " + ", ".join(LEVELS))
    return value


def at_least(actual, required):
    return LEVELS.index(normalize_level(actual)) >= LEVELS.index(normalize_level(required))
