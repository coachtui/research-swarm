from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    model_config = ConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore"  # Ignore extra fields from .env
    )

    # API Keys
    anthropic_api_key: str = ""  # Set in .env for actual use
    fmp_api_key: str = ""  # Optional for Phase 1
    news_api_key: str = ""  # Optional for Phase 1

    # Paths
    cache_dir: Path = Path("./data/cache")
    state_dir: Path = Path("./data/state")
    reports_dir: Path = Path("./reports")

    # Logging
    log_level: str = "INFO"

    # LLM Settings
    default_model: str = "claude-3-5-haiku-20241022"  # Cheap for Phase 1
    max_tokens: int = 4000
    temperature: float = 0.1

    # Phase 9: Automation & Scheduling
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True

    sendgrid_api_key: str = ""

    notification_recipients: str = ""  # Comma-separated emails
    notification_from_email: str = "research-swarm@localhost"

    monthly_budget_usd: float = 200.0
    budget_alert_threshold_usd: float = 180.0

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Ensure directories exist
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

# Global settings instance
settings = Settings()
