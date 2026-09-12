from bot.learning.transcription_rules import is_plausible_ipa


def test_accepts_well_formed_ipa() -> None:
    assert is_plausible_ipa("/əˈfɔːdəbl/") is True


def test_rejects_none() -> None:
    assert is_plausible_ipa(None) is False


def test_rejects_empty_string() -> None:
    assert is_plausible_ipa("") is False


def test_rejects_missing_slashes() -> None:
    assert is_plausible_ipa("əˈfɔːdəbl") is False


def test_rejects_digits() -> None:
    assert is_plausible_ipa("/test123/") is False


def test_rejects_html_like_characters() -> None:
    assert is_plausible_ipa("/<script>/") is False


def test_accepts_us_and_uk_variants() -> None:
    assert is_plausible_ipa("/əˈfɔːrdəbl/") is True
    assert is_plausible_ipa("/ˈwɔːtər/") is True
