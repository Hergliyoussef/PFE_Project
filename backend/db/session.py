from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os

# On récupère l'URL depuis tes variables d'environnement
# Format : postgresql://user:password@localhost:5432/dbname
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:pfe_password_2026@localhost:5432/pm_chatbot")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Cette fonction sera utilisée par FastAPI (Depends)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
