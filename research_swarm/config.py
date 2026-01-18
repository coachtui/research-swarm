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

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Ensure directories exist
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

# Global settings instance
settings = Settings()
