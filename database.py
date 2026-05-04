import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import declarative_base
from motor.motor_asyncio import AsyncIOMotorClient

from dotenv import load_dotenv

load_dotenv()

# ──────────────────────────────────────────────
# Configuración de bases de datos (asíncrona)
# ──────────────────────────────────────────────

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:password@localhost/db")
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")

# Motor asíncrono de SQLAlchemy + asyncpg
engine = create_async_engine(DATABASE_URL, echo=False)

# Fábrica de sesiones asíncronas
AsyncSessionLocal = sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

Base = declarative_base()


async def get_db():
    """Generador de sesión asíncrona de base de datos.

    Crea una sesión, la entrega al endpoint y al finalizar
    hace commit o rollback según corresponda.
    """
    async with AsyncSessionLocal() as db:
        try:
            yield db
            await db.commit()
        except Exception:
            await db.rollback()
            raise


# Cliente asíncrono de MongoDB usando Motor
mongo_client = AsyncIOMotorClient(MONGO_URL)
db = mongo_client["audit_db"]
audit_collection = db["update_logs"]