# HRMS Backend API

This is a scalable, production-ready backend for the Human Resource Management System, built with Python and FastAPI.

## Project Structure

```
app/
├── api/            # API endpoints and routers
├── core/           # Global configuration and security settings
├── db/             # Database connection and session management
├── models/         # SQLAlchemy models
├── schemas/        # Pydantic schemas for request/response validation
├── tests/          # Test suite
└── main.py         # Application entry point
alembic/            # Database migrations
```

## Setup

1.  **Environment**: The project uses a virtual environment (already set up as `hrmenv` or create a new one).
    ```bash
    source hrmenv/bin/activate
    # or
    python3 -m venv venv
    source venv/bin/activate
    ```

2.  **Dependencies**: Install the required packages.
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configuration**:
    Copy `.env.example` to `.env` (if provided, else create one) and configure your database settings.
    ```bash
    # Example .env content
    # POSTGRES_SERVER=localhost
    # POSTGRES_USER=postgres
    # POSTGRES_PASSWORD=yourpassword
    # POSTGRES_DB=hrms_db
    ```
    Ensure you have a PostgreSQL database running and created (`createdb hrms_db`).

## Running the Application

Start the development server:
```bash
uvicorn app.main:app --reload
```
The API will be available at `http://localhost:8000`.
API Documentation (Swagger UI): `http://localhost:8000/docs`

## Database Migrations

This project uses Alembic for migrations.

1.  **Create a migration** (after changing models):
    ```bash
    alembic revision --autogenerate -m "Description of changes"
    ```

2.  **Apply migrations**:
    ```bash
    alembic upgrade head
    ```

## Testing

Run the test suite using pytest:
```bash
pytest
```
