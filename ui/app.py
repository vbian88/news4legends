import html
import json
import sqlite3
import urllib.request
import urllib.error

from db_bootstrap import bootstrap_database
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse, Response


app = FastAPI(title="News 4 Legends")


DB_PATH = "/data/home-ai-news.db"

bootstrap_database(DB_PATH)


def get_db():
    db = sqlite3.connect(DB_PATH, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    db.execute("PRAGMA busy_timeout = 30000")
    return db


def page(body):
    return f"""
    <!doctype html>
    <html>
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>News 4 Legends</title>
        <style>
          :root {{
            --roma: #8e1f2f;
            --roma-dark: #3b0710;
            --roma-deep: #18070b;
            --gold: #f0bc2d;
            --gold-light: #ffd75c;
            --ink: #070d12;
            --panel: rgba(7, 15, 21, .96);
            --text: #edf0f2;
            --muted: #b7bec4;
            --border: rgba(240, 188, 45, .65);
          }}

          * {{
            box-sizing: border-box;
          }}

          html {{
            min-height: 100%;
            background: var(--roma-deep);
          }}

          body {{
            min-height: 100vh;
            margin: 0;
            padding: 38px 30px 60px;
            color: var(--text);
            font-family:
              Inter, ui-sans-serif, system-ui,
              -apple-system, BlinkMacSystemFont,
              "Segoe UI", sans-serif;
            line-height: 1.55;
            background:
              radial-gradient(
                circle at 75% 10%,
                rgba(240,188,45,.13),
                transparent 30%
              ),
              linear-gradient(
                135deg,
                #24080d 0%,
                #5b101d 45%,
                #25070c 100%
              );
          }}

          .site-header {{
            max-width: 1450px;
            margin: 0 auto 26px;
            padding: 4px 4px 18px;
            border-bottom: 1px solid rgba(240,188,45,.38);
          }}

          .site-title {{
            margin: 0;
            color: var(--gold-light);
            font-family: Georgia, "Times New Roman", serif;
            font-size: clamp(2.4rem, 5vw, 4.2rem);
            line-height: 1;
            letter-spacing: -.035em;
          }}

          .site-tagline {{
            margin: 10px 0 0;
            color: #f1f1f1;
            font-size: 1.12rem;
            letter-spacing: .03em;
          }}

          .roma-rule {{
            display: flex;
            width: 105px;
            height: 5px;
            margin-top: 15px;
            overflow: hidden;
            border-radius: 3px;
          }}

          .roma-rule span:first-child {{
            width: 70%;
            background: var(--gold);
          }}

          .roma-rule span:last-child {{
            width: 30%;
            background: var(--roma);
          }}

          .page-grid {{
            display: grid;
            grid-template-columns:
              minmax(0, 1.55fr)
              minmax(330px, .85fr);
            gap: 18px;
            max-width: 1450px;
            margin: 0 auto;
            align-items: start;
          }}

          .content-panel,
          .passion-panel {{
            overflow: hidden;
            border: 1px solid var(--border);
            border-radius: 14px;
            box-shadow: 0 20px 50px rgba(0,0,0,.32);
          }}

          .content-panel {{
            min-width: 0;
            padding: 26px;
            background: var(--panel);
          }}

          .passion-panel {{
            position: sticky;
            top: 24px;
            background:
              linear-gradient(
                160deg,
                #650d1c,
                #31070e
              );
          }}

          .passion-copy {{
            padding: 24px 27px 28px;
          }}

          .passion-copy h2 {{
            margin: 0 0 16px;
            color: var(--gold-light);
            font-family: Georgia, "Times New Roman", serif;
            font-size: 2rem;
          }}

          .passion-copy p {{
            margin: 0 0 16px;
            color: #f1e9eb;
          }}

          .passion-copy strong {{
            color: white;
          }}

          .passion-signoff {{
            color: var(--gold-light) !important;
            font-size: 1.06rem;
          }}

          .passion-footer {{
            margin-top: 24px;
            padding-top: 18px;
            color: var(--gold);
            border-top: 1px solid var(--gold);
            font-size: .76rem;
            font-weight: 700;
            letter-spacing: .18em;
            text-align: center;
            text-transform: uppercase;
          }}

          h1 {{
            margin-top: 0;
            color: white;
            font-family: Georgia, "Times New Roman", serif;
            font-size: 2.2rem;
          }}

          h2, h3 {{
            color: var(--gold-light);
          }}

          p {{
            margin: 0 0 18px;
          }}

          a {{
            color: var(--gold-light);
          }}

          a:hover {{
            color: white;
          }}

          .card {{
            margin: 20px 0;
            padding: 22px;
            color: var(--text);
            background: rgba(13,22,29,.96);
            border: 1px solid rgba(240,188,45,.34);
            border-radius: 10px;
          }}

          table {{
            width: 100%;
            border-collapse: collapse;
            color: var(--text);
          }}

          th, td {{
            padding: 10px;
            text-align: left;
            border-bottom: 1px solid rgba(255,255,255,.10);
          }}

          th {{
            color: var(--gold-light);
            background: rgba(240,188,45,.07);
          }}

          input:not([type="checkbox"]):not([type="radio"]),
          select,
          textarea {{
            max-width: 100%;
            padding: 8px 10px;
            color: var(--text);
            background: #0c151d;
            border: 1px solid #59636b;
            border-radius: 5px;
          }}

          input:focus,
          select:focus,
          textarea:focus {{
            outline: 2px solid rgba(240,188,45,.28);
            border-color: var(--gold);
          }}

          input[type="checkbox"],
          input[type="radio"] {{
            accent-color: var(--gold);
          }}

          button,
          input[type="submit"] {{
            padding: 9px 15px;
            color: #1c1300;
            font-weight: 750;
            background: var(--gold);
            border: 1px solid var(--gold-light);
            border-radius: 6px;
            cursor: pointer;
          }}

          button:hover,
          input[type="submit"]:hover {{
            background: var(--gold-light);
          }}

          .source-actions {{
            display: flex;
            align-items: center;
            gap: 7px;
            flex-wrap: nowrap;
            white-space: nowrap;
          }}

          .source-actions form {{
            display: inline-flex !important;
            margin: 0 !important;
          }}

          .source-actions button,
          .action-button {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            box-sizing: border-box;
            min-height: 36px;
            padding: 8px 13px;
            border-radius: 6px;
            font-weight: 750;
            line-height: 1;
            text-decoration: none;
          }}

          .action-edit {{
            color: var(--gold-light);
            background: rgba(240,188,45,.08);
            border: 1px solid rgba(240,188,45,.55);
          }}

          .action-edit:hover {{
            color: #1c1300;
            background: var(--gold-light);
          }}

          .action-delete {{
            color: #ff9b9b;
            background: rgba(255,121,121,.06);
            border: 1px solid rgba(255,121,121,.55);
          }}

          .action-delete:hover {{
            color: #fff;
            background: rgba(190,45,45,.55);
            border-color: #ff7979;
          }}

          .info {{
            display: inline-block;
            margin-left: 4px;
            color: var(--gold-light);
            cursor: help;
            font-weight: bold;
            text-decoration: none;
          }}

          .info-box {{
            display: none;
            position: fixed;
            z-index: 1000;
            left: 50%;
            top: 50%;
            transform: translate(-50%, -50%);
            max-width: 520px;
            width: calc(100% - 60px);
            padding: 22px;
            color: var(--text);
            background: #10171d;
            border: 1px solid var(--gold);
            border-radius: 8px;
            box-shadow: 0 10px 40px rgba(0,0,0,.7);
          }}

          .info-box:target {{
            display: block;
          }}

          .info-close {{
            float: right;
            color: var(--gold-light);
            font-size: 22px;
            text-decoration: none;
          }}

          .guidance {{
            padding: 17px;
            margin: 18px 0;
            color: var(--text);
            background: rgba(240,188,45,.07);
            border-left: 5px solid var(--gold);
          }}

          .guidance.warning {{
            border-left-color: #e5a820;
            background: rgba(229,168,32,.10);
          }}

          .guidance.pass {{
            border-left-color: #67d27a;
            background: rgba(103,210,122,.08);
          }}

          .guidance.fail {{
            border-left-color: #ff7979;
            background: rgba(255,121,121,.08);
          }}

          small {{
            color: var(--muted);
          }}

          @media (max-width: 950px) {{
            .page-grid {{
              grid-template-columns: 1fr;
            }}

            .passion-panel {{
              position: static;
            }}

          }}

          @media (max-width: 600px) {{
            body {{
              padding: 22px 12px 45px;
            }}

            .content-panel {{
              padding: 17px;
            }}

            .passion-copy {{
              padding: 20px;
            }}
          }}
        </style>
      </head>

      <body>
        <header class="site-header">
          <div class="site-title">News 4 Legends</div>

          <p class="site-tagline">
            Your sources. Your signals. Your digest.
          </p>

          <div class="roma-rule">
            <span></span><span></span>
          </div>
        </header>

        <main class="page-grid">
          <section class="content-panel">
            {body}
          </section>

          <aside class="passion-panel">
            <div class="passion-copy">
              <h2>A Personal Passion</h2>

              <p>
                This project has stemmed from my passion for
                <strong>AS Roma</strong> and the desire to stay
                connected to the club, the people and everything
                that makes this club so special.
              </p>

              <p>
                It would never have started without
                <strong>Claudio Ranieri</strong>.
              </p>

              <p class="passion-signoff">
                Grazie, Mister. Sempre con noi. &#10084;
              </p>

              <div class="passion-footer">
                AS Roma · Più di una squadra · Una famiglia
              </div>
            </div>
          </aside>
        </main>
      </body>
    </html>
    """


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "home-ai-news-ui",
    }


@app.get("/logs/download")
def download_latest_worker_log():
    try:
        with urllib.request.urlopen(
            "http://news4legends-worker:8080/logs",
            timeout=15,
        ) as response:
            content = response.read()
            disposition = response.headers.get(
                "Content-Disposition",
                'attachment; filename="news4legends-worker-log.txt"',
            )
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return HTMLResponse(
                "No worker run log is available yet.",
                status_code=404,
            )
        return HTMLResponse(
            "Worker log request failed.",
            status_code=502,
        )
    except urllib.error.URLError:
        return HTMLResponse(
            "Worker log service is unavailable.",
            status_code=502,
        )

    return Response(
        content=content,
        media_type="text/plain",
        headers={"Content-Disposition": disposition},
    )


@app.get("/", response_class=HTMLResponse)
def home():
    db = get_db()

    profiles = db.execute("""
        SELECT
            p.slug,
            p.name,
            p.enabled,
            p.telegram_enabled,
            COUNT(ps.id) AS source_count,
            COALESCE(SUM(ps.enabled), 0) AS enabled_count
        FROM profiles p
        LEFT JOIN profile_sources ps
            ON ps.profile_id = p.id
        GROUP BY p.id
        ORDER BY p.name
    """).fetchall()

    db.close()

    cards = []

    for profile in profiles:
        status = "Enabled" if profile["enabled"] else "Disabled"

        cards.append(
            f"""
            <div class="card">
              <h3>{html.escape(profile["name"])}</h3>
              <p>
                {status}
                &nbsp;|&nbsp;
                {profile["enabled_count"]}/{profile["source_count"]}
                sources enabled
                &nbsp;|&nbsp;
                News feeds:
                <strong>
                  {"Yes" if profile["telegram_enabled"] else "No"}
                </strong>
              </p>

              <form method="post"
                    action="/profiles/{html.escape(profile['slug'])}/telegram"
                    style="margin:12px 0">
                <label>
                  <input type="checkbox"
                         name="telegram_enabled"
                         {"checked" if profile["telegram_enabled"] else ""}
                         onchange="this.form.submit()">
                  Add this profile to your news feeds
                </label>
              </form>

              <a href="/profiles/{html.escape(profile['slug'])}">
                Open profile
              </a>
            </div>
            """
        )

    return page(
        f"""
        <h2>Profiles</h2>

        <p>
          <a href="/new-profile">+ Add Profile</a>
          &nbsp;|&nbsp;
          <a href="/guide">📖 Zero-to-Hero Guide</a>
          &nbsp;|&nbsp;
          <a href="/logs/download">Download latest worker log</a>
        </p>

        {''.join(cards)}

        <div class="card">
          <h3>New here?</h3>
          <p>
            Learn what profiles, sources, validation, budgets and
            automation mean, then build a profile from scratch.
          </p>
          <p>
            <a href="/guide">
              Start with the Zero-to-Hero Guide →
            </a>
          </p>
        </div>

        <p><em>SQLite management configuration.</em></p>
        """
    )


@app.get("/profiles/{profile_id}", response_class=HTMLResponse)
def profile_view(profile_id: str):
    db = get_db()

    profile = db.execute(
        "SELECT * FROM profiles WHERE slug = ?",
        (profile_id,),
    ).fetchone()

    if profile is None:
        db.close()
        return HTMLResponse("Profile not found", status_code=404)

    sources = db.execute("""
        SELECT
            ps.id,
            s.name,
            ps.enabled,
            ps.collector_type,
            ps.topic_focused,
            ps.credibility_score,
            ps.validation_status,
            ps.validation_reason,
            ps.validated_at
        FROM profile_sources ps
        JOIN sources s
            ON s.id = ps.source_id
        WHERE ps.profile_id = ?
        ORDER BY ps.id
    """, (profile["id"],)).fetchall()

    db.close()

    rows = []

    for source in sources:
        validation_status = source["validation_status"] or "NOT VALIDATED"

        validate_form = (
            f'<form method="post" style="display:inline" '
            f'action="/profiles/{html.escape(profile_id)}/sources/{source["id"]}/validate">'
            f'<button type="submit">Validate</button>'
            f'</form>'
        )

        edit_link = (
            f'<a class="action-button action-edit" '
            f'href="/profiles/{html.escape(profile_id)}/sources/{source["id"]}/edit">Edit</a>'
        )

        if source["enabled"]:
            state_form = (
                f'<form method="post" style="display:inline;margin-left:6px" '
                f'action="/profiles/{html.escape(profile_id)}/sources/{source["id"]}/disable">'
                f'<button type="submit">Disable</button>'
                f'</form>'
            )
        elif validation_status in ("PASS", "WARNING"):
            state_form = (
                f'<form method="post" style="display:inline;margin-left:6px" '
                f'action="/profiles/{html.escape(profile_id)}/sources/{source["id"]}/enable">'
                f'<button type="submit">Enable</button>'
                f'</form>'
            )
        else:
            state_form = ""

        rows.append(
            "<tr>"
            f"<td>{html.escape(source['name'])}</td>"
            f"<td>{'Yes' if source['enabled'] else 'No'}</td>"
            f"<td>{html.escape(source['collector_type'])}</td>"
            f"<td>{'Yes' if source['topic_focused'] else 'No'}</td>"
            f"<td>{html.escape(str(source['credibility_score']))}</td>"
            f"<td>{html.escape(validation_status)}</td>"
            f"""<td>
            <div class="source-actions">
              {validate_form}
              {edit_link}
              {state_form}
              <a class="action-button action-delete"
                 href="/profiles/{html.escape(profile_id)}/sources/{source["id"]}/delete">
                Delete
              </a>
            </div>
            </td>"""
            "</tr>"
        )

    return page(
        f"""
        <p><a href="/">← Profiles</a></p>

        <h2>Profile: {html.escape(profile["name"])}</h2>

        <p>
          Status:
          <strong>
            {"Enabled" if profile["enabled"] else "Disabled"}
          </strong>
          &nbsp;|&nbsp;
          <a href="/profiles/{html.escape(profile_id)}/edit">
            Edit profile
          </a>
          &nbsp;|&nbsp;
          <a href="/profiles/{html.escape(profile_id)}/delete"
             style="color:#b42318">
            Delete profile
          </a>
        </p>

        <form method="post"
              action="/profiles/{html.escape(profile_id)}/{"disable" if profile["enabled"] else "enable"}"
              style="display:inline">
          <button type="submit">
            {"Disable profile" if profile["enabled"] else "Enable profile"}
          </button>
        </form>

        <p>
          Stories in digest:
          <strong>{profile["llm_limit"] or 3}</strong>
          &nbsp;|&nbsp;
          Maximum age:
          <strong>{profile["maximum_age_hours"]}h</strong>
        </p>

        <h2>Sources</h2>
        <p><a href="/profiles/{html.escape(profile_id)}/new-source">+ Add Source</a></p>
        <table>
          <thead>
            <tr>
              <th>Source</th>
              <th>Enabled</th>
              <th>Collector</th>
              <th>Topic focused</th>
              <th>Credibility score</th>
              <th>Validation</th>
            </tr>
          </thead>
          <tbody>
            {''.join(rows)}
          </tbody>
        </table>

        <p><em>SQLite management configuration.</em></p>
        """
    )



# ============================================================
# GUIDE
# ============================================================

@app.get("/guide", response_class=HTMLResponse)
def guide():
    return page("""
        <p><a href="/">← Profiles</a></p>

        <h2>Zero-to-Hero Guide</h2>

        <div class="card">
          <h3>1. Profile</h3>
          <p>
            A profile is a topic that News 4 Legends monitors.
            Examples: Cybersecurity, Artificial Intelligence,
            Local News.
          </p>
          <p>
            Each profile has its own topic rules, sources,
            freshness settings and workload limits.
          </p>
        </div>

        <div class="card">
          <h3>2. Tell News 4 Legends What to Look For</h3>

          <p>
            There are two separate questions:
          </p>

          <p>
            <strong>What am I interested in?</strong>
            The Profile answers this with its Topic and optional
            Keywords.
          </p>

          <p>
            <strong>Where should News 4 Legends look?</strong>
            Sources answer this. You add those after creating the
            profile.
          </p>

          <p>
            When the profile runs, the basic flow is:
            <strong>
              discover possible articles → identify promising
              material → fetch it → check relevance and freshness →
              keep useful articles → build the digest.
            </strong>
          </p>

          <p>
            Topic is the foundation. Keywords enrich that definition;
            they do not replace it and they
            are not mandatory words that every article must contain.
          </p>

          <p>
            <strong>Topic</strong> describes what the whole profile
            is about. Example: "Cybersecurity" or "The Smurfs".
          </p>

          <p>
            <strong>Keywords are optional.</strong> They are
            profile-wide relevance hints that you control. Topic is
            the primary definition of the profile. Keywords add useful
            synonyms, terminology and phrases but are not a mandatory
            allow-list.
          </p>

          <p>
            Examples include alternative names, important
            terminology, recurring subjects or phrases strongly
            associated with the topic. It is perfectly valid to leave
            Keywords empty and add them later if collection needs
            refinement.
          </p>

          <div class="guidance warning">
            <strong>Important:</strong>
            Do not try to enumerate every possible relevant word.
            Topic is always considered. Keywords provide additional
            signals. A missing keyword does not by itself
            reject an article if another profile signal identifies it
            as relevant.
          </div>

          <p>
            Keywords belong to the <strong>profile</strong>, not
            individual sources.
            Every source attached to that profile uses the same
            profile topic definition.
          </p>
        </div>

        <div class="card">
          <h3>3. Choose the Digest Size</h3>
          <p>
            <strong>Stories in digest</strong> requests between 1 and
            10 prioritised stories. The effective result is bounded by
            the configured LLM-call budget and the number of valid
            clusters available. Asking for more stories does not
            increase collection budgets automatically.
          </p>
        </div>

        <div class="card">
          <h3>4. Source</h3>

          <p>
            A source is a website, feed or provider from which
            candidate articles are discovered.
          </p>

          <p>
            Production discovery currently supports
            <strong>web</strong> sources.
          </p>

          <p>
            FreshRSS and social are planned ingestion types and
            should not yet be treated as production-ready.
          </p>
        </div>

        <div class="card">
          <h3>5. Topic Focused vs Broad Sources</h3>

          <p>
            <strong>Topic focused</strong> means the source mainly
            publishes material about this profile's subject.
            Examples include an official project site, specialist
            publication, team site or dedicated topic site.
          </p>

          <p>
            Because most of its content is already relevant, the
            generic collector can use less aggressive topic filtering.
          </p>

          <p>
            A <strong>broad source</strong> publishes many unrelated
            subjects. Those sources need stronger relevance checks
            using the profile topic and relevance signals to avoid
            collecting unrelated articles.
          </p>

          <div class="guidance warning">
            Do not mark a broad news site as Topic Focused simply to
            collect more articles. That would weaken an important
            relevance guardrail.
          </div>
        </div>

        <div class="card">
          <h3>6. Credibility score</h3>

          <p>
            This is a profile-specific weighting you control.
            It is not an objective or global rating of a source.
          </p>
        </div>

        <div class="card">
          <h3>7. Validate before enabling</h3>

          <p>
            Validation performs a bounded pre-flight check before a
            source is admitted into production.
          </p>

          <p>
            <strong>PASS</strong> — sampled collection worked.
          </p>

          <p>
            <strong>WARNING</strong> — source may be usable, but
            review the reported limitation or workload.
          </p>

          <p>
            <strong>FAIL</strong> — leave the source disabled,
            correct the problem and validate again.
          </p>
        </div>

        <div class="card">
          <h3>8. Workload budgets</h3>

          <p>
            <strong>Candidate budget</strong> — maximum links
            considered from the listing page.
          </p>

          <p>
            <strong>Fetch budget</strong> — maximum article pages
            fetched from the source.
          </p>

          <p>
            <strong>Request timeout</strong> — maximum time to wait
            for an individual HTTP request.
          </p>

          <p>
            <strong>Source runtime</strong> — wall-clock guardrail
            for work performed on one source.
          </p>

          <p>
            Start conservatively. Increase limits only when
            monitoring shows useful material is being missed.
          </p>
        </div>

        <div class="card">
          <h3>9. Zero to Hero</h3>

          <ol>
            <li>Create a profile.</li>
            <li>Add meaningful keywords.</li>
            <li>Choose 1–10 stories for the digest.</li>
            <li>Add a web source.</li>
            <li>Set conservative workload budgets.</li>
            <li>Validate the source.</li>
            <li>Review PASS, WARNING or FAIL.</li>
            <li>Enable acceptable sources.</li>
            <li>Enable the profile.</li>
            <li>Monitor collection results and workload.</li>
          </ol>
        </div>

        <div class="card">
          <h3>10. Delete vs Disable</h3>

          <p>
            <strong>Disable</strong> is reversible and should normally
            be your first choice.
          </p>

          <p>
            <strong>Delete</strong> removes configuration.
            Profile and source deletion therefore require explicit
            confirmation.
          </p>
        </div>

        <div class="card">
          <h3>11. What Happens When a Profile Runs?</h3>

          <ol>
            <li>The collector reads the enabled profile.</li>
            <li>It loads that profile's enabled sources.</li>
            <li>Each source listing is inspected for candidate links.</li>
            <li>Workload budgets limit how much work is attempted.</li>
            <li>Candidate article pages are fetched.</li>
            <li>The article is checked for profile relevance.</li>
            <li>Freshness and other validation rules are applied.</li>
            <li>Accepted articles continue into analysis.</li>
            <li>
              If this profile is included in your news feeds, its
              completed output is automatically included in scheduled
              runs.
            </li>
          </ol>

          <p>
            Source discovery and topic relevance are deliberately
            separate. Finding a link does not automatically mean the
            article is accepted.
          </p>
        </div>

        <div class="card">
          <h3>12. Production automation</h3>

          <p>
            UI-created web sources can enter production without
            manually editing YAML once they are validated and enabled.
          </p>

          <p>
            Generic multi-profile orchestration is active. Enabled
            profiles are automatically discovered and included in
            your news feeds.
          </p>

          <p>
            Creating a new profile does not require changes to n8n.
            Enable the profile when you want it included in scheduled
            runs.
          </p>
        </div>

        <p><a href="/">← Back to profiles</a></p>
    """)


# ============================================================
# EDIT PROFILE
# ============================================================

@app.get(
    "/profiles/{profile_id}/edit",
    response_class=HTMLResponse,
)
def edit_profile(profile_id: str):
    db = get_db()

    profile = db.execute(
        "SELECT * FROM profiles WHERE slug = ?",
        (profile_id,),
    ).fetchone()

    if profile is None:
        db.close()
        return HTMLResponse(
            "Profile not found",
            status_code=404,
        )

    keywords = [
        row["keyword"]
        for row in db.execute(
            """
            SELECT keyword
            FROM profile_keywords
            WHERE profile_id = ?
            ORDER BY rowid
            """,
            (profile["id"],),
        ).fetchall()
    ]

    db.close()

    return page(f"""
        <p>
          <a href="/profiles/{html.escape(profile_id)}">
            ← Profile
          </a>
        </p>

        <h2>
          Edit Profile: {html.escape(profile["name"])}
        </h2>

        <div class="card">
          <h3>How this profile works</h3>

          <p>
            Think of a profile as instructions telling News 4 Legends
            <strong>what to look for</strong>.
          </p>

          <p>
            <strong>Topic</strong> is the main subject.
            <strong>Keywords</strong> add optional supporting clues
            such as synonyms, jargon and alternative phrases.
          </p>

          <p>
            Topic and Keywords work together. Keywords
            <strong>enrich the Topic</strong>; they are not a list of
            words that every article must contain.
          </p>

          <p>
            <strong>Sources tell the system where to look.</strong>
            When this profile runs, News 4 Legends visits its enabled
            sources, discovers possible articles, filters obviously
            unrelated links, fetches promising articles and checks
            their actual content against this profile.
          </p>

          <p>
            Relevant and recent articles are kept. Unrelated, stale
            or unusable articles are discarded. The accepted material
            can then be processed into this profile's digest.
          </p>

          <p>
            If <strong>Include this profile in my news feeds</strong>
            is enabled, the finished profile digest is included in
            your news feeds.
          </p>
        </div>

        <form method="post"
              action="/profiles/{html.escape(profile_id)}/edit">

          <p>
            <label>
              <strong>Profile name</strong><br>
              <input name="name"
                     required
                     value="{html.escape(profile["name"], quote=True)}">
            </label>
          </p>

          <p>
            <strong>Slug:</strong>
            {html.escape(profile["slug"])}
            <br>
            <small>
              The profile slug is intentionally immutable.
            </small>
          </p>

          <p>
            <label>
              <strong>What should this profile be about?</strong><br>
              <input name="topic"
                     required
                     style="width:100%"
                     value="{html.escape(profile["topic"], quote=True)}">
            </label>
            <br>
            <small>
              <strong>This is the starting point.</strong>
              Tell News 4 Legends what you want it to look for.
              Use a clear subject such as <em>Cybersecurity</em>,
              <em>Formula 1</em> or <em>Artificial Intelligence</em>.
              The collector uses this as its main relevance signal
              when examining material discovered from your sources.
            </small>
          </p>

          <p>
            <label>
              <strong>Keywords (optional)</strong><br>
              <input name="keywords"
                     style="width:100%"
                     value="{html.escape(", ".join(keywords), quote=True)}">
            </label>
            <br>
            <small>
              <strong>Optional clues that enrich the Topic.</strong>
              Add alternative names, abbreviations, jargon or common
              phrases that may help the collector recognise relevant
              material. These apply across every source in the profile.
              They are not mandatory words: an article does not need
              to contain every keyword to be relevant.
            </small>
          </p>

          <p>
            <label>
              <strong>Stories in digest</strong><br>
              <input type="number"
                     name="llm_limit"
                     min="1"
                     max="10"
                     required
                     value="{profile["llm_limit"] or 3}">
            </label>
            <br>
            <small>
              Choose 1–10. The actual digest may contain fewer stories
              when fewer valid clusters are available or a lower
              configured LLM-call budget applies. Collection budgets
              do not increase automatically.
            </small>
          </p>

          <p>
            <label>
              <strong>How old can an article be?</strong><br>
              <input type="number"
                     name="maximum_age_hours"
                     min="1"
                     required
                     value="{profile["maximum_age_hours"]}">
            </label>
            <br>
            <small>
              Articles older than this are rejected as stale.
              Example: <strong>36</strong> means an article published
              more than 36 hours ago will not enter the digest.
              Increase this for slow-moving subjects; decrease it for
              fast-moving news.
            </small>
          </p>

          <div class="card">
            <h3>Email appearance</h3>

            <p>
              <label>
                <strong>Colour theme</strong><br>
                <select name="email_theme">
                  <option value="auto"
                    {"selected" if profile["email_theme"] == "auto" else ""}>
                    Auto
                  </option>
                  <option value="burgundy_gold"
                    {"selected" if profile["email_theme"] == "burgundy_gold" else ""}>
                    Burgundy &amp; Gold
                  </option>
                  <option value="navy_cyan"
                    {"selected" if profile["email_theme"] == "navy_cyan" else ""}>
                    Navy &amp; Cyan
                  </option>
                  <option value="emerald"
                    {"selected" if profile["email_theme"] == "emerald" else ""}>
                    Emerald
                  </option>
                  <option value="purple"
                    {"selected" if profile["email_theme"] == "purple" else ""}>
                    Purple
                  </option>
                  <option value="orange"
                    {"selected" if profile["email_theme"] == "orange" else ""}>
                    Orange
                  </option>
                  <option value="monochrome"
                    {"selected" if profile["email_theme"] == "monochrome" else ""}>
                    Monochrome
                  </option>
                </select>
              </label>
            </p>

            <small>
              Controls the colours used for this profile in email.
              <strong>Auto</strong> automatically chooses a built-in
              colour theme when News 4 Legends recognises the profile
              type. Known profiles such as Roma and Cybersecurity use
              their matching theme; other profiles use the neutral
              News 4 Legends theme. Choose a specific colour theme
              above whenever you want to override Auto.
            </small>
          </div>

          <p>
            <label>
              <input type="checkbox"
                     name="telegram_enabled"
                     {"checked" if profile["telegram_enabled"] else ""}>
              <strong>Include this profile in my news feeds</strong>
            </label>
            <br>
            <small>
              Turn this on if you want this profile's finished digest
              delivered to your news feeds.
              Sources do not need their own feed setting:
              every enabled source contributes to its parent profile,
              and the profile controls delivery.
            </small>
          </p>

          <button type="submit">
            Save profile
          </button>
        </form>
    """)


@app.post("/profiles/{profile_id}/edit")
def save_profile(
    profile_id: str,
    name: str = Form(...),
    topic: str = Form(...),
    keywords: str = Form(""),
    llm_limit: int = Form(3),
    maximum_age_hours: int = Form(...),
    email_theme: str = Form("auto"),
    telegram_enabled: str | None = Form(None),
):
    name = name.strip()
    topic = topic.strip()
    email_theme = email_theme.strip().lower()

    valid_email_themes = {
        "auto",
        "burgundy_gold",
        "navy_cyan",
        "emerald",
        "purple",
        "orange",
        "monochrome",
    }

    keyword_values = [
        value.strip()
        for value in keywords.split(",")
        if value.strip()
    ]

    if (
        not name
        or not topic
        or not 1 <= llm_limit <= 10
        or maximum_age_hours < 1
        or email_theme not in valid_email_themes
    ):
        return HTMLResponse(
            "Invalid profile",
            status_code=400,
        )

    db = get_db()

    profile = db.execute(
        "SELECT id FROM profiles WHERE slug = ?",
        (profile_id,),
    ).fetchone()

    if profile is None:
        db.close()
        return HTMLResponse(
            "Profile not found",
            status_code=404,
        )

    db.execute(
        """
        UPDATE profiles
        SET name = ?,
            topic = ?,
            llm_limit = ?,
            maximum_age_hours = ?,
            email_theme = ?,
            telegram_enabled = ?
        WHERE id = ?
        """,
        (
            name,
            topic,
            llm_limit,
            maximum_age_hours,
            email_theme,
            1 if telegram_enabled else 0,
            profile["id"],
        ),
    )

    db.execute(
        """
        DELETE FROM profile_keywords
        WHERE profile_id = ?
        """,
        (profile["id"],),
    )

    db.executemany(
        """
        INSERT INTO profile_keywords (
            profile_id,
            keyword
        )
        VALUES (?, ?)
        """,
        [
            (profile["id"], value)
            for value in keyword_values
        ],
    )

    db.commit()
    db.close()

    return RedirectResponse(
        url=f"/profiles/{profile_id}",
        status_code=303,
    )


# ============================================================
# ENABLE / DISABLE PROFILE
# ============================================================

@app.post("/profiles/{profile_id}/enable")
def enable_profile(profile_id: str):
    db = get_db()

    profile = db.execute(
        "SELECT id FROM profiles WHERE slug = ?",
        (profile_id,),
    ).fetchone()

    if profile is None:
        db.close()
        return HTMLResponse(
            "Profile not found",
            status_code=404,
        )

    eligible = db.execute(
        """
        SELECT COUNT(*)
        FROM profile_sources
        WHERE profile_id = ?
          AND enabled = 1
          AND collector_type = 'web'
          AND validation_status IN (
              'PASS',
              'WARNING'
          )
        """,
        (profile["id"],),
    ).fetchone()[0]

    if eligible < 1:
        db.close()
        return HTMLResponse(
            "Profile cannot be enabled: "
            "no enabled and validated web sources.",
            status_code=409,
        )

    db.execute(
        """
        UPDATE profiles
        SET enabled = 1
        WHERE id = ?
        """,
        (profile["id"],),
    )

    db.commit()
    db.close()

    return RedirectResponse(
        url=f"/profiles/{profile_id}",
        status_code=303,
    )


@app.post("/profiles/{profile_id}/disable")
def disable_profile(profile_id: str):
    db = get_db()

    cursor = db.execute(
        """
        UPDATE profiles
        SET enabled = 0
        WHERE slug = ?
        """,
        (profile_id,),
    )

    if cursor.rowcount != 1:
        db.close()
        return HTMLResponse(
            "Profile not found",
            status_code=404,
        )

    db.commit()
    db.close()

    return RedirectResponse(
        url=f"/profiles/{profile_id}",
        status_code=303,
    )


# ============================================================
# DELETE PROFILE
# ============================================================

@app.get(
    "/profiles/{profile_id}/delete",
    response_class=HTMLResponse,
)
def delete_profile_confirmation(
    profile_id: str,
):
    db = get_db()

    profile = db.execute(
        """
        SELECT
            p.id,
            p.name,
            p.slug,
            COUNT(ps.id) AS source_count
        FROM profiles p
        LEFT JOIN profile_sources ps
          ON ps.profile_id = p.id
        WHERE p.slug = ?
        GROUP BY p.id
        """,
        (profile_id,),
    ).fetchone()

    db.close()

    if profile is None:
        return HTMLResponse(
            "Profile not found",
            status_code=404,
        )

    return page(f"""
        <p>
          <a href="/profiles/{html.escape(profile_id)}">
            ← Profile
          </a>
        </p>

        <h2>
          Delete Profile:
          {html.escape(profile["name"])}
        </h2>

        <div class="guidance fail">
          <strong>This is destructive.</strong>

          <p>
            This profile has
            {profile["source_count"]}
            source relationship(s).
          </p>

          <p>
            Profile keywords, entities and profile/source
            relationships will be deleted.
          </p>

          <p>
            Shared global source records are not automatically
            deleted by profile deletion.
          </p>
        </div>

        <form method="post"
              action="/profiles/{html.escape(profile_id)}/delete">

          <p>
            Type
            <strong>{html.escape(profile["slug"])}</strong>
            to confirm:
          </p>

          <input name="confirmation"
                 required
                 autocomplete="off">

          <button type="submit">
            Permanently delete profile
          </button>
        </form>
    """)


@app.post("/profiles/{profile_id}/delete")
def delete_profile(
    profile_id: str,
    confirmation: str = Form(...),
):
    if confirmation.strip() != profile_id:
        return HTMLResponse(
            "Confirmation did not match profile slug.",
            status_code=400,
        )

    db = get_db()

    cursor = db.execute(
        """
        DELETE FROM profiles
        WHERE slug = ?
        """,
        (profile_id,),
    )

    if cursor.rowcount != 1:
        db.close()
        return HTMLResponse(
            "Profile not found",
            status_code=404,
        )

    db.commit()
    db.close()

    return RedirectResponse(
        url="/",
        status_code=303,
    )


# ============================================================
# DELETE SOURCE FROM PROFILE
# ============================================================

@app.get(
    "/profiles/{profile_id}/sources/{profile_source_id}/delete",
    response_class=HTMLResponse,
)
def delete_source_confirmation(
    profile_id: str,
    profile_source_id: int,
):
    db = get_db()

    source = db.execute(
        """
        SELECT
            ps.id,
            s.name,
            ps.enabled,
            ps.validation_status
        FROM profile_sources ps
        JOIN profiles p
          ON p.id = ps.profile_id
        JOIN sources s
          ON s.id = ps.source_id
        WHERE p.slug = ?
          AND ps.id = ?
        """,
        (
            profile_id,
            profile_source_id,
        ),
    ).fetchone()

    db.close()

    if source is None:
        return HTMLResponse(
            "Source not found",
            status_code=404,
        )

    return page(f"""
        <p>
          <a href="/profiles/{html.escape(profile_id)}">
            ← Profile
          </a>
        </p>

        <h2>
          Delete Source:
          {html.escape(source["name"])}
        </h2>

        <div class="guidance fail">
          <strong>This is destructive.</strong>

          <p>
            This removes the source from this profile,
            including its validation state and
            profile-specific workload settings.
          </p>

          <p>
            If another profile uses the same source,
            that relationship will not be touched.
          </p>
        </div>

        <form method="post"
              action="/profiles/{html.escape(profile_id)}/sources/{profile_source_id}/delete">

          <p>
            Type
            <strong>{html.escape(source["name"])}</strong>
            to confirm:
          </p>

          <input name="confirmation"
                 required
                 autocomplete="off">

          <button type="submit">
            Permanently delete source from profile
          </button>
        </form>
    """)


@app.post(
    "/profiles/{profile_id}/sources/{profile_source_id}/delete"
)
def delete_source(
    profile_id: str,
    profile_source_id: int,
    confirmation: str = Form(...),
):
    db = get_db()

    source = db.execute(
        """
        SELECT
            ps.id,
            ps.source_id,
            s.name
        FROM profile_sources ps
        JOIN profiles p
          ON p.id = ps.profile_id
        JOIN sources s
          ON s.id = ps.source_id
        WHERE p.slug = ?
          AND ps.id = ?
        """,
        (
            profile_id,
            profile_source_id,
        ),
    ).fetchone()

    if source is None:
        db.close()
        return HTMLResponse(
            "Source not found",
            status_code=404,
        )

    if confirmation.strip() != source["name"]:
        db.close()
        return HTMLResponse(
            "Confirmation did not match source name.",
            status_code=400,
        )

    source_id = source["source_id"]

    db.execute(
        """
        DELETE FROM profile_sources
        WHERE id = ?
        """,
        (profile_source_id,),
    )

    remaining = db.execute(
        """
        SELECT COUNT(*)
        FROM profile_sources
        WHERE source_id = ?
        """,
        (source_id,),
    ).fetchone()[0]

    if remaining == 0:
        db.execute(
            """
            DELETE FROM sources
            WHERE id = ?
            """,
            (source_id,),
        )

    db.commit()
    db.close()

    return RedirectResponse(
        url=f"/profiles/{profile_id}",
        status_code=303,
    )


@app.post("/profiles/{profile_id}/telegram")
def set_profile_telegram(
    profile_id: str,
    telegram_enabled: str | None = Form(None),
):
    db = get_db()

    profile = db.execute(
        "SELECT id FROM profiles WHERE slug = ?",
        (profile_id,),
    ).fetchone()

    if profile is None:
        db.close()
        return HTMLResponse(
            "Profile not found",
            status_code=404,
        )

    db.execute(
        """
        UPDATE profiles
        SET telegram_enabled = ?
        WHERE id = ?
        """,
        (
            1 if telegram_enabled else 0,
            profile["id"],
        ),
    )

    db.commit()
    db.close()

    return RedirectResponse(
        url="/",
        status_code=303,
    )


@app.get("/new-profile", response_class=HTMLResponse)
def new_profile():
    return page("""
        <p><a href="/">← Profiles</a></p>
        <h2>Add Profile</h2>

        <div class="card">
          <h3>What are you creating?</h3>

          <p>
            A profile tells News 4 Legends
            <strong>what you want to follow</strong>.
            After creating it, you add Sources that tell the system
            <strong>where to look</strong>.
          </p>

          <p>
            <strong>Topic</strong> is the main subject.
            <strong>Keywords</strong> optionally enrich it with
            synonyms, jargon and related phrases.
          </p>

          <p>
            When the profile runs, News 4 Legends visits its enabled
            sources, discovers possible articles, fetches promising
            material and checks whether it matches the profile.
            Relevant and recent articles continue into the digest;
            unrelated or stale material is discarded.
          </p>

          <p>
            You do not need to predict every possible keyword.
            Start with a clear Topic and add Keywords when they
            genuinely help describe what you want.
          </p>
        </div>

        <form method="post" action="/new-profile">
          <p>
            <label>
              <strong>Profile name</strong><br>
              <input name="name" required placeholder="Cybersecurity">
            </label>
          </p>

          <p>
            <label>
              Slug<br>
              <input name="slug" required
                     pattern="[a-z0-9_-]+"
                     placeholder="cybersecurity">
            </label>
          </p>

          <p>
            <label>
              <strong>What should this profile be about?</strong><br>
              <input name="topic" required
                     placeholder="Cybersecurity">
            </label>
            <br>
            <small>
              <strong>Required.</strong>
              This is the main definition of what you want to follow.
              The collector always uses it for relevance.
              You can use commas for closely related terms.
            </small>
          </p>

          <p>
            <label>
              <strong>Keywords (optional)</strong><br>
              <input name="keywords"
                     style="width:100%"
                     placeholder="Optional: ransomware, vulnerability, zero-day">
            </label>
            <br>
            <small>
              <strong>Optional.</strong>
              Add synonyms, abbreviations, jargon or phrases that may
              help identify relevant stories. Separate them with
              commas. Leave this blank if Topic already describes
              what you want. You can tune this later.
            </small>
          </p>

          <p>
            <label>
              <strong>Stories in digest</strong><br>
              <input type="number"
                     name="llm_limit"
                     min="1"
                     max="10"
                     required
                     value="3">
            </label>
            <br>
            <small>
              Choose 1–10. This controls the requested output size,
              not the collection workload. Fewer stories may be
              produced when fewer valid clusters are available.
            </small>
          </p>

          <p>
            <label>
              <input type="checkbox"
                     name="telegram_enabled">
              <strong>Include this profile in my news feeds</strong>
            </label>
            <br>
            <small>
              Turn this on if you want this profile's finished digest
              delivered to your news feeds. You configure
              this once for the profile, not separately for every
              source you add later.
            </small>
          </p>

          <button type="submit">Create disabled profile</button>
        </form>

        <p>
          <em>
            New profiles remain disabled until their sources
            have been configured and validated.
          </em>
        </p>
    """)


@app.post("/new-profile")
def create_profile(
    name: str = Form(...),
    slug: str = Form(...),
    topic: str = Form(...),
    keywords: str = Form(""),
    llm_limit: int = Form(3),
    telegram_enabled: str | None = Form(None),
):
    name = name.strip()
    slug = slug.strip().lower()
    topic = topic.strip()

    keyword_values = [
        value.strip()
        for value in keywords.split(",")
        if value.strip()
    ]

    if (
        not name
        or not slug
        or not topic
        or not 1 <= llm_limit <= 10
    ):
        return HTMLResponse(
            "Invalid profile",
            status_code=400,
        )

    if not all(
        c.islower() or c.isdigit() or c in "_-"
        for c in slug
    ):
        return HTMLResponse("Invalid slug", status_code=400)

    db = get_db()

    try:
        db.execute("""
            INSERT INTO profiles (
                slug,
                name,
                enabled,
                topic,
                minimum_source_score,
                maximum_age_hours,
                similarity_threshold,
                llm_enabled,
                llm_limit,
                telegram_enabled
            )
            VALUES (?, ?, 0, ?, 60, 36, 0.5, 1, ?, ?)
        """, (
            slug,
            name,
            topic,
            llm_limit,
            1 if telegram_enabled else 0,
        ))
        profile_row = db.execute(
            "SELECT id FROM profiles WHERE slug = ?",
            (slug,),
        ).fetchone()

        profile_db_id = profile_row["id"]

        db.executemany(
            """
            INSERT INTO profile_keywords (
                profile_id,
                keyword
            )
            VALUES (?, ?)
            """,
            [
                (profile_db_id, value)
                for value in keyword_values
            ],
        )

        db.commit()

    except sqlite3.IntegrityError:
        db.close()
        return HTMLResponse(
            "Profile already exists",
            status_code=409,
        )

    db.close()

    return RedirectResponse(
        url=f"/profiles/{slug}",
        status_code=303,
    )

@app.post(
    "/profiles/{profile_id}/sources/{profile_source_id}/validate",
    response_class=HTMLResponse,
)
def validate_source(
    profile_id: str,
    profile_source_id: int,
):
    db = get_db()

    source = db.execute("""
        SELECT
            s.name,
            ps.listing_url,
            ps.max_candidates,
            ps.max_fetches,
            ps.request_timeout_seconds,
            ps.max_source_runtime_seconds
        FROM profile_sources ps
        JOIN profiles p
            ON p.id = ps.profile_id
        JOIN sources s
            ON s.id = ps.source_id
        WHERE p.slug = ?
          AND ps.id = ?
    """, (
        profile_id,
        profile_source_id,
    )).fetchone()

    db.close()

    if source is None:
        return HTMLResponse(
            "Source not found",
            status_code=404,
        )

    payload = json.dumps({
        "listing_url": source["listing_url"],
    }).encode("utf-8")

    request = urllib.request.Request(
        "http://news4legends-worker:8080/preflight",
        data=payload,
        headers={
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=30,
        ) as response:
            result = json.loads(
                response.read().decode("utf-8")
            )
    except Exception as exc:
        return page(f"""
            <p>
              <a href="/profiles/{html.escape(profile_id)}">
                ← Profile
              </a>
            </p>
            <h2>Validation failed</h2>
            <p>{html.escape(str(exc))}</p>
        """)

    status = result.get("status", "UNKNOWN")
    reason = result.get("reason", "")
    failures = result.get("failures", [])

    db = get_db()
    db.execute("""
        UPDATE profile_sources
        SET validation_status = ?,
            validation_reason = ?,
            validated_at = CURRENT_TIMESTAMP
        WHERE id = ?
          AND profile_id = (
              SELECT id
              FROM profiles
              WHERE slug = ?
          )
    """, (
        status,
        reason,
        profile_source_id,
        profile_id,
    ))
    db.commit()
    db.close()

    if status == "WARNING":
        if reason == "candidate discovery reached pre-flight limit":
            guidance_html = """
              <div class="guidance warning">
                <h3>So what?</h3>
                <p>
                  The source is working, but it exposes a large number
                  of candidate links. In production this can consume
                  more collection time and request budget than a more
                  focused source.
                </p>
                <h3>Recommended action</h3>
                <p>
                  The source can be enabled. Start with conservative
                  candidate, fetch and runtime limits. If possible,
                  prefer a more focused news or topic listing URL.
                </p>
              </div>
            """
        elif reason == "partial sample extraction success":
            guidance_html = """
              <div class="guidance warning">
                <h3>So what?</h3>
                <p>
                  News 4 Legends can use this source, but some sampled
                  articles could not be fetched or extracted. This
                  means relevant stories may occasionally be missed
                  or have insufficient content for a good summary.
                </p>
                <h3>Recommended action</h3>
                <p>
                  Review the individual failures below. Enable the
                  source if occasional losses are acceptable. If the
                  failures are frequent or systematic, leave it
                  disabled and investigate the source first.
                </p>
              </div>
            """
        else:
            guidance_html = """
              <div class="guidance warning">
                <h3>So what?</h3>
                <p>
                  Validation found a non-fatal issue. The source may
                  work, but collection reliability or efficiency may
                  be reduced.
                </p>
                <h3>Recommended action</h3>
                <p>
                  Review the validation measurements and failures
                  below before deciding whether to enable the source.
                </p>
              </div>
            """
    elif status == "PASS":
        guidance_html = """
          <div class="guidance pass">
            <h3>So what?</h3>
            <p>
              News 4 Legends reached the listing page, discovered
              candidate articles, and successfully fetched and
              extracted the bounded sample.
            </p>
            <h3>Recommended action</h3>
            <p>
              The source is suitable for enabling with its configured
              production workload limits.
            </p>
          </div>
        """
    elif status == "FAIL":
        if reason == "listing request failed":
            guidance_html = """
              <div class="guidance fail">
                <h3>So what?</h3>
                <p>
                  News 4 Legends cannot currently reach the source.
                  If enabled, it will contribute no articles and may
                  waste collection time waiting for failed requests.
                </p>
                <h3>Recommended action</h3>
                <p>
                  Leave it disabled. Verify the listing URL and check
                  whether the site is redirecting, unavailable, or
                  blocking automated requests. Then validate again.
                </p>
              </div>
            """
        elif reason == "no candidate article links discovered":
            guidance_html = """
              <div class="guidance fail">
                <h3>So what?</h3>
                <p>
                  The page is reachable, but News 4 Legends cannot
                  discover usable article links from it. Enabling the
                  source would therefore contribute no stories.
                </p>
                <h3>Recommended action</h3>
                <p>
                  Leave it disabled. Confirm the URL is a news or
                  article-listing page rather than a generic homepage,
                  login page or other non-listing page. A more focused
                  section or feed URL may work better.
                </p>
              </div>
            """
        elif reason == "sample article extraction failed":
            guidance_html = """
              <div class="guidance fail">
                <h3>So what?</h3>
                <p>
                  Article links were found, but News 4 Legends could
                  not extract usable article content from the sample.
                  Without article text, reliable summaries cannot be
                  produced from this source.
                </p>
                <h3>Recommended action</h3>
                <p>
                  Leave it disabled. Review the failures below. The
                  site may require different extraction handling or a
                  better listing/feed URL before it can be used.
                </p>
              </div>
            """
        else:
            guidance_html = """
              <div class="guidance fail">
                <h3>So what?</h3>
                <p>
                  Validation could not demonstrate that News 4 Legends
                  can collect usable stories from this source
                  reliably.
                </p>
                <h3>Recommended action</h3>
                <p>
                  Leave it disabled. Review the reason, measurements
                  and failures below, correct the problem, and
                  validate again.
                </p>
              </div>
            """
    else:
        guidance_html = """
          <div class="guidance fail">
            <h3>So what?</h3>
            <p>
              The validator returned an unrecognised result, so source
              safety and usability have not been established.
            </p>
            <h3>Recommended action</h3>
            <p>
              Leave the source disabled and investigate the validation
              result before using it.
            </p>
          </div>
        """

    failure_html = ""

    if failures:
        failure_html = (
            "<h3>Failures</h3><ul>"
            + "".join(
                "<li>"
                + html.escape(
                    f"{item.get('url', '')}: "
                    f"{item.get('reason', '')}"
                )
                + "</li>"
                for item in failures
            )
            + "</ul>"
        )

    return page(f"""
        <p>
          <a href="/profiles/{html.escape(profile_id)}">
            ← Profile
          </a>
        </p>

        <h2>
          Validate: {html.escape(source["name"])}
        </h2>

        <p>
          <strong>URL being validated:</strong><br>
          <a href="{html.escape(source["listing_url"], quote=True)}"
             target="_blank"
             rel="noopener noreferrer">
            {html.escape(source["listing_url"])}
          </a>
        </p>

        <div class="card">
          <h2>
            {html.escape(status)}
            <a class="info" href="#help-status">ⓘ</a>
          </h2>
          <p>{html.escape(reason)}</p>

          {guidance_html}

          <table>
            <tr>
              <th>Candidates discovered <a class="info" href="#help-candidates">ⓘ</a></th>
              <td>{result.get("candidates", 0)}</td>
            </tr>
            <tr>
              <th>Candidate limit reached <a class="info" href="#help-limit">ⓘ</a></th>
              <td>{result.get("candidate_limit_reached", False)}</td>
            </tr>
            <tr>
              <th>Sample requested <a class="info" href="#help-sample">ⓘ</a></th>
              <td>{result.get("sample_requested", 0)}</td>
            </tr>
            <tr>
              <th>Sample fetched <a class="info" href="#help-fetched">ⓘ</a></th>
              <td>{result.get("sample_fetched", 0)}</td>
            </tr>
            <tr>
              <th>Sample extracted <a class="info" href="#help-extracted">ⓘ</a></th>
              <td>{result.get("sample_extracted", 0)}</td>
            </tr>
            <tr>
              <th>Listing time</th>
              <td>{result.get("listing_seconds", "-")}s</td>
            </tr>
            <tr>
              <th>Total validation time</th>
              <td>{result.get("total_seconds", "-")}s</td>
            </tr>
            <tr>
              <th>Preflight candidate limit <a class="info" href="#help-preflight-budget">ⓘ</a></th>
              <td>{result.get("limits", {}).get("max_candidates", "-")}</td>
            </tr>
            <tr>
              <th>Preflight sample fetches</th>
              <td>{result.get("limits", {}).get("sample_fetches", "-")}</td>
            </tr>
            <tr>
              <th>Preflight request timeout <a class="info" href="#help-timeout">ⓘ</a></th>
              <td>{result.get("limits", {}).get("request_timeout_seconds", "-")}s</td>
            </tr>
            <tr>
              <th>Production candidate override <a class="info" href="#help-prod-candidate">ⓘ</a></th>
              <td>{source["max_candidates"] if source["max_candidates"] is not None else "YAML default"}</td>
            </tr>
            <tr>
              <th>Production fetch override <a class="info" href="#help-fetch-budget">ⓘ</a></th>
              <td>{source["max_fetches"] if source["max_fetches"] is not None else "Unlimited / collector default"}</td>
            </tr>
            <tr>
              <th>Production request-timeout override</th>
              <td>{str(source["request_timeout_seconds"]) + "s" if source["request_timeout_seconds"] is not None else "YAML default"}</td>
            </tr>
            <tr>
              <th>Production source-runtime override <a class="info" href="#help-runtime">ⓘ</a></th>
              <td>{str(source["max_source_runtime_seconds"]) + "s" if source["max_source_runtime_seconds"] is not None else "Unlimited"}</td>
            </tr>
          </table>

          {failure_html}
        </div>

        <p>
          Validation does not automatically enable the source.
        </p>

        <div id="help-status" class="info-box">
          <a class="info-close" href="#">×</a>
          <h3>Validation status</h3>
          <p><strong>PASS:</strong> sampled collection worked normally.</p>
          <p><strong>WARNING:</strong> the source works, but something
          deserves attention before or after enabling it.</p>
          <p><strong>FAIL:</strong> the source should remain disabled
          until the problem is corrected.</p>
        </div>

        <div id="help-candidates" class="info-box">
          <a class="info-close" href="#">×</a>
          <h3>Candidates discovered</h3>
          <p>
            Article links found on the source listing page. They are
            possible articles, not necessarily articles that will be
            accepted.
          </p>
        </div>

        <div id="help-limit" class="info-box">
          <a class="info-close" href="#">×</a>
          <h3>Candidate limit reached</h3>
          <p>
            Yes means discovery reached its safety ceiling. There may
            have been more links, but validation deliberately stopped
            counting them to keep the test bounded.
          </p>
        </div>

        <div id="help-sample" class="info-box">
          <a class="info-close" href="#">×</a>
          <h3>Sample requested</h3>
          <p>
            The small number of candidate articles selected for the
            validation test. Preflight intentionally does not download
            every discovered article.
          </p>
        </div>

        <div id="help-fetched" class="info-box">
          <a class="info-close" href="#">×</a>
          <h3>Sample fetched</h3>
          <p>
            How many sampled article pages were successfully downloaded.
            A lower number than requested indicates request failures or
            timeouts.
          </p>
        </div>

        <div id="help-extracted" class="info-box">
          <a class="info-close" href="#">×</a>
          <h3>Sample extracted</h3>
          <p>
            How many downloaded pages produced usable article content.
            For example, 3/3 means all three sampled pages could be
            extracted.
          </p>
        </div>

        <div id="help-preflight-budget" class="info-box">
          <a class="info-close" href="#">×</a>
          <h3>Preflight candidate limit</h3>
          <p>
            The maximum number of links validation will inspect during
            discovery. This protects the lab from unexpectedly broad
            listing pages.
          </p>
        </div>

        <div id="help-timeout" class="info-box">
          <a class="info-close" href="#">×</a>
          <h3>Request timeout</h3>
          <p>
            Maximum time allowed for an individual web request before
            it is treated as failed. It prevents a slow or broken site
            from waiting indefinitely.
          </p>
        </div>

        <div id="help-prod-candidate" class="info-box">
          <a class="info-close" href="#">×</a>
          <h3>Production candidate budget</h3>
          <p>
            Maximum candidate links the production collector may
            consider for this source during a run. Lower values reduce
            workload; higher values search more links.
          </p>
        </div>

        <div id="help-fetch-budget" class="info-box">
          <a class="info-close" href="#">×</a>
          <h3>Production fetch budget</h3>
          <p>
            Maximum article pages the collector may actually download
            from this source during a run. This is stronger protection
            than candidate discovery because page fetching costs more
            time and resources.
          </p>
        </div>

        <div id="help-runtime" class="info-box">
          <a class="info-close" href="#">×</a>
          <h3>Source runtime budget</h3>
          <p>
            How long one source is allowed to consume collection time.
            When the budget has been consumed, the collector stops
            starting further candidate requests for that source.
          </p>
        </div>
    """)



@app.post("/profiles/{profile_id}/sources/{profile_source_id}/enable")
def enable_source(profile_id: str, profile_source_id: int):
    db = get_db()

    source = db.execute("""
        SELECT
            ps.id,
            ps.validation_status
        FROM profile_sources ps
        JOIN profiles p
            ON p.id = ps.profile_id
        WHERE p.slug = ?
          AND ps.id = ?
    """, (
        profile_id,
        profile_source_id,
    )).fetchone()

    if source is None:
        db.close()
        return HTMLResponse("Source not found", status_code=404)

    if source["validation_status"] not in ("PASS", "WARNING"):
        db.close()
        return HTMLResponse(
            "Source must pass validation or have a reviewed warning before enabling.",
            status_code=409,
        )

    db.execute(
        "UPDATE profile_sources SET enabled = 1 WHERE id = ?",
        (profile_source_id,),
    )
    db.commit()
    db.close()

    return RedirectResponse(
        url=f"/profiles/{profile_id}",
        status_code=303,
    )


@app.post("/profiles/{profile_id}/sources/{profile_source_id}/disable")
def disable_source(profile_id: str, profile_source_id: int):
    db = get_db()

    cursor = db.execute("""
        UPDATE profile_sources
        SET enabled = 0
        WHERE id = ?
          AND profile_id = (
              SELECT id
              FROM profiles
              WHERE slug = ?
          )
    """, (
        profile_source_id,
        profile_id,
    ))

    db.commit()
    changed = cursor.rowcount
    db.close()

    if changed != 1:
        return HTMLResponse("Source not found", status_code=404)

    return RedirectResponse(
        url=f"/profiles/{profile_id}",
        status_code=303,
    )


@app.get(
    "/profiles/{profile_id}/sources/{profile_source_id}/edit",
    response_class=HTMLResponse,
)
def edit_source(
    profile_id: str,
    profile_source_id: int,
):
    db = get_db()

    source = db.execute("""
        SELECT
            ps.id,
            s.name,
            ps.collector_type,
            ps.listing_url,
            ps.topic_focused,
            ps.credibility_score,
            ps.max_candidates,
            ps.max_fetches,
            ps.request_timeout_seconds,
            ps.max_source_runtime_seconds,
            ps.stop_after_consecutive_stale,
            ps.validation_status
        FROM profile_sources ps
        JOIN profiles p
          ON p.id = ps.profile_id
        JOIN sources s
          ON s.id = ps.source_id
        WHERE p.slug = ?
          AND ps.id = ?
    """, (
        profile_id,
        profile_source_id,
    )).fetchone()

    db.close()

    if source is None:
        return HTMLResponse("Source not found", status_code=404)

    checked = "checked" if source["topic_focused"] else ""
    stale = (
        source["stop_after_consecutive_stale"]
        if source["stop_after_consecutive_stale"] is not None
        else ""
    )
    max_candidates_value = (
        source["max_candidates"]
        if source["max_candidates"] is not None
        else 40
    )
    max_fetches_value = (
        source["max_fetches"]
        if source["max_fetches"] is not None
        else 40
    )
    request_timeout_value = (
        source["request_timeout_seconds"]
        if source["request_timeout_seconds"] is not None
        else 15
    )
    max_source_runtime_value = (
        source["max_source_runtime_seconds"]
        if source["max_source_runtime_seconds"] is not None
        else 60
    )

    collector_options = "".join(
        f'<option value="{value}"'
        + (" selected" if source["collector_type"] == value else "")
        + f'>{value}</option>'
        for value in ("web", "freshrss", "social")
    )

    return page(f"""
        <p>
          <a href="/profiles/{html.escape(profile_id)}">
            ← Profile
          </a>
        </p>

        <h2>Edit Source: {html.escape(source["name"])}</h2>

        <form method="post"
              action="/profiles/{html.escape(profile_id)}/sources/{profile_source_id}/edit">

          <p><label>
            Name<br>
            <input value="{html.escape(source["name"], quote=True)}"
                   disabled>
          </label></p>

          <p><label>
            Collector<br>
            <select name="collector_type">
              {collector_options}
            </select>
          </label></p>

          <p><label>
            Listing URL<br>
            <input name="listing_url"
                   type="url"
                   required
                   size="70"
                   value="{html.escape(source["listing_url"], quote=True)}">
          </label></p>

          <p><label>
            <input name="topic_focused"
                   type="checkbox"
                   value="1"
                   {checked}>
            Topic focused
          </label></p>

          <p><label>
            Credibility score<br>
            <input name="credibility_score"
                   type="number"
                   min="0"
                   max="100"
                   required
                   value="{source["credibility_score"]}">
          </label></p>

          <p><label>
            Candidate discovery budget<br>
            <input name="max_candidates"
                   type="number"
                   min="1"
                   required
                   value="{max_candidates_value}">
          </label></p>

          <p><label>
            Fetch budget<br>
            <input name="max_fetches"
                   type="number"
                   min="1"
                   required
                   value="{max_fetches_value}">
          </label></p>

          <p><label>
            Request timeout (seconds)<br>
            <input name="request_timeout_seconds"
                   type="number"
                   min="1"
                   step="0.1"
                   required
                   value="{request_timeout_value}">
          </label></p>

          <p><label>
            Maximum source runtime (seconds)<br>
            <input name="max_source_runtime_seconds"
                   type="number"
                   min="1"
                   step="0.1"
                   required
                   value="{max_source_runtime_value}">
          </label></p>

          <p><label>
            Stop after consecutive stale articles<br>
            <input name="stop_after_consecutive_stale"
                   type="number"
                   min="1"
                   value="{stale}"
                   placeholder="Unlimited">
          </label></p>

          <button type="submit">Save changes</button>
        </form>

        <div class="guidance warning">
          <h3>Validation safety</h3>
          <p>
            Changing the listing URL or collector type changes how
            News 4 Legends reaches this source. If either changes,
            the source will be disabled and its previous validation
            cleared until you validate it again.
          </p>
          <p>
            Changing weighting or workload budgets does not discard
            an otherwise valid source validation.
          </p>
        </div>
    """)


@app.post(
    "/profiles/{profile_id}/sources/{profile_source_id}/edit"
)
def update_source(
    profile_id: str,
    profile_source_id: int,
    collector_type: str = Form(...),
    listing_url: str = Form(...),
    topic_focused: str | None = Form(None),
    credibility_score: int = Form(...),
    max_candidates: int = Form(...),
    max_fetches: int = Form(...),
    request_timeout_seconds: float = Form(...),
    max_source_runtime_seconds: float = Form(...),
    stop_after_consecutive_stale: int | None = Form(None),
):
    listing_url = listing_url.strip()

    if (
        not listing_url
        or collector_type not in {"web", "freshrss", "social"}
        or not 0 <= credibility_score <= 100
        or max_candidates < 1
        or max_fetches < 1
        or request_timeout_seconds <= 0
        or max_source_runtime_seconds <= 0
        or (
            stop_after_consecutive_stale is not None
            and stop_after_consecutive_stale < 1
        )
    ):
        return HTMLResponse("Invalid source", status_code=400)

    db = get_db()

    source = db.execute("""
        SELECT
            ps.id,
            ps.collector_type,
            ps.listing_url
        FROM profile_sources ps
        JOIN profiles p
          ON p.id = ps.profile_id
        WHERE p.slug = ?
          AND ps.id = ?
    """, (
        profile_id,
        profile_source_id,
    )).fetchone()

    if source is None:
        db.close()
        return HTMLResponse("Source not found", status_code=404)

    validation_stale = (
        source["collector_type"] != collector_type
        or source["listing_url"] != listing_url
    )

    if validation_stale:
        db.execute("""
            UPDATE profile_sources
            SET collector_type = ?,
                listing_url = ?,
                topic_focused = ?,
                credibility_score = ?,
                max_candidates = ?,
                max_fetches = ?,
                request_timeout_seconds = ?,
                max_source_runtime_seconds = ?,
                stop_after_consecutive_stale = ?,
                enabled = 0,
                validation_status = NULL,
                validation_reason = NULL,
                validated_at = NULL
            WHERE id = ?
        """, (
            collector_type,
            listing_url,
            1 if topic_focused else 0,
            credibility_score,
            max_candidates,
            max_fetches,
            request_timeout_seconds,
            max_source_runtime_seconds,
            stop_after_consecutive_stale,
            profile_source_id,
        ))
    else:
        db.execute("""
            UPDATE profile_sources
            SET topic_focused = ?,
                credibility_score = ?,
                max_candidates = ?,
                max_fetches = ?,
                request_timeout_seconds = ?,
                max_source_runtime_seconds = ?,
                stop_after_consecutive_stale = ?
            WHERE id = ?
        """, (
            1 if topic_focused else 0,
            credibility_score,
            max_candidates,
            max_fetches,
            request_timeout_seconds,
            max_source_runtime_seconds,
            stop_after_consecutive_stale,
            profile_source_id,
        ))

    db.commit()
    db.close()

    return RedirectResponse(
        url=f"/profiles/{profile_id}",
        status_code=303,
    )


@app.get("/profiles/{profile_id}/new-source", response_class=HTMLResponse)
def new_source(profile_id: str):
    db = get_db()
    profile = db.execute(
        "SELECT slug, name FROM profiles WHERE slug = ?",
        (profile_id,),
    ).fetchone()
    db.close()

    if profile is None:
        return HTMLResponse("Profile not found", status_code=404)

    return page(f"""
        <p><a href="/profiles/{html.escape(profile_id)}">← Profile</a></p>
        <h2>Add Source to {html.escape(profile["name"])}</h2>

        <form method="post"
              action="/profiles/{html.escape(profile_id)}/new-source">

          <p><label>
            Name<br>
            <input name="name" required>
          </label></p>

          <p><label>
            Collector<br>
            <select name="collector_type">
              <option value="web">web</option>
              <option value="freshrss">freshrss</option>
              <option value="social">social</option>
            </select>
          </label></p>

          <p><label>
            Listing URL<br>
            <input name="listing_url" type="url" required size="70">
          </label></p>

          <p><label>
            <input name="topic_focused" type="checkbox" value="1">
            Topic focused <a class="info" href="#help-topic-focused">ⓘ</a>
          </label></p>

          <p><label>
            Credibility score <a class="info" href="#help-credibility">ⓘ</a><br>
            <input name="credibility_score"
                   type="number" min="0" max="100" value="50" required>
          </label></p>

          <p><label>
            Candidate discovery budget <a class="info" href="#help-form-candidates">ⓘ</a><br>
            <input name="max_candidates"
                   type="number" min="1" value="40" required>
          </label></p>

          <p><label>
            Fetch budget <a class="info" href="#help-form-fetch">ⓘ</a><br>
            <input name="max_fetches"
                   type="number" min="1" value="40" required>
          </label></p>

          <p><label>
            Request timeout (seconds) <a class="info" href="#help-form-timeout">ⓘ</a><br>
            <input name="request_timeout_seconds"
                   type="number" min="1" step="0.1" value="15" required>
          </label></p>

          <p><label>
            Maximum source runtime (seconds) <a class="info" href="#help-form-runtime">ⓘ</a><br>
            <input name="max_source_runtime_seconds"
                   type="number" min="1" step="0.1" value="60" required>
          </label></p>

          <p><label>
            Stop after consecutive stale articles <a class="info" href="#help-stale">ⓘ</a><br>
            <input name="stop_after_consecutive_stale"
                   type="number" min="1"
                   placeholder="Unlimited">
          </label></p>

          <button type="submit">Save disabled source</button>
        </form>

        <p><em>Source will not run until validated and enabled.</em></p>

        <div id="help-topic-focused" class="info-box">
          <a class="info-close" href="#">×</a>
          <h3>Topic focused</h3>
          <p>
            Use this when the source is primarily dedicated to this
            profile's subject rather than covering many unrelated topics.
          </p>
        </div>

        <div id="help-credibility" class="info-box">
          <a class="info-close" href="#">×</a>
          <h3>Credibility score</h3>
          <p>
            Your profile-specific weighting for this source. It affects
            how the profile treats information from the source; it is
            not an objective or global rating of the publisher.
          </p>
        </div>

        <div id="help-form-candidates" class="info-box">
          <a class="info-close" href="#">×</a>
          <h3>Candidate discovery budget</h3>
          <p>
            Maximum article links this source may consider in one
            collection run. Lower values reduce workload.
          </p>
        </div>

        <div id="help-form-fetch" class="info-box">
          <a class="info-close" href="#">×</a>
          <h3>Fetch budget</h3>
          <p>
            Maximum article pages this source may download in one run.
            Use this to prevent a broad source from consuming excessive
            network, CPU and collection time.
          </p>
        </div>

        <div id="help-form-timeout" class="info-box">
          <a class="info-close" href="#">×</a>
          <h3>Request timeout</h3>
          <p>
            Maximum time for one web request. A request that takes
            longer is abandoned rather than allowed to hang collection.
          </p>
        </div>

        <div id="help-form-runtime" class="info-box">
          <a class="info-close" href="#">×</a>
          <h3>Maximum source runtime</h3>
          <p>
            Overall time budget for this source. Once consumed, the
            collector stops starting further candidate requests for it.
          </p>
        </div>

        <div id="help-stale" class="info-box">
          <a class="info-close" href="#">×</a>
          <h3>Stop after consecutive stale articles</h3>
          <p>
            If this many articles in a row are older than the profile's
            freshness window, stop checking further links from this
            source. Leave blank for no stale-article early stop.
          </p>
        </div>
    """)


@app.post("/profiles/{profile_id}/new-source")
def create_source(
    profile_id: str,
    name: str = Form(...),
    collector_type: str = Form(...),
    listing_url: str = Form(...),
    topic_focused: str | None = Form(None),
    credibility_score: int = Form(...),
    max_candidates: int = Form(...),
    max_fetches: int = Form(...),
    request_timeout_seconds: float = Form(...),
    max_source_runtime_seconds: float = Form(...),
    stop_after_consecutive_stale: int | None = Form(None),
):
    name = name.strip()
    listing_url = listing_url.strip()

    if (
        not name
        or not listing_url
        or collector_type not in {"web", "freshrss", "social"}
        or not 0 <= credibility_score <= 100
        or max_candidates < 1
        or max_fetches < 1
        or request_timeout_seconds <= 0
        or max_source_runtime_seconds <= 0
        or (
            stop_after_consecutive_stale is not None
            and stop_after_consecutive_stale < 1
        )
    ):
        return HTMLResponse("Invalid source", status_code=400)

    db = get_db()

    profile = db.execute(
        "SELECT id FROM profiles WHERE slug = ?",
        (profile_id,),
    ).fetchone()

    if profile is None:
        db.close()
        return HTMLResponse("Profile not found", status_code=404)

    try:
        source = db.execute(
            "SELECT id FROM sources WHERE name = ?",
            (name,),
        ).fetchone()

        if source is None:
            cursor = db.execute(
                "INSERT INTO sources (name) VALUES (?)",
                (name,),
            )
            source_id = cursor.lastrowid
        else:
            source_id = source["id"]

        db.execute("""
            INSERT INTO profile_sources (
                profile_id,
                source_id,
                enabled,
                collector_type,
                listing_url,
                topic_focused,
                credibility_score,
                max_candidates,
                max_fetches,
                request_timeout_seconds,
                max_source_runtime_seconds,
                stop_after_consecutive_stale
            )
            VALUES (?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            profile["id"],
            source_id,
            collector_type,
            listing_url,
            1 if topic_focused else 0,
            credibility_score,
            max_candidates,
            max_fetches,
            request_timeout_seconds,
            max_source_runtime_seconds,
            stop_after_consecutive_stale,
        ))

        db.commit()

    except sqlite3.IntegrityError:
        db.rollback()
        db.close()
        return HTMLResponse(
            "Source already exists in this profile",
            status_code=409,
        )

    db.close()

    return RedirectResponse(
        url=f"/profiles/{profile_id}",
        status_code=303,
    )
