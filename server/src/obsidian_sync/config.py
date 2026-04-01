from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Core
    app_name: str = "Obsidian Sync Server"
    debug: bool = False
    secret_key: str = "change-me-in-production"

    # Deployment mode
    deployment_mode: str = "self_hosted"  # "self_hosted" or "saas"

    # Database
    database_url: str = "sqlite+aiosqlite:///data/obsidian-sync.db"

    # Storage
    storage_backend: str = "local"  # "local" or "s3"
    storage_local_path: str = "data/vaults"
    s3_bucket: str = ""
    s3_region: str = ""

    # Auth
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    # OAuth
    google_client_id: str = ""
    google_client_secret: str = ""
    github_client_id: str = ""
    github_client_secret: str = ""

    # Stripe (SaaS mode)
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""

    # AWS
    aws_region: str = ""

    model_config = {"env_prefix": "OSS_", "env_file": ".env"}


settings = Settings()
