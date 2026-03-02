from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Pfad zur Datenbank
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

# Engine & Session-Konfiguration
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Die Basisklasse für alle Models
Base = declarative_base()