"""AI task taxonomy: every distinct reason the app calls Gemini for, and
which model tier handles it. This is the single place that decision lives --
GeminiAIProvider asks bot.ai.router.AIRouter before every call instead of
hardcoding a model per method.
"""

import enum


class AITaskType(enum.StrEnum):
    TRANSLATE_WORD = "translate_word"
    GENERATE_WORD_CARD = "generate_word_card"
    GENERATE_EXAMPLE = "generate_example"
    GENERATE_QUESTION = "generate_question"
    CHECK_ANSWER = "check_answer"
    GENERATE_IPA = "generate_ipa"
    FIND_RELATED_WORDS = "find_related_words"
    GENERATE_COLLOCATIONS = "generate_collocations"
    GENERATE_PHRASE = "generate_phrase"
    ANALYZE_KNOWLEDGE_GRAPH = "analyze_knowledge_graph"
    SELECT_NEXT_WORD = "select_next_word"
    ANALYZE_PROGRESS = "analyze_progress"
    GENERATE_EXPLANATION = "generate_explanation"


# Tasks that need real reasoning over a user's knowledge graph/history rather
# than short, well-scoped generation -- routed to the advanced model tier.
ADVANCED_TASKS: frozenset[AITaskType] = frozenset(
    {
        AITaskType.ANALYZE_KNOWLEDGE_GRAPH,
        AITaskType.SELECT_NEXT_WORD,
        AITaskType.ANALYZE_PROGRESS,
        AITaskType.GENERATE_EXPLANATION,
    }
)


def is_advanced_task(task: AITaskType) -> bool:
    return task in ADVANCED_TASKS
