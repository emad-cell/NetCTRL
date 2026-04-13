from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    DATABASE_URL: str
    ENCRYPTION_KEY: str | None = None

    class Config:
        env_file = ".env"

# Single instance imported everywhere
settings = Settings()
