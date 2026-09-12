from pathlib import Path

import yaml
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models.enums import CEFRLevel, PartOfSpeech, WordStatus
from bot.database.models.user import User
from bot.database.repositories.knowledge_node_repository import KnowledgeNodeRepository
from bot.database.repositories.user_word_repository import UserWordRepository
from bot.database.repositories.word_repository import WordRepository
from bot.services.knowledge_graph_service import KnowledgeGraphService
from bot.services.mappers import user_word_to_dto


async def _create_user(session: AsyncSession) -> User:
    user = User(telegram_id=1, current_level=CEFRLevel.B1)
    session.add(user)
    await session.flush()
    return user


async def test_sync_word_node_writes_note_file_and_db_row(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    user = await _create_user(db_session)
    words = WordRepository(db_session)
    user_words = UserWordRepository(db_session)
    nodes = KnowledgeNodeRepository(db_session)

    word = await words.create(
        lemma="affordable",
        translation="доступний за ціною",
        example_en="This restaurant is affordable for students.",
        example_uk="Цей ресторан доступний за ціною для студентів.",
        level=CEFRLevel.B1,
        part_of_speech=PartOfSpeech.ADJECTIVE,
        topic="Money",
        transcription_uk="/əˈfɔːdəbl/",
        synonyms=["cheap"],
    )
    user_word = await user_words.create(user.id, word.id)
    service = KnowledgeGraphService(db_session, str(tmp_path))

    await service.sync_word_node(user.id, user_word_to_dto(user_word))

    note_path = tmp_path / "users" / str(user.id) / "Words" / "affordable.md"
    assert note_path.exists()
    content = note_path.read_text(encoding="utf-8")
    assert "[[cheap|cheap]]" in content
    assert "[[money|Money]]" in content

    _, frontmatter_block, _ = content.split("---\n", 2)
    frontmatter = yaml.safe_load(frontmatter_block)
    assert frontmatter["status"] == "new"
    assert frontmatter["word_id"] == word.id

    db_node = await nodes.get_by_word(user.id, word.id)
    assert db_node is not None
    assert db_node.obsidian_path == f"users/{user.id}/Words/affordable.md"

    topic_note_path = tmp_path / "users" / str(user.id) / "Topics" / "money.md"
    assert topic_note_path.exists()
    topic_content = topic_note_path.read_text(encoding="utf-8")
    assert "[[affordable|affordable]]" in topic_content


async def test_topic_note_accumulates_words_from_the_same_topic(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    user = await _create_user(db_session)
    words = WordRepository(db_session)
    user_words = UserWordRepository(db_session)
    service = KnowledgeGraphService(db_session, str(tmp_path))

    first = await words.create(
        lemma="affordable",
        translation="доступний за ціною",
        example_en="This restaurant is affordable.",
        example_uk="Цей ресторан доступний за ціною.",
        level=CEFRLevel.B1,
        part_of_speech=PartOfSpeech.ADJECTIVE,
        topic="Money",
    )
    second = await words.create(
        lemma="budget",
        translation="бюджет",
        example_en="We need a budget.",
        example_uk="Нам потрібен бюджет.",
        level=CEFRLevel.B1,
        part_of_speech=PartOfSpeech.NOUN,
        topic="Money",
    )

    first_user_word = await user_words.create(user.id, first.id)
    await service.sync_word_node(user.id, user_word_to_dto(first_user_word))
    second_user_word = await user_words.create(user.id, second.id)
    await service.sync_word_node(user.id, user_word_to_dto(second_user_word))

    topic_content = (tmp_path / "users" / str(user.id) / "Topics" / "money.md").read_text(
        encoding="utf-8"
    )
    assert "[[affordable|affordable]]" in topic_content
    assert "[[budget|budget]]" in topic_content


async def test_sync_word_node_updates_existing_note_status(
    db_session: AsyncSession, tmp_path: Path
) -> None:
    user = await _create_user(db_session)
    words = WordRepository(db_session)
    user_words = UserWordRepository(db_session)
    nodes = KnowledgeNodeRepository(db_session)

    word = await words.create(
        lemma="achieve",
        translation="досягати",
        example_en="She worked hard to achieve her goals.",
        example_uk="Вона наполегливо працювала, щоб досягти своїх цілей.",
        level=CEFRLevel.B1,
        part_of_speech=PartOfSpeech.VERB,
    )
    user_word = await user_words.create(user.id, word.id)
    service = KnowledgeGraphService(db_session, str(tmp_path))

    await service.sync_word_node(user.id, user_word_to_dto(user_word))

    user_word.status = WordStatus.LEARNED
    await user_words.save(user_word)
    await service.sync_word_node(user.id, user_word_to_dto(user_word))

    note_path = tmp_path / "users" / str(user.id) / "Words" / "achieve.md"
    content = note_path.read_text(encoding="utf-8")
    _, frontmatter_block, _ = content.split("---\n", 2)
    frontmatter = yaml.safe_load(frontmatter_block)
    assert frontmatter["status"] == "learned"

    # Still exactly one DB node -- the second sync updated it, didn't duplicate it.
    db_node = await nodes.get_by_word(user.id, word.id)
    assert db_node is not None
