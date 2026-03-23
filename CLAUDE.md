# cc-deepfeed

Deep research briefings delivered as RSS feeds, powered by Claude Code.

## How It Works

- Single `config.yaml` defines global topics and user feeds
- Topics are global — each defined once with name, target, depth, model
- Feeds are per-user — each subscribes to a set of topics
- `@research` orchestrator spawns parallel workers (one per topic)
- `feed.py add` automatically distributes entries to all subscriber feeds
- `publish.sh` pushes to GitHub Pages (gh-pages branch) and pings WebSub hub (if configured)

## Architecture

- **Topics + Feeds:** `config.yaml` has a `topics` section (global topic definitions) and a `feeds` section (per-user feed subscriptions). Topics are researched once; entries are auto-distributed to all subscriber feeds.
- **Orchestrator + Workers:** `@research` is a thin Sonnet orchestrator that spawns parallel `research-worker` agents (one per topic). Workers do the actual research/writing on Opus (or Sonnet for factual topics via the `model` field).
- **File locking:** `feed.py` uses `fcntl.flock` to safely handle concurrent XML writes from parallel workers.
- **Per-topic targets:** Each topic has a `target` field specifying how many entries to aim for per run.
- **Model selection:** Each topic can set `model: sonnet` for cheaper factual work; defaults to Opus.
- **Bilingual entries:** Topics can set `bilingual: <lang>` to produce entries in the primary language first, with a translation appended. Useful when the reader's expertise domain is in a different language than their preferred reading language.
- **WebSub:** Optional. Set `websub_hub` in config settings. `publish.sh` pings the hub for all XMLs after each push.
- **Scheduling:** See `docs/scheduling.md` for launchd, cron, and systemd templates.
- **Remote:** Uses SSH (`git@github.com:...`) for auth in headless/cron contexts.

## Usage

Run the research cycle by invoking the agent:

```
@research                    # all topics, all feeds
@research ai-research        # single topic
@research --dry-run          # preview without writing
```

Or for headless/cron use:

```bash
claude -p "@research run the research cycle"
```

## Configuration

Copy `config.example.yaml` to `config.yaml` and customize. Full schema in `docs/config-reference.md`.

Each topic needs a brief file at `.claude/agents/topics/<id>.md`. See `_template.md` for the format.

## feed.py Reference

```bash
# Core
python feed.py init                    # init all feed XMLs from config
python feed.py add <topic_id> --title "..." --content "<p>...</p>" --sources "url1,url2" --image "https://..." --run-id "..."
python feed.py prune --keep 50        # prune all feed XMLs
python feed.py list <topic_id>
python feed.py state <topic_id>

# Knowledge
python feed.py knowledge <topic_id>
python feed.py learn <topic_id> --brief "..." --entities "e1,e2" --threads '<json>'

# Operations
python feed.py status                  # shows all topics + feeds
python feed.py rollback <topic_id>     # rollback from all subscriber feeds
python feed.py log <topic_id> --started "..." --finished "..." --entries-added 4

# Discoverability
python feed.py opml --base-url "https://..."
python feed.py index-html --base-url "https://..."
```
