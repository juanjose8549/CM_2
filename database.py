import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from pymongo import MongoClient
from sqlalchemy.ext.declarative import declarative_base

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:password@localhost/db")
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")


engine = create_engine(DATABASE_URL)
session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """Function to get a SQLAlchemy database session"""
    db = session()
    try:
        return db
    finally:
        db.close()

mongo_client = MongoClient(MONGO_URL)
db = mongo_client["audit_db"]
audit_collection = db["update_logs"]