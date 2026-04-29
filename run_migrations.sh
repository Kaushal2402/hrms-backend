#!/bin/bash
# Check if Postgres is running
if ! nc -z localhost 5432; then
  echo "Error: Postgres is not running on localhost:5432"
  exit 1
fi

echo "Running Alembic migrations..."
./hrmenv/bin/alembic revision --autogenerate -m "Create organizations table"
./hrmenv/bin/alembic upgrade head
echo "Migrations applied."
