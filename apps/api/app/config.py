from typing import Annotated
from pydantic import Field, TypeAdapter, ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://lodge:lodge_dev_password@postgres:5432/lodge_crm"
    redis_url: str = "redis://redis:6379/0"
    app_env: str = "production"
    frontend_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    cookie_secure: bool = False
    session_ttl_hours: int = 12
    login_rate_limit: int = 10
    login_rate_window_seconds: int = 900
    object_storage_endpoint: str = "http://minio:9000"
    object_storage_public_endpoint: str = "http://localhost:9000"
    object_storage_access_key: str = "lodgecrm"
    object_storage_secret_key: str = "change-this-object-storage-secret"
    object_storage_bucket: str = "lodge-crm-media"
    object_storage_region: str = "us-east-1"
    public_web_url: str = "http://localhost:3000"
    smtp_host: str = ""
    smtp_port: int = Field(587, ge=1, le=65535)
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False
    email_encryption_key: str = ""
    notification_escalation_minutes: int = Field(60, ge=1, le=10080)
    invitation_ttl_hours: int = Field(72, ge=1, le=168)
    invitation_resend_cooldown_seconds: int = Field(60, ge=1, le=86400)
    mfa_encryption_key: str = ""
    password_reset_ttl_minutes: int = 30
    ai_configuration_invalid: bool = False
    ai_enabled: bool = False
    ai_provider: str = "vllm"
    vllm_base_url: str = ""
    vllm_api_key: str = ""
    vllm_model: str = ""
    ai_request_timeout: float = Field(30, ge=1, le=120)
    ai_max_context: int = Field(16384, ge=2048, le=131072)
    ai_max_output_tokens: int = Field(1024, ge=64, le=4096)
    ai_max_rounds: int = Field(4, ge=1, le=6)
    ai_user_requests_per_minute: int = Field(6, ge=1, le=60)
    ai_lodge_requests_per_minute: int = Field(30, ge=1, le=300)
    ai_lodge_concurrency: int = Field(2, ge=1, le=8)
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="before")
    @classmethod
    def isolate_invalid_ai_configuration(cls, data):
        # Optional inference configuration must not prevent core CRM startup.
        if not isinstance(data, dict):
            return data
        result = dict(data)
        invalid = False
        for name, field in cls.model_fields.items():
            if not name.startswith(("ai_", "vllm_")) or name not in result:
                continue
            try:
                annotation = Annotated[field.annotation, *field.metadata] if field.metadata else field.annotation
                result[name] = TypeAdapter(annotation).validate_python(result[name])
            except (ValidationError, TypeError, ValueError):
                result[name] = field.default
                invalid = True
        if invalid:
            result["ai_enabled"] = False
            result["ai_configuration_invalid"] = True
        return result

    @property
    def origins(self):
        return [x.strip() for x in self.frontend_origins.split(",") if x.strip()]

settings = Settings()
