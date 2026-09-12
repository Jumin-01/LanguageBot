"""The interface the rest of the app depends on for AI-generated content.

Deliberately narrow and DB-free: an AIProvider only ever returns proposed
data (words, sentences, a correctness judgement). It never touches
user_words, never sees a DB session, and has no say over the 20-word pool
cap, dedup, or level filtering -- those business rules are enforced by
VocabularyGenerationService and QuizService, in code, regardless of what an
implementation of this Protocol returns.
"""

from dataclasses import dataclass, field
from typing import Protocol

from bot.ai.schemas import GeneratedWord, RankedWordCandidate
from bot.database.models.enums import CEFRLevel, PartOfSpeech


@dataclass(frozen=True)
class GenerateWordsRequest:
    level: CEFRLevel
    count: int
    known_words: list[str] = field(default_factory=list)
    exclude_lemmas: set[str] = field(default_factory=set)
    topics_hint: list[str] = field(default_factory=list)
    mistake_topics: list[str] = field(default_factory=list)


class AIProvider(Protocol):
    async def generate_words(self, request: GenerateWordsRequest) -> list[GeneratedWord]: ...

    async def generate_quiz_sentence(
        self, lemma: str, translation: str, level: CEFRLevel, known_words: list[str]
    ) -> tuple[str, str]:
        """Returns (sentence_en, sentence_uk) -- a fresh example sentence for
        the word, distinct from its stored dictionary example, for use in a
        TRANSLATE_SENTENCE quiz question."""
        ...

    async def evaluate_translation(
        self, sentence_en: str, reference_uk: str, user_answer_uk: str
    ) -> bool:
        """Loosely judges whether a user's free-text translation is an
        acceptable translation of sentence_en, using reference_uk as a guide
        rather than requiring an exact match."""
        ...

    async def generate_transcription(
        self, lemma: str, part_of_speech: PartOfSpeech
    ) -> tuple[str | None, str | None]:
        """Returns (transcription_uk, transcription_us) IPA pronunciations for
        a word that doesn't have one yet (e.g. backfilling older rows)."""
        ...

    async def rank_next_word_candidates(
        self,
        user_level: CEFRLevel,
        known_words_sample: list[str],
        candidate_lemmas: list[str],
    ) -> list[RankedWordCandidate]:
        """Scores a pre-filtered set of candidate words (business logic has
        already vetted them for dedup/level -- this call never introduces or
        drops a candidate, only ranks the given set) by how well each one
        extends the user's current knowledge. VocabularyGenerationService
        picks the final selection from this ranking; the AI's role stops at
        proposing an order."""
        ...
