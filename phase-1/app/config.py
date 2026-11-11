from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
    database_url: str = "sqlite:///./ledgerforge.db"
    data_dir: str = "data"
    secret_key: str = "dev-only-change-me"
    # Ignore unrelated entries in a shared local .env file. Only settings
    # declared above are used by this application.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
settings = Settings()
