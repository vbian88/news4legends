FROM python:3.12-slim

WORKDIR /src
COPY docker/ui/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY ui/ /src/ui/
COPY scripts/generate_api_pdf.py /src/scripts/generate_api_pdf.py
RUN mkdir -p /output
CMD ["python", "/src/scripts/generate_api_pdf.py", "/output/News-4-Legends-REST-API-Guide.pdf"]
