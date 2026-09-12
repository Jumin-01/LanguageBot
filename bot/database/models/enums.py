import enum


class CEFRLevel(enum.StrEnum):
    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"


CEFR_ORDER: list[CEFRLevel] = [
    CEFRLevel.A1,
    CEFRLevel.A2,
    CEFRLevel.B1,
    CEFRLevel.B2,
    CEFRLevel.C1,
    CEFRLevel.C2,
]


class PartOfSpeech(enum.StrEnum):
    NOUN = "noun"
    VERB = "verb"
    ADJECTIVE = "adjective"
    ADVERB = "adverb"
    PHRASE = "phrase"
    PHRASAL_VERB = "phrasal_verb"
    IDIOM = "idiom"
    PREPOSITION = "preposition"
    CONJUNCTION = "conjunction"
    OTHER = "other"


class WordStatus(enum.StrEnum):
    NEW = "new"
    LEARNING = "learning"
    REVIEW = "review"
    LEARNED = "learned"
    SUSPENDED = "suspended"


ACTIVE_POOL_STATUSES: tuple[WordStatus, ...] = (
    WordStatus.NEW,
    WordStatus.LEARNING,
    WordStatus.REVIEW,
)


class QuestionType(enum.StrEnum):
    EN_TO_UA_CHOICE = "en_to_ua_choice"
    UA_TO_EN_CHOICE = "ua_to_en_choice"
    FILL_BLANK = "fill_blank"
    CHOOSE_WORD_FOR_SENTENCE = "choose_word_for_sentence"
    TRANSLATE_SENTENCE = "translate_sentence"
    CHOOSE_CORRECT_EXAMPLE = "choose_correct_example"


class WordSource(enum.StrEnum):
    AI_GENERATED = "ai_generated"
    SEED = "seed"
    MANUAL = "manual"


class OnboardingStatus(enum.StrEnum):
    PENDING_LEVEL = "pending_level"
    ACTIVE = "active"


class SessionRunStatus(enum.StrEnum):
    PENDING = "pending"
    SENT = "sent"
    DEFERRED = "deferred"
    SKIPPED = "skipped"


class KnowledgeNodeType(enum.StrEnum):
    WORD = "word"
    PHRASE = "phrase"
    TOPIC = "topic"
    GRAMMAR = "grammar"
