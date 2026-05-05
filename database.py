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
# Configurado con pool_size limitado y timeouts para Railway
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=5,                  # Max conexiones en el pool
    max_overflow=10,              # Max conexiones extras bajo demanda
    pool_timeout=30,              # Timeout esperando una conexion del pool (segundos)
    pool_recycle=1800,            # Reciclar conexiones cada 30 min (evita caidas)
    pool_pre_ping=True,           # Verificar conexion antes de usarla
)

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
# Configurado con pool limitado y timeouts para evitar fugas de conexiones
mongo_client = AsyncIOMotorClient(
    MONGO_URL,
    maxPoolSize=10,           # Max conexiones simultaneas
    minPoolSize=1,            # Mantener al menos 1 conexion activa
    maxIdleTimeMS=30000,      # Cerrar conexiones inactivas tras 30s
    connectTimeoutMS=5000,    # Timeout de conexion: 5 segundos
    serverSelectionTimeoutMS=5000,  # Timeout de seleccion de servidor: 5s
    socketTimeoutMS=30000,        # Timeout de operaciones: 30s
    waitQueueTimeoutMS=5000,      # Timeout esperando en cola: 5s
    retryWrites=True,             # Reintentar escrituras fallidas
)

db = mongo_client["audit_db"]
audit_collection = db["update_logs"]