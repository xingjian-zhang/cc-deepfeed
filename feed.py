#!/usr/bin/env python3
"""RSS feed helper for rss-research. Manages RSS 2.0 XML files and dedup state."""

import argparse
import html
import json
import sys
import uuid
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from xml.etree import ElementTree as ET


def load_config():
    """Load config.yaml and return settings + feeds."""
    import yaml

    config_path = Path(__file__).parent / "config.yaml"
    if not config_path.exists():
        print("Error: config.yaml not found. Copy config.example.yaml to config.yaml", file=sys.stderr)
        sys.exit(1)
    with open(config_path) as f:
        return yaml.safe_load(f)


def get_dirs(config=None):
    """Return (feeds_dir, state_dir) from config, creating if needed."""
    if config is None:
        config = load_config()
    base = Path(__file__).parent
    feeds_dir = base / config.get("settings", {}).get("feeds_dir", "./feeds")
    state_dir = base / config.get("settings", {}).get("state_dir", "./.state")
    feeds_dir.mkdir(parents=True, exist_ok=True)
    state_dir.mkdir(parents=True, exist_ok=True)
    return feeds_dir, state_dir


def rfc822(dt=None):
    """Format datetime as RFC 822 for RSS."""
    if dt is None:
        dt = datetime.now(timezone.utc)
    return format_datetime(dt)


def make_guid(feed_id, title, date_str):
    """Generate a deterministic GUID from feed_id + title + date."""
    raw = f"{feed_id}:{title}:{date_str}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, raw))


def init_feed(feed_id, name, description, feeds_dir):
    """Create a new empty RSS feed XML file."""
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = name
    ET.SubElement(channel, "description").text = description
    ET.SubElement(channel, "link").text = f"file://rss-research/feeds/{feed_id}.xml"
    ET.SubElement(channel, "lastBuildDate").text = rfc822()
    ET.SubElement(channel, "generator").text = "rss-research via Claude Code"

    path = feeds_dir / f"{feed_id}.xml"
    tree = ET.ElementTree(rss)
    ET.indent(tree, space="  ")
    tree.write(path, encoding="unicode", xml_declaration=True)
    print(f"Initialized feed: {path}")


def add_entry(feed_id, title, content_html, sources, feeds_dir, state_dir):
    """Add an entry to an existing feed and update state."""
    path = feeds_dir / f"{feed_id}.xml"
    if not path.exists():
        print(f"Error: Feed {feed_id} not found. Run init first.", file=sys.stderr)
        sys.exit(1)

    tree = ET.parse(path)
    root = tree.getroot()
    channel = root.find("channel")
    if channel is None:
        print(f"Error: Invalid feed XML for {feed_id}.", file=sys.stderr)
        sys.exit(1)

    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    guid = make_guid(feed_id, title, date_str)

    # Build content with sources
    body = content_html
    if sources:
        source_links = sources if isinstance(sources, list) else [s.strip() for s in sources.split(",")]
        body += "\n<hr/>\n<p><strong>Sources:</strong></p>\n<ul>\n"
        for url in source_links:
            escaped = html.escape(url)
            body += f'  <li><a href="{escaped}">{escaped}</a></li>\n'
        body += "</ul>"

    item = ET.SubElement(channel, "item")
    ET.SubElement(item, "title").text = title
    ET.SubElement(item, "description").text = body
    ET.SubElement(item, "guid", isPermaLink="false").text = guid
    ET.SubElement(item, "pubDate").text = rfc822(now)
    if sources:
        source_list = sources if isinstance(sources, list) else [s.strip() for s in sources.split(",")]
        if source_list:
            ET.SubElement(item, "link").text = source_list[0]

    # Update lastBuildDate
    last_build = channel.find("lastBuildDate")
    if last_build is not None:
        last_build.text = rfc822(now)

    ET.indent(tree, space="  ")
    tree.write(path, encoding="unicode", xml_declaration=True)

    # Update state
    update_state(feed_id, state_dir, {
        "guid": guid,
        "title": title,
        "date": date_str,
        "fingerprints": extract_fingerprints(title, content_html),
    })

    print(f"Added entry to {feed_id}: {title}")


def extract_fingerprints(title, _content):
    """Extract simple fingerprints for dedup — lowercase key phrases from title."""
    words = title.lower().split()
    # Use 3-word sliding windows as fingerprints
    fingerprints = []
    if len(words) >= 3:
        for i in range(len(words) - 2):
            fingerprints.append(" ".join(words[i:i+3]))
    else:
        fingerprints.append(" ".join(words))
    return fingerprints


def update_state(feed_id, state_dir, entry_record):
    """Update .state/<feed_id>.json with a new entry record."""
    state_path = state_dir / f"{feed_id}.json"
    if state_path.exists():
        with open(state_path) as f:
            state = json.load(f)
    else:
        state = {"last_run": None, "entries": []}

    state["last_run"] = datetime.now(timezone.utc).isoformat()
    state["entries"].append(entry_record)
    # Keep only last 100 entries in state for memory
    state["entries"] = state["entries"][-100:]

    with open(state_path, "w") as f:
        json.dump(state, f, indent=2)


def load_state(feed_id, state_dir):
    """Load state for a feed. Returns dict with last_run and entries."""
    state_path = state_dir / f"{feed_id}.json"
    if state_path.exists():
        with open(state_path) as f:
            return json.load(f)
    return {"last_run": None, "entries": []}


def prune_feed(feed_id, keep, feeds_dir, state_dir):
    """Remove oldest entries beyond `keep` count."""
    path = feeds_dir / f"{feed_id}.xml"
    if not path.exists():
        print(f"Feed {feed_id} not found.", file=sys.stderr)
        sys.exit(1)

    tree = ET.parse(path)
    root = tree.getroot()
    channel = root.find("channel")
    if channel is None:
        print(f"Error: Invalid feed XML for {feed_id}.", file=sys.stderr)
        sys.exit(1)
    items = channel.findall("item")

    if len(items) <= keep:
        print(f"Feed {feed_id} has {len(items)} entries (limit: {keep}), no pruning needed.")
        return

    # Items are in document order (newest last since we append).
    # Remove oldest (first in list) until we're at `keep`.
    to_remove = items[:len(items) - keep]
    removed_guids = set()
    for item in to_remove:
        guid_el = item.find("guid")
        if guid_el is not None:
            removed_guids.add(guid_el.text)
        channel.remove(item)

    ET.indent(tree, space="  ")
    tree.write(path, encoding="unicode", xml_declaration=True)

    # Clean state too
    if removed_guids:
        state_path = state_dir / f"{feed_id}.json"
        if state_path.exists():
            with open(state_path) as f:
                state = json.load(f)
            state["entries"] = [e for e in state["entries"] if e.get("guid") not in removed_guids]
            with open(state_path, "w") as f:
                json.dump(state, f, indent=2)

    print(f"Pruned {len(to_remove)} entries from {feed_id}, kept {keep}.")


def list_entries(feed_id, _feeds_dir, state_dir):
    """List existing entries for a feed (reads from state for speed)."""
    state = load_state(feed_id, state_dir)
    if not state["entries"]:
        print(f"No entries for {feed_id}.")
        if state["last_run"]:
            print(f"Last run: {state['last_run']}")
        return

    print(f"Feed: {feed_id}")
    print(f"Last run: {state['last_run']}")
    print(f"Entries ({len(state['entries'])}):")
    for entry in reversed(state["entries"]):  # newest first
        print(f"  [{entry['date']}] {entry['title']}")
        if entry.get("fingerprints"):
            print(f"           fingerprints: {entry['fingerprints'][:3]}")


def show_state(feed_id, state_dir):
    """Dump raw state JSON for a feed (for Claude to read)."""
    state = load_state(feed_id, state_dir)
    print(json.dumps(state, indent=2))


def main():
    parser = argparse.ArgumentParser(description="RSS feed helper for rss-research")
    sub = parser.add_subparsers(dest="command", required=True)

    # init
    p_init = sub.add_parser("init", help="Initialize a new feed")
    p_init.add_argument("feed_id")
    p_init.add_argument("--name", required=True)
    p_init.add_argument("--description", default="")

    # add
    p_add = sub.add_parser("add", help="Add an entry to a feed")
    p_add.add_argument("feed_id")
    p_add.add_argument("--title", required=True)
    p_add.add_argument("--content", required=True, help="HTML content of the entry")
    p_add.add_argument("--sources", default="", help="Comma-separated source URLs")

    # prune
    p_prune = sub.add_parser("prune", help="Prune old entries")
    p_prune.add_argument("feed_id")
    p_prune.add_argument("--keep", type=int, default=30)

    # list
    p_list = sub.add_parser("list", help="List entries in a feed")
    p_list.add_argument("feed_id")

    # state
    p_state = sub.add_parser("state", help="Show raw state JSON for a feed")
    p_state.add_argument("feed_id")

    args = parser.parse_args()
    config = load_config()
    feeds_dir, state_dir = get_dirs(config)

    if args.command == "init":
        init_feed(args.feed_id, args.name, args.description, feeds_dir)
    elif args.command == "add":
        sources = [s.strip() for s in args.sources.split(",") if s.strip()] if args.sources else []
        add_entry(args.feed_id, args.title, args.content, sources, feeds_dir, state_dir)
    elif args.command == "prune":
        prune_feed(args.feed_id, args.keep, feeds_dir, state_dir)
    elif args.command == "list":
        list_entries(args.feed_id, feeds_dir, state_dir)
    elif args.command == "state":
        show_state(args.feed_id, state_dir)


if __name__ == "__main__":
    main()
