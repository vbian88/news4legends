FROM python:3.12-slim

WORKDIR /app

COPY docker/ui/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

COPY ui/ /app/
RUN mkdir -p /app/static

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
