import json
from functools import lru_cache
from typing import List, Optional, Tuple, Union

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = ""
    redis_url: str = ""
    opensky_base_url: str = "https://opensky-network.org/api"
    opensky_username: str = ""
    opensky_password: str = ""
    opensky_client_id: str = ""
    opensky_client_secret: str = ""
    cors_origins: Union[List[str], str] = ["http://localhost:3000"]
    log_level: str = "INFO"
    app_env: str = "development"

    # Ingestion settings
    ingestion_interval_seconds: int = 10  # OpenSky anonymous limit: 10s; authenticated: 5s
    ingestion_bounds: str = ""  # Optional "lamin,lomin,lamax,lomax" e.g. "45.0,5.0,48.0,10.0"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origins_list(self) -> List[str]:
        if isinstance(self.cors_origins, str):
            try:
                return json.loads(self.cors_origins)
            except json.JSONDecodeError:
                return [x.strip() for x in self.cors_origins.split(",") if x.strip()]
        return self.cors_origins

    @property
    def parsed_ingestion_bounds(self) -> Optional[Tuple[float, float, float, float]]:
        """Parse ``ingestion_bounds`` into (lamin, lomin, lamax, lomax) or None."""
        if not self.ingestion_bounds:
            return None
        parts = [float(p.strip()) for p in self.ingestion_bounds.split(",")]
        if len(parts) != 4:
            return None
        return (parts[0], parts[1], parts[2], parts[3])


@lru_cache
def get_settings() -> Settings:
    return Settings()
