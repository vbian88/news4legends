FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    fastapi \
    python-multipart \
    "uvicorn[standard]"

COPY ui/app.py /app/app.py
COPY ui/db_bootstrap.py /app/db_bootstrap.py
COPY ui/schema.sql /app/schema.sql

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
