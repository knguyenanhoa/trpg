"""Input sanitization and validation utilities."""

import re

from app.config import MAX_NAME_LENGTH, MAX_BACKSTORY_LENGTH


def sanitize_name(name: str) -> str:
    """Sanitize a character name: alphanumeric and spaces only, max length."""
    cleaned = re.sub(r"[^a-zA-Z0-9 ]", "", name)
    return cleaned[:MAX_NAME_LENGTH].strip()


def validate_name(name: str) -> tuple[bool, str]:
    """Validate a character name. Returns (valid, error_message)."""
    if not name or not name.strip():
        return False, "Name cannot be empty."
    if len(name) > MAX_NAME_LENGTH:
        return False, f"Name must be {MAX_NAME_LENGTH} characters or less."
    if not re.match(r"^[a-zA-Z0-9 ]+$", name):
        return False, "Name can only contain letters, numbers, and spaces."
    return True, ""


def sanitize_backstory(text: str) -> str:
    """Sanitize backstory text: printable ASCII only, max length."""
    cleaned = re.sub(r"[^\x20-\x7E\n]", "", text)
    return cleaned[:MAX_BACKSTORY_LENGTH]


def validate_backstory(text: str) -> tuple[bool, str]:
    """Validate backstory text."""
    if len(text) > MAX_BACKSTORY_LENGTH:
        return False, f"Backstory must be {MAX_BACKSTORY_LENGTH} characters or less."
    if re.search(r"[^\x20-\x7E\n]", text):
        return False, "Backstory can only contain printable characters."
    return True, ""


def name_to_folder(name: str) -> str:
    """Convert a character name to a safe folder name."""
    safe = re.sub(r"[^a-zA-Z0-9]", "_", name.lower())
    safe = re.sub(r"_+", "_", safe).strip("_")
    return safe or "unnamed"


def validate_float(value: str, min_val: float, max_val: float) -> tuple[bool, float, str]:
    """Validate and parse a float value within range."""
    try:
        f = float(value)
    except (ValueError, TypeError):
        return False, 0.0, "Must be a number."
    if f < min_val or f > max_val:
        return False, 0.0, f"Must be between {min_val} and {max_val}."
    return True, f, ""


def validate_int(value: str, min_val: int, max_val: int) -> tuple[bool, int, str]:
    """Validate and parse an integer value within range."""
    try:
        i = int(value)
    except (ValueError, TypeError):
        return False, 0, "Must be a whole number."
    if i < min_val or i > max_val:
        return False, 0, f"Must be between {min_val} and {max_val}."
    return True, i, ""
