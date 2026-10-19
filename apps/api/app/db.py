from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from .config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True, pool_size=10, max_overflow=20)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def set_rls_context(db: Session, lodge_id: str | None, is_super_admin: bool = False, user_id: str | None = None):
    db.execute(text("select set_config('app.current_lodge_id', :lodge_id, true)"), {"lodge_id": lodge_id or ""})
    db.execute(text("select set_config('app.is_super_admin', :flag, true)"), {"flag": "true" if is_super_admin else "false"})
    if user_id is not None:
        db.execute(text("select set_config('app.current_user_id', :user_id, true)"), {"user_id": user_id})
