# Getting Started

A complete walkthrough from clone to first published feed.

## Prerequisites

You need all of the following before starting:

- **Python 3.9+** — [python.org/downloads](https://www.python.org/downloads/) or `brew install python` on macOS
- **PyYAML** — `pip install pyyaml` (the only Python dependency)
- **Claude Code** — Anthropic's CLI tool. [Install here](https://docs.anthropic.com/en/docs/claude-code). Requires a Claude Pro ($20/mo) or Max ($100/mo) subscription.
- **Git** — for publishing feeds to GitHub Pages
- **GNU timeout** — included on Linux; on macOS: `brew install coreutils`
- **An RSS reader** — you need somewhere to read the feeds this project produces. Some options:
  - [Reeder](https://reederapp.com) — macOS, iOS (paid, polished)
  - [NetNewsWire](https://netnewswire.com) — macOS, iOS (free, open source)
  - [Feedly](https://feedly.com) — web, mobile (free tier available)
  - [Inoreader](https://inoreader.com) — web, mobile (free tier available)

## Clone and Install

```bash
git clone https://github.com/xingjian-zhang/cc-deepfeed.git
cd cc-deepfeed
pip install pyyaml
```

Note: `config.yaml` and custom topic briefs are gitignored — your personal configuration stays local.

## Quick Setup with `/setup`

The recommended way to get started is the interactive setup wizard. Open Claude Code in the project directory and run:

```
/setup
```

This checks your environment, creates your config, helps you write topic briefs, and initializes your feeds — all interactively.

If you prefer to set up manually, follow the sections below.

## Manual Setup

### Understanding config.yaml

Copy the example config:

```bash
make setup    # or: cp config.example.yaml config.yaml
```

Open `config.yaml`. It has three sections:

**settings** — global configuration:

```yaml
settings:
  feeds_dir: ./feeds              # where XML files are written
  state_dir: ./.state             # where per-topic state is stored
  max_entries: 50                 # per feed, oldest pruned automatically
  base_url: "https://yourusername.github.io/cc-deepfeed"  # CHANGE THIS
  # websub_hub: "https://pubsubhubbub.appspot.com"        # uncomment for instant reader updates
```

`base_url` is the most important setting — it's the public URL where your feeds will be hosted. If you're using GitHub Pages, it's `https://<username>.github.io/<repo-name>`.

**topics** — what to research (global, defined once):

```yaml
topics:
  - id: ai-research               # must match a brief file in .claude/agents/topics/
    name: "AI Research Highlights" # display name in the feed
    depth: deep                    # quick (~200w) | standard (~400w) | deep (~600-800w)
    language: en                   # en or zh
    target: 3                      # mandatory entries per research cycle
```

Optional topic fields:
- `model: sonnet` — use the cheaper Sonnet model (default: Opus). Good for factual/news topics.
- `bilingual: zh` — append a translation in the specified language after each entry.

**feeds** — personalized RSS feeds that subscribe to topics:

```yaml
feeds:
  - id: my-feed
    combined_feed: daily-briefings       # becomes feeds/daily-briefings.xml
    feed_name: "My Research Feed"
    feed_description: "Deep research briefings powered by Claude"
    topics: [ai-research, world-news]    # subscribe to any topic IDs
```

A topic is researched once per cycle. Entries are automatically distributed to every feed that subscribes to that topic. You can have multiple feeds with different topic combinations — for example, one for yourself and one for a colleague.

See the [full config reference](config-reference.md) for all options.

### Writing Your First Topic Brief

Each topic needs a matching brief file at `.claude/agents/topics/<id>.md`. The brief tells the research worker what to cover, what to skip, and how to write.

Start from the template:

```bash
cp .claude/agents/topics/_template.md .claude/agents/topics/my-topic.md
```

The brief has four sections:

**Scope** — what to cover. Be specific about sub-areas of interest:
```markdown
## Scope
- Latest research papers on reinforcement learning
- Open-source model releases with technical details
- New benchmark results and methodology comparisons
```

**Skip** — what to exclude. Keeps the worker focused:
```markdown
## Skip
- Product launch announcements without technical substance
- Funding/hiring news
- Opinion pieces and hype content
```

**Research Strategy** (optional) — special instructions for how to research:
```markdown
## Research Strategy
- Check arXiv for new preprints in cs.AI, cs.LG
- Cross-reference claims with at least 2 sources
```

**Writing Style** — tone, structure, and depth target:
```markdown
## Writing Style
**Target: 600-800 words per entry.**
- Write like a knowledgeable colleague explaining something interesting
- Structure: problem, key insight, method, results, implications
- Include concrete numbers and comparisons
```

See the included [ai-research.md](.claude/agents/topics/ai-research.md) example for a complete brief.

> **Tip:** You can ask Claude Code to help you write a brief — describe your interests and it will draft one for you.

### First Research Cycle

Start by testing a single topic to verify everything works:

```bash
make run-topic TOPIC=ai-research
```

This spawns one Claude worker that researches the topic, writes entries, and adds them to your feed. It typically takes 5-10 minutes.

Check the results:

```bash
make status    # dashboard of all topics and feeds
```

You should see entries listed under your topic. The feed XML is in `feeds/<combined_feed>.xml`.

Once you're satisfied, run all topics:

```bash
make run
```

This spawns one worker per topic in parallel. The orchestrator checks if all targets were met and retries any shortfalls.

### Publishing to GitHub Pages

1. Go to your GitHub repo **Settings > Pages**
2. Set Source to **Deploy from a branch**
3. Set Branch to **gh-pages**, root **/**
4. Save

The `gh-pages` branch is created automatically on first publish — you don't need to create it manually.

Publish your feeds:

```bash
make publish
```

This generates `index.html` and OPML, pushes to `gh-pages`, and pings the WebSub hub if configured.

> The research orchestrator (`make run`) publishes automatically after each cycle, so you only need `make publish` for manual runs.

See the [Publishing Guide](publishing.md) for alternatives (S3, rsync, local testing).

### Subscribing in Your RSS Reader

Your feed URL is:

```
https://<your-base-url>/<combined_feed>.xml
```

For example: `https://yourusername.github.io/cc-deepfeed/daily-briefings.xml`

Add this URL in your RSS reader. If you have multiple feeds, you can import them all at once using the OPML file at `<base_url>/index.opml`.

For instant updates (no polling delay), enable WebSub by uncommenting `websub_hub` in your config. This works with Feedly, Inoreader, and other readers that support WebSub.

## Scheduling Recurring Runs

To get daily briefings, schedule the research cycle to run automatically. The entry point is `run-research.sh`.

Quick examples:

**macOS launchd** (recommended for Mac):
```bash
# See docs/scheduling.md for the full plist template
```

**Linux cron:**
```bash
7 9 * * * cd /path/to/cc-deepfeed && bash run-research.sh
```

**Linux systemd:**
```bash
# See docs/scheduling.md for service + timer templates
```

### Environment Variables

`run-research.sh` uses these env vars with platform-specific defaults:

| Variable | Default | Notes |
|----------|---------|-------|
| `CLAUDE_BIN` | `claude` | Path to Claude Code CLI |
| `PYTHON` | `/opt/homebrew/Caskroom/miniforge/base/bin/python3` | Path to Python 3. Set this if your Python is elsewhere. |
| `TIMEOUT_BIN` | `/opt/homebrew/bin/timeout` | Path to GNU timeout. Linux: `timeout`. macOS without Homebrew: install via `brew install coreutils`. |
| `WORKER_TIMEOUT` | `900` | Seconds per worker (15 min). Increase for topics with many targets. |

If you're on Linux or your tools are in different locations, set these in your shell profile or cron environment:

```bash
export PYTHON=$(which python3)
export TIMEOUT_BIN=$(which timeout)
```

See the [Scheduling Guide](scheduling.md) for complete templates.

## What `.state/` Contains

Each topic gets a state file at `.state/<topic-id>.json` containing:

- **Entry fingerprints** — 3-word sliding windows used to deduplicate entries across runs
- **Knowledge brief** — a 2-3 paragraph summary of what's been covered, updated after each run
- **Active threads** — tracked story threads with status (ongoing/resolved/stale) and update counts
- **Run logs** — timestamps and entry counts for each research cycle

Knowledge accumulates across runs — run 10 knows everything runs 1-9 learned. This is how the system avoids repeating itself and tracks developing stories.

To start fresh on a topic, delete its state file: `rm .state/<topic-id>.json`. The next run will produce a "landscape" briefing covering the current state of the field.

## Cost and Usage

cc-deepfeed runs entirely within Claude Code. If you have a Claude Pro or Max subscription, there are no additional API keys or usage fees.

Key cost factors:
- **More topics = more usage per cycle.** Each topic spawns one Claude worker.
- **`model: sonnet`** uses the cheaper, faster model — good for factual/news topics.
- **`model: opus`** (default) gives deeper analysis but uses more of your plan's capacity.
- **`depth: deep`** produces longer entries (~600-800 words) requiring more research time.

Start with 2-3 topics and see how it fits your usage patterns before scaling up.

Anthropic's rate limits for Pro and Max plans assume ordinary individual usage. Running many topics at high frequency may count toward your plan's limits. The orchestrator handles timeouts gracefully — if a worker hits a rate limit, it fails and the retry round picks it up.

## Troubleshooting

### Common Issues

| Problem | Solution |
|---------|----------|
| `timeout: command not found` | Set `TIMEOUT_BIN` env var. macOS: `brew install coreutils`. Linux: should be built-in. |
| `ModuleNotFoundError: No module named 'yaml'` | `pip install pyyaml` |
| Worker times out (killed after 900s) | Increase `WORKER_TIMEOUT` (default 900s). Check `.logs/` for details. |
| Entries not appearing in reader | Run `make status` to confirm entries exist. Run `make publish`. Enable WebSub for instant Feedly updates. |
| `ssh: connect to host github.com port 22: Connection refused` | SSH may be blocked. Switch to HTTPS: `git remote set-url origin https://github.com/...` |
| Want to start fresh on a topic | Delete `.state/<topic-id>.json`. Next run produces a landscape briefing. |
| Need to undo the last run's entries | `python3 feed.py rollback <topic-id>` removes entries from the last run. |

### Checking Logs

Each research cycle creates logs in `.logs/`:

- `research-YYYY-MM-DD.log` — the main orchestrator log
- `<topic-id>_round1.log` — per-worker output from the first round
- `<topic-id>_retry.log` — per-worker output from retry rounds (if any)

Logs are automatically cleaned up after 7 days.

### Getting Help

- Run `make status` for a quick health check
- Run `make help` to see all available commands
- Check the [config reference](config-reference.md) for all settings
- Open Claude Code in the project and ask — it understands the codebase
