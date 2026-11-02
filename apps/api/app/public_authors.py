"""Minimal public attribution, without exposing account identifiers or contacts."""


def public_publisher_name(name: str | None) -> str | None:
    if name is None:
        return None
    parts = name.split()
    first = parts[0] if parts else ""
    if not first or "@" in first or not any(character.isalpha() for character in first):
        return "Usuario de MascoMatch"
    return first
