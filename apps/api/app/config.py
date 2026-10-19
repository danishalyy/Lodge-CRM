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
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_use_tls: bool = True
    mfa_encryption_key: str = ""
    password_reset_ttl_minutes: int = 30
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def origins(self):
        return [x.strip() for x in self.frontend_origins.split(",") if x.strip()]

settings = Settings()
