from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models.enums import CEFRLevel
from bot.database.repositories.user_repository import UserRepository
from bot.services.dto import UserDTO, UserSettingsDTO
from bot.services.mappers import user_settings_to_dto, user_to_dto


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)

    async def get_or_create_user(
        self, telegram_id: int, username: str | None, first_name: str | None
    ) -> UserDTO:
        user = await self._users.get_by_telegram_id(telegram_id)
        if user is None:
            user = await self._users.create(telegram_id, username, first_name)
            await self._users.create_default_settings(user.id)
        return user_to_dto(user)

    async def set_level(self, user_id: int, level: CEFRLevel) -> None:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise ValueError(f"user {user_id} not found")
        await self._users.set_level(user, level)

    async def complete_onboarding(self, user_id: int) -> None:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise ValueError(f"user {user_id} not found")
        await self._users.complete_onboarding(user)

    async def get_settings(self, user_id: int) -> UserSettingsDTO:
        settings = await self._users.get_settings(user_id)
        if settings is None:
            settings = await self._users.create_default_settings(user_id)
        return user_settings_to_dto(settings)

    async def update_settings(self, user_id: int, **fields: Any) -> UserSettingsDTO:
        settings = await self._users.get_settings(user_id)
        if settings is None:
            settings = await self._users.create_default_settings(user_id)

        allowed = {
            "utc_offset_minutes",
            "daily_new_words_goal",
            "sessions_per_day",
            "quiet_hours_start",
            "quiet_hours_end",
        }
        for key, value in fields.items():
            if key not in allowed:
                raise ValueError(f"unknown setting: {key}")
            setattr(settings, key, value)

        await self._session.flush()
        return user_settings_to_dto(settings)
