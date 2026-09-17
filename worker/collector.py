import argparse
import json
import re
import time
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse, urlunparse

import dateparser
import requests
import trafilatura
import yaml
import sqlite3
from bs4 import BeautifulSoup


#
# The automation is intended to run twice per day.
#
# Articles older than this window are therefore not useful
# for the next intelligence cycle.
#
DEFAULT_MAX_AGE_HOURS = 12


GENERIC_PAGE_TERMS = (
    "news",
    "notizie",
    "as roma",
    "roma news",
    "categoria",
    "category",
    "fixtures",
    "matches",
    "calendario",
    "classifica",
    "tickets",
    "biglietti",
    "players",
    "staff",
    "squadra",
    "team",
    "radio",
    "video",
    "gallery",
    "photogallery",
)


BAD_TITLE_FRAGMENTS = (
    "categoria:",
    "ultime notizie",
    "official ticket",
    "fixtures",
    "calendario",
    "classifica",
    "players and staff",
    "matches |",
    "condizioni generali",
    "terms and conditions",
    "privacy policy",
    "cookie policy",
    "utilizzo dei cookies",
    "informativa privacy",
    "collabora con noi",
    "pubblicità",
    "pubblicita",
    "disclaimer",
    "avatar e identità",
    "avatar e identita",

    # Static/archive TuttoASRoma pages.
    "ex dirigenti as roma",
    "tabellini serie a as roma",
    "tabellini femminile as roma",
    "comunicati as roma",
    "allenatori as roma",
    "giocatori as roma",

    # Match-lineup information is obsolete by the time
    # a non-real-time digest is generated.
    "formazioni",
)


NON_FOOTBALL_TITLE_FRAGMENTS = (
    "eurocup",
    "pallacanestro",
    "basketball",
    "basket ",
    "eurolega",
    "volley",
    "pallavolo",
    "tennis",
    "formula 1",
    "motogp",
)


BLOCKED_PATH_PARTS = (
    "/tag/",
    "/tags/",
    "/category/",
    "/categorie/",
    "/author/",
    "/autore/",
    "/search",
    "/login",
    "/privacy",
    "/cookie",
    "/cookies",
    "/contact",
    "/contatti",
    "/tickets",
    "/biglietti",
    "/fixtures",
    "/matches",
    "/calendario",
    "/classifica",
    "/players",
    "/staff",
    "/rosa/",
    "/team/",
    "/squadra/",
    "/radio/",
    "/video/",
    "/gallery/",
    "/photogallery/",
    "/foto/",
    "/utility/",
    "/widget/",
    "/info/",
    "/terms",
    "/conditions",
    "/condizioni",
    "/disclaimer",
    "/pubblicita",
    "/pubblicità",
    "/collabora",
    "/avatar",
    "/archivio",
    "/formazione/",
    "/comparison/",
    "/statistics/",
    "/squad/",

    # Line-up pages.
    "/probabili-formazioni",
    "/formazioni-ufficiali",

    # Known TuttoASRoma static/archive sections.
    "/pinzolo-2017/",
    "/trigoria-2019",
    "/info-biglietti-as-roma/",
    "/as-roma-calcio-dirigenti-as-roma/",
    "/as-roma-calcio-tabellini-as-roma/",
)


BLOCKED_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".svg",
    ".pdf",
    ".zip",
    ".mp3",
    ".mp4",
)


SITE_TITLE_SUFFIX_PATTERNS = (
    r"\s+\|\s+Pagine Romaniste$",
    r"\s+\|\s+TuttoASRoma\.it$",
    r"\s+-\s+Roma news$",
    r"\s+-\s+Forzaroma\.info$",
    r"\s+-\s+Retesport 104\.2 FM$",
    r"\s+\|\s+Notizie AS Roma$",
    r"\s+-\s+Giallorossi\.net$",
)


GENERAL_FOOTBALL_CONTEXT = (
    "inter",
    "milan",
    "torino",
    "juventus",
    "napoli",
    "lazio",
    "atalanta",
    "fiorentina",
    "bologna",
    "parma",
    "como",
    "udinese",
    "sassuolo",
    "genoa",
    "lecce",
    "cagliari",
    "verona",
    "cremonese",
    "serie a",
    "champions",
    "champions league",
    "europa league",
    "conference league",
    "coppa italia",
    "scudetto",
    "classifica",
    "capolista",
    "campionato",
    "calcio",
    "gol",
    "goal",
    "partita",
    "match",
    "allenamento",
    "allenamenti",
    "trigoria",
    "calciomercato",
    "mercato",
    "derby",
    "rigore",
    "rigori",
    "infortunio",
    "squalifica",
    "trasferta",
)


STRONG_ROMA_URL_FRAGMENTS = (
    "/as_roma/",
    "/as-roma/",
    "/serie-a/roma/",
    "/squadra/calcio/roma/",
)


def load_yaml(path):
    with open(
        path,
        "r",
        encoding="utf-8",
    ) as file:
        return yaml.safe_load(file)


def clean_url(url):
    parsed = urlparse(url)

    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            "",
            parsed.query,
            "",
        )
    )


def repair_mojibake(value):
    if not value:
        return value

    if not isinstance(value, str):
        return value

    bad_markers = (
        "Ã",
        "Â",
        "â€",
        "â€™",
        "â€œ",
        "â€\x9d",
        "â",
    )

    original_score = sum(
        value.count(marker)
        for marker in bad_markers
    )

    if original_score == 0:
        return value

    candidates = []

    for encoding in (
        "latin1",
        "cp1252",
    ):
        try:
            fixed = (
                value
                .encode(encoding)
                .decode("utf-8")
            )
        except (
            UnicodeEncodeError,
            UnicodeDecodeError,
        ):
            continue

        score = sum(
            fixed.count(marker)
            for marker in bad_markers
        )

        candidates.append(
            (
                score,
                fixed,
            )
        )

    if not candidates:
        return value

    best_score, best_value = min(
        candidates,
        key=lambda item: item[0],
    )

    if best_score < original_score:
        return best_value

    return value


def same_domain(url_a, url_b):
    domain_a = (
        urlparse(url_a)
        .netloc
        .lower()
        .removeprefix("www.")
    )

    domain_b = (
        urlparse(url_b)
        .netloc
        .lower()
        .removeprefix("www.")
    )

    return domain_a == domain_b


def looks_like_possible_article_url(
    url,
    listing_url,
):
    parsed = urlparse(url)

    if parsed.scheme not in (
        "http",
        "https",
    ):
        return False

    if clean_url(url) == clean_url(
        listing_url
    ):
        return False

    path = parsed.path.lower()

    if path in (
        "",
        "/",
    ):
        return False

    if any(
        part in path
        for part in BLOCKED_PATH_PARTS
    ):
        return False

    if path.endswith(
        BLOCKED_EXTENSIONS
    ):
        return False

    return True


def candidate_score(
    url,
    anchor_text,
):
    parsed = urlparse(url)

    path = parsed.path.strip("/")
    path_lower = path.lower()

    text = " ".join(
        anchor_text.split()
    )

    text_lower = text.lower()

    score = 0

    path_parts = [
        part
        for part in path.split("/")
        if part
    ]

    score += min(
        len(path_parts) * 2,
        8,
    )

    if len(text) >= 20:
        score += 4

    if len(text) >= 40:
        score += 3

    if re.search(
        r"/20\d{2}/",
        "/" + path_lower + "/",
    ):
        score += 5

    final_part = (
        path_parts[-1]
        if path_parts
        else ""
    )

    if final_part.count("-") >= 2:
        score += 4

    if len(final_part) >= 20:
        score += 3

    if text_lower in GENERIC_PAGE_TERMS:
        score -= 10

    if len(text) < 5:
        score -= 5

    return score


def discover_links(
    html,
    listing_url,
    maximum_candidates,
):
    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    candidates = {}
    seen = set()

    for anchor in soup.find_all(
        "a",
        href=True,
    ):
        href = anchor["href"].strip()

        if not href:
            continue

        url = clean_url(
            urljoin(
                listing_url,
                href,
            )
        )

        if url in seen:
            continue

        seen.add(url)

        if not same_domain(
            url,
            listing_url,
        ):
            continue

        if not looks_like_possible_article_url(
            url,
            listing_url,
        ):
            continue

        anchor_text = anchor.get_text(
            " ",
            strip=True,
        )

        score = candidate_score(
            url,
            anchor_text,
        )

        candidates[url] = {
            "url": url,
            "anchor_text": anchor_text,
            "score": score,
        }

    ordered = sorted(
        candidates.values(),
        key=lambda item: item["score"],
        reverse=True,
    )

    return ordered[
        :maximum_candidates
    ]


def jsonld_type_is_article(value):
    if isinstance(value, str):
        types = [
            value,
        ]

    elif isinstance(value, list):
        types = [
            str(item)
            for item in value
        ]

    else:
        return False

    article_types = (
        "article",
        "newsarticle",
        "reportagenewsarticle",
        "analysisnewsarticle",
        "opinionnewsarticle",
        "liveblogposting",
    )

    return any(
        item.casefold()
        in article_types
        for item in types
    )


def walk_json(value):
    if isinstance(value, dict):
        yield value

        for child in value.values():
            yield from walk_json(
                child
            )

    elif isinstance(value, list):
        for child in value:
            yield from walk_json(
                child
            )


def jsonld_url(item):
    value = item.get("url")

    if isinstance(value, str):
        return value

    main_entity = item.get(
        "mainEntityOfPage"
    )

    if isinstance(
        main_entity,
        str,
    ):
        return main_entity

    if isinstance(
        main_entity,
        dict,
    ):
        for key in (
            "@id",
            "url",
        ):
            value = main_entity.get(
                key
            )

            if isinstance(
                value,
                str,
            ):
                return value

    return None


def extract_jsonld_article(
    soup,
    fallback_url,
):
    best = None

    for tag in soup.find_all(
        "script",
        type="application/ld+json",
    ):
        raw = tag.string

        if not raw:
            raw = tag.get_text(
                strip=True
            )

        if not raw:
            continue

        try:
            payload = json.loads(
                raw
            )
        except (
            json.JSONDecodeError,
            TypeError,
        ):
            continue

        for item in walk_json(
            payload
        ):
            if not jsonld_type_is_article(
                item.get("@type")
            ):
                continue

            title = item.get(
                "headline"
            )

            text = item.get(
                "articleBody"
            )

            published = item.get(
                "datePublished"
            )

            if not isinstance(
                title,
                str,
            ):
                title = None

            if not isinstance(
                text,
                str,
            ):
                text = None

            if not isinstance(
                published,
                str,
            ):
                published = None

            candidate = {
                "title": (
                    repair_mojibake(
                        title
                    )
                    if title
                    else None
                ),
                "url": clean_url(
                    jsonld_url(item)
                    or fallback_url
                ),
                "published_at": published,
                "text": (
                    repair_mojibake(
                        text
                    )
                    if text
                    else None
                ),
            }

            candidate_score_value = (
                len(
                    candidate["text"]
                    or ""
                )
            )

            if best is None:
                best = candidate
                continue

            best_score = len(
                best["text"]
                or ""
            )

            if (
                candidate_score_value
                > best_score
            ):
                best = candidate

    return best


def extract_html_metadata(
    soup,
):
    title = None
    published = None

    og_title = soup.find(
        "meta",
        property="og:title",
    )

    if og_title:
        title = og_title.get(
            "content"
        )

    if not title:
        twitter_title = soup.find(
            "meta",
            attrs={
                "name":
                "twitter:title"
            },
        )

        if twitter_title:
            title = twitter_title.get(
                "content"
            )

    for selector in (
        {
            "property":
            "article:published_time"
        },
        {
            "name":
            "article:published_time"
        },
        {
            "itemprop":
            "datePublished"
        },
    ):
        tag = soup.find(
            "meta",
            attrs=selector,
        )

        if tag:
            published = tag.get(
                "content"
            )

            if published:
                break

    return (
        repair_mojibake(title)
        if title
        else None,
        published,
    )


def extract_article(
    html,
    fallback_url,
):
    trafilatura_data = None

    extracted = trafilatura.extract(
        html,
        output_format="json",
        with_metadata=True,
        include_comments=False,
        include_tables=False,
        favor_precision=True,
    )

    if extracted:
        try:
            data = json.loads(
                extracted
            )
        except json.JSONDecodeError:
            data = None

        if isinstance(
            data,
            dict,
        ):
            trafilatura_data = {
                "title": (
                    repair_mojibake(
                        data.get("title")
                    )
                    if data.get(
                        "title"
                    )
                    else None
                ),
                "url": clean_url(
                    data.get("url")
                    or fallback_url
                ),
                "published_at": (
                    data.get("date")
                ),
                "text": (
                    repair_mojibake(
                        data.get("text")
                    )
                    if data.get(
                        "text"
                    )
                    else None
                ),
            }

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    jsonld_data = (
        extract_jsonld_article(
            soup,
            fallback_url,
        )
    )

    html_title, html_date = (
        extract_html_metadata(
            soup
        )
    )

    body_candidates = []

    if trafilatura_data:
        body_candidates.append(
            trafilatura_data.get(
                "text"
            )
        )

    if jsonld_data:
        body_candidates.append(
            jsonld_data.get(
                "text"
            )
        )

    body_candidates = [
        text.strip()
        for text in body_candidates
        if isinstance(
            text,
            str,
        )
        and text.strip()
    ]

    article_element = soup.find(
        "article"
    )

    if article_element:
        paragraph_text = "\n".join(
            paragraph.get_text(
                " ",
                strip=True,
            )
            for paragraph
            in article_element.find_all(
                "p"
            )
            if len(
                paragraph.get_text(
                    " ",
                    strip=True,
                )
            ) >= 30
        ).strip()

        if paragraph_text:
            body_candidates.append(
                repair_mojibake(
                    paragraph_text
                )
            )

    if not body_candidates:
        return None

    text = max(
        body_candidates,
        key=len,
    )

    title = None
    published = None
    article_url = fallback_url

    if trafilatura_data:
        title = trafilatura_data.get(
            "title"
        )

        published = (
            trafilatura_data.get(
                "published_at"
            )
        )

        article_url = (
            trafilatura_data.get(
                "url"
            )
            or article_url
        )

    if jsonld_data:
        if not title:
            title = jsonld_data.get(
                "title"
            )

        if not published:
            published = (
                jsonld_data.get(
                    "published_at"
                )
            )

        if (
            article_url
            == fallback_url
        ):
            article_url = (
                jsonld_data.get(
                    "url"
                )
                or article_url
            )

    if not title:
        title = html_title

    if not published:
        published = html_date

    if not title:
        return None

    return {
        "title": repair_mojibake(
            title.strip()
        ),
        "url": clean_url(
            article_url
        ),
        "published_at": published,
        "text": repair_mojibake(
            text.strip()
        ),
    }


def normalize_date(value):
    if not value:
        return None

    parsed = dateparser.parse(
        str(value),
        languages=[
            "it",
            "en",
        ],
        settings={
            "RETURN_AS_TIMEZONE_AWARE":
            True,
            "TO_TIMEZONE":
            "UTC",
        },
    )

    if parsed is None:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=timezone.utc
        )

    return (
        parsed
        .astimezone(
            timezone.utc
        )
        .isoformat()
        .replace(
            "+00:00",
            "Z",
        )
    )


def article_age_hours(
    published_at,
):
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

    now = datetime.now(
        timezone.utc
    )

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


def article_is_fresh(
    published_at,
    max_age_hours,
):
    age_hours = article_age_hours(
        published_at
    )

    if age_hours is None:
        return (
            False,
            "unusable publication date",
        )

    if age_hours < -6:
        return (
            False,
            (
                "publication date is "
                "unexpectedly in the future"
            ),
        )

    if age_hours > max_age_hours:
        return (
            False,
            (
                f"stale article "
                f"({age_hours:.1f}h old, "
                f"limit {max_age_hours}h)"
            ),
        )

    return (
        True,
        "fresh",
    )


def clean_headline_for_topic_check(
    title,
):
    headline = re.sub(
        r"\s+",
        " ",
        title,
    ).strip()

    changed = True

    while changed:
        changed = False

        for pattern in (
            SITE_TITLE_SUFFIX_PATTERNS
        ):
            cleaned = re.sub(
                pattern,
                "",
                headline,
                flags=re.IGNORECASE,
            ).strip()

            if cleaned != headline:
                headline = cleaned
                changed = True

    return headline


def title_is_generic(title):
    cleaned = re.sub(
        r"\s+",
        " ",
        title.lower(),
    ).strip()

    if cleaned in GENERIC_PAGE_TERMS:
        return True

    return any(
        fragment in cleaned
        for fragment
        in BAD_TITLE_FRAGMENTS
    )


def title_is_non_football(title):
    cleaned = re.sub(
        r"\s+",
        " ",
        title.casefold(),
    ).strip()

    return any(
        fragment.casefold()
        in cleaned
        for fragment
        in NON_FOOTBALL_TITLE_FRAGMENTS
    )


def headline_contains_any(
    title,
    terms,
):
    headline = (
        clean_headline_for_topic_check(
            title
        )
        .casefold()
    )

    return any(
        str(term).casefold()
        in headline
        for term in terms
    )


def headline_has_football_roma_context(
    title,
):
    headline = (
        clean_headline_for_topic_check(
            title
        )
        .casefold()
    )

    if "roma" not in headline:
        return False

    roma_patterns = (
        r"\b[a-zà-ÿ]+-roma\b",
        r"\broma-[a-zà-ÿ]+\b",
        r"\bla roma\b",
        r"\bdella roma\b",
        r"\balla roma\b",
        r"\bcontro la roma\b",
    )

    if any(
        re.search(
            pattern,
            headline,
        )
        for pattern
        in roma_patterns
    ):
        return True

    return any(
        term in headline
        for term
        in GENERAL_FOOTBALL_CONTEXT
    )


def url_has_roma_football_context(
    url,
):
    parsed = urlparse(url)

    path = parsed.path.casefold()

    if any(
        fragment
        in path
        for fragment
        in STRONG_ROMA_URL_FRAGMENTS
    ):
        return True

    normalized = re.sub(
        r"[^a-zà-ÿ0-9]+",
        " ",
        path,
    )

    normalized = re.sub(
        r"\s+",
        " ",
        normalized,
    ).strip()

    words = normalized.split()

    if "roma" not in words:
        return False

    return any(
        term in normalized
        for term
        in GENERAL_FOOTBALL_CONTEXT
    )


def headline_matches_topic(
    title,
    url,
    keywords,
    entities,
    roma_focused,
):
    if roma_focused:
        if headline_contains_any(
            title,
            keywords,
        ):
            return True

        if headline_contains_any(
            title,
            entities,
        ):
            return True

        return False

    general_strong_keywords = [
        keyword
        for keyword in keywords
        if str(
            keyword
        ).casefold()
        != "roma"
    ]

    if headline_contains_any(
        title,
        general_strong_keywords,
    ):
        return True

    if headline_has_football_roma_context(
        title
    ):
        return True

    if url_has_roma_football_context(
        url
    ):
        return True

    return False


def generic_text_matches_topic(
    title,
    text,
    topic,
    keywords,
    entities,
):
    title_text = clean_headline_for_topic_check(
        title or ""
    ).casefold()

    body_text = re.sub(
        r"\\s+",
        " ",
        text or "",
    ).casefold()

    topic_terms = [
        value.strip()
        for value in re.split(
            r"[,;]",
            topic or "",
        )
        if value.strip()
    ]

    strong_terms = list(
        dict.fromkeys(
            [
                *topic_terms,
                *keywords,
                *entities,
            ]
        )
    )

    for term in strong_terms:
        normalized = str(term).strip().casefold()

        if not normalized:
            continue

        if normalized in title_text:
            return True

        if normalized in body_text:
            return True

    return False


def validate_article(
    article,
    keywords,
    entities,
    roma_focused,
    minimum_text_characters,
    max_age_hours,
    profile_slug="roma",
    topic="",
):
    title = article["title"]
    text = article["text"]
    url = article["url"]

    if not title:
        return (
            False,
            "missing title",
        )

    if len(title) < 12:
        return (
            False,
            "title too short",
        )

    if title_is_generic(
        title
    ):
        return (
            False,
            "generic/static/low-value title",
        )

    if (
        profile_slug == "roma"
        and title_is_non_football(
            title
        )
    ):
        return (
            False,
            "non-football headline",
        )

    if len(text) < (
        minimum_text_characters
    ):
        return (
            False,
            (
                "text too short "
                f"({len(text)} chars)"
            ),
        )

    if not article[
        "published_at"
    ]:
        return (
            False,
            "no usable publication date",
        )

    fresh, freshness_reason = (
        article_is_fresh(
            article[
                "published_at"
            ],
            max_age_hours,
        )
    )

    if not fresh:
        return (
            False,
            freshness_reason,
        )

    if profile_slug == "roma":
        relevant = headline_matches_topic(
            title=title,
            url=url,
            keywords=keywords,
            entities=entities,
            roma_focused=roma_focused,
        )
        relevance_reason = (
            "headline/URL not Roma-related"
        )
    else:
        relevant = generic_text_matches_topic(
            title=title,
            text=text,
            topic=topic,
            keywords=keywords,
            entities=entities,
        )
        relevance_reason = (
            "article not profile-related"
        )

    if not relevant:
        return (
            False,
            relevance_reason,
        )

    return (
        True,
        "valid",
    )


def fetch(
    session,
    url,
    timeout,
):
    response = session.get(
        url,
        timeout=timeout,
        allow_redirects=True,
    )

    response.raise_for_status()

    declared = (
        response.encoding
        or ""
    ).casefold()

    if declared in (
        "",
        "iso-8859-1",
        "latin-1",
    ):
        detected = (
            response.apparent_encoding
        )

        if detected:
            response.encoding = (
                detected
            )

    return repair_mojibake(
        response.text
    )


def collect_source(
    source,
    session,
    keywords,
    entities,
    max_articles,
    max_candidates,
    minimum_text_characters,
    max_age_hours,
    timeout,
    delay,
    max_fetches=None,
    max_source_runtime_seconds=None,
    profile_slug="roma",
    topic="",
):
    name = source["name"]
    source_deadline = (
        time.monotonic() + max_source_runtime_seconds
        if max_source_runtime_seconds is not None
        else None
    )

    listing_url = source[
        "listing_url"
    ]

    roma_focused = source.get(
        "roma_focused",
        False,
    )

    print()
    print(
        f"=== {name} ==="
    )

    print(
        f"Listing: {listing_url}"
    )

    print(
        "Source context: "
        + (
            "Roma-focused"
            if roma_focused
            else "general"
        )
    )

    print(
        "Freshness limit: "
        f"{max_age_hours}h"
    )

    try:
        listing_html = fetch(
            session,
            listing_url,
            timeout,
        )

    except requests.RequestException as exc:
        print(
            "FAILED listing request: "
            f"{exc}"
        )

        return []

    candidates = discover_links(
        listing_html,
        listing_url,
        max_candidates,
    )

    print(
        "Candidate links discovered: "
        f"{len(candidates)}"
    )

    results = []
    fetched_count = 0
    consecutive_stale = 0
    stale_stop_limit = source.get(
        "stop_after_consecutive_stale"
    )

    for number, candidate in enumerate(
        candidates,
        start=1,
    ):
        if (
            source_deadline is not None
            and time.monotonic() >= source_deadline
        ):
            print(
                "      stopping source: "
                f"runtime budget "
                f"{max_source_runtime_seconds}s reached"
            )
            break

        if len(results) >= max_articles:
            break

        url = candidate["url"]
        score = candidate["score"]

        print(
            f"  [{number}/"
            f"{len(candidates)}] "
            f"score={score} "
            f"{url}"
        )

        if not roma_focused:
            anchor_text = candidate["anchor_text"]

            if profile_slug == "roma":
                listing_relevant = headline_matches_topic(
                    title=anchor_text,
                    url=url,
                    keywords=keywords,
                    entities=entities,
                    roma_focused=False,
                )
                listing_reason = (
                    "listing headline/URL not Roma-related"
                )
            else:
                listing_relevant = (
                    generic_text_matches_topic(
                        title=anchor_text,
                        text="",
                        topic=topic,
                        keywords=keywords,
                        entities=entities,
                    )
                )
                listing_reason = (
                    "listing headline not profile-related"
                )

            if not listing_relevant:
                print(
                    "      skipped before fetch: "
                    + listing_reason
                )
                continue

        if (
            max_fetches is not None
            and fetched_count >= max_fetches
        ):
            print(
                "      stopping source: "
                f"fetch budget {max_fetches} reached"
            )
            break

        try:
            html = fetch(
                session,
                url,
                timeout,
            )
            fetched_count += 1

        except requests.RequestException as exc:
            print(
                "      request failed: "
                f"{exc}"
            )

            continue

        article = extract_article(
            html,
            url,
        )

        if article is None:
            print(
                "      rejected: "
                "extraction failed"
            )

            continue

        article[
            "published_at"
        ] = normalize_date(
            article[
                "published_at"
            ]
        )

        valid, reason = (
            validate_article(
                article=article,
                keywords=keywords,
                entities=entities,
                roma_focused=(
                    roma_focused
                ),
                minimum_text_characters=(
                    minimum_text_characters
                ),
                max_age_hours=(
                    max_age_hours
                ),
                profile_slug=profile_slug,
                topic=topic,
            )
        )

        if not valid:
            print(
                "      rejected: "
                f"{reason}"
            )

            if reason.startswith("stale article"):
                consecutive_stale += 1

                if (
                    stale_stop_limit
                    and consecutive_stale
                    >= stale_stop_limit
                ):
                    print(
                        "      stopping source: "
                        f"{consecutive_stale} consecutive "
                        "stale articles"
                    )
                    break
            else:
                consecutive_stale = 0

            continue

        consecutive_stale = 0
        article["source"] = name

        results.append(
            article
        )

        print(
            "      ACCEPTED: "
            f'{article["title"]}'
        )

        time.sleep(
            delay
        )

    print(
        f"{name}: collected "
        f"{len(results)} "
        "valid article(s)"
    )

    print(
        f"SOURCE WORK: {name}: "
        f"candidates={len(candidates)} "
        f"fetched={fetched_count} "
        f"accepted={len(results)}"
    )

    return results


def remove_duplicate_urls(
    articles,
):
    output = []
    seen = set()

    for article in articles:
        url = article["url"]

        if url in seen:
            continue

        seen.add(url)

        output.append(
            article
        )

    return output



def load_profile_definition(
    profile_slug,
    db_path="/config/home-ai-news.db",
):
    try:
        db = sqlite3.connect(
            f"file:{db_path}?mode=ro",
            uri=True,
        )
        db.row_factory = sqlite3.Row

        profile = db.execute(
            """
            SELECT
                id,
                slug,
                name,
                enabled,
                topic,
                maximum_age_hours,
                telegram_enabled
            FROM profiles
            WHERE slug = ?
            """,
            (profile_slug,),
        ).fetchone()

        if profile is None:
            db.close()
            return None

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

        entities = [
            row["entity"]
            for row in db.execute(
                """
                SELECT entity
                FROM profile_entities
                WHERE profile_id = ?
                ORDER BY rowid
                """,
                (profile["id"],),
            ).fetchall()
        ]

        result = {
            "id": profile["id"],
            "slug": profile["slug"],
            "name": profile["name"],
            "enabled": bool(profile["enabled"]),
            "topic": profile["topic"] or "",
            "maximum_age_hours": profile["maximum_age_hours"],
            "telegram_enabled": bool(
                profile["telegram_enabled"]
            ),
            "keywords": keywords,
            "entities": entities,
        }

        db.close()
        return result

    except sqlite3.Error as exc:
        print(
            "PROFILE CONFIG DB unavailable: "
            f"{exc}"
        )
        return None


def load_profile_budgets(
    db_path="/config/home-ai-news.db",
    profile_slug="roma",
):
    try:
        db = sqlite3.connect(
            f"file:{db_path}?mode=ro",
            uri=True,
        )
        row = db.execute(
            """
            SELECT
                max_total_collection_seconds,
                max_total_requests,
                max_total_articles,
                max_llm_calls
            FROM profiles
            WHERE slug = ?
            """,
            (profile_slug,),
        ).fetchone()
        db.close()
    except sqlite3.Error as exc:
        print(
            "PROFILE BUDGET DB unavailable; "
            f"using unlimited defaults: {exc}"
        )
        return {}

    if row is None:
        return {}

    return {
        "max_total_collection_seconds": row[0],
        "max_total_requests": row[1],
        "max_total_articles": row[2],
        "max_llm_calls": row[3],
    }


def load_ui_sources(
    db_path="/config/home-ai-news.db",
    profile_slug="roma",
):
    try:
        db = sqlite3.connect(
            f"file:{db_path}?mode=ro",
            uri=True,
        )
        rows = db.execute(
            """
            SELECT
                s.name,
                ps.enabled,
                ps.collector_type,
                ps.listing_url,
                ps.topic_focused,
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
            """,
            (profile_slug,),
        ).fetchall()
        db.close()
    except sqlite3.Error as exc:
        print(
            "SOURCE CONFIG DB unavailable; "
            f"using YAML source membership: {exc}"
        )
        return []

    sources = []

    for row in rows:
        (
            name,
            enabled,
            collector_type,
            listing_url,
            topic_focused,
            max_candidates,
            max_fetches,
            request_timeout_seconds,
            max_source_runtime_seconds,
            stop_after_consecutive_stale,
            validation_status,
        ) = row

        if not enabled:
            continue

        if validation_status not in ("PASS", "WARNING"):
            continue

        if collector_type != "web":
            continue

        if not listing_url:
            continue

        sources.append(
            {
                "name": name,
                "enabled": True,
                "collector": collector_type,
                "listing_url": listing_url,
                "roma_focused": bool(topic_focused),
                "max_candidates": max_candidates,
                "max_fetches": max_fetches,
                "request_timeout_seconds": request_timeout_seconds,
                "max_source_runtime_seconds": max_source_runtime_seconds,
                "stop_after_consecutive_stale": stop_after_consecutive_stale,
            }
        )

    return sources


def load_source_budgets(
    db_path="/config/home-ai-news.db",
    profile_slug="roma",
):
    try:
        db = sqlite3.connect(
            f"file:{db_path}?mode=ro",
            uri=True,
        )
        rows = db.execute(
            """
            SELECT
                s.name,
                ps.enabled,
                ps.max_candidates,
                ps.max_fetches,
                ps.request_timeout_seconds,
                ps.max_source_runtime_seconds,
                ps.stop_after_consecutive_stale
            FROM profile_sources ps
            JOIN profiles p
              ON p.id = ps.profile_id
            JOIN sources s
              ON s.id = ps.source_id
            WHERE p.slug = ?
            """,
            (profile_slug,),
        ).fetchall()
        db.close()
    except sqlite3.Error as exc:
        print(
            "SOURCE BUDGET DB unavailable; "
            f"using YAML defaults: {exc}"
        )
        return {}

    return {
        row[0].casefold(): {
            "enabled": bool(row[1]),
            "max_candidates": row[2],
            "max_fetches": row[3],
            "request_timeout_seconds": row[4],
            "max_source_runtime_seconds": row[5],
            "stop_after_consecutive_stale": row[6],
        }
        for row in rows
    }


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Collect AS Roma news "
            "from configured sources"
        )
    )

    parser.add_argument(
        "--profile",
        default="roma",
        help=(
            "Profile slug. "
            "Defaults to roma for compatibility."
        ),
    )

    parser.add_argument(
        "--config",
        default=(
            "profiles/"
            "roma_sources.yaml"
        ),
        help=(
            "Collector YAML "
            "configuration"
        ),
    )

    parser.add_argument(
        "--output",
        default=(
            "real_articles.json"
        ),
        help="Output JSON file",
    )

    parser.add_argument(
        "--max-per-source",
        type=int,
        default=None,
        help=(
            "Override maximum VALID "
            "articles per source"
        ),
    )

    parser.add_argument(
        "--source",
        action="append",
        default=[],
        help=(
            "Run only the named source. "
            "May be specified more than once."
        ),
    )

    parser.add_argument(
        "--max-fetches",
        type=int,
        default=None,
        help=(
            "Override maximum article pages "
            "fetched per source"
        ),
    )

    args = parser.parse_args()

    config = load_yaml(
        args.config
    )

    profile = load_profile_definition(
        args.profile
    )

    if profile is None:
        parser.error(
            f"Unknown or unavailable profile: {args.profile}"
        )

    print(
        "PROFILE: "
        f'{profile["name"]} '
        f'({profile["slug"]})'
    )
    print(
        "PROFILE STATE: "
        f'enabled={profile["enabled"]} '
        f'telegram={profile["telegram_enabled"]}'
    )

    request_config = config[
        "request"
    ]

    collection_config = config[
        "collection"
    ]

    timeout = request_config[
        "timeout_seconds"
    ]

    delay = request_config[
        "delay_seconds"
    ]

    max_articles = (
        args.max_per_source
        if args.max_per_source
        is not None
        else collection_config[
            "max_articles_per_source"
        ]
    )

    max_candidates = (
        collection_config[
            "max_candidates_per_source"
        ]
    )

    minimum_text_characters = (
        collection_config[
            "minimum_text_characters"
        ]
    )

    max_age_hours = (
        collection_config.get(
            "max_age_hours",
            DEFAULT_MAX_AGE_HOURS,
        )
    )

    keywords = profile["keywords"]
    entities = profile["entities"]
    topic = profile["topic"]

    if profile["maximum_age_hours"] is not None:
        max_age_hours = profile[
            "maximum_age_hours"
        ]

    print(
        "PROFILE TOPIC: "
        f"{topic}"
    )
    print(
        "PROFILE KEYWORDS: "
        + ", ".join(keywords)
    )
    print(
        "PROFILE ENTITIES: "
        + (
            ", ".join(entities)
            if entities
            else "(none)"
        )
    )

    requested_sources = {
        name.casefold()
        for name in args.source
    }

    effective_sources = []

    yaml_source_names = {
        source["name"].casefold()
        for source in effective_sources
    }

    for ui_source in load_ui_sources(
        profile_slug=args.profile
    ):
        if (
            ui_source["name"].casefold()
            not in yaml_source_names
        ):
            effective_sources.append(
                ui_source
            )
            print(
                f'SOURCE DISCOVERY: {ui_source["name"]} '
                f'added from SQLite/UI'
            )

    if requested_sources:
        available_sources = {
            source["name"].casefold()
            for source
            in effective_sources
        }

        unknown_sources = (
            requested_sources
            - available_sources
        )

        if unknown_sources:
            parser.error(
                "Unknown source(s): "
                + ", ".join(
                    sorted(
                        unknown_sources
                    )
                )
            )

    source_budgets = load_source_budgets(
        profile_slug=args.profile
    )
    profile_budgets = load_profile_budgets(
        profile_slug=args.profile
    )
    profile_started = time.monotonic()

    session = requests.Session()

    session.headers.update(
        {
            "User-Agent": (
                request_config[
                    "user_agent"
                ]
            ),
            "Accept": (
                "text/html,"
                "application/xhtml+xml,"
                "application/xml;q=0.9,"
                "*/*;q=0.8"
            ),
        }
    )

    all_articles = []

    for source in effective_sources:
        profile_runtime_limit = profile_budgets.get(
            "max_total_collection_seconds"
        )
        if (
            profile_runtime_limit is not None
            and time.monotonic() - profile_started
            >= profile_runtime_limit
        ):
            print(
                "PROFILE STOP: collection runtime budget "
                f"{profile_runtime_limit}s reached"
            )
            break

        profile_article_limit = profile_budgets.get(
            "max_total_articles"
        )
        if (
            profile_article_limit is not None
            and len(all_articles) >= profile_article_limit
        ):
            print(
                "PROFILE STOP: article budget "
                f"{profile_article_limit} reached"
            )
            break

        if (
            requested_sources
            and source[
                "name"
            ].casefold()
            not in requested_sources
        ):
            continue

        source_overlay = source_budgets.get(
            source["name"].casefold(),
            {},
        )

        yaml_enabled = source.get(
            "enabled",
            False,
        )

        effective_enabled = source_overlay.get(
            "enabled",
            yaml_enabled,
        )

        if (
            "enabled" in source_overlay
            and effective_enabled != yaml_enabled
        ):
            print(
                f'SOURCE STATE: {source["name"]} '
                f'enabled={effective_enabled} '
                f'(SQLite override; YAML={yaml_enabled})'
            )

        if not effective_enabled:
            reason = source.get(
                "reason",
                "disabled",
            )

            print()
            print(
                f'SKIPPED '
                f'{source["name"]}: '
                f'{reason}'
            )

            continue

        if source.get(
            "collector"
        ) != "web":
            collector_type = (
                source.get(
                    "collector"
                )
            )

            print()
            print(
                f'SKIPPED '
                f'{source["name"]}: '
                f'collector type '
                f'{collector_type} '
                f'is not implemented'
            )

            continue

        budget = source_budgets.get(
            source["name"].casefold(),
            {},
        )

        source_max_candidates = (
            budget.get("max_candidates")
            if budget.get("max_candidates") is not None
            else max_candidates
        )

        source_max_fetches = (
            args.max_fetches
            if args.max_fetches is not None
            else budget.get("max_fetches")
        )

        source_timeout = (
            budget.get("request_timeout_seconds")
            if budget.get("request_timeout_seconds") is not None
            else timeout
        )

        if (
            budget.get("stop_after_consecutive_stale")
            is not None
        ):
            source = dict(source)
            source["stop_after_consecutive_stale"] = (
                budget["stop_after_consecutive_stale"]
            )

        source_started = time.monotonic()

        articles = collect_source(
            source=source,
            session=session,
            keywords=keywords,
            entities=entities,
            max_articles=max_articles,
            max_candidates=source_max_candidates,
            minimum_text_characters=(
                minimum_text_characters
            ),
            max_age_hours=(
                max_age_hours
            ),
            timeout=source_timeout,
            delay=delay,
            max_fetches=source_max_fetches,
            max_source_runtime_seconds=(
                budget.get("max_source_runtime_seconds")
            ),
            profile_slug=args.profile,
            topic=topic,
        )

        source_elapsed = (
            time.monotonic()
            - source_started
        )

        print(
            f'SOURCE TIMING: {source["name"]}: '
            f'{source_elapsed:.2f}s'
        )

        profile_article_limit = profile_budgets.get(
            "max_total_articles"
        )
        if profile_article_limit is not None:
            remaining = max(
                0,
                profile_article_limit - len(all_articles),
            )
            all_articles.extend(
                articles[:remaining]
            )
        else:
            all_articles.extend(
                articles
            )

    all_articles = (
        remove_duplicate_urls(
            all_articles
        )
    )

    with open(
        args.output,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            all_articles,
            file,
            ensure_ascii=False,
            indent=2,
        )

    print()
    print(
        "=============================="
    )
    print(
        "Collected valid articles: "
        f"{len(all_articles)}"
    )
    print(
        f"Output: {args.output}"
    )
    print(
        "=============================="
    )


if __name__ == "__main__":
    main()

