"""Maps an AITaskType to the Gemini model that should handle it.

Two configured tiers (bot/config.py: GEMINI_DEFAULT_MODEL /
GEMINI_ADVANCED_MODEL) -- simple, well-scoped tasks use the cheap/
high-quota default model; tasks that need real reasoning over a user's
knowledge graph use the advanced tier. The advanced model also serves as
the one-shot fallback if the default model's calls keep failing (and vice
versa), so a temporary outage or exhausted quota on one tier doesn't take
the whole AI Engine down.
"""

from dataclasses import dataclass

from bot.ai.task_types import AITaskType, is_advanced_task


@dataclass(frozen=True)
class AIRouter:
    default_model: str
    advanced_model: str

    def model_for(self, task: AITaskType) -> str:
        return self.advanced_model if is_advanced_task(task) else self.default_model

    def fallback_model_for(self, task: AITaskType) -> str:
        primary = self.model_for(task)
        return self.default_model if primary == self.advanced_model else self.advanced_model
