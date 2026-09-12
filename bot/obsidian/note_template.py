"""Builds the frontmatter + Markdown body for one Obsidian note.

Pure functions, no filesystem I/O (see bot/obsidian/vault.py for that) and
no DB session -- everything needed is passed in as plain values, so this
module is fully unit-testable.
"""

from dataclasses import dataclass
from datetime import date
from typing import Any

import yaml

from bot.database.models.enums import WordStatus
from bot.obsidian.slugs import slugify
from bot.services.dto import WordDTO


@dataclass(frozen=True)
class RelatedLink:
    slug: str
    label: str


def render_note(frontmatter: dict[str, Any], body: str) -> str:
    yaml_block = yaml.safe_dump(frontmatter, allow_unicode=True, sort_keys=False).strip()
    return f"---\n{yaml_block}\n---\n\n{body.strip()}\n"


def build_word_frontmatter(
    word: WordDTO, status: WordStatus, word_id: int, user_word_id: int
) -> dict[str, Any]:
    return {
        "type": "word",
        "word": word.lemma,
        "translation": word.translation,
        "transcription_uk": word.transcription_uk,
        "transcription_us": word.transcription_us,
        "level": word.level.value,
        "part_of_speech": word.part_of_speech.value,
        "status": status.value,
        "source": word.source.value,
        "word_id": word_id,
        "user_word_id": user_word_id,
        "updated_at": date.today().isoformat(),
    }


def build_word_body(
    word: WordDTO,
    related: list[RelatedLink],
    collocation_links: list[RelatedLink],
    topic: RelatedLink | None,
) -> str:
    lines = [f"# {word.lemma}", ""]

    if word.transcription_uk or word.transcription_us:
        pron = " / ".join(p for p in (word.transcription_uk, word.transcription_us) if p)
        lines += [f"**{pron}**", ""]

    lines += [
        f"**Переклад:** {word.translation}",
        "",
        f"**Рівень:** {word.level.value}",
        "",
        f"**Частина мови:** {word.part_of_speech.value}",
        "",
    ]

    if related:
        lines += ["## Related words", ""]
        lines += [f"- [[{link.slug}|{link.label}]]" for link in related]
        lines.append("")

    if collocation_links:
        lines += ["## Collocations", ""]
        lines += [f"- [[{link.slug}|{link.label}]]" for link in collocation_links]
        lines.append("")

    if topic:
        lines += ["## Topics", "", f"- [[{topic.slug}|{topic.label}]]", ""]

    lines += [
        "## Examples",
        "",
        f"> {word.example_en}",
        "",
        word.example_uk,
        "",
    ]
    return "\n".join(lines)


def build_word_note(
    word: WordDTO,
    status: WordStatus,
    word_id: int,
    user_word_id: int,
    related: list[RelatedLink],
    collocation_links: list[RelatedLink],
    topic: RelatedLink | None,
) -> str:
    frontmatter = build_word_frontmatter(word, status, word_id, user_word_id)
    body = build_word_body(word, related, collocation_links, topic)
    return render_note(frontmatter, body)


def build_topic_note(topic: str, words: list[RelatedLink]) -> str:
    frontmatter = {
        "type": "topic",
        "topic": topic,
        "updated_at": date.today().isoformat(),
    }
    lines = [f"# {topic}", "", f"Words and phrases related to **{topic}**:", ""]
    if words:
        lines += [f"- [[{link.slug}|{link.label}]]" for link in words]
    else:
        lines.append("*(none yet)*")
    body = "\n".join(lines)
    return render_note(frontmatter, body)


def related_links_from_lemmas(lemmas: list[str]) -> list[RelatedLink]:
    return [RelatedLink(slug=slugify(lemma), label=lemma) for lemma in lemmas]
