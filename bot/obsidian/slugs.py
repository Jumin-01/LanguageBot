"""Turns a word/phrase/topic string into a filesystem- and
wiki-link-safe Obsidian note name. Pure function, no I/O."""

import re

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    lowered = text.strip().lower()
    slug = _NON_ALNUM.sub("_", lowered).strip("_")
    return slug or "note"
