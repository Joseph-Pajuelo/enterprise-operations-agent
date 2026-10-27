# =====================================================================
# DOCKERFILE - PROYECTO 1: ENTERPRISE OPERATIONS AI AGENT
# =====================================================================
# Empaqueta el entorno de Python, las dependencias (LangGraph, FastAPI,
# Streamlit, SQLAlchemy, Gemini SDK) y el código fuente en un contenedor ligero.

FROM python:3.11-slim

# Evita que Python escriba archivos .pyc en disco y fuerza logs en tiempo real
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Directorio de trabajo dentro del contenedor
WORKDIR /app

# Instala dependencias del sistema necesarias para compilar conectores PostgreSQL (psycopg2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copia e instala primero las librerías de Python para aprovechar la caché de capas de Docker
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt psycopg2-binary

# Copia todo el código fuente del proyecto dentro del contenedor
COPY . .

# Expone el puerto 8000 (FastAPI REST) y el puerto 8501 (Dashboard Streamlit)
EXPOSE 8000 8501

# Comando por defecto: levanta el Dashboard interactivo de Streamlit
CMD ["streamlit", "run", "src/monitoring/dashboard.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
