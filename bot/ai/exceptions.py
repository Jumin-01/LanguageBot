class AIError(Exception):
    """Base class for all AI-layer failures."""


class AIGenerationError(AIError):
    """The AI call failed or returned no usable structured output."""


class AIValidationError(AIError):
    """The AI returned structured output that failed our own validation."""


class AITimeoutError(AIError):
    """The AI call did not complete within the configured timeout."""
