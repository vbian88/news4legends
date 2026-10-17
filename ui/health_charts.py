import html
import json
import math
import os
import time
from datetime import datetime
from pathlib import Path

REPORTS = Path(os.environ.get("NEWS4LEGENDS_REPORT_DIR", "/security-reports"))
SNAPSHOT = REPORTS / "system-health.json"
WINDOW = 30 * 86400

def e(value):
    return html.escape(str(value), quote=True)

def fmt(value):
    return f"{value:,.2f}" if value is not None else "N/A"

def chart(name, current, samples):
    """System Health chart with observed-time X axis and numeric Y axis."""
    from datetime import datetime

    now = time.time()
    points = sorted(
        (float(t), float(v))
        for t, v in samples
        if isinstance(t, (int, float))
        and isinstance(v, (int, float))
        and math.isfinite(t)
        and math.isfinite(v)
        and now - WINDOW <= t <= now + 60
    )

    if not points:
        return (
            f'<article class="metric"><h3>{e(name)}</h3>'
            '<p>No historical samples</p></article>'
        )

    values = [v for _, v in points]
    avg = sum(values) / len(values)
    low, high = min(values), max(values)

    binary = (
        name.startswith("container.")
        or name in (
            "docker.query_ok",
            "worker.available",
            "backup.success_marker",
        )
    )
    percent = name.endswith("_pct") or name.endswith(".pct")

    if binary:
        bottom, top = 0.0, 1.0
    elif percent:
        bottom, top = 0.0, 100.0
    else:
        spread = high - low
        pad = max(spread * 0.15, abs(avg) * 0.01, 0.01)
        bottom, top = low - pad, high + pad

    # Scale X to the timestamps actually observed, rather than forcing
    # short histories into the right edge of a 30-day canvas.
    first, last = points[0][0], points[-1][0]
    if last <= first:
        first -= 1800
        last += 1800

    left, right = 80.0, 700.0
    upper, lower = 22.0, 166.0

    def x(t):
        return left + (right - left) * (t - first) / (last - first)

    def y(v):
        return lower - (lower - upper) * (v - bottom) / (top - bottom)

    def number(v):
        if percent:
            return f"{v:.0f}%"
        if binary:
            return f"{v:.2f}"
        if abs(v) >= 1000:
            return f"{v:,.0f}"
        if abs(v) >= 10:
            return f"{v:.1f}"
        return f"{v:.2f}"

    grid = []
    for i in range(5):
        value = bottom + (top - bottom) * i / 4
        yy = y(value)
        grid.append(
            f'<line x1="{left}" y1="{yy:.1f}" '
            f'x2="{right}" y2="{yy:.1f}" '
            'stroke="#64748b" stroke-opacity=".35" '
            'stroke-dasharray="3 5"/>'
            f'<text x="72" y="{yy + 4:.1f}" '
            'fill="#aeb8c5" font-size="11" '
            f'text-anchor="end">{e(number(value))}</text>'
        )

    # Every label is derived from a timestamp, not the current date
    # or an assumed thirty-day-old observation.
    span = last - first
    date_format = "%d-%m-%Y %H:%M"

    for i in range(5):
        timestamp = first + span * i / 4
        xx = left + (right - left) * i / 4
        label = datetime.fromtimestamp(timestamp).strftime(date_format)
        anchor = "start" if i == 0 else (
            "end" if i == 4 else "middle"
        )
        grid.append(
            f'<line x1="{xx:.1f}" y1="{upper}" '
            f'x2="{xx:.1f}" y2="{lower}" '
            'stroke="#64748b" stroke-opacity=".18"/>'
            f'<text x="{xx:.1f}" y="191" '
            f'fill="#aeb8c5" font-size="10" '
            f'text-anchor="end" transform="rotate(-45 {xx:.1f} 191)">{e(label)}</text>'
        )

    coordinates = " ".join(
        f"{x(t):.1f},{y(v):.1f}" for t, v in points
    )

    latest = (
        float(current)
        if isinstance(current, (int, float))
        and math.isfinite(current)
        else values[-1]
    )

    def display(v):
        if binary:
            return "Healthy" if v == 1 else "Failed"
        return f"{v:.2f}"

    average_display = (
        f"{avg * 100:.1f}% passing" if binary else f"{avg:.2f}"
    )
    coverage = max(0.0, (points[-1][0] - points[0][0]) / 86400)

    # The average is drawn against the same numeric Y scale.
    average_y = y(avg)
    guides = "".join(grid)

    return f"""
    <article class="metric">
      <h3>{e(name)}</h3>
      <div class="stats">
        <span>Now <strong>{e(display(latest))}</strong></span>
        <span>30-day average <strong>{e(average_display)}</strong></span>
        <span>Min <strong>{low:.2f}</strong></span>
        <span>Max <strong>{high:.2f}</strong></span>
        <span>Samples <strong>{len(points)}</strong></span>
      </div>
      <svg viewBox="0 0 730 265" role="img"
           aria-label="Numeric metric values over actual observation dates for {e(name)}">
        {guides}
        <line x1="{left}" y1="{average_y:.1f}"
              x2="{right}" y2="{average_y:.1f}"
              stroke="#d8ad62" stroke-width="2"
              stroke-dasharray="9 6"/>
        <polyline points="{coordinates}" fill="none"
                  stroke="#55c7b0" stroke-width="2.5"
                  stroke-linecap="round" stroke-linejoin="round"/>
        <circle cx="{x(points[-1][0]):.1f}"
                cy="{y(points[-1][1]):.1f}"
                r="4" fill="#55c7b0"/>
      </svg>
      <p class="note">Rolling 30-day sample window ·
      {coverage:.2f} days of observed history ·
      horizontal axis shows actual observation dates</p>
    </article>"""


def security_monitoring():
    from datetime import datetime, timezone
    reports = REPORTS
    now = datetime.now(timezone.utc)

    def age(value):
        try:
            timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return max(0, int((now - timestamp).total_seconds() / 3600))
        except (ValueError, TypeError, AttributeError):
            return None

    av = reports / "clamav-current.json"
    if av.exists():
        try:
            result = json.loads(av.read_text())
            hours = age(result.get("timestamp"))
            av_text = (
                f"Status: {result.get('status', 'unknown')} | "
                f"Detections: {len(result.get('detections', []))} | "
                f"Last scan: {result.get('timestamp', 'unknown')} | "
                f"Age: {hours if hours is not None else '?'} hours"
            )
        except (ValueError, OSError, TypeError):
            av_text = "Report unreadable"
    else:
        av_text = "No scan report available"

    images = list((reports / "container-images").glob("*.json"))
    skipped = reports / "container-scan-skipped-images.txt"
    missing = (
        [line.strip() for line in skipped.read_text().splitlines()
         if line.strip()]
        if skipped.exists() else []
    )

    high = critical = 0
    latest = None
    for report in images:
        try:
            data = json.loads(report.read_text())
            timestamp = report.stat().st_mtime
            latest = max(latest or timestamp, timestamp)
            for result in data.get("Results", []):
                for vuln in result.get("Vulnerabilities") or []:
                    if vuln.get("Severity") == "HIGH":
                        high += 1
                    elif vuln.get("Severity") == "CRITICAL":
                        critical += 1
        except (OSError, ValueError, TypeError):
            continue

    coverage = "PARTIAL" if missing else (
        "COMPLETE" if images else "UNKNOWN"
    )
    scan_time = (
        datetime.fromtimestamp(latest, timezone.utc).isoformat()
        if latest else "Unavailable"
    )
    trivy_text = (
        f"Coverage: {coverage} | Scanned reports: {len(images)} | "
        f"Skipped images: {len(missing)} | HIGH: {high} | "
        f"CRITICAL: {critical} | Latest report: {scan_time}"
    )

    return (
        '<section><h2>Security monitoring</h2><div class="grid">'
        '<article class="metric"><h3>ClamAV</h3><p>'
        + e(av_text) +
        '</p></article><article class="metric"><h3>Trivy</h3><p>'
        + e(trivy_text) +
        '</p><p class="note">Partial coverage does not suppress '
        'security notifications. Findings are processed through '
        'the existing n8n Telegram integration.</p>'
        '</article></div></section>'
    )



def ctem_trends():
    """Unified vulnerability view with separately identified sources."""
    reports = REPORTS
    container_path = reports / "container-vulnerability-trends.json"
    application_history = reports / "history"

    try:
        container = json.loads(container_path.read_text()).get("items", [])
    except (OSError, ValueError, TypeError):
        container = []

    application = []
    if application_history.is_dir():
        for path in sorted(application_history.glob("*.json"))[-90:]:
            try:
                data = json.loads(path.read_text())
                counts = data.get("counts") or {}
                if not isinstance(counts, dict):
                    continue
                stamp = data.get("generated_at")
                if isinstance(stamp, (int, float)):
                    date = datetime.fromtimestamp(stamp).strftime("%d-%m-%Y %H:%M")
                elif isinstance(stamp, str):
                    date = stamp[:10]
                else:
                    date = path.stem[:10]
                application.append({
                    "date": date,
                    "counts": {
                        level: counts.get(level, counts.get(level.lower(), 0))
                        for level in ("CRITICAL", "HIGH", "MEDIUM", "LOW")
                    },
                    "manual_review": len(data.get("manual_review") or []),
                })
            except (OSError, ValueError, TypeError):
                continue

    try:
        debian_data = json.loads(
            (reports / "debian-vulnerability-trends.json").read_text()
        )
        if debian_data.get("schema_version") != 1:
            raise ValueError("Unsupported Debian history")
        debian = debian_data["items"]
    except (OSError, ValueError, KeyError, TypeError):
        debian = []

    levels = ("CRITICAL", "HIGH", "MEDIUM", "LOW")
    colors = {
        "CRITICAL": "#f87171",
        "HIGH": "#fb923c",
        "MEDIUM": "#facc15",
        "LOW": "#55c7b0",
    }

    def source_table(title, rows, coverage=False):
        if not rows:
            return (
                f'<article class="metric"><h3>{e(title)}</h3>'
                '<p>No historical snapshots available</p></article>'
            )

        rows = sorted(rows, key=lambda r: r["date"])[-30:]
        observed = [
            r.get("counts", {}).get(level)
            for r in rows for level in levels
        ]
        maximum = max(
            [v for v in observed
             if isinstance(v, (int, float)) and not isinstance(v, bool)
             and v >= 0] or [1]
        )
        maximum = max(maximum, 1)

        def x(i):
            return 55 + 815 * i / max(len(rows) - 1, 1)

        def y(v):
            return 205 - 185 * v / maximum

        lines = [
            '<svg viewBox="0 0 900 250" role="img" '
            f'aria-label="{e(title)} severity trends">',
            '<line x1="55" y1="205" x2="870" y2="205" '
            'stroke="#64748b"/>',
        ]

        for level in levels:
            segment = []
            for i, row in enumerate(rows):
                value = row.get("counts", {}).get(level)
                if (isinstance(value, (int, float))
                        and not isinstance(value, bool) and value >= 0):
                    segment.append(f"{x(i):.1f},{y(value):.1f}")
                elif segment:
                    lines.append(
                        f'<polyline points="{" ".join(segment)}" '
                        f'fill="none" stroke="{colors[level]}" '
                        'stroke-width="2.5"/>'
                    )
                    segment = []
            if segment:
                lines.append(
                    f'<polyline points="{" ".join(segment)}" '
                    f'fill="none" stroke="{colors[level]}" '
                    'stroke-width="2.5"/>'
                )

        # Numeric severity labels for observed points.
        # Skip some labels on long histories to prevent collisions.
        stride = max(1, (len(rows) + 11) // 12)
        for i, row in enumerate(rows):
            if i % stride and i != len(rows) - 1:
                continue
            for level_index, level in enumerate(levels):
                value = row.get("counts", {}).get(level)
                if not isinstance(value, (int, float)) or isinstance(value, bool):
                    continue
                if value < 0:
                    continue
                px, py = x(i), y(value)
                lines.append(
                    f'<circle cx="{px:.1f}" cy="{py:.1f}" r="3.5" '
                    f'fill="{colors[level]}"/>'
                )
                # Alternating offsets keep labels readable where possible.
                offset = (-10, 14, -10, 14)[level_index]
                label_y = min(218, max(12, py + offset))
                lines.append(
                    f'<text x="{px:.1f}" y="{label_y:.1f}" '
                    f'text-anchor="middle" fill="{colors[level]}" '
                    f'font-size="12" font-weight="600">'
                    f'{e(f"{value:g}")}</text>'
                )

        lines.append(
            f'<text x="55" y="240" fill="#aeb8c5" font-size="13">'
            f'{e(rows[0].get("timestamp", rows[0]["date"])[:16].replace("T", " "))}</text>'
        )
        lines.append(
            f'<text x="870" y="240" text-anchor="end" '
            f'fill="#aeb8c5" font-size="13">'
            f'{e(rows[-1].get("timestamp", rows[-1]["date"])[:16].replace("T", " "))}</text></svg>'
        )

        header = (
            "<tr><th>Date</th><th>Critical</th><th>High</th>"
            "<th>Medium</th><th>Low</th>"
            + ("<th>Coverage</th>" if coverage else "<th>Manual review</th>")
            + "</tr>"
        )

        body = []
        for row in reversed(rows):
            counts = row.get("counts") or {}
            cells = "".join(
                "<td>" + (
                    str(counts.get(level))
                    if isinstance(counts.get(level), (int, float))
                    else "N/A"
                ) + "</td>"
                for level in levels
            )
            extra = (
                row.get("coverage", "unknown")
                if coverage else row.get("manual_review", 0)
            )
            body.append(
                f'<tr><td>{e(row.get("timestamp", row["date"]).replace("T", " ")[:19])}</td>{cells}'
                f'<td>{e(extra)}</td></tr>'
            )

        legend = " &nbsp; ".join(
            f'<span style="color:{colors[level]}">━━ {level}</span>'
            for level in levels
        )

        return (
            f'<article class="metric"><h3>{e(title)}</h3>'
            '<p>' + legend + '</p>' + "".join(lines)
            + '<div style="overflow-x:auto"><table style="width:100%;'
            'text-align:left"><thead>' + header + '</thead><tbody>'
            + "".join(body) + '</tbody></table></div></article>'
        )

    return (
        '<section><h2>Vulnerability Trends (CTEM)</h2>'
        '<p class="note">Actual scan dates. Container findings and '
        'application advisories are separate sources; counts are not '
        'summed because duplicate CVEs may occur. Manual review is '
        'uncertain, not a confirmed severity. Missing observations '
        'are not treated as zero.</p>'
        '<div class="grid">'
        + source_table("Debian OS vulnerabilities", debian, True)
        + source_table("Container vulnerabilities", container, True)
        + source_table("Application advisories", application, False)
        + '</div></section>'
    )


def render():
    data = json.loads(SNAPSHOT.read_text())
    if data.get("schema_version") != 1:
        raise ValueError("Unsupported snapshot version")

    metrics = data["metrics"]
    history = data["history"]
    age = max(0, int(time.time() - data["generated_at"]))
    incidents = data.get("active_incidents", {})
    stale = age > 1200

    status = (
        "DATA STALE" if stale else
        "ATTENTION REQUIRED" if incidents else
        "ALL SYSTEMS OPERATIONAL"
    )

    groups = {
        "CPU and memory": [
            "cpu.", "memory.", "swap."
        ],
        "Disk and host": [
            "disk.", "host."
        ],
        "Containers and Docker": [
            "container.", "docker."
        ],
        "Worker and backups": [
            "worker.", "backup."
        ],
    }

    sections = []
    for heading, prefixes in groups.items():
        charts = "".join(
            chart(name, metrics[name], history.get(name, []))
            for name in sorted(metrics)
            if any(name.startswith(prefix) for prefix in prefixes)
        )
        sections.append(f"<section><h2>{e(heading)}</h2><div class='grid'>{charts}</div></section>")

    _dashboard_html = f'''<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="300">
<title>News 4 Legends · System Health</title>
<style>
body{{margin:0;background:#10151d;color:#f1e9d8;font:15px system-ui,sans-serif}}
main{{max-width:1500px;margin:auto;padding:28px 20px}}
h1,h2{{color:#d8ad62}}
a{{color:#d8ad62}}
header{{margin-bottom:24px}}
.banner,.metric{{background:#1b2430;border:1px solid #394354;border-radius:12px;padding:18px}}
.banner{{margin:18px 0 30px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,480px),1fr));gap:16px}}
.metric h3{{font-size:15px;color:#f1e9d8;overflow-wrap:anywhere}}
.stats{{display:flex;flex-wrap:wrap;gap:12px;font-size:12px;color:#aeb8c5}}
.stats strong{{color:#f1e9d8}}
svg{{display:block;width:100%;height:auto;margin-top:12px}}
.note{{font-size:12px;color:#aeb8c5}}
section{{margin-bottom:32px}}
</style></head><body><main>
<header><a href="/">← Profiles</a>
<h1>News 4 Legends · System Health</h1>
<p>22 monitored metrics · updated every 15 minutes · page refreshes every 5 minutes</p>
</header>
<div class="banner"><strong>{e(status)}</strong>
<p>Snapshot age: {age} seconds · Active incidents: {len(incidents)}</p>
<p><span style="color:#55c7b0">━━</span> Observed
&nbsp;&nbsp; <span style="color:#d8ad62">┄┄</span> Rolling 30-day average</p>
</div>
{''.join(sections)}
{ctem_trends()}
{security_monitoring()}
</main></body></html>'''

    return _dashboard_html
