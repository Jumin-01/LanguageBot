"""Pure rule for whether a candidate word's CEFR level is acceptable for a
user of a given level -- enforced in code so the AI's own level tagging is
never blindly trusted (spec: "an A1 user shouldn't get C1/C2 words without
good reason")."""

from bot.database.models.enums import CEFR_ORDER, CEFRLevel

DEFAULT_MAX_STEPS_ABOVE = 1


def is_within_level_band(
    candidate: CEFRLevel, user_level: CEFRLevel, max_steps_above: int = DEFAULT_MAX_STEPS_ABOVE
) -> bool:
    """True if `candidate` is no more than `max_steps_above` CEFR steps above
    `user_level`. Anything at or below the user's level is always allowed
    (reinforcing easier, related vocabulary is fine)."""

    candidate_index = CEFR_ORDER.index(candidate)
    user_index = CEFR_ORDER.index(user_level)
    return candidate_index <= user_index + max_steps_above
