from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "HRMS Backend API"
    API_V1_STR: str = "/api/v1"
    
    # Database
    # POSTGRES_SERVER: str = "localhost"
    # POSTGRES_USER: str = "postgres"
    # POSTGRES_PASSWORD: str = "password"
    # POSTGRES_DB: str = "hrms_db"
    # POSTGRES_PORT: str = "5432"
    MYSQL_SERVER: str = "127.0.0.1"
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = "root"
    MYSQL_DB: str = "hrm"
    MYSQL_PORT: str = "8889"
    
    # Email
    SMTP_TLS: bool = True
    SMTP_PORT: Optional[int] = 587
    SMTP_HOST: Optional[str] = "smtpout.secureserver.net"
    SMTP_USER: Optional[str] = "support@softpital.in"
    SMTP_PASSWORD: Optional[str] = "Kau2402@Mad.me8301u"
    EMAILS_FROM_EMAIL: Optional[str] = "support@softpital.in"
    EMAILS_FROM_NAME: Optional[str] = "Softpital Support Team"
    
    # Security
    SECRET_KEY: str = "2f06655b82a81f4e515dad4b45d3d2e78dac15f9f74cb25ff5fdc2795c63d99b"
    ALGORITHM: str = "HS256"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8 # 8 days
    
    # Storage
    STORAGE_TYPE: str = "local" # local or firebase
    UPLOAD_DIR: str = "uploads"
    SERVER_HOST: str = "http://127.0.0.1:8000"
    
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        return f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}@{self.MYSQL_SERVER}:{self.MYSQL_PORT}/{self.MYSQL_DB}"

    class Config:
        case_sensitive = True
        env_file = ".env"

settings = Settings()
# python3 -c "import secrets; print(secrets.token_hex(32))"