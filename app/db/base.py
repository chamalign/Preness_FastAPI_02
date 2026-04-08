"""SQLAlchemy declarative base and engine."""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base

from app.core.config import get_settings

Base = declarative_base()
_settings = get_settings()
engine = create_engine(
    _settings.database_url,
    pool_pre_ping=True,
    echo=False,
)
