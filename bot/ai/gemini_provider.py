"""AIProvider implementation backed by Google's Gemini API.

The single point of contact with Gemini for the whole app (bot/ai/router.py
picks the model per task; nothing outside this module ever calls the
Gemini client directly). Every call is:

1. Routed to a model tier (AIRouter) based on the AITaskType.
2. Rate-limited in-process (RateLimiter) to avoid bursting past the
   free-tier per-minute quota -- the exact failure mode hit during
   development.
3. Retried a couple of times with backoff, then tried once more on the
   *other* model tier before giving up (a temporary outage or exhausted
   quota on one tier doesn't take the AI Engine down).
4. Logged to `ai_requests` (latency, tokens, status) via its own short-lived
   DB session -- a narrow, deliberate exception to "bot/ai has no DB
   session": this is write-only telemetry, never a read a business
   decision depends on.

Structured JSON output (response_schema) is used throughout, so responses
are guaranteed to parse into our own pydantic models -- no free-form text
parsing.
"""

import asyncio
import time
from typing import Any

from google import genai
from google.genai import types

from bot.ai.exceptions import AIGenerationError, AITimeoutError
from bot.ai.prompts import (
    build_evaluate_translation_prompt,
    build_generate_quiz_sentence_prompt,
    build_generate_words_prompt,
    build_rank_next_word_prompt,
    build_transcription_prompt,
)
from bot.ai.provider import GenerateWordsRequest
from bot.ai.rate_limiter import RateLimiter
from bot.ai.router import AIRouter
from bot.ai.schemas import (
    GeneratedQuizSentence,
    GeneratedWord,
    RankedWordCandidate,
    TranscriptionPair,
    TranslationEvaluation,
)
from bot.ai.task_types import AITaskType
from bot.database.models.enums import CEFRLevel, PartOfSpeech
from bot.database.repositories.ai_request_repository import AIRequestRepository
from bot.database.session import get_session
from bot.utils.logging import get_logger

logger = get_logger(__name__)

_TIMEOUT_SECONDS = 30.0
_PRIMARY_ATTEMPTS = 2
_FALLBACK_ATTEMPTS = 1
_MAX_BACKOFF_SECONDS = 8.0

# Conservative default: free-tier per-minute limits observed during
# development ranged from ~5 to ~15 requests/minute depending on model.
_DEFAULT_RATE_LIMIT_CALLS = 8
_DEFAULT_RATE_LIMIT_PERIOD_SECONDS = 60.0


class GeminiAIProvider:
    def __init__(
        self,
        api_key: str,
        router: AIRouter,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        self._client = genai.Client(api_key=api_key)
        self._router = router
        self._rate_limiter = rate_limiter or RateLimiter(
            _DEFAULT_RATE_LIMIT_CALLS, _DEFAULT_RATE_LIMIT_PERIOD_SECONDS
        )

    async def _call_model_with_retry(
        self, model: str, prompt: str, response_schema: Any, max_attempts: int
    ) -> Any:
        last_exc: Exception | None = None
        for attempt in range(max_attempts):
            await self._rate_limiter.acquire()
            try:
                return await asyncio.wait_for(
                    self._client.aio.models.generate_content(
                        model=model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=response_schema,
                        ),
                    ),
                    timeout=_TIMEOUT_SECONDS,
                )
            except TimeoutError as exc:
                last_exc = AITimeoutError(f"Gemini call timed out after {_TIMEOUT_SECONDS}s")
                last_exc.__cause__ = exc
            except Exception as exc:  # noqa: BLE001 -- any failure triggers our own retry/fallback
                last_exc = exc

            if attempt < max_attempts - 1:
                await asyncio.sleep(min(2**attempt, _MAX_BACKOFF_SECONDS))

        raise AIGenerationError(f"Gemini call failed after {max_attempts} attempt(s): {last_exc}")

    async def _attempt(
        self, task: AITaskType, model: str, prompt: str, response_schema: Any, max_attempts: int
    ) -> Any:
        start = time.monotonic()
        try:
            response = await self._call_model_with_retry(
                model, prompt, response_schema, max_attempts
            )
        except AIGenerationError as exc:
            await self._log_usage(
                task, model, self._elapsed_ms(start), "error", error_code=str(exc)[:128]
            )
            raise

        latency_ms = self._elapsed_ms(start)
        usage = response.usage_metadata
        await self._log_usage(
            task,
            model,
            latency_ms,
            "success",
            input_tokens=getattr(usage, "prompt_token_count", None) if usage else None,
            output_tokens=getattr(usage, "candidates_token_count", None) if usage else None,
            total_tokens=getattr(usage, "total_token_count", None) if usage else None,
        )

        if response.parsed is None:
            await self._log_usage(task, model, latency_ms, "error", error_code="no_parsed_output")
            raise AIGenerationError("Gemini returned no parsable structured output")
        return response.parsed

    async def _generate(self, task: AITaskType, prompt: str, response_schema: Any) -> Any:
        primary_model = self._router.model_for(task)
        try:
            return await self._attempt(
                task, primary_model, prompt, response_schema, _PRIMARY_ATTEMPTS
            )
        except AIGenerationError:
            fallback_model = self._router.fallback_model_for(task)
            logger.warning(
                "ai_call_falling_back",
                task=task.value,
                primary_model=primary_model,
                fallback_model=fallback_model,
            )
            return await self._attempt(
                task, fallback_model, prompt, response_schema, _FALLBACK_ATTEMPTS
            )

    @staticmethod
    def _elapsed_ms(start: float) -> int:
        return int((time.monotonic() - start) * 1000)

    async def _log_usage(
        self,
        task: AITaskType,
        model: str,
        latency_ms: int,
        status: str,
        *,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        total_tokens: int | None = None,
        error_code: str | None = None,
    ) -> None:
        try:
            async with get_session() as session:
                await AIRequestRepository(session).create(
                    task_type=task.value,
                    model=model,
                    latency_ms=latency_ms,
                    status=status,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    error_code=error_code,
                )
        except Exception:  # noqa: BLE001 -- telemetry must never break the caller
            logger.warning("ai_usage_logging_failed", task=task.value, model=model)

    async def generate_words(self, request: GenerateWordsRequest) -> list[GeneratedWord]:
        prompt = build_generate_words_prompt(request)
        result = await self._generate(AITaskType.GENERATE_WORD_CARD, prompt, list[GeneratedWord])
        return list(result)

    async def generate_quiz_sentence(
        self, lemma: str, translation: str, level: CEFRLevel, known_words: list[str]
    ) -> tuple[str, str]:
        prompt = build_generate_quiz_sentence_prompt(lemma, translation, level, known_words)
        result: GeneratedQuizSentence = await self._generate(
            AITaskType.GENERATE_QUESTION, prompt, GeneratedQuizSentence
        )
        return result.sentence_en, result.sentence_uk

    async def evaluate_translation(
        self, sentence_en: str, reference_uk: str, user_answer_uk: str
    ) -> bool:
        prompt = build_evaluate_translation_prompt(sentence_en, reference_uk, user_answer_uk)
        result: TranslationEvaluation = await self._generate(
            AITaskType.CHECK_ANSWER, prompt, TranslationEvaluation
        )
        return result.is_correct

    async def generate_transcription(
        self, lemma: str, part_of_speech: PartOfSpeech
    ) -> tuple[str | None, str | None]:
        prompt = build_transcription_prompt(lemma, part_of_speech)
        result: TranscriptionPair = await self._generate(
            AITaskType.GENERATE_IPA, prompt, TranscriptionPair
        )
        return result.transcription_uk, result.transcription_us

    async def rank_next_word_candidates(
        self,
        user_level: CEFRLevel,
        known_words_sample: list[str],
        candidate_lemmas: list[str],
    ) -> list[RankedWordCandidate]:
        if not candidate_lemmas:
            return []
        prompt = build_rank_next_word_prompt(user_level, known_words_sample, candidate_lemmas)
        result = await self._generate(
            AITaskType.SELECT_NEXT_WORD, prompt, list[RankedWordCandidate]
        )
        return list(result)
