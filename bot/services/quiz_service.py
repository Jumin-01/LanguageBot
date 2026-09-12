"""Builds and grades quiz questions.

Choice-type questions (EN->UA, UA->EN, fill-blank, choose-word-for-sentence,
choose-correct-example) are built entirely from the local `words` catalog --
no AI call needed, keeping quizzes fast and free to run. TRANSLATE_SENTENCE is
the one type that benefits from an LLM-generated sentence (and LLM-graded
free-text answer); when no AI provider is configured or a live call fails,
it falls back to CHOOSE_CORRECT_EXAMPLE, its difficulty-tier sibling, so quiz
generation always succeeds without the AI in the loop.
"""

import random
import re
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models.enums import CEFRLevel, QuestionType
from bot.database.repositories.user_word_repository import UserWordRepository
from bot.database.repositories.word_repository import WordRepository
from bot.learning.models import AnswerOutcome, QuizQuestion, WordProgress
from bot.learning.question_selector import choose_question_type
from bot.services.answer_history_service import AnswerHistoryService
from bot.services.dto import UserWordDTO, WordDTO
from bot.services.mappers import word_to_dto
from bot.services.spaced_repetition_service import SpacedRepetitionService


class QuizAIProvider(Protocol):
    """Structural slice of the full AIProvider (bot/ai/provider.py) that
    QuizService needs. Defined here too so this module has no import-time
    dependency on bot.ai -- any object with these two methods (in
    particular, a GeminiAIProvider) satisfies this Protocol automatically."""

    async def generate_quiz_sentence(
        self, lemma: str, translation: str, level: CEFRLevel, known_words: list[str]
    ) -> tuple[str, str]: ...

    async def evaluate_translation(
        self, sentence_en: str, reference_uk: str, user_answer_uk: str
    ) -> bool: ...


def _progress_from_user_word(user_word: UserWordDTO) -> WordProgress:
    return WordProgress(
        user_word_id=user_word.id,
        status=user_word.status,
        correct_answers=user_word.correct_answers,
        wrong_answers=user_word.wrong_answers,
        repetitions=user_word.repetitions,
        consecutive_correct=user_word.consecutive_correct,
        ease_factor=user_word.ease_factor,
        current_interval_days=user_word.current_interval_days,
        last_review_at=user_word.last_review_at,
        next_review_at=user_word.next_review_at,
    )


class QuizService:
    def __init__(
        self,
        session: AsyncSession,
        spaced_repetition_service: SpacedRepetitionService,
        answer_history_service: AnswerHistoryService,
        ai_provider: QuizAIProvider | None = None,
    ) -> None:
        self._words = WordRepository(session)
        self._user_words = UserWordRepository(session)
        self._srs = spaced_repetition_service
        self._history = answer_history_service
        self._ai_provider = ai_provider

    async def build_distractors(
        self, word: WordDTO, count: int = 3, by: str = "translation"
    ) -> list[str]:
        candidates = await self._words.get_distractor_candidates(
            exclude_word_id=word.id,
            part_of_speech=word.part_of_speech,
            level=word.level,
            limit=count * 4,
        )
        if len(candidates) < count:
            candidates = await self._words.get_distractor_candidates(
                exclude_word_id=word.id, level=word.level, limit=count * 4
            )
        if len(candidates) < count:
            candidates = await self._words.get_distractor_candidates(
                exclude_word_id=word.id, limit=count * 4
            )

        pool = [word_to_dto(w) for w in candidates]
        random.shuffle(pool)

        target = word.translation if by == "translation" else word.lemma
        seen = {target.strip().lower()}
        chosen: list[str] = []
        for candidate in pool:
            value = candidate.translation if by == "translation" else candidate.lemma
            if value.strip().lower() in seen:
                continue
            seen.add(value.strip().lower())
            chosen.append(value)
            if len(chosen) >= count:
                break
        return chosen

    async def _build_choice_question(
        self,
        user_word: UserWordDTO,
        question_type: QuestionType,
        rng: random.Random,
    ) -> QuizQuestion:
        word = user_word.word

        if question_type == QuestionType.EN_TO_UA_CHOICE:
            distractors = await self.build_distractors(word, count=3, by="translation")
            options = [*distractors, word.translation]
            rng.shuffle(options)
            return QuizQuestion(
                user_word_id=user_word.id,
                word_id=word.id,
                question_type=question_type,
                prompt=f'What does "{word.lemma}" mean?',
                options=options,
                correct_option_index=options.index(word.translation),
                correct_answer_text=word.translation,
            )

        if question_type == QuestionType.UA_TO_EN_CHOICE:
            distractors = await self.build_distractors(word, count=3, by="lemma")
            options = [*distractors, word.lemma]
            rng.shuffle(options)
            return QuizQuestion(
                user_word_id=user_word.id,
                word_id=word.id,
                question_type=question_type,
                prompt=f'Choose the English word for: "{word.translation}"',
                options=options,
                correct_option_index=options.index(word.lemma),
                correct_answer_text=word.lemma,
            )

        if question_type == QuestionType.FILL_BLANK:
            blanked = _blank_out(word.example_en, word.lemma)
            distractors = await self.build_distractors(word, count=3, by="lemma")
            options = [*distractors, word.lemma]
            rng.shuffle(options)
            return QuizQuestion(
                user_word_id=user_word.id,
                word_id=word.id,
                question_type=question_type,
                prompt=f"Fill in the blank: {blanked}",
                options=options,
                correct_option_index=options.index(word.lemma),
                correct_answer_text=word.lemma,
                metadata={"example_en": word.example_en},
            )

        if question_type == QuestionType.CHOOSE_WORD_FOR_SENTENCE:
            blanked = _blank_out(word.example_en, word.lemma)
            distractors = await self.build_distractors(word, count=3, by="lemma")
            options = [*distractors, word.lemma]
            rng.shuffle(options)
            return QuizQuestion(
                user_word_id=user_word.id,
                word_id=word.id,
                question_type=question_type,
                prompt=f"Which word fits this sentence?\n{blanked}",
                options=options,
                correct_option_index=options.index(word.lemma),
                correct_answer_text=word.lemma,
                metadata={"example_en": word.example_en},
            )

        if question_type == QuestionType.CHOOSE_CORRECT_EXAMPLE:
            candidates = await self._words.get_distractor_candidates(
                exclude_word_id=word.id, level=word.level, limit=9
            )
            distractor_examples = [word_to_dto(w).example_en for w in candidates][:3]
            options = [*distractor_examples, word.example_en]
            rng.shuffle(options)
            return QuizQuestion(
                user_word_id=user_word.id,
                word_id=word.id,
                question_type=question_type,
                prompt=f'Which sentence correctly uses "{word.lemma}"?',
                options=options,
                correct_option_index=options.index(word.example_en),
                correct_answer_text=word.example_en,
            )

        raise ValueError(f"unsupported local question type: {question_type}")

    async def _build_translate_sentence_question(self, user_word: UserWordDTO) -> QuizQuestion:
        assert self._ai_provider is not None  # only called when configured
        word = user_word.word
        known_words = await self._known_words_sample(user_word.user_id, exclude_word_id=word.id)
        sentence_en, sentence_uk = await self._ai_provider.generate_quiz_sentence(
            word.lemma, word.translation, word.level, known_words=known_words
        )
        return QuizQuestion(
            user_word_id=user_word.id,
            word_id=word.id,
            question_type=QuestionType.TRANSLATE_SENTENCE,
            prompt=f'Translate this sentence into Ukrainian:\n"{sentence_en}"',
            options=None,
            correct_option_index=None,
            correct_answer_text=sentence_uk,
            metadata={"sentence_en": sentence_en},
        )

    async def _known_words_sample(
        self, user_id: int, exclude_word_id: int, limit: int = 15
    ) -> list[str]:
        """A small sample of words the user already knows, so the generated
        sentence can lean on familiar vocabulary instead of introducing a
        pile of unfamiliar words alongside the one being tested."""

        learned = await self._user_words.list_learned_words(user_id, limit=limit)
        return [w.lemma for w in learned if w.id != exclude_word_id]

    async def generate_question(
        self, user_word: UserWordDTO, rng: random.Random | None = None
    ) -> QuizQuestion:
        rng = rng or random.Random()
        progress = _progress_from_user_word(user_word)
        question_type = choose_question_type(progress, rng)

        if question_type == QuestionType.TRANSLATE_SENTENCE:
            if self._ai_provider is None:
                question_type = QuestionType.CHOOSE_CORRECT_EXAMPLE
            else:
                try:
                    return await self._build_translate_sentence_question(user_word)
                except Exception:
                    question_type = QuestionType.CHOOSE_CORRECT_EXAMPLE

        return await self._build_choice_question(user_word, question_type, rng)

    async def generate_fast_track_question(self, user_word: UserWordDTO) -> QuizQuestion:
        """The verification question for "I already know this word": always
        the hardest type available (TRANSLATE_SENTENCE, or its difficulty-tier
        sibling CHOOSE_CORRECT_EXAMPLE without AI), regardless of the word's
        current repetition tier -- a claim of prior knowledge earns the
        hardest check, not the tier-appropriate one."""

        if self._ai_provider is not None:
            try:
                return await self._build_translate_sentence_question(user_word)
            except Exception:
                pass
        return await self._build_choice_question(
            user_word, QuestionType.CHOOSE_CORRECT_EXAMPLE, random.Random()
        )

    async def validate_answer(self, question: QuizQuestion, user_answer: str) -> tuple[bool, str]:
        correct_text = question.correct_answer_text.strip().lower()

        if question.options is not None:
            try:
                index = int(user_answer)
                is_correct = index == question.correct_option_index
            except ValueError:
                is_correct = user_answer.strip().lower() == correct_text
            return is_correct, question.correct_answer_text

        is_translate_sentence = question.question_type == QuestionType.TRANSLATE_SENTENCE
        if is_translate_sentence and self._ai_provider is not None:
            sentence_en = question.metadata.get("sentence_en", "")
            try:
                is_correct = await self._ai_provider.evaluate_translation(
                    sentence_en, question.correct_answer_text, user_answer
                )
            except Exception:
                # AI grading unavailable -- fall back to a loose exact-ish match
                # rather than silently failing the user's answer.
                is_correct = user_answer.strip().lower() == correct_text
            return is_correct, question.correct_answer_text

        is_correct = user_answer.strip().lower() == correct_text
        return is_correct, question.correct_answer_text

    async def submit_answer(
        self,
        user_id: int,
        user_word_id: int,
        question: QuizQuestion,
        user_answer: str,
        response_time_ms: int | None = None,
        session_run_id: int | None = None,
        fast_track: bool = False,
    ) -> AnswerOutcome:
        is_correct, correct_answer_text = await self.validate_answer(question, user_answer)

        await self._history.record(
            user_id=user_id,
            word_id=question.word_id,
            user_word_id=user_word_id,
            question_type=question.question_type,
            question_payload={
                "prompt": question.prompt,
                "options": question.options,
                "correct_option_index": question.correct_option_index,
            },
            user_answer=user_answer,
            correct_answer=correct_answer_text,
            is_correct=is_correct,
            response_time_ms=response_time_ms,
            session_run_id=session_run_id,
        )

        srs_result = await self._srs.apply_answer(
            user_id, user_word_id, is_correct, fast_track=fast_track
        )

        return AnswerOutcome(
            is_correct=is_correct,
            correct_answer_text=correct_answer_text,
            srs_result=srs_result,
            became_learned=srs_result.became_learned,
        )


def _blank_out(sentence: str, lemma: str) -> str:
    pattern = re.compile(re.escape(lemma), re.IGNORECASE)
    blanked = pattern.sub("____", sentence, count=1)
    if blanked == sentence:
        # lemma didn't literally appear (e.g. multi-word phrase with inflection) --
        # fall back to appending a blank marker rather than a silent no-op question.
        blanked = f"{sentence} (____)"
    return blanked
