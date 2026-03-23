# Configuration Reference

All configuration lives in `config.yaml` at the project root. Copy `config.example.yaml` to get started.

## Settings

```yaml
settings:
  feeds_dir: ./feeds          # where RSS XML files are written
  state_dir: ./.state         # where per-topic state is stored
  max_entries: 50             # max entries per feed (oldest pruned)
  base_url: "https://..."    # public URL where feeds are hosted
  websub_hub: "https://..."  # optional WebSub hub for instant updates
```

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `feeds_dir` | no | `./feeds` | Directory for RSS XML output |
| `state_dir` | no | `./.state` | Directory for per-topic state JSON |
| `max_entries` | no | `50` | Prune limit per feed XML |
| `base_url` | yes | — | Public URL prefix for feed links (e.g., GitHub Pages URL) |
| `websub_hub` | no | — | WebSub hub URL for instant reader updates. Use `https://pubsubhubbub.appspot.com` for Feedly/Inoreader support |

## Topics

Topics define **what** to research. Each topic is researched once per cycle and distributed to all subscribing feeds.

```yaml
topics:
  - id: ai-research
    name: "AI Research Highlights"
    depth: deep
    language: en
    target: 3
    model: sonnet

  - id: product-design
    name: "Product Design Trends / 产品设计趋势"
    depth: deep
    language: en
    bilingual: zh           # English first, Chinese translation appended
    target: 3
```

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `id` | yes | — | Unique identifier. Must match the topic brief filename in `.claude/agents/topics/<id>.md` |
| `name` | yes | — | Display name used in feed entries |
| `depth` | yes | — | Entry length: `quick` (~200 words), `standard` (~400 words), `deep` (~600-800 words) |
| `language` | no | `en` | Output language. `en` for English, `zh` for Chinese |
| `bilingual` | no | — | Secondary language for bilingual entries (e.g., `zh`). When set, entries are written in the primary `language` first, then a translation in this language is appended after an `<hr/>` separator. Word count targets apply to the primary version only |
| `target` | yes | — | Mandatory number of entries to produce per research cycle. Workers are retried if targets aren't met |
| `model` | no | `opus` | Claude model for research. Use `sonnet` for cheaper factual topics, `opus` for deep analysis |

### Topic Briefs

Each topic **must** have a matching brief file at `.claude/agents/topics/<id>.md`. The brief tells the research worker:
- **Scope** — what to cover
- **Skip** — what to exclude
- **Writing Style** — tone, structure, depth expectations
- **Research Strategy** (optional) — special research instructions

See `.claude/agents/topics/_template.md` for the full format.

## Feeds

Feeds define **who** gets what. Each feed is an RSS XML file that subscribes to one or more topics.

```yaml
feeds:
  - id: my-feed
    combined_feed: daily-briefings
    feed_name: "My Research Feed"
    feed_description: "Deep research briefings powered by Claude"
    topics: [ai-research, world-news]
```

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `id` | yes | — | Unique feed identifier |
| `combined_feed` | yes | — | XML filename (without `.xml`). Becomes `feeds/<combined_feed>.xml` |
| `feed_name` | yes | — | RSS feed title shown in readers |
| `feed_description` | no | — | RSS feed description |
| `topics` | yes | — | List of topic IDs this feed subscribes to |

### Multi-Feed Example

```yaml
feeds:
  - id: personal
    combined_feed: daily-briefings
    feed_name: "My Daily Briefings"
    topics: [ai-research, world-news, climate-tech]

  - id: work
    combined_feed: work-briefings
    feed_name: "Work Research Feed"
    topics: [ai-research]
```

Both feeds receive `ai-research` entries, but only the personal feed gets `world-news` and `climate-tech`.
