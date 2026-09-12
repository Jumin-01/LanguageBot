"""AI-backed word generation with dedup and level filtering enforced here in
code -- never trusted to the LLM's own output. This is PoolService's
production VocabularyProvider once a real AIProvider is configured.

Selection priority, cheapest/smartest first:

1. **Graph-adjacent catalog reuse.** The user's known words' own
   synonyms/antonyms/collocations (already stored on each Word row --
   Postgres *is* the knowledge graph; Obsidian is just a human-readable
   view of it) point at other catalog words. These are the candidates most
   likely to meaningfully extend what the user already knows. When there
   are more of them than needed, the advanced AI model *ranks* them
   (score + reason) -- business logic still makes the final pick and still
   enforces dedup/level, so the AI can only reorder a pre-vetted set, never
   invent or smuggle in a new one (spec: "AI не може порушити правила
   системи").
2. **Any other unlinked, level-appropriate catalog word**, if step 1 didn't
   fill the request.
3. **Live AI generation**, only for whatever's still missing after 1 and 2.
   One over-requested call rather than several small ones (a free-tier
   quota is spent per *call*, not per word).

Every AI-generated candidate is validated (bot/ai/validators.py) before it's
persisted; a candidate that fails validation is dropped, not written to the
DB, per spec.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from bot.ai.exceptions import AIGenerationError
from bot.ai.provider import AIProvider, GenerateWordsRequest
from bot.ai.validators import sanitize_transcriptions, validate_generated_word
from bot.database.models.enums import WordSource
from bot.database.models.user import User
from bot.database.models.word import Word
from bot.database.repositories.answer_history_repository import AnswerHistoryRepository
from bot.database.repositories.user_repository import UserRepository
from bot.database.repositories.user_word_repository import UserWordRepository
from bot.database.repositories.word_repository import WordRepository
from bot.learning.level_rules import is_within_level_band
from bot.services.dto import WordDTO
from bot.services.mappers import word_to_dto
from bot.utils.logging import get_logger

logger = get_logger(__name__)

# A single AI request costs the same against a free-tier quota whether it
# asks for 2 words or 6 -- so over-requesting generously in one call is
# effectively free, while a second *call* (MAX_GENERATION_ATTEMPTS) is not.
MAX_GENERATION_ATTEMPTS = 1
OVER_REQUEST_FACTOR = 3

# Cap on how many known words feed the graph-adjacency lookup and the
# ranking prompt -- keeps both the SQL IN-clause and the AI context small
# (spec section 22: "не передавати Gemini зайві дані").
MAX_KNOWN_WORDS_FOR_GRAPH = 60
MAX_KNOWN_WORDS_FOR_RANKING_PROMPT = 20


class VocabularyGenerationService:
    def __init__(self, session: AsyncSession, ai_provider: AIProvider) -> None:
        self._words = WordRepository(session)
        self._user_words = UserWordRepository(session)
        self._users = UserRepository(session)
        self._history = AnswerHistoryRepository(session)
        self._ai = ai_provider

    async def generate_candidate_words(self, user_id: int, count: int) -> list[WordDTO]:
        user = await self._users.get_by_id(user_id)
        if user is None or count <= 0:
            return []

        known_word_ids = await self._user_words.list_known_word_ids(user_id)
        known_words = await self._words.list_by_ids(list(known_word_ids))
        exclude_lemmas = {w.lemma.strip().lower() for w in known_words}
        known_words_context = [f"{w.lemma} - {w.translation}" for w in known_words[:60]]
        topics_hint = sorted({w.topic for w in known_words if w.topic})[:10]
        mistake_topics = await self._recent_mistake_topics(user_id)

        accepted: list[Word] = await self._reuse_from_catalog(
            user, known_words, count, exclude_lemmas, known_word_ids
        )
        if len(accepted) >= count:
            logger.info("vocabulary_reused_from_catalog", user_id=user_id, count=len(accepted))
            return [word_to_dto(w) for w in accepted]

        for _ in range(MAX_GENERATION_ATTEMPTS):
            still_needed = count - len(accepted)
            if still_needed <= 0:
                break

            request = GenerateWordsRequest(
                level=user.current_level,
                count=still_needed * OVER_REQUEST_FACTOR,
                known_words=known_words_context,
                exclude_lemmas=set(exclude_lemmas),
                topics_hint=topics_hint,
                mistake_topics=mistake_topics,
            )
            try:
                generated = await self._ai.generate_words(request)
            except AIGenerationError:
                logger.warning("vocabulary_generation_ai_call_failed", user_id=user_id)
                break

            for item in generated:
                if len(accepted) >= count:
                    break

                lemma_normalized = item.lemma.strip().lower()
                if lemma_normalized in exclude_lemmas:
                    continue
                if not is_within_level_band(item.level, user.current_level):
                    continue

                existing = await self._words.get_by_lemma(item.lemma, item.part_of_speech)
                if existing is not None:
                    if existing.id in known_word_ids:
                        exclude_lemmas.add(lemma_normalized)
                        continue
                    word = existing
                else:
                    problems = validate_generated_word(item)
                    if problems:
                        logger.warning(
                            "vocabulary_candidate_rejected", lemma=item.lemma, problems=problems
                        )
                        exclude_lemmas.add(lemma_normalized)
                        continue

                    transcription_uk, transcription_us = sanitize_transcriptions(item)
                    word = await self._words.create(
                        lemma=item.lemma,
                        translation=item.translation,
                        example_en=item.example_en,
                        example_uk=item.example_uk,
                        level=item.level,
                        part_of_speech=item.part_of_speech,
                        topic=item.topic,
                        transcription_uk=transcription_uk,
                        transcription_us=transcription_us,
                        synonyms=item.synonyms,
                        antonyms=item.antonyms,
                        collocations=item.collocations,
                        source=WordSource.AI_GENERATED,
                    )

                accepted.append(word)
                exclude_lemmas.add(lemma_normalized)
                known_word_ids.add(word.id)

        return [word_to_dto(w) for w in accepted]

    async def _reuse_from_catalog(
        self,
        user: User,
        known_words: list[Word],
        count: int,
        exclude_lemmas: set[str],
        known_word_ids: set[int],
    ) -> list[Word]:
        accepted: list[Word] = []

        graph_candidates = await self._graph_adjacent_candidates(known_words)
        if len(graph_candidates) > count:
            graph_candidates = await self._rank_candidates(user, known_words, graph_candidates)
        accepted += self._take(
            user, graph_candidates, count - len(accepted), exclude_lemmas, known_word_ids
        )

        if len(accepted) < count:
            same_level = await self._words.get_unlinked_for_user(
                user.id, count, level=user.current_level
            )
            broader = await self._words.get_unlinked_for_user(user.id, count * 3)
            accepted += self._take(
                user, [*same_level, *broader], count - len(accepted), exclude_lemmas, known_word_ids
            )

        return accepted

    def _take(
        self,
        user: User,
        candidates: list[Word],
        limit: int,
        exclude_lemmas: set[str],
        known_word_ids: set[int],
    ) -> list[Word]:
        taken: list[Word] = []
        for word in candidates:
            if len(taken) >= limit:
                break

            lemma_normalized = word.lemma.strip().lower()
            if lemma_normalized in exclude_lemmas or word.id in known_word_ids:
                continue
            if not is_within_level_band(word.level, user.current_level):
                continue

            taken.append(word)
            exclude_lemmas.add(lemma_normalized)
            known_word_ids.add(word.id)
        return taken

    async def _graph_adjacent_candidates(self, known_words: list[Word]) -> list[Word]:
        """Words already in the catalog that are a synonym/antonym/
        collocation of something the user knows -- this user's local
        knowledge-graph neighbors, read straight off Word rows already in
        Postgres rather than a separate graph store."""

        neighbor_lemmas: set[str] = set()
        for word in known_words[:MAX_KNOWN_WORDS_FOR_GRAPH]:
            neighbor_lemmas.update(s.strip().lower() for s in word.synonyms if s.strip())
            neighbor_lemmas.update(s.strip().lower() for s in word.antonyms if s.strip())
            neighbor_lemmas.update(s.strip().lower() for s in word.collocations if s.strip())

        if not neighbor_lemmas:
            return []
        return await self._words.list_by_lemmas(neighbor_lemmas)

    async def _rank_candidates(
        self, user: User, known_words: list[Word], candidates: list[Word]
    ) -> list[Word]:
        known_sample = known_words[:MAX_KNOWN_WORDS_FOR_RANKING_PROMPT]
        try:
            ranked = await self._ai.rank_next_word_candidates(
                user_level=user.current_level,
                known_words_sample=[w.lemma for w in known_sample],
                candidate_lemmas=[w.lemma for w in candidates],
            )
        except AIGenerationError:
            logger.warning("next_word_ranking_failed", user_id=user.id)
            return candidates

        score_by_lemma = {r.lemma.strip().lower(): r.score for r in ranked}
        return sorted(
            candidates, key=lambda w: score_by_lemma.get(w.lemma.strip().lower(), 0.0), reverse=True
        )

    async def _recent_mistake_topics(self, user_id: int, limit: int = 10) -> list[str]:
        mistakes = await self._history.get_recent_mistakes(user_id, limit=limit)
        if not mistakes:
            return []
        word_ids = list({m.word_id for m in mistakes})
        words = await self._words.list_by_ids(word_ids)
        return sorted({w.topic for w in words if w.topic})
