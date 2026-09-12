"""Prompt builders, one module per task family, kept out of the provider
code itself so prompts can be read/tested/tweaked independently of the
Gemini client plumbing.
"""

from bot.ai.prompts.next_word import build_rank_next_word_prompt
from bot.ai.prompts.quiz import (
    build_evaluate_translation_prompt,
    build_generate_quiz_sentence_prompt,
)
from bot.ai.prompts.word_generation import build_generate_words_prompt, build_transcription_prompt

__all__ = [
    "build_evaluate_translation_prompt",
    "build_generate_quiz_sentence_prompt",
    "build_generate_words_prompt",
    "build_rank_next_word_prompt",
    "build_transcription_prompt",
]
