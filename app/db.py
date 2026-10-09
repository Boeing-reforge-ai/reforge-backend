from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings


def _normalize_url(url: str) -> str:
    # Railway는 postgresql:// 로 주므로 psycopg 드라이버 지정
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


engine = create_engine(
    _normalize_url(settings.database_url),
    pool_pre_ping=True,  # 끊긴 연결 자동 감지
)


def init_db() -> None:
    from app import models  # noqa: F401  테이블 등록용
    from app.seed import seed_materials

    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        seed_materials(session)


def get_session():
    with Session(engine) as session:
        yield session