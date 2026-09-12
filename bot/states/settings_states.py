from aiogram.fsm.state import State, StatesGroup


class SettingsFlow(StatesGroup):
    awaiting_level = State()
    awaiting_daily_goal = State()
    awaiting_sessions = State()
    awaiting_quiet_hours = State()
    awaiting_local_time = State()
