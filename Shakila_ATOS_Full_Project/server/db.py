from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from config import database_url

_url = database_url()
engine = create_engine(_url, connect_args={"check_same_thread": False} if _url.startswith("sqlite") else {}, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
Base = declarative_base()


def init_db():
    from server import models  # noqa: F401
    Base.metadata.create_all(engine)
