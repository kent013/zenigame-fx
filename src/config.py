from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    oanda_env: str = "practice"
    oanda_account_id: str = ""
    oanda_api_token: str = ""
    oanda_base_url_practice: str = "https://api-fxpractice.oanda.com"
    oanda_base_url_live: str = "https://api-fxtrade.oanda.com"
    fred_api_key: str = ""
    fred_base_url: str = "https://api.stlouisfed.org/fred"
    database_url: str = "postgresql+psycopg://zenigame_fx:zenigame_fx_dev@localhost:15433/zenigame_fx"
    diskcache_dir: str = ".cache/http"
    log_level: str = "INFO"
    log_format: str = "json"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def oanda_base_url(self) -> str:
        return self.oanda_base_url_practice if self.oanda_env == "practice" else self.oanda_base_url_live


settings = Settings()
