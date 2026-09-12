from bot.obsidian.slugs import slugify


def test_simple_word() -> None:
    assert slugify("affordable") == "affordable"


def test_multi_word_phrase() -> None:
    assert slugify("give up") == "give_up"


def test_apostrophe_and_punctuation() -> None:
    assert slugify("on the other hand") == "on_the_other_hand"


def test_mixed_case_is_lowercased() -> None:
    assert slugify("Affordable") == "affordable"


def test_leading_trailing_whitespace_stripped() -> None:
    assert slugify("  buy  ") == "buy"


def test_empty_string_falls_back_to_note() -> None:
    assert slugify("") == "note"


def test_only_punctuation_falls_back_to_note() -> None:
    assert slugify("---") == "note"
