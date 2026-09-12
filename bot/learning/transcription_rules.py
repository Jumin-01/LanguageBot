"""Lightweight sanity check for AI-generated IPA transcriptions.

Not a full IPA grammar validator -- just rejects obviously-wrong output
(empty, missing slashes, or containing characters that can't appear in an
IPA transcription) before it reaches the database, per the spec's
"automatic validation before saving". A word with an implausible
transcription is still saved -- only the transcription field is dropped.
"""

import re

_SLASH_WRAPPED = re.compile(r"^/.+/$")
_DISALLOWED_CHARS = re.compile(r"[0-9=+*_#<>@]")


def is_plausible_ipa(value: str | None) -> bool:
    if not value:
        return False
    stripped = value.strip()
    if not _SLASH_WRAPPED.match(stripped):
        return False
    return not _DISALLOWED_CHARS.search(stripped)
