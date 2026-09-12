from bot.ai.router import AIRouter
from bot.ai.task_types import AITaskType

_ROUTER = AIRouter(default_model="default-model", advanced_model="advanced-model")


def test_simple_task_routes_to_default_model() -> None:
    assert _ROUTER.model_for(AITaskType.GENERATE_WORD_CARD) == "default-model"
    assert _ROUTER.model_for(AITaskType.GENERATE_IPA) == "default-model"
    assert _ROUTER.model_for(AITaskType.CHECK_ANSWER) == "default-model"


def test_complex_task_routes_to_advanced_model() -> None:
    assert _ROUTER.model_for(AITaskType.SELECT_NEXT_WORD) == "advanced-model"
    assert _ROUTER.model_for(AITaskType.ANALYZE_KNOWLEDGE_GRAPH) == "advanced-model"
    assert _ROUTER.model_for(AITaskType.ANALYZE_PROGRESS) == "advanced-model"


def test_fallback_for_default_task_is_the_advanced_model() -> None:
    assert _ROUTER.fallback_model_for(AITaskType.GENERATE_WORD_CARD) == "advanced-model"


def test_fallback_for_advanced_task_is_the_default_model() -> None:
    assert _ROUTER.fallback_model_for(AITaskType.SELECT_NEXT_WORD) == "default-model"


def test_every_task_type_has_a_model() -> None:
    for task in AITaskType:
        assert _ROUTER.model_for(task) in {"default-model", "advanced-model"}
