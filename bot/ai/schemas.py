"""Pydantic models used as Gemini structured-output (response_schema) targets.

Using our own CEFRLevel/PartOfSpeech StrEnums directly as field types means
Gemini's generated JSON schema constrains the model to exactly our valid
enum values -- the AI physically cannot return a level or part-of-speech
outside what the rest of the system understands.
"""

from pydantic import BaseModel, Field

from bot.database.models.enums import CEFRLevel, PartOfSpeech


class GeneratedWord(BaseModel):
    lemma: str
    translation: str
    example_en: str
    example_uk: str
    level: CEFRLevel
    part_of_speech: PartOfSpeech
    topic: str | None = None
    # British/American IPA pronunciation, e.g. "/əˈfɔːdəbl/" -- distinct from
    # the Ukrainian-language "_uk" fields elsewhere (translation, example_uk).
    transcription_uk: str | None = None
    transcription_us: str | None = None
    synonyms: list[str] = Field(default_factory=list)
    antonyms: list[str] = Field(default_factory=list)
    collocations: list[str] = Field(default_factory=list)


class GeneratedQuizSentence(BaseModel):
    sentence_en: str
    sentence_uk: str


class TranslationEvaluation(BaseModel):
    is_correct: bool
    feedback: str | None = None


class TranscriptionPair(BaseModel):
    transcription_uk: str | None = None
    transcription_us: str | None = None


class RankedWordCandidate(BaseModel):
    """One scored entry in the AI's ranking of pre-filtered next-word
    candidates (see bot/services/vocabulary_generation_service.py). The AI
    only ever reorders a candidate set business logic already vetted for
    dedup/level -- it cannot introduce new words through this call."""

    lemma: str
    score: float = Field(ge=0.0, le=1.0)
    reason: str
