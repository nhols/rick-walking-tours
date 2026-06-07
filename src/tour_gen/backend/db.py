import os
from collections.abc import Generator
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine


DEFAULT_SQLITE_PATH = Path("data/tour_gen.sqlite3")


def database_url() -> str:
    return os.getenv("TOUR_GEN_DATABASE_URL", f"sqlite:///{DEFAULT_SQLITE_PATH}")


def _ensure_sqlite_parent(url: str) -> None:
    if not url.startswith("sqlite:///"):
        return

    path = Path(url.removeprefix("sqlite:///"))
    if path == Path(":memory:"):
        return

    path.parent.mkdir(parents=True, exist_ok=True)


DATABASE_URL = database_url()
_ensure_sqlite_parent(DATABASE_URL)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session]:
    with Session(engine) as session:
        yield session

