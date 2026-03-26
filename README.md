# cc-deepfeed

[![CI](https://github.com/xingjian-zhang/cc-deepfeed/actions/workflows/validate.yml/badge.svg)](https://github.com/xingjian-zhang/cc-deepfeed/actions/workflows/validate.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org)
[![Claude Code](https://img.shields.io/badge/Built%20with-Claude%20Code-blueviolet?logo=anthropic)](https://claude.ai/claude-code)

**Deep research briefings delivered as RSS feeds, powered by Claude Code.**

You define the topics you care about. Every morning, Claude researches them — searching the web, cross-referencing sources — and writes deep briefings that show up in your reader. You control the algorithm deciding what you see. No scrolling. Just your interests, analyzed in depth. **And if you already have a Claude subscription, it costs nothing extra to run.**

<p align="center">
  <img src="docs/reeder-desktop.png" alt="Reeder on macOS" width="75%">
</p>
<p align="center">
  <img src="docs/reeder-mobile-list.png" alt="Feed list on iOS" height="360">
  &nbsp;&nbsp;&nbsp;
  <img src="docs/reeder-mobile-article.png" alt="Article view on iOS" height="360">
</p>

## Features

**Claude Code native.** Runs entirely within Claude Code — free with your Max or Pro subscription. No API keys, no usage fees, no external services.

**You control your feed.** Define exactly what you want researched, how deep to go, and what to skip. No recommendation algorithm deciding what you see. Your information diet, your rules.

**Endlessly extensible.** AI research papers today, your university dining hall menu tomorrow, a daily deep-dive into an obscure historical fact the day after. If you can describe it, cc-deepfeed will research and write about it.

**Any RSS reader.** Standard RSS 2.0 — Reeder, Feedly, NetNewsWire, Inoreader, or whatever you already use. Zero lock-in. Migrate anytime.

**Easy to configure.** One YAML file. Describe your interests in plain English. Run `make run`. That's it.

**Gets smarter over time.** Each run builds on the last — accumulated knowledge briefs, tracked story threads, entity memory. Run 10 knows everything runs 1–9 learned.

## Get Started

**Requires:** Python 3.9+, [PyYAML](https://pypi.org/project/PyYAML/), [Claude Code](https://docs.anthropic.com/en/docs/claude-code), an RSS reader ([Reeder](https://reederapp.com), [NetNewsWire](https://netnewswire.com), [Feedly](https://feedly.com), etc.)

```bash
git clone https://github.com/xingjian-zhang/cc-deepfeed.git
cd cc-deepfeed && pip install pyyaml
```

Then open Claude Code in the project directory and run `/setup` — it checks your environment, creates your config, helps you write topic briefs, and initializes your feeds interactively.

Or set up manually:

```bash
make setup          # creates config.yaml from example
# Edit config.yaml with your topics and base_url, then:
make init && make run
```

See the **[Getting Started Guide](docs/getting-started.md)** for a full walkthrough from clone to first published feed.

## How It Works

1. **You define topics** in `config.yaml` with a plain-English brief for each
2. **Claude Code runs headlessly** — a scheduled task kicks off the orchestrator via `claude -p`
3. **Workers research in parallel** — one Claude agent per topic, searching the web from multiple angles
4. **Briefings are written** — long-form analysis, deduplicated, distributed to your feeds
5. **Feeds are published** to GitHub Pages (or any static host)
6. **Knowledge carries forward** — each run builds on what previous runs learned

## Commands

| Command | |
|---|---|
| `/setup` | Interactive setup wizard (in Claude Code) |
| `make run` | Run full research cycle |
| `make run-topic TOPIC=id` | Run a single topic |
| `make status` | Dashboard of all topics and feeds |
| `make publish` | Publish feeds to GitHub Pages |

## Docs

- [Getting Started Guide](docs/getting-started.md) — full walkthrough from clone to published feed
- [Configuration Reference](docs/config-reference.md) — topics, feeds, settings
- [Publishing Guide](docs/publishing.md) — GitHub Pages, S3, WebSub
- [Scheduling Guide](docs/scheduling.md) — cron, launchd, systemd

## Disclaimer

cc-deepfeed runs on [Claude Code](https://docs.anthropic.com/en/docs/claude-code), Anthropic's official CLI tool. Running it headlessly via cron or launchd is a [supported use case](https://code.claude.com/docs/en/legal-and-compliance). Anthropic's usage limits for Pro and Max plans assume ordinary, individual usage — running many topics at high frequency may count toward your plan's limits. This project is not affiliated with or endorsed by Anthropic. AI-generated content may contain inaccuracies; always verify critical information against original sources.

## License

MIT
