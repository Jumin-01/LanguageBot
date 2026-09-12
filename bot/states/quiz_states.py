from aiogram.fsm.state import State, StatesGroup


class QuizFlow(StatesGroup):
    awaiting_translation = State()
