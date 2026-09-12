from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.repositories.ai_request_repository import AIRequestRepository


async def test_create_and_usage_since(db_session: AsyncSession) -> None:
    repo = AIRequestRepository(db_session)
    now = datetime.now(UTC)

    await repo.create(
        task_type="generate_word_card",
        model="default-model",
        latency_ms=120,
        status="success",
        input_tokens=50,
        output_tokens=80,
        total_tokens=130,
    )
    await repo.create(
        task_type="select_next_word",
        model="advanced-model",
        latency_ms=300,
        status="success",
        total_tokens=200,
    )
    await repo.create(
        task_type="generate_word_card",
        model="default-model",
        latency_ms=50,
        status="error",
        error_code="429",
    )

    since = now - timedelta(minutes=1)
    requests = await repo.usage_since(since)
    assert len(requests) == 3

    summary = await repo.summary_by_model_since(since)
    by_model = {model: (count, tokens) for model, count, tokens in summary}
    assert by_model["default-model"] == (2, 130)
    assert by_model["advanced-model"] == (1, 200)


async def test_usage_since_excludes_older_entries(db_session: AsyncSession) -> None:
    repo = AIRequestRepository(db_session)
    now = datetime.now(UTC)

    await repo.create(task_type="generate_word_card", model="m", latency_ms=10, status="success")

    future_cutoff = now + timedelta(minutes=1)
    assert await repo.usage_since(future_cutoff) == []
