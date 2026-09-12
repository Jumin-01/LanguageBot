"""Chooses which quiz question type to ask for a given word, based on how far
along the user is with it -- simpler recognition questions for new words,
harder production/translation questions as the correct-answer streak grows,
per the product spec. Pure function, no randomness leaks outside this module's
seam so it stays deterministically testable via an injected RNG.
"""

import random

from bot.database.models.enums import QuestionType
from bot.learning.models import WordProgress

_TIER_2_TYPES = (QuestionType.FILL_BLANK, QuestionType.CHOOSE_WORD_FOR_SENTENCE)
_TIER_3_TYPES = (QuestionType.TRANSLATE_SENTENCE, QuestionType.CHOOSE_CORRECT_EXAMPLE)
_ALL_TYPES = tuple(QuestionType)


def choose_question_type(progress: WordProgress, rng: random.Random | None = None) -> QuestionType:
    rng = rng or random.Random()

    # A miss temporarily downgrades to the easiest recognition question,
    # regardless of how many repetitions the word had accumulated before.
    if progress.consecutive_correct == 0 and progress.wrong_answers > 0:
        return QuestionType.EN_TO_UA_CHOICE

    tier = min(progress.repetitions, 4)
    if tier == 0:
        return QuestionType.EN_TO_UA_CHOICE
    if tier == 1:
        return QuestionType.UA_TO_EN_CHOICE
    if tier == 2:
        return rng.choice(_TIER_2_TYPES)
    if tier == 3:
        return rng.choice(_TIER_3_TYPES)
    return rng.choice(_ALL_TYPES)
