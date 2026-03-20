# rss-research

Deep research briefings delivered as RSS feeds.

## How It Works

- `config.yaml` defines topics in plain English
- `@research` agent searches, synthesizes, and writes RSS entries
- `feed.py` handles RSS XML generation and dedup state
- Output goes to `feeds/*.xml` — standard RSS 2.0, works with any reader

## Usage

Run the research cycle by invoking the agent:

```
@research
```

Or for headless/cron use:

```bash
claude -p "@research run the research cycle"
```

## feed.py Reference

```bash
python feed.py init <feed_id> --name "..." --description "..."
python feed.py add <feed_id> --title "..." --content "<p>...</p>" --sources "url1,url2"
python feed.py prune <feed_id> --keep 30
python feed.py list <feed_id>
python feed.py state <feed_id>
```
