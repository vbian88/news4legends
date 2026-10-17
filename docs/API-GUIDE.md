# REST API guide

The authenticated management API is described by [`openapi.json`](openapi.json)
and the generated [PDF reference](../assets/News-4-Legends-REST-API-Guide.pdf).
Both are generated from the application source; they do not contain production
data or credentials.

Regenerate them after an API change:

```bash
python3 scripts/generate_openapi.py
python3 scripts/generate_api_pdf.py assets/News-4-Legends-REST-API-Guide.pdf
```

Or use the isolated builder image:

```bash
docker compose --profile tools build news4legends-pdf-builder
docker compose --profile tools run --rm news4legends-pdf-builder
```

Use `Authorization: Bearer YOUR_TOKEN` for `/api/v1` endpoints and issue only
the scopes required by the client. Monitoring inventories require
`monitoring.read`. Missing scanner data returns HTTP 503 rather than an empty
success that could be misread as zero vulnerabilities.
