from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str
    gemini_api_key: str
    # Two-tier model strategy (see bot/ai/router.py): "default" handles the
    # bulk of small, well-scoped tasks (translation, IPA, examples, choice
    # questions) on the cheap/high-quota tier; "advanced" is reserved for
    # tasks that need real reasoning over the user's knowledge graph
    # (ranking next-word candidates, progress analysis). Both model names
    # are configurable, never hardcoded elsewhere, and use "-latest" aliases
    # so a model doesn't get deprecated out from under us (already happened
    # once with a pinned version -- see README's "Відомі обмеження"). The
    # advanced model also serves as the fallback if the default model's
    # calls keep failing.
    gemini_default_model: str = "gemini-flash-lite-latest"
    gemini_advanced_model: str = "gemini-flash-latest"
    database_url: str
    log_level: str = "INFO"
    environment: str = "development"
    # Root folder for the bot-managed Obsidian vault (see bot/obsidian/).
    # Point Obsidian's "Open folder as vault" at this path to browse it.
    obsidian_vault_path: str = "./obsidian-vault"


settings = Settings()  # type: ignore[call-arg]
