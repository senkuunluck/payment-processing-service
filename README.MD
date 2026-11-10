
# Payment Processing Service

Asynchronous payment processing microservice built with FastAPI,
PostgreSQL, RabbitMQ and FastStream.

## Tech Stack

- Python 3.12
- FastAPI
- Pydantic v2
- SQLAlchemy 2.0
- PostgreSQL
- RabbitMQ
- FastStream
- Alembic
- Docker Compose
- Pytest

## Project Status

The project is under active development.

## Local Development

### 1. Clone the repository

```bash
git clone https://github.com/senkuunluck/payment-processing-service.git
cd payment-processing-service
```

### 2. Create virtual environment

```bash
python -m venv .venv
```

### 3. Activate virtual environment

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

### 4. Install dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

### 5. Configure environment variables

Copy `.env.example` to `.env` and configure the values.

### 6. Run application

```bash
python -m uvicorn app.main:app --reload
```

## API Documentation

After starting the application:

- Swagger UI: http://127.0.0.1:8000/docs
- Health check: http://127.0.0.1:8000/health

## License

MIT
