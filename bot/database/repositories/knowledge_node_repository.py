from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.database.models.enums import KnowledgeNodeType
from bot.database.models.knowledge_node import KnowledgeNode
from bot.database.models.word import Word


class KnowledgeNodeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_word(self, user_id: int, word_id: int) -> KnowledgeNode | None:
        result = await self._session.execute(
            select(KnowledgeNode).where(
                KnowledgeNode.user_id == user_id, KnowledgeNode.word_id == word_id
            )
        )
        return result.scalar_one_or_none()

    async def get_by_type_and_slug(
        self, user_id: int, node_type: KnowledgeNodeType, slug: str
    ) -> KnowledgeNode | None:
        result = await self._session.execute(
            select(KnowledgeNode).where(
                KnowledgeNode.user_id == user_id,
                KnowledgeNode.node_type == node_type,
                KnowledgeNode.slug == slug,
            )
        )
        return result.scalar_one_or_none()

    async def list_word_nodes_for_lemmas(
        self, user_id: int, slugs: list[str]
    ) -> list[KnowledgeNode]:
        if not slugs:
            return []
        result = await self._session.execute(
            select(KnowledgeNode).where(
                KnowledgeNode.user_id == user_id,
                KnowledgeNode.node_type == KnowledgeNodeType.WORD,
                KnowledgeNode.slug.in_(slugs),
            )
        )
        return list(result.scalars().all())

    async def list_word_nodes_by_topic(self, user_id: int, topic: str) -> list[KnowledgeNode]:
        """Word nodes belonging to this user whose underlying Word.topic
        matches, used to keep a topic note's word list current."""

        result = await self._session.execute(
            select(KnowledgeNode)
            .join(Word, KnowledgeNode.word_id == Word.id)
            .options(selectinload(KnowledgeNode.word))
            .where(
                KnowledgeNode.user_id == user_id,
                KnowledgeNode.node_type == KnowledgeNodeType.WORD,
                Word.topic == topic,
            )
            .order_by(KnowledgeNode.slug)
        )
        return list(result.scalars().all())

    async def create(
        self,
        *,
        user_id: int,
        word_id: int | None,
        node_type: KnowledgeNodeType,
        slug: str,
        obsidian_id: str,
        obsidian_path: str,
    ) -> KnowledgeNode:
        node = KnowledgeNode(
            user_id=user_id,
            word_id=word_id,
            node_type=node_type,
            slug=slug,
            obsidian_id=obsidian_id,
            obsidian_path=obsidian_path,
        )
        self._session.add(node)
        await self._session.flush()
        return node
