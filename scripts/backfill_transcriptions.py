"""One-off maintenance script: fills in IPA transcription for any `words`
row that doesn't have one yet (e.g. words generated before the transcription
feature existed), then re-syncs each affected user's Obsidian note so the
fix is visible in the vault immediately rather than waiting for that word's
next natural sync (a status change).

    python -m scripts.backfill_transcriptions
"""

import asyncio

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from bot.ai.gemini_provider import GeminiAIProvider
from bot.ai.router import AIRouter
from bot.config import settings
from bot.database.models.knowledge_node import KnowledgeNode
from bot.database.models.user_word import UserWord
from bot.database.models.word import Word
from bot.database.session import get_session
from bot.learning.transcription_rules import is_plausible_ipa
from bot.services.knowledge_graph_service import KnowledgeGraphService
from bot.services.mappers import user_word_to_dto


async def main() -> None:
    router = AIRouter(
        default_model=settings.gemini_default_model, advanced_model=settings.gemini_advanced_model
    )
    ai_provider = GeminiAIProvider(settings.gemini_api_key, router)
    updated_word_ids: set[int] = set()

    async with get_session() as session:
        result = await session.execute(
            select(Word).where(
                (Word.transcription_uk.is_(None)) | (Word.transcription_us.is_(None))
            )
        )
        words = list(result.scalars().all())
        print(f"Found {len(words)} words missing transcription.")

        for word in words:
            try:
                uk, us = await ai_provider.generate_transcription(word.lemma, word.part_of_speech)
            except Exception as exc:  # noqa: BLE001 -- best-effort backfill, keep going
                print(f"  ! {word.lemma}: generation failed ({exc})")
                continue

            word.transcription_uk = uk if is_plausible_ipa(uk) else None
            word.transcription_us = us if is_plausible_ipa(us) else None
            updated_word_ids.add(word.id)
            print(f"  {word.lemma}: uk={word.transcription_uk!r} us={word.transcription_us!r}")

        await session.flush()

    print(f"\nUpdated {len(updated_word_ids)} words. Re-syncing affected Obsidian notes...")

    if not updated_word_ids:
        return

    async with get_session() as session:
        result = await session.execute(
            select(UserWord)
            .options(selectinload(UserWord.word))
            .where(UserWord.word_id.in_(updated_word_ids))
        )
        affected_user_words = list(result.scalars().all())

        knowledge_graph = KnowledgeGraphService(session, settings.obsidian_vault_path)
        resynced = 0
        for user_word in affected_user_words:
            # Only bother re-syncing words that actually already have a note
            # in the vault (i.e. were synced at least once before).
            node_check = await session.execute(
                select(KnowledgeNode).where(
                    KnowledgeNode.user_id == user_word.user_id,
                    KnowledgeNode.word_id == user_word.word_id,
                )
            )
            if node_check.scalar_one_or_none() is None:
                continue

            await knowledge_graph.sync_word_node(user_word.user_id, user_word_to_dto(user_word))
            resynced += 1

        print(f"Re-synced {resynced} notes.")


if __name__ == "__main__":
    asyncio.run(main())
