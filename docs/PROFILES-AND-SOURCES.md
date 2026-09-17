# Profiles and sources

The web UI and SQLite database form the News 4 Legends control plane. Do not configure profiles in Python, n8n, or `collector.yaml`.

## Profile lifecycle

1. Create a profile with a unique name and slug.
2. Describe the topic precisely.
3. Add keywords and named entities that distinguish relevant coverage.
4. Choose freshness, clustering, collection, and LLM budgets.
5. Add sources and validate each one.
6. Enable acceptable sources.
7. Enable the profile.

The next bodyless `/run` automatically discovers it. Disabling a profile excludes it; no workflow edit is necessary.

## Settings

| Setting | Meaning |
| --- | --- |
| Minimum source score | Lowest user-defined weight accepted by the pipeline |
| Maximum age | Oldest acceptable article |
| Similarity threshold | Jaccard title-similarity threshold from 0 to 1; higher requires closer titles |
| LLM enabled/limit | Whether and how many top stories receive synthesis |
| Collection budgets | Caps for total time, requests, articles, and LLM calls |
| Telegram enabled | Profile-level compact delivery rendering preference |
| Email theme | Deterministic theme or explicit override |

Use conservative limits first. Increase one budget at a time after observing a successful run.

## Keywords and entities

Keywords are topic terms; entities are important names such as organizations, people, products, competitions, or locations. Prefer distinctive terms. Generic words create noise, while an excessively narrow set can eliminate relevant stories. Test changes with a controlled run.

## Source model

A base source has a name. Its relationship to a profile contains the operational settings: collector type, listing URL, topic-focused flag, weight, source type, candidate/fetch/time limits, stale-stop threshold, validation state, and enablement. Therefore one named source can be configured differently per profile.

Use a category/listing page that exposes recent article links, not an individual article URL. The public collector currently accepts enabled `web` sources whose validation state is `PASS` or `WARNING`.

## Weighting is a preference

Credibility/weight is user-defined prioritization. It can express personal trust, relevance, or importance, but it does not objectively measure truth. A high score cannot correct a false article, and a low score does not prove unreliability.

## Validate before enabling

The bounded preflight fetches the listing page, discovers candidate links, and samples a few articles.

| Result | Interpretation | Action |
| --- | --- | --- |
| `PASS` | Bounded discovery and sample extraction succeeded | Review details, then enable |
| `WARNING` | Partial extraction or a discovery limit was reached | Inspect failures and decide deliberately |
| `FAIL` | Listing or sample extraction did not work | Fix URL/access or choose another source |

Validation is a technical extraction check, not an editorial endorsement. A site can later change markup, block automated requests, or return stale/irrelevant content.

## Editing behavior

The UI supports `Validate | Edit | Disable | Delete`. Editable settings include collector type, listing URL, topic focus, weight, candidates, fetches, request timeout, source runtime, and stale-stop count.

Changing `collector_type` or `listing_url` disables the source and clears its prior validation because the extraction target materially changed. Revalidate, review, and re-enable it. Other edits preserve validation/enablement when appropriate.

## Theme behavior

Themes include Auto, Burgundy & Gold, Navy & Cyan, Emerald, Purple, Orange, and Monochrome. Auto is deterministic code. Known profile types may map to a built-in palette; unknown subjects use the neutral News 4 Legends theme. No extra LLM request chooses colors.

## Safe tuning sequence

1. Start with one profile and one or two sources.
2. Validate sources.
3. Run manually and inspect article count and relevance.
4. Adjust topic terms before increasing collection budgets.
5. Tune maximum age.
6. Tune similarity threshold if unrelated stories merge or duplicates remain split.
7. Increase LLM limit only after collection quality is acceptable.
8. Add further profiles after the first behaves predictably.

Avoid starting simultaneous manual runs; check `docker top news4legends-worker -eo pid,ppid,etime,stat,cmd` first.

## Data ownership and deletion

Profile deletion cascades to its keyword, entity, and source relationships. A source name may still be used by another profile. Back up SQLite before large changes. See [Backup and restore](BACKUP-RESTORE.md).

