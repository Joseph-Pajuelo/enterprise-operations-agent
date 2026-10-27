"""
MÓDULO DE CONEXIÓN Y SESIONES DE BASE DE DATOS
==============================================
Gestiona la conexión dual:
- Por defecto usa SQLite local (`enterprise_ops.db`) para ejecución inmediata sin instalar servidores.
- Si se define `DATABASE_URL` con PostgreSQL en el archivo `.env`, se conecta a PostgreSQL automáticamente.
"""

import os
from contextlib import contextmanager
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from src.database.models import Base

# Carga las variables de entorno definidas en el archivo .env
load_dotenv()

# Define la ruta del archivo SQLite local en la raíz del proyecto
DEFAULT_SQLITE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "enterprise_ops.db",
)
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_SQLITE_PATH}")
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

# En SQLite se desactiva check_same_thread para permitir peticiones concurrentes desde FastAPI y Streamlit
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

# Creación del motor de base de datos y fábrica de sesiones transaccionales
engine = create_engine(DATABASE_URL, connect_args=connect_args, future=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)


def init_db() -> None:
    """
    Inicializa el esquema de base de datos:
    1. Crea todas las tablas si aún no existen.
    2. Inserta los datos iniciales de demostración (clientes, pedidos, stock y telemetría).
    """
    Base.metadata.create_all(bind=engine)
    from src.database.seed import seed_initial_data

    with get_db_context() as db:
        seed_initial_data(db)


@contextmanager
def get_db_context():
    """
    Administrador de contexto transaccional para las herramientas del agente.
    Garantiza que si ocurre un error se haga `rollback` (deshacer cambios a medias)
    y que siempre se cierre la conexión al terminar.
    """
    db: Session = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db():
    """Generador de sesión inyectable para los endpoints de FastAPI."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
