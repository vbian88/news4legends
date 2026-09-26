import argparse
import json
import re
import sys
from contextlib import redirect_stdout
from datetime import datetime, timezone

from llm_client import ask_llm
from profile_adapter import load_profile_from_db


DEFAULT_PROFILE_DB = "/config/home-ai-news.db"
MAX_TELEGRAM_ARTICLES_PER_STORY = 3


def load_articles(path):
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def score_source(article, profile):
    source = article["source"]

    source_config = profile["sources"].get(source)

    if source_config is None:
        return None

    return source_config["score"]


def source_is_acceptable(article, profile):
    return (
        article["source_score"]
        >= profile["minimum_source_score"]
    )


def parse_published_at(article):
    published_at = article.get("published_at")

    if not published_at:
        return None

    try:
        published = datetime.fromisoformat(
            published_at.replace(
                "Z",
                "+00:00",
            )
        )
    except ValueError:
        return None

    if published.tzinfo is None:
        published = published.replace(
            tzinfo=timezone.utc
        )

    return published


def format_published_at(article):
    published = parse_published_at(article)

    if published is None:
        return "Unknown"

    timezone_text = published.strftime("%z")

    if timezone_text:
        timezone_text = (
            timezone_text[:3]
            + ":"
            + timezone_text[3:]
        )

    return (
        published.strftime(
            "%d %b %Y, %H:%M"
        )
        + (
            f" {timezone_text}"
            if timezone_text
            else ""
        )
    )


def calculate_age_hours(article):
    published = parse_published_at(article)

    if published is None:
        return None

    now = datetime.now(timezone.utc)

    age = (
        now
        - published.astimezone(
            timezone.utc
        )
    )

    return (
        age.total_seconds()
        / 3600
    )


def article_is_fresh(article, profile):
    age_hours = article.get("age_hours")

    if age_hours is None:
        return False

    return (
        age_hours
        <= profile["maximum_age_hours"]
    )


def normalize_title(title):
    title = title.casefold()

    title = re.sub(
        r"[^\w\s]",
        " ",
        title,
        flags=re.UNICODE,
    )

    title = re.sub(
        r"\s+",
        " ",
        title,
    )

    return title.strip()


def title_words(title):
    return set(
        normalize_title(title).split()
    )


def title_similarity(
    title_a,
    title_b,
):
    words_a = title_words(title_a)
    words_b = title_words(title_b)

    if not words_a or not words_b:
        return 0.0

    common_words = (
        words_a
        & words_b
    )

    all_words = (
        words_a
        | words_b
    )

    return (
        len(common_words)
        / len(all_words)
    )


def remove_exact_duplicates(articles):
    seen_urls = set()
    unique_articles = []

    for article in articles:
        url = article["url"]

        if url in seen_urls:
            print(
                "Exact duplicate URL "
                f"rejected: {url}"
            )
            continue

        seen_urls.add(url)
        unique_articles.append(article)

    return unique_articles


def cluster_articles(
    articles,
    similarity_threshold,
):
    clusters = []

    for article in articles:
        added_to_cluster = False

        for cluster in clusters:
            representative = cluster[0]

            similarity = title_similarity(
                article["title"],
                representative["title"],
            )

            if (
                similarity
                >= similarity_threshold
            ):
                cluster.append(article)
                added_to_cluster = True
                break

        if not added_to_cluster:
            clusters.append([article])

    return clusters


def calculate_story_priority(
    cluster,
    profile,
):
    source_scores = [
        article["source_score"]
        for article in cluster
    ]

    average_source_score = (
        sum(source_scores)
        / len(source_scores)
    )

    unique_sources = {
        article["source"]
        for article in cluster
    }

    corroboration = profile.get(
        "corroboration",
        {}
    )

    corroboration_bonus = 0

    if len(unique_sources) >= 2:
        corroboration_bonus += corroboration.get(
            "two_sources_bonus",
            0,
        )

    if len(unique_sources) >= 3:
        corroboration_bonus += corroboration.get(
            "three_sources_bonus",
            0,
        )

    if len(unique_sources) >= 4:
        corroboration_bonus += corroboration.get(
            "four_sources_bonus",
            0,
        )

    story_priority = (
        average_source_score
        + corroboration_bonus
    )

    return min(
        story_priority,
        100,
    )


def deterministic_processing(
    articles,
    profile,
    similarity_threshold,
):
    accepted_articles = []

    for article in articles:
        source = article.get(
            "source",
            "UNKNOWN",
        )

        title = article.get(
            "title",
            "UNTITLED",
        )

        article["source_score"] = (
            score_source(
                article,
                profile,
            )
        )

        article["age_hours"] = (
            calculate_age_hours(article)
        )

        print()

        if article["source_score"] is None:
            print(
                f"{source}: "
                "no profile-defined source weight"
            )
            print(
                "  Rejected: "
                "source not configured for profile"
            )
            continue

        print(
            f"{source}: "
            f'{article["source_score"]}'
            ""
        )

        print(
            f"  Title: {title}"
        )

        print(
            "  Published: "
            f"{format_published_at(article)}"
        )

        if article["age_hours"] is None:
            print(
                "  Rejected: "
                "invalid publication date"
            )
            continue

        if not source_is_acceptable(
            article,
            profile,
        ):
            print(
                "  Rejected: "
                "source weight below profile minimum"
            )
            continue

        if not article_is_fresh(
            article,
            profile,
        ):
            print(
                "  Rejected: stale"
            )
            continue

        print("  Accepted")

        accepted_articles.append(
            article
        )

    print()
    print(
        "=============================="
    )

    print(
        "Accepted before "
        "duplicate check: "
        f"{len(accepted_articles)}"
    )

    unique_articles = (
        remove_exact_duplicates(
            accepted_articles
        )
    )

    print(
        "Accepted after "
        "duplicate check: "
        f"{len(unique_articles)}"
    )

    clusters = cluster_articles(
        unique_articles,
        similarity_threshold,
    )

    print(
        "Story clusters: "
        f"{len(clusters)}"
    )

    print(
        "=============================="
    )

    for number, cluster in enumerate(
        clusters,
        start=1,
    ):
        story_priority = (
            calculate_story_priority(
                cluster,
                profile,
            )
        )

        print()
        print(
            f"Cluster {number}:"
        )

        print(
            "  Reports: "
            f"{len(cluster)}"
        )

        print(
            "  Story priority: "
            f"{story_priority:.1f}"
        )

        for article in cluster:
            print(
                "  - "
                f'{article["source"]}: '
                f'{article["title"]}'
            )

    return clusters


def rank_clusters(
    clusters,
    profile,
):
    return sorted(
        clusters,
        key=lambda cluster: (
            calculate_story_priority(
                cluster,
                profile,
            ),
            len(
                {
                    article["source"]
                    for article in cluster
                }
            ),
            len(cluster),
        ),
        reverse=True,
    )


def build_llm_prompt(
    cluster,
    story_priority,
    profile,
):
    reports = []

    for article in cluster:
        reports.append(
            f"""
SOURCE: {article["source"]}
SOURCE WEIGHT: {article["source_score"]}
TITLE: {article["title"]}
PUBLISHED: {article["published_at"]}
URL: {article["url"]}

{article["text"]}
""".strip()
        )

    combined_reports = (
        "\n\n---\n\n".join(
            reports
        )
    )

    return f"""
You are analysing reports about {profile["topic"]}.

The reports below have already passed deterministic
profile source-weight and freshness checks.

They may describe the same event from multiple sources.

Produce one very concise intelligence summary for this story.

Requirements:
- Write one short paragraph, maximum 240 characters.
- Prioritise the most decision-relevant facts.
- Do not invent facts.
- Distinguish confirmed facts from claims where necessary.
- Use corroboration across sources where appropriate.
- Do not treat repeated reporting as separate events.
- Do not include URLs in the summary.
- Do not repeat the article titles.

Number of reports: {len(cluster)}
Story priority: {story_priority:.1f}

REPORTS:

{combined_reports}
""".strip()


def synthesize_clusters(
    clusters,
    llm_limit,
    profile,
    print_console_results=True,
):
    ranked_clusters = rank_clusters(
        clusters,
        profile,
    )

    selected_clusters = (
        ranked_clusters[:llm_limit]
    )

    results = []
    llm_attempts = 0
    llm_failures = 0

    for number, cluster in enumerate(
        selected_clusters,
        start=1,
    ):
        story_priority = (
            calculate_story_priority(
                cluster,
                profile,
            )
        )

        prompt = build_llm_prompt(
            cluster,
            story_priority,
            profile,
        )

        try:
            llm_attempts += 1
            result = ask_llm(prompt)
            summary = result.strip()
        except Exception as exc:
            llm_failures += 1
            print(
                f"LLM synthesis failed for story {number}: {exc}",
                file=sys.stderr,
            )
            summary = cluster[0]["title"]

        synthesis = {
            "number": number,
            "cluster": cluster,
            "story_priority": story_priority,
            "summary": summary,
        }

        results.append(synthesis)

        if print_console_results:
            print()
            print(
                "=============================="
            )

            print(
                f"Story {number} synthesis:"
            )

            print(summary)

    if llm_attempts > 0 and llm_failures == llm_attempts:
        raise RuntimeError(
            "Systemic LLM failure: "
            f"all {llm_attempts} synthesis attempt(s) failed"
        )

    return results


def render_telegram_digest(
    syntheses,
    total_clusters,
    profile,
):
    from datetime import datetime
    from zoneinfo import ZoneInfo

    generated_at = datetime.now(
        ZoneInfo("Europe/London")
    )

    lines = [
        f"📰 {profile['topic']}",
        (
            "Digest generated: "
            + generated_at.strftime(
                "%d %b %Y, %H:%M %Z"
            )
        ),
        "",
    ]

    for number, synthesis in enumerate(
        syntheses,
        start=1,
    ):
        cluster = synthesis["cluster"]
        story_priority = synthesis[
            "story_priority"
        ]

        if len(syntheses) > 1:
            lines.extend(
                [
                    f"*STORY {number}*",
                    "",
                ]
            )

        lines.append("*Summary*")
        lines.append(
            synthesis["summary"]
        )
        lines.append("")

        articles_to_show = sorted(
            cluster,
            key=lambda article: (
                article["source_score"]
            ),
            reverse=True,
        )[
            :MAX_TELEGRAM_ARTICLES_PER_STORY
        ]

        for article in articles_to_show:
            lines.extend(
                [
                    f"*{article['source']}*",
                    article["title"],
                    (
                        "Published: "
                        + format_published_at(
                            article
                        )
                    ),
                    article["url"],
                    "",
                ]
            )

        hidden_reports = (
            len(cluster)
            - len(articles_to_show)
        )

        if hidden_reports > 0:
            lines.extend(
                [
                    (
                        f"+ {hidden_reports} "
                        "additional report"
                        + (
                            "s"
                            if hidden_reports != 1
                            else ""
                        )
                    ),
                    "",
                ]
            )

        lines.append(
            (
                f"Priority: "
                f"{story_priority:.0f}"
                f" · {len(cluster)} reports"
            )
        )
        lines.append("")

    return "\n".join(lines).strip()




def render_email_digest(
    syntheses,
    total_clusters,
    profile,
):
    import html
    from datetime import datetime
    from zoneinfo import ZoneInfo

    generated_at = datetime.now(
        ZoneInfo("Europe/London")
    )

    identity = profile.get("identity", {})
    slug = str(identity.get("slug", "")).lower()
    name = str(
        identity.get("name")
        or profile.get("topic")
        or "News"
    )

    # Built-in defaults. Later these become UI-selectable
    # profile settings stored in SQLite.
    themes = {
        "roma": {
            "primary": "#7A1731",
            "secondary": "#4A0E1E",
            "accent": "#F2C14E",
            "page": "#120D10",
            "card": "#21161A",
            "text": "#F7F3EE",
            "muted": "#CDBFC2",
        },
        "cybersecurity": {
            "primary": "#071B33",
            "secondary": "#0B2D4D",
            "accent": "#20C7E8",
            "page": "#06101B",
            "card": "#0B1D2B",
            "text": "#F2F8FC",
            "muted": "#AFC4D3",
        },
        "default": {
            "primary": "#171B24",
            "secondary": "#252B38",
            "accent": "#D7B45A",
            "page": "#0E1117",
            "card": "#1A1F29",
            "text": "#F5F6F8",
            "muted": "#B7BEC9",
        },
    }

    selected_theme = (
        profile.get("delivery", {})
        .get("email_theme", "auto")
    )

    extra_themes = {
        "burgundy_gold": themes["roma"],
        "navy_cyan": themes["cybersecurity"],
        "emerald": {
            **themes["default"],
            "primary": "#064E3B",
            "secondary": "#083C32",
            "accent": "#34D399",
            "page": "#071A15",
            "card": "#0B2820",
        },
        "purple": {
            **themes["default"],
            "primary": "#4C1D95",
            "secondary": "#31205C",
            "accent": "#C4B5FD",
            "page": "#160E27",
            "card": "#24163B",
        },
        "orange": {
            **themes["default"],
            "primary": "#7C2D12",
            "secondary": "#54200F",
            "accent": "#FDBA74",
            "page": "#1C100A",
            "card": "#30190E",
        },
        "monochrome": {
            **themes["default"],
            "primary": "#171717",
            "secondary": "#262626",
            "accent": "#E5E5E5",
            "page": "#0A0A0A",
            "card": "#1A1A1A",
        },
    }

    if selected_theme == "auto":
        theme = themes.get(
            slug,
            themes["default"],
        )
    else:
        theme = extra_themes.get(
            selected_theme,
            themes["default"],
        )

    esc = lambda value: html.escape(
        str(value),
        quote=True,
    )

    # Build a profile-level executive briefing from the
    # story syntheses already produced by this pipeline.
    # This deliberately makes no additional LLM request.
    overview_items = []

    for number, synthesis in enumerate(
        syntheses,
        start=1,
    ):
        text = " ".join(
            str(synthesis["summary"]).split()
        ).strip()

        # Prefer the first sentence. If the synthesis is a
        # single sentence, use it as-is.
        first_sentence = text
        for separator in (". ", "? ", "! "):
            if separator in first_sentence:
                first_sentence = (
                    first_sentence.split(
                        separator,
                        1,
                    )[0].strip()
                )
                break

        if first_sentence:
            first_sentence = (
                first_sentence.rstrip(".?!")
            )
            overview_items.append(
                (
                    f'<a href="#story-{number}" '
                    f'style="color:{theme["accent"]};'
                    f'font-weight:800;'
                    f'text-decoration:none;">'
                    f'Story {number}</a>: '
                    f'{esc(first_sentence)}'
                )
            )

    if not overview_items:
        overview_text = (
            "No prioritised stories "
            "were available today."
        )
    elif len(overview_items) == 1:
        overview_text = overview_items[0] + "."
    elif len(overview_items) == 2:
        overview_text = (
            overview_items[0]
            + " and "
            + overview_items[1]
            + "."
        )
    else:
        overview_text = (
            ", ".join(overview_items[:-1])
            + ", and "
            + overview_items[-1]
            + "."
        )

    # overview_items are constructed from escaped story
    # text plus our own controlled HTML links.
    overview_html = overview_text

    story_blocks = []

    for number, synthesis in enumerate(
        syntheses,
        start=1,
    ):
        cluster = synthesis["cluster"]
        summary = esc(synthesis["summary"])

        source_blocks = []

        for article in sorted(
            cluster,
            key=lambda item: item["source_score"],
            reverse=True,
        ):
            source = esc(article["source"])
            title = esc(article["title"])
            published = esc(
                format_published_at(article)
            )
            url = esc(article["url"])

            source_blocks.append(
                f"""
                <tr>
                  <td style="
                    padding:14px 0;
                    border-top:1px solid {theme['secondary']};
                  ">
                    <div style="
                      color:{theme['accent']};
                      font-size:12px;
                      font-weight:700;
                      text-transform:uppercase;
                      letter-spacing:.7px;
                    ">{source}</div>
                    <div style="
                      color:{theme['text']};
                      font-size:15px;
                      line-height:1.45;
                      font-weight:600;
                      padding:5px 0 4px;
                    ">{title}</div>
                    <div style="
                      color:{theme['muted']};
                      font-size:12px;
                      padding-bottom:10px;
                    ">Published: {published}</div>
                    <a href="{url}" style="
                      display:inline-block;
                      background:{theme['accent']};
                      color:#111111;
                      text-decoration:none;
                      font-size:12px;
                      font-weight:800;
                      padding:9px 14px;
                      border-radius:5px;
                    ">READ SOURCE</a>
                  </td>
                </tr>
                """
            )

        story_blocks.append(
            f"""
            <table role="presentation"
                   id="story-{number}"
                   width="100%"
                   cellspacing="0"
                   cellpadding="0"
                   style="
                     background:{theme['card']};
                     border-radius:10px;
                     margin:0 0 18px 0;
                     border-left:4px solid {theme['accent']};
                   ">
              <tr>
                <td style="padding:22px;">
                  <div style="
                    color:{theme['accent']};
                    font-size:12px;
                    font-weight:800;
                    letter-spacing:1px;
                    text-transform:uppercase;
                    padding-bottom:9px;
                  ">Story {number}</div>

                  <div style="
                    color:{theme['text']};
                    font-size:17px;
                    line-height:1.6;
                    padding-bottom:18px;
                  ">{summary}</div>

                  <div style="
                    color:{theme['muted']};
                    font-size:11px;
                    font-weight:800;
                    letter-spacing:1px;
                    text-transform:uppercase;
                    padding-bottom:4px;
                  ">Sources</div>

                  <table role="presentation"
                         width="100%"
                         cellspacing="0"
                         cellpadding="0">
                    {''.join(source_blocks)}
                  </table>
                </td>
              </tr>
            </table>
            """
        )

    generated = esc(
        generated_at.strftime(
            "%d %b %Y, %H:%M %Z"
        )
    )
    display_name = esc(name)

    return f"""<!doctype html>
<html>
<body style="
  margin:0;
  padding:0;
  background:{theme['page']};
  font-family:Arial,Helvetica,sans-serif;
">
<table role="presentation"
       width="100%"
       cellspacing="0"
       cellpadding="0"
       style="background:{theme['page']};">
<tr>
<td align="center" style="padding:28px 12px;">
<table role="presentation"
       width="100%"
       cellspacing="0"
       cellpadding="0"
       style="max-width:760px;">

<tr>
<td style="
  background:{theme['primary']};
  border-bottom:4px solid {theme['accent']};
  border-radius:12px 12px 0 0;
  padding:32px 28px;
">
  <div style="
    color:{theme['accent']};
    font-size:13px;
    font-weight:800;
    letter-spacing:2px;
  ">NEWS 4 LEGENDS</div>

  <div style="
    color:#FFFFFF;
    font-size:30px;
    line-height:1.15;
    font-weight:800;
    padding-top:7px;
  ">{display_name}</div>

  <div style="
    color:{theme['muted']};
    font-size:13px;
    padding-top:10px;
  ">
    Intelligence Briefing · {generated}
  </div>
</td>
</tr>

<tr>
<td style="
  background:{theme['secondary']};
  padding:18px 28px;
  color:{theme['text']};
  font-size:14px;
">
  <strong>{len(syntheses)}</strong> prioritised
  stor{'y' if len(syntheses) == 1 else 'ies'}
  from <strong>{total_clusters}</strong> relevant
  story cluster{'' if total_clusters == 1 else 's'}.
</td>
</tr>

<tr>
<td style="padding:24px 0 6px;">

  <table role="presentation"
         width="100%"
         cellspacing="0"
         cellpadding="0"
         style="
           background:{theme['card']};
           border:1px solid {theme['secondary']};
           border-radius:10px;
           margin:0 0 20px 0;
         ">
    <tr>
      <td style="padding:22px 24px;">
        <div style="
          color:{theme['accent']};
          font-size:12px;
          font-weight:800;
          letter-spacing:1px;
          text-transform:uppercase;
          padding-bottom:9px;
        ">
          Today in {display_name}
        </div>

        <div style="
          color:{theme['text']};
          font-size:16px;
          line-height:1.6;
        ">
          {overview_html}
        </div>
      </td>
    </tr>
  </table>

  {''.join(story_blocks)}
</td>
</tr>

<tr>
<td style="
  text-align:center;
  color:{theme['muted']};
  font-size:11px;
  line-height:1.6;
  padding:12px 20px 28px;
">
  NEWS 4 LEGENDS<br>
  Automated intelligence briefing
</td>
</tr>

</table>
</td>
</tr>
</table>
</body>
</html>"""

def parse_arguments():
    parser = argparse.ArgumentParser(
        description=(
            "Content-agnostic deterministic "
            "news processing pipeline"
        )
    )

    parser.add_argument(
        "articles_json",
        help=(
            "JSON file produced by "
            "collector.py"
        ),
    )

    parser.add_argument(
        "--profile",
        required=True,
        help=(
            "Profile slug used for processing"
        ),
    )

    parser.add_argument(
        "--profile-db",
        default=DEFAULT_PROFILE_DB,
        help=(
            "SQLite profile database "
            f"(default: {DEFAULT_PROFILE_DB})"
        ),
    )

    parser.add_argument(
        "--similarity-threshold",
        type=float,
        default=None,
        help=(
            "Optional Jaccard title similarity "
            "threshold override. By default the "
            "profile value is used."
        ),
    )

    parser.add_argument(
        "--llm",
        action="store_true",
        help=(
            "Explicitly enable LLM "
            "synthesis. Without this "
            "flag no LLM request is made."
        ),
    )

    parser.add_argument(
        "--llm-limit",
        type=int,
        default=None,
        help=(
            "Optional maximum number of story "
            "clusters sent to the LLM. By "
            "default the profile value is used."
        ),
    )

    parser.add_argument(
        "--telegram",
        action="store_true",
        help=(
            "Write a clean Telegram "
            "digest to stdout and send "
            "diagnostic output to stderr."
        ),
    )

    parser.add_argument(
        "--email",
        action="store_true",
        help=(
            "Write a full email digest to stdout "
            "and send diagnostic output to stderr."
        ),
    )

    parser.add_argument(
        "--delivery-bundle",
        action="store_true",
        help=(
            "Write Telegram and email renderings as "
            "one JSON object from a single synthesis pass."
        ),
    )

    return parser.parse_args()


def print_startup_banner(args, articles):
    print(
        "=============================="
    )

    print(
        "News 4 Legends generic pipeline"
    )

    print(
        "Input articles: "
        f"{len(articles)}"
    )

    print(
        "Profile: "
        f"{args.profile}"
    )

    print(
        "Similarity threshold: "
        f"{args.similarity_threshold}"
    )

    print(
        "LLM synthesis: "
        + (
            "ENABLED"
            if args.llm
            else "DISABLED"
        )
    )

    if args.llm:
        print(
            "LLM cluster limit: "
            f"{args.llm_limit}"
        )

    print(
        "=============================="
    )


def run_pipeline(
    args,
    articles,
    profile,
):
    print_startup_banner(
        args,
        articles,
    )

    clusters = (
        deterministic_processing(
            articles=articles,
            profile=profile,
            similarity_threshold=(
                args.similarity_threshold
            ),
        )
    )

    if not args.llm:
        print()
        print(
            "LLM synthesis skipped."
        )

        print(
            "Use --llm only when "
            "you explicitly want "
            "external synthesis."
        )

        return None, clusters

    effective_llm_limit = args.llm_limit
    max_llm_calls = profile.get("budgets", {}).get(
        "max_llm_calls"
    )
    if max_llm_calls is not None:
        effective_llm_limit = min(
            effective_llm_limit,
            max_llm_calls,
        )

    syntheses = synthesize_clusters(
        clusters,
        llm_limit=effective_llm_limit,
        profile=profile,
        print_console_results=(
            not (
                args.telegram
                or args.email
                or args.delivery_bundle
            )
        ),
    )

    return syntheses, clusters


def main():
    args = parse_arguments()

    delivery_modes = sum(
        bool(value)
        for value in (
            args.telegram,
            args.email,
            args.delivery_bundle,
        )
    )

    if delivery_modes > 1:
        raise SystemExit(
            "Choose only one delivery output mode"
        )

    if delivery_modes and not args.llm:
        raise SystemExit(
            "Delivery output requires --llm"
        )

    profile = load_profile_from_db(
        args.profile,
        db_path=args.profile_db,
    )

    if args.similarity_threshold is None:
        args.similarity_threshold = profile[
            "clustering"
        ]["title_similarity_threshold"]

    if not (
        0.0
        <= args.similarity_threshold
        <= 1.0
    ):
        raise SystemExit(
            "--similarity-threshold "
            "must be between 0 and 1"
        )

    if args.llm_limit is None:
        args.llm_limit = profile[
            "llm"
        ]["limit"]

    if (
        args.llm_limit is None
        or not 1 <= args.llm_limit <= 10
    ):
        raise SystemExit(
            "LLM limit must be between 1 and 10"
        )

    articles = load_articles(
        args.articles_json
    )

    if args.telegram or args.email or args.delivery_bundle:
        with redirect_stdout(
            sys.stderr
        ):
            syntheses, clusters = (
                run_pipeline(
                    args,
                    articles,
                    profile,
                )
            )

        if not clusters:
            if args.delivery_bundle:
                print(json.dumps({
                    "telegram": "",
                    "email": "",
                }))
            return

        if args.delivery_bundle:
            print(json.dumps({
                "telegram": render_telegram_digest(
                    syntheses,
                    len(clusters),
                    profile,
                ),
                "email": render_email_digest(
                    syntheses,
                    len(clusters),
                    profile,
                ),
            }))
            return

        if args.telegram:
            digest = render_telegram_digest(
                syntheses,
                len(clusters),
                profile,
            )
        else:
            digest = render_email_digest(
                syntheses,
                len(clusters),
                profile,
            )

        print(digest)
        return

    run_pipeline(
        args,
        articles,
        profile,
    )


if __name__ == "__main__":
    main()
