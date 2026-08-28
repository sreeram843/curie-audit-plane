from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CAP_", env_file=".env", extra="ignore")

    data_dir: Path = Path("./data")
    signing_key_path: Path = Path("./data/keys/ed25519.pem")
    verifying_key_path: Path = Path("./data/keys/ed25519.pub")
    host: str = "127.0.0.1"
    port: int = 8080
    llm_provider: str = "stub"
    llm_base_url: str = "http://127.0.0.1:1234/v1"
    llm_model: str = "medgemma-4b-it-mlx"
    llm_api_key: str = ""
    llm_timeout_seconds: float = 120
    admin_token: str = ""
    reviewer_token: str = ""
    investigator_token: str = ""

    @property
    def audit_db_path(self) -> Path:
        return self.data_dir / "audit.sqlite"

    @property
    def protected_dir(self) -> Path:
        return self.data_dir / "protected"


settings = Settings()
