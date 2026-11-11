import re
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
    database_url: str = "sqlite:///./ledgerforge.db"
    data_dir: str = "data"
    secret_key: str = "dev-only-change-me"
    jwt_issuer: str = "ledgerforge-identity"
    jwt_audience: str = "ledgerforge-api"
    company_legal_name: str | None = None
    company_address: str | None = None
    company_contact_email: str | None = None
    company_contact_phone: str | None = None

    @field_validator("company_legal_name", "company_address", "company_contact_email", "company_contact_phone", mode="before")
    @classmethod
    def clean_company_details(cls, value):
        if value is None:
            return None
        cleaned = str(value).strip()
        if not cleaned:
            return None
        if any(marker in cleaned.casefold() for marker in ("replace_with", "placeholder", "your_company", "your_address")):
            raise ValueError("Replace example company details with verified values or leave them unset")
        return cleaned

    @field_validator("company_contact_email")
    @classmethod
    def validate_company_email(cls, value):
        if value is not None and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
            raise ValueError("company_contact_email must be a valid email address")
        return value

    @property
    def payslip_company_details_configured(self) -> bool:
        return bool(self.company_legal_name and self.company_address and
                    (self.company_contact_email or self.company_contact_phone))
    # Ignore unrelated entries in a shared local .env file. Only settings
    # declared above are used by this application.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
settings = Settings()
