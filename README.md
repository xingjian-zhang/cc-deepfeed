# rss-research

Deep research briefings delivered as RSS feeds, powered by Claude Code.

## What You Get

Open your RSS reader and see entries like:

> **Anthropic's RLHF-v3 shows 40% reduction in reward hacking**
>
> Anthropic published results from their third-generation RLHF pipeline, targeting the reward hacking problem that has limited deployment of RL-tuned models. The key technique is a dual-critic architecture where a second reward model acts as a check on the primary reward signal. Compared to DeepMind's constrained optimization approach from last month, this trades less helpfulness for better safety coverage...
>
> **Sources:** [Anthropic blog](url) · [arXiv paper](url)

Not a link aggregator. Not a summarizer. Each entry is a **research briefing** — it explains what happened, why it matters, and how it connects to the bigger picture.

## Setup

**Prerequisites:** Python 3.9+, [PyYAML](https://pypi.org/project/PyYAML/), [Claude Code](https://docs.anthropic.com/en/docs/claude-code)

```bash
git clone https://github.com/yourusername/rss-research.git
cd rss-research
pip install pyyaml
cp config.example.yaml config.yaml   # edit with your topics
```

## Config

Describe your interests in plain English:

```yaml
settings:
  feeds_dir: ./feeds
  state_dir: ./.state
  max_entries: 30

feeds:
  - id: rl-agents
    name: "RL Agents Research"
    description: |
      Latest research on reinforcement learning for autonomous agents.
      Focus on: new papers, open-source implementations, benchmark results.
      Skip: product announcements, beginner tutorials, hype pieces.
    depth: deep        # quick (~200w) | standard (~400w) | deep (~600-800w)
```

No keyword arrays or structured filters. Just describe what you care about, including what to skip.

## Usage

### Manual run

```bash
claude -p "Run research cycle"
```

### Automate with cron

```bash
crontab -e
# Run daily at 8:03 AM
3 8 * * * cd ~/rss-research && claude -p "Run research cycle"
```

Every run researches all topics. Control frequency via cron — one knob, not two.

### First run

The first time a topic runs, it generates a **landscape briefing** — an overview of the current state of the field. Subsequent runs focus only on what's new.

## Reading Your Feeds

**Local file** (some readers support this):
```
file:///path/to/rss-research/feeds/rl-agents.xml
```

**Local HTTP server:**
```bash
python -m http.server 8080 -d feeds/
# Then add http://localhost:8080/rl-agents.xml to your reader
```

**Any static host** — S3, Netlify, rsync to a VPS, etc.

## How It Works

1. Claude reads `config.yaml` for your topic definitions
2. Checks `.state/<feed-id>.json` to know what's already been reported
3. Searches the web from multiple angles per topic
4. Cross-references and synthesizes findings into briefings
5. Writes entries via `feed.py` (handles RSS XML, dedup, pruning)
6. Updates state so the next run knows what's been covered

`feed.py` is a small CLI helper (~150 lines) that keeps Claude from writing raw XML. Everything else — the research, synthesis, and writing — is Claude Code doing what it does.

## feed.py Reference

```bash
python feed.py init <feed_id> --name "..." --description "..."
python feed.py add <feed_id> --title "..." --content "<p>...</p>" --sources "url1,url2"
python feed.py prune <feed_id> --keep 30
python feed.py list <feed_id>
python feed.py state <feed_id>    # raw JSON for debugging
```

## Project Structure

```
rss-research/
├── README.md
├── CLAUDE.md              # Research + quality instructions for Claude
├── config.example.yaml    # Copy and customize
├── feed.py                # RSS XML helper
├── feeds/                 # Output XML files (gitignored)
└── .state/                # Dedup state (gitignored)
```

## License

MIT
