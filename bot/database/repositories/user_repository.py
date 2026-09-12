from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models.enums import CEFRLevel, OnboardingStatus
from bot.database.models.user import User
from bot.database.models.user_settings import UserSettings


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        result = await self._session.execute(select(User).where(User.telegram_id == telegram_id))
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: int) -> User | None:
        return await self._session.get(User, user_id)

    async def list_active_users(self) -> list[User]:
        result = await self._session.execute(
            select(User).where(User.onboarding_status == OnboardingStatus.ACTIVE)
        )
        return list(result.scalars().all())

    async def create(self, telegram_id: int, username: str | None, first_name: str | None) -> User:
        user = User(telegram_id=telegram_id, username=username, first_name=first_name)
        self._session.add(user)
        await self._session.flush()
        return user

    async def set_level(self, user: User, level: CEFRLevel) -> None:
        user.current_level = level
        await self._session.flush()

    async def complete_onboarding(self, user: User) -> None:
        user.onboarding_status = OnboardingStatus.ACTIVE
        await self._session.flush()

    async def get_settings(self, user_id: int) -> UserSettings | None:
        result = await self._session.execute(
            select(UserSettings).where(UserSettings.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def create_default_settings(self, user_id: int) -> UserSettings:
        settings = UserSettings(user_id=user_id)
        self._session.add(settings)
        await self._session.flush()
        return settings
