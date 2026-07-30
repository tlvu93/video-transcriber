import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


os.environ.setdefault(
    "DATABASE_URL",
    "postgresql://videotranscriber:videotranscriber@localhost:5432/videotranscriber",
)

from backend.app.persistence.database import Base  # noqa: E402


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
