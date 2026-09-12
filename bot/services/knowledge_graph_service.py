"""Keeps each user's Obsidian vault in sync with their learning state.

PostgreSQL stays the sole source of truth for SRS state, statistics,
scheduling and answer history (see bot/database/models/knowledge_node.py's
docstring) -- this service only ever writes note files and a lightweight
cross-reference row (`knowledge_nodes`) pointing at them. Nothing in the
learning engine reads the vault back; it is a one-way, best-effort mirror
for the user to browse and explore in Obsidian.

Wiki-links to a word's synonyms/antonyms/collocations are written
unconditionally, even if the target note doesn't exist yet -- that's normal
Obsidian usage (an "unresolved link" renders as a ghost node in the graph)
and deliberately does NOT create a new learning item in user_words. Topic
notes, in contrast, are real notes kept in sync with the current word list
every time any word in that topic is synced.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models.enums import KnowledgeNodeType
from bot.database.repositories.knowledge_node_repository import KnowledgeNodeRepository
from bot.obsidian.note_template import (
    RelatedLink,
    build_topic_note,
    build_word_note,
    related_links_from_lemmas,
)
from bot.obsidian.slugs import slugify
from bot.obsidian.vault import VaultWriter
from bot.services.dto import UserWordDTO
from bot.utils.logging import get_logger

logger = get_logger(__name__)


class KnowledgeGraphService:
    def __init__(self, session: AsyncSession, vault_root: str) -> None:
        self._nodes = KnowledgeNodeRepository(session)
        self._vault = VaultWriter(vault_root)

    async def sync_word_node(self, user_id: int, user_word: UserWordDTO) -> None:
        word = user_word.word
        slug = slugify(word.lemma)

        topic_link = RelatedLink(slug=slugify(word.topic), label=word.topic) if word.topic else None
        related = related_links_from_lemmas([*word.synonyms, *word.antonyms])
        collocation_links = related_links_from_lemmas(word.collocations)

        content = build_word_note(
            word=word,
            status=user_word.status,
            word_id=word.id,
            user_word_id=user_word.id,
            related=related,
            collocation_links=collocation_links,
            topic=topic_link,
        )

        relative_path = f"users/{user_id}/Words/{slug}.md"
        self._vault.write_note(relative_path, content)

        existing = await self._nodes.get_by_word(user_id, word.id)
        if existing is None:
            await self._nodes.create(
                user_id=user_id,
                word_id=word.id,
                node_type=KnowledgeNodeType.WORD,
                slug=slug,
                obsidian_id=f"user-{user_id}/word/{slug}",
                obsidian_path=relative_path,
            )

        if word.topic:
            # Runs after the word's own node above so this word is included
            # in the topic's word list on its very first sync too.
            await self._sync_topic_node(user_id, word.topic)

        logger.info(
            "knowledge_node_synced",
            user_id=user_id,
            word=word.lemma,
            status=user_word.status.value,
        )

    async def _sync_topic_node(self, user_id: int, topic: str) -> None:
        slug = slugify(topic)
        existing = await self._nodes.get_by_type_and_slug(user_id, KnowledgeNodeType.TOPIC, slug)
        relative_path = f"users/{user_id}/Topics/{slug}.md"

        if existing is None:
            await self._nodes.create(
                user_id=user_id,
                word_id=None,
                node_type=KnowledgeNodeType.TOPIC,
                slug=slug,
                obsidian_id=f"user-{user_id}/topic/{slug}",
                obsidian_path=relative_path,
            )

        word_nodes = await self._nodes.list_word_nodes_by_topic(user_id, topic)
        word_links = [
            RelatedLink(slug=node.slug, label=node.word.lemma if node.word else node.slug)
            for node in word_nodes
        ]
        self._vault.write_note(relative_path, build_topic_note(topic, word_links))
