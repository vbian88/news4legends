from io import BytesIO
from html import escape

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table,
    TableStyle, KeepTogether
)

router = APIRouter(tags=["Documentation"])


def build_api_guide():
    from app import app
    from api_tokens import SCOPES

    spec = app.openapi()
    output = BytesIO()
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="N4LTitle", parent=styles["Title"],
        textColor=colors.HexColor("#9b742a"),
        alignment=TA_CENTER, spaceAfter=18
    ))
    styles.add(ParagraphStyle(
        name="N4LRoute", parent=styles["Heading3"],
        textColor=colors.HexColor("#1c5260"),
        spaceBefore=12, spaceAfter=5
    ))

    doc = SimpleDocTemplate(
        output, pagesize=A4,
        rightMargin=42, leftMargin=42,
        topMargin=48, bottomMargin=45,
        title="News 4 Legends REST API Guide",
        author="News 4 Legends"
    )

    story = [
        Paragraph("News 4 Legends", styles["N4LTitle"]),
        Paragraph("REST API Reference - v1", styles["Heading1"]),
        Paragraph(
            "Generated from the running application's OpenAPI contract.",
            styles["BodyText"]
        ),
        Spacer(1, 12),
        Paragraph("Authentication", styles["Heading2"]),
        Paragraph(
            "Use Authorization: Bearer &lt;API_TOKEN&gt; for /api/v1 endpoints. "
            "Create, rotate and revoke tokens through the authenticated "
            "management UI or authorized token API. Token secrets are returned "
            "only when created or rotated.",
            styles["BodyText"]
        ),
        Spacer(1, 10),
        Paragraph("Authorization scopes", styles["Heading2"]),
        Paragraph(
            escape(", ".join(sorted(SCOPES))), styles["BodyText"]
        ),
        Spacer(1, 10),
        Paragraph("Important operational limitations", styles["Heading2"]),
        Paragraph(
            "Collection history currently returns HTTP 503 until a trusted "
            "worker history source is integrated. The backups endpoint exposes "
            "monitoring signals, not proof of remote archive integrity. "
            "Destructive endpoints require appropriate permissions and may "
            "require explicit confirmation.",
            styles["BodyText"]
        ),
        Spacer(1, 12),
        Paragraph("Endpoints", styles["Heading1"]),
    ]

    for path, methods in sorted(spec["paths"].items()):
        if not path.startswith("/api/v1"):
            continue
        for method, operation in sorted(methods.items()):
            if method.lower() not in (
                "get", "post", "patch", "put", "delete"
            ):
                continue
            title = f"{method.upper()} {path}"
            section = [
                Paragraph(escape(title), styles["N4LRoute"]),
                Paragraph(
                    escape(operation.get("summary") or "API operation"),
                    styles["BodyText"]
                )
            ]
            description = operation.get("description")
            if description:
                section.append(Paragraph(
                    escape(description[:900]), styles["BodyText"]
                ))

            parameters = operation.get("parameters") or []
            if parameters:
                section.append(Paragraph(
                    "Parameters: " + escape(", ".join(
                        f"{p['name']} ({p.get('in', 'unknown')})"
                        for p in parameters
                    )),
                    styles["BodyText"]
                ))

            request = operation.get("requestBody")
            if request:
                section.append(Paragraph(
                    "Request body: " + escape(", ".join(
                        (request.get("content") or {}).keys()
                    )),
                    styles["BodyText"]
                ))

            responses = operation.get("responses") or {}
            section.append(Paragraph(
                "Responses: " + escape(", ".join(
                    f"{code} {value.get('description', '')}"
                    for code, value in responses.items()
                )),
                styles["BodyText"]
            ))
            story.append(KeepTogether(section))

    story.extend([
        Spacer(1, 15),
        Paragraph("Operational notes", styles["Heading2"]),
        Paragraph(
            "Profile-scoped reads must respect contributor assignments. "
            "Administrative operations require administrator privileges. "
            "The UI and API share persistent configuration, but collection "
            "processing remains a separate worker responsibility. "
            "Do not interpret a successful monitoring signal as a tested restore.",
            styles["BodyText"]
        ),
    ])

    doc.build(story)
    return output.getvalue()


@router.get("/api-guide.pdf", include_in_schema=False)
def api_guide_pdf():
    content = build_api_guide()
    return StreamingResponse(
        BytesIO(content),
        media_type="application/pdf",
        headers={
            "Content-Disposition":
                'attachment; filename="News4Legends-REST-API-Guide.pdf"',
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
