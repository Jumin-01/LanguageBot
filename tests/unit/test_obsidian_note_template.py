import yaml

from bot.database.models.enums import CEFRLevel, PartOfSpeech, WordSource, WordStatus
from bot.obsidian.note_template import (
    RelatedLink,
    build_topic_note,
    build_word_note,
    related_links_from_lemmas,
    render_note,
)
from bot.services.dto import WordDTO


def _word(**overrides) -> WordDTO:
    defaults = dict(
        id=1,
        lemma="affordable",
        translation="доступний за ціною, недорогий",
        example_en="This restaurant is affordable for students.",
        example_uk="Цей ресторан доступний за ціною для студентів.",
        level=CEFRLevel.B1,
        part_of_speech=PartOfSpeech.ADJECTIVE,
        topic="Money",
        transcription_uk="/əˈfɔːdəbl/",
        transcription_us="/əˈfɔːrdəbl/",
        synonyms=["cheap", "inexpensive"],
        antonyms=["expensive"],
        collocations=["affordable price", "affordable housing"],
        source=WordSource.AI_GENERATED,
    )
    defaults.update(overrides)
    return WordDTO(**defaults)


def test_render_note_produces_parseable_frontmatter() -> None:
    content = render_note({"type": "word", "word": "affordable"}, "# affordable")
    assert content.startswith("---\n")
    frontmatter_block = content.split("---\n")[1]
    parsed = yaml.safe_load(frontmatter_block)
    assert parsed["word"] == "affordable"


def test_word_note_includes_frontmatter_fields() -> None:
    word = _word()
    content = build_word_note(
        word=word,
        status=WordStatus.LEARNING,
        word_id=1,
        user_word_id=42,
        related=related_links_from_lemmas(word.synonyms + word.antonyms),
        collocation_links=related_links_from_lemmas(word.collocations),
        topic=RelatedLink(slug="money", label="Money"),
    )

    _, frontmatter_block, body = content.split("---\n", 2)
    frontmatter = yaml.safe_load(frontmatter_block)

    assert frontmatter["word"] == "affordable"
    assert frontmatter["status"] == "learning"
    assert frontmatter["level"] == "B1"
    assert frontmatter["transcription_uk"] == "/əˈfɔːdəbl/"
    assert frontmatter["transcription_us"] == "/əˈfɔːrdəbl/"
    assert frontmatter["word_id"] == 1
    assert frontmatter["user_word_id"] == 42


def test_word_note_body_has_wiki_links_for_related_and_collocations_and_topic() -> None:
    word = _word()
    content = build_word_note(
        word=word,
        status=WordStatus.NEW,
        word_id=1,
        user_word_id=42,
        related=related_links_from_lemmas(word.synonyms + word.antonyms),
        collocation_links=related_links_from_lemmas(word.collocations),
        topic=RelatedLink(slug="money", label="Money"),
    )

    assert "[[cheap|cheap]]" in content
    assert "[[expensive|expensive]]" in content
    assert "[[affordable_price|affordable price]]" in content
    assert "[[money|Money]]" in content
    assert "This restaurant is affordable for students." in content
    assert "Цей ресторан доступний за ціною для студентів." in content


def test_word_note_omits_sections_with_no_links() -> None:
    word = _word(synonyms=[], antonyms=[], collocations=[], topic=None)
    content = build_word_note(
        word=word,
        status=WordStatus.NEW,
        word_id=1,
        user_word_id=42,
        related=[],
        collocation_links=[],
        topic=None,
    )
    assert "## Related words" not in content
    assert "## Collocations" not in content
    assert "## Topics" not in content


def test_topic_note_has_type_topic() -> None:
    content = build_topic_note("Money", [])
    _, frontmatter_block, _ = content.split("---\n", 2)
    frontmatter = yaml.safe_load(frontmatter_block)
    assert frontmatter["type"] == "topic"


def test_topic_note_lists_linked_words() -> None:
    content = build_topic_note("Money", [RelatedLink(slug="affordable", label="affordable")])
    assert "[[affordable|affordable]]" in content


def test_topic_note_shows_placeholder_when_no_words_yet() -> None:
    content = build_topic_note("Money", [])
    assert "(none yet)" in content
