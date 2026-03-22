#!/usr/bin/env python3
"""RSS feed helper for rss-research. Manages RSS 2.0 XML files and dedup state."""

import argparse
import contextlib
import fcntl
import html
import json
import re
import sys
import uuid
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree as ET


def fetch_og_image(url, timeout=10):
    """Try to extract og:image or twitter:image from a URL. Returns image URL or None."""
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; rss-research/1.0)",
            "Accept": "text/html",
        })
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            # Only read first 50KB to find meta tags quickly
            head_bytes = resp.read(51200)
            try:
                head_html = head_bytes.decode("utf-8", errors="ignore")
            except Exception:
                head_html = head_bytes.decode("latin-1", errors="ignore")

        # Try og:image first, then twitter:image
        for pattern in [
            r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image["\']',
            r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']twitter:image["\']',
        ]:
            match = re.search(pattern, head_html, re.IGNORECASE)
            if match:
                img_url = match.group(1).strip()
                # Basic validation: must look like a URL
                parsed = urlparse(img_url)
                if parsed.scheme in ("http", "https") and parsed.netloc:
                    return img_url
        return None
    except Exception as e:
        print(f"  ⚠️  Auto-image fetch failed for {url}: {e}", file=sys.stderr)
        return None


def load_config(config_path=None):
    """Load a config YAML file and return settings + feeds."""
    import yaml

    if config_path is None:
        config_path = Path(__file__).parent / "config.yaml"
    else:
        config_path = Path(config_path)
        if not config_path.is_absolute():
            config_path = Path(__file__).parent / config_path
    if not config_path.exists():
        print(f"Error: {config_path} not found.", file=sys.stderr)
        sys.exit(1)
    with open(config_path) as f:
        return yaml.safe_load(f)


def get_topic(config, topic_id):
    """Return topic definition by ID, or None."""
    for t in config.get("topics", []):
        if t["id"] == topic_id:
            return t
    return None


def get_feeds_for_topic(config, topic_id):
    """Return list of feed defs that subscribe to a topic."""
    return [f for f in config.get("feeds", []) if topic_id in f.get("topics", [])]


def get_all_feed_names(config):
    """Return list of all combined_feed names from config."""
    return [f["combined_feed"] for f in config.get("feeds", [])]


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


def split_csv(value):
    """Split a comma-separated string into a list, stripping whitespace."""
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


@contextlib.contextmanager
def lock_xml(xml_path):
    """Acquire exclusive lock on an XML feed file for read-modify-write."""
    lock_path = str(xml_path) + ".lock"
    fd = open(lock_path, "w")
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        fd.close()


def write_xml(tree, path):
    """Write an ElementTree to an XML file with consistent formatting."""
    ET.indent(tree, space="  ")
    tree.write(path, encoding="unicode", xml_declaration=True)


def save_state(state, state_path):
    """Write state dict to a JSON file with consistent formatting."""
    with open(state_path, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def feed_path(feeds_dir, combined_feed):
    """Return the path to the combined feed XML."""
    return feeds_dir / f"{combined_feed}.xml"


def init_feed(name, description, feeds_dir, combined_feed, base_url=None):
    """Create the combined RSS feed XML file. No-op if it already exists."""
    path = feed_path(feeds_dir, combined_feed)
    if path.exists():
        print(f"Feed already exists: {path}")
        return

    link = f"{base_url.rstrip('/')}/{combined_feed}.xml" if base_url else f"https://example.com/{combined_feed}.xml"

    ATOM_NS = "http://www.w3.org/2005/Atom"
    ET.register_namespace("atom", ATOM_NS)

    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = name
    ET.SubElement(channel, "description").text = description
    ET.SubElement(channel, "link").text = link
    ET.SubElement(channel, "lastBuildDate").text = rfc822()
    ET.SubElement(channel, "generator").text = "rss-research via Claude Code"

    # WebSub hub for instant Feedly notifications
    if base_url:
        feed_url = f"{base_url.rstrip('/')}/{combined_feed}.xml"
        hub = ET.SubElement(channel, f"{{{ATOM_NS}}}link")
        hub.set("rel", "hub")
        hub.set("href", "https://pubsubhubbub.appspot.com")
        self_link = ET.SubElement(channel, f"{{{ATOM_NS}}}link")
        self_link.set("rel", "self")
        self_link.set("href", feed_url)
        self_link.set("type", "application/rss+xml")

    tree = ET.ElementTree(rss)
    write_xml(tree, path)
    print(f"Initialized feed: {path}")


def add_entry(feed_id, title, content_html, sources, feeds_dir, state_dir, target_feeds, run_id=None, image_url=None):
    """Add an entry to subscriber feed XMLs and update per-topic state.

    target_feeds: list of combined_feed name strings (e.g., ["daily-briefings", "rachel-briefings"])
    """
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    guid = make_guid(feed_id, title, date_str)

    # Normalize sources to list once
    source_list = sources if isinstance(sources, list) else split_csv(sources or "")

    # Auto-extract og:image from first source if no image provided (outside lock — network I/O)
    if not image_url and source_list:
        print(f"  📷 No --image provided, auto-extracting from {source_list[0]}...")
        image_url = fetch_og_image(source_list[0])
        if image_url:
            print(f"  ✅ Found og:image: {image_url[:80]}...")
        else:
            print(f"  ⚠️  No og:image found. Entry will lack thumbnail.")

    # Prepend image if provided
    if image_url:
        escaped_img = html.escape(image_url)
        content_html = f'<figure><img src="{escaped_img}" alt="{html.escape(title)}" style="max-width:100%;height:auto;" /></figure>\n' + content_html

    # Build content with sources
    body = content_html
    if source_list:
        body += "\n<hr/>\n<p><strong>Sources:</strong></p>\n<ul>\n"
        for url in source_list:
            escaped = html.escape(url)
            body += f'  <li><a href="{escaped}">{escaped}</a></li>\n'
        body += "</ul>"

    # Write to each subscriber feed XML
    wrote_any = False
    for combined_feed in target_feeds:
        path = feed_path(feeds_dir, combined_feed)
        if not path.exists():
            print(f"Warning: {path} not found, skipping. Run init first.", file=sys.stderr)
            continue

        with lock_xml(path):
            tree = ET.parse(path)
            root = tree.getroot()
            channel = root.find("channel")
            if channel is None:
                print(f"Error: Invalid feed XML for {combined_feed}.", file=sys.stderr)
                continue

            # Dedup: skip if guid already exists in this XML
            existing_guids = {item.find("guid").text for item in channel.findall("item") if item.find("guid") is not None}
            if guid in existing_guids:
                print(f"Skipped duplicate in {combined_feed}: {title}")
                continue

            item = ET.SubElement(channel, "item")
            ET.SubElement(item, "title").text = title
            ET.SubElement(item, "description").text = body
            ET.SubElement(item, "guid", isPermaLink="false").text = guid
            ET.SubElement(item, "pubDate").text = rfc822(now)
            ET.SubElement(item, "category").text = feed_id
            if source_list:
                ET.SubElement(item, "link").text = source_list[0]
            if image_url:
                ET.SubElement(item, "enclosure", url=image_url, type="image/jpeg", length="0")

            # Update lastBuildDate
            last_build = channel.find("lastBuildDate")
            if last_build is not None:
                last_build.text = rfc822(now)

            write_xml(tree, path)
            wrote_any = True
            print(f"  Wrote to {combined_feed}.xml")

    # Update state once (outside lock — per-topic file, no contention)
    update_state(feed_id, state_dir, {
        "guid": guid,
        "title": title,
        "date": date_str,
        "fingerprints": extract_fingerprints(title, content_html),
    }, run_id=run_id)

    # Report word count so the agent can self-correct if too short
    import re
    text_only = re.sub(r'<[^>]+>', '', content_html).strip()
    char_count = len(text_only)
    # For Chinese text: count CJK characters individually, non-CJK by spaces
    cjk_chars = len(re.findall(r'[\u4e00-\u9fff\u3400-\u4dbf]', text_only))
    non_cjk = re.sub(r'[\u4e00-\u9fff\u3400-\u4dbf]', ' ', text_only)
    en_words = len(non_cjk.split())
    # ~1.5 CJK chars ≈ 1 English word
    equiv_words = int(cjk_chars / 1.5) + en_words
    print(f"Added entry to {feed_id}: {title} (~{equiv_words} words equivalent, {char_count} chars)")


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


def update_state(feed_id, state_dir, entry_record, run_id=None):
    """Update .state/<feed_id>.json with a new entry record."""
    state_path = state_dir / f"{feed_id}.json"
    if state_path.exists():
        with open(state_path) as f:
            state = json.load(f)
    else:
        state = {"last_run": None, "entries": []}

    now = datetime.now(timezone.utc).isoformat()
    state["last_run"] = now
    entry_record["run_id"] = run_id or now
    # Dedup: skip if guid already present (e.g., sync_to wrote the same entry)
    existing_guids = {e.get("guid") for e in state.get("entries", [])}
    if entry_record.get("guid") in existing_guids:
        save_state(state, state_path)
        return
    state["entries"].append(entry_record)
    # Keep only last 100 entries in state for memory
    state["entries"] = state["entries"][-100:]

    save_state(state, state_path)


def load_state(feed_id, state_dir):
    """Load state for a feed. Returns dict with last_run, entries, and knowledge."""
    state_path = state_dir / f"{feed_id}.json"
    if state_path.exists():
        with open(state_path) as f:
            state = json.load(f)
    else:
        state = {"last_run": None, "entries": []}
    # Ensure knowledge key exists (backward compat with pre-Phase1 state)
    if "knowledge" not in state:
        state["knowledge"] = {
            "brief": "",
            "key_entities": [],
            "active_threads": [],
        }
    return state


def prune_feed(keep, feeds_dir, state_dir, combined_feed):
    """Remove oldest entries beyond `keep` count from combined feed."""
    path = feed_path(feeds_dir, combined_feed)
    if not path.exists():
        print(f"Combined feed not found.", file=sys.stderr)
        sys.exit(1)

    with lock_xml(path):
        tree = ET.parse(path)
        root = tree.getroot()
        channel = root.find("channel")
        if channel is None:
            print(f"Error: Invalid feed XML.", file=sys.stderr)
            sys.exit(1)
        items = channel.findall("item")

        if len(items) <= keep:
            print(f"Feed has {len(items)} entries (limit: {keep}), no pruning needed.")
            return

        # Items are in document order (newest last since we append).
        to_remove = items[:len(items) - keep]
        removed_guids = set()
        for item in to_remove:
            guid_el = item.find("guid")
            if guid_el is not None:
                removed_guids.add(guid_el.text)
            channel.remove(item)

        write_xml(tree, path)

    # Clean all state files
    if removed_guids:
        for state_file in state_dir.glob("*.json"):
            with open(state_file) as f:
                state = json.load(f)
            before = len(state.get("entries", []))
            state["entries"] = [e for e in state.get("entries", []) if e.get("guid") not in removed_guids]
            if len(state["entries"]) < before:
                save_state(state, state_file)

    print(f"Pruned {len(to_remove)} entries, kept {keep}.")


def rollback_feed(feed_id, feeds_dir, state_dir, target_feeds):
    """Remove entries from the most recent run across all subscriber feeds.

    target_feeds: list of combined_feed name strings to rollback from.
    """
    state = load_state(feed_id, state_dir)
    entries = state.get("entries", [])

    if not entries:
        print(f"No entries to roll back for {feed_id}.")
        return

    # Find the run_id of the most recent entry
    last_entry = entries[-1]
    target_run_id = last_entry.get("run_id")

    if target_run_id is None:
        # Pre-run_id entries: fall back to date-based grouping
        target_date = last_entry.get("date")
        to_remove = [e for e in entries if e.get("date") == target_date]
    else:
        to_remove = [e for e in entries if e.get("run_id") == target_run_id]

    if not to_remove:
        print(f"No entries found for rollback in {feed_id}.")
        return

    guids_to_remove = {e["guid"] for e in to_remove}
    actually_removed = set()

    # Remove from each subscriber feed XML
    for combined_feed in target_feeds:
        path = feed_path(feeds_dir, combined_feed)
        if not path.exists():
            continue
        with lock_xml(path):
            tree = ET.parse(path)
            root = tree.getroot()
            channel = root.find("channel")
            if channel is not None:
                for item in channel.findall("item"):
                    guid_el = item.find("guid")
                    if guid_el is not None and guid_el.text in guids_to_remove:
                        channel.remove(item)
                        actually_removed.add(guid_el.text)
                write_xml(tree, path)

    if not actually_removed:
        print(f"No entries found to roll back for {feed_id}.")
        return

    # Update state once
    state["entries"] = [e for e in entries if e.get("guid") not in actually_removed]
    save_state(state, state_dir / f"{feed_id}.json")

    rolled = [e for e in to_remove if e["guid"] in actually_removed]
    print(f"Rolled back {len(rolled)} entries from {feed_id}:")
    for e in rolled:
        print(f"  - {e['title']}")


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
    print(json.dumps(state, indent=2, ensure_ascii=False))


def show_knowledge(feed_id, state_dir):
    """Dump knowledge object for a feed (for agent to read before research)."""
    state = load_state(feed_id, state_dir)
    print(json.dumps(state["knowledge"], indent=2, ensure_ascii=False))


def update_knowledge(feed_id, state_dir, brief, entities, threads_json):
    """Update the knowledge object in state after a research cycle."""
    state_path = state_dir / f"{feed_id}.json"
    state = load_state(feed_id, state_dir)

    knowledge = state["knowledge"]

    if brief is not None:
        knowledge["brief"] = brief

    if entities is not None:
        knowledge["key_entities"] = entities

    if threads_json is not None:
        knowledge["active_threads"] = json.loads(threads_json)

    state["knowledge"] = knowledge

    save_state(state, state_path)

    print(f"Updated knowledge for {feed_id}")


def show_status(config):
    """Show a dashboard of all topics and feeds."""
    feeds_dir, state_dir = get_dirs(config)
    topics = config.get("topics", [])

    if not topics:
        print("No topics configured.")
        return

    max_entries = config.get("settings", {}).get("max_entries", 30)

    # Show feed XMLs
    print("Feeds:")
    for feed_def in config.get("feeds", []):
        path = feed_path(feeds_dir, feed_def["combined_feed"])
        status = "OK" if path.exists() else "MISSING"
        print(f"  {feed_def['id']:<12} {feed_def['combined_feed']}.xml  [{status}]  topics: {', '.join(feed_def.get('topics', []))}")
    print()

    # Show topics
    print(f"{'Topic':<22} {'Last Run':<25} {'Entries':<10} {'Target':<8} {'Feeds'}")
    print("-" * 85)

    for topic in topics:
        topic_id = topic["id"]
        state = load_state(topic_id, state_dir)
        entry_count = len(state.get("entries", []))
        target = topic.get("target", "-")

        last_run = state.get("last_run")
        lr_dt = None
        delta = None
        if last_run:
            try:
                lr_dt = datetime.fromisoformat(last_run)
                delta = datetime.now(timezone.utc) - lr_dt
            except (ValueError, TypeError):
                pass

        if delta is not None:
            if delta.days > 0:
                age = f"{delta.days}d ago"
            elif delta.seconds >= 3600:
                age = f"{delta.seconds // 3600}h ago"
            else:
                age = f"{delta.seconds // 60}m ago"
            lr_display = f"{age} ({lr_dt.strftime('%Y-%m-%d')})"
        elif last_run:
            lr_display = last_run[:19]
        else:
            lr_display = "never"

        subscriber_feeds = [f["id"] for f in get_feeds_for_topic(config, topic_id)]
        feeds_str = ", ".join(subscriber_feeds)

        print(f"{topic_id:<22} {lr_display:<25} {entry_count}/{max_entries:<7} {str(target):<8} {feeds_str}")


def check_targets(config, run_id):
    """Check if today's run met entry targets. Returns list of shortfall dicts.

    Exits 0 if all targets met, 1 if any shortfalls.
    """
    _, state_dir = get_dirs(config)
    topics = config.get("topics", [])
    shortfalls = []

    for topic in topics:
        topic_id = topic["id"]
        target = topic.get("target")
        if not target:
            continue

        state = load_state(topic_id, state_dir)
        entries = state.get("entries", [])

        # Count entries from this run_id
        if run_id:
            added = sum(1 for e in entries if e.get("run_id") == run_id)
        else:
            # Count today's entries
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            added = sum(1 for e in entries if e.get("date") == today)

        if added < target:
            shortfalls.append({
                "topic_id": topic_id,
                "target": target,
                "added": added,
                "gap": target - added,
            })

    if not shortfalls:
        print("All targets met.")
        return shortfalls

    print("TARGET SHORTFALLS:")
    for s in shortfalls:
        print(f"  {s['topic_id']:<22} added {s['added']}/{s['target']}  (need {s['gap']} more)")

    # Output as JSON for orchestrator to parse
    print(f"\n__SHORTFALLS_JSON__:{json.dumps(shortfalls)}")
    sys.exit(1)


def log_run(feed_id, log_data):
    """Append a structured log entry for a research run."""
    base = Path(__file__).parent
    log_dir = base / ".logs" / feed_id
    log_dir.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_path = log_dir / f"{date_str}.json"

    if log_path.exists():
        with open(log_path) as f:
            entries = json.load(f)
    else:
        entries = []

    entries.append(log_data)

    with open(log_path, "w") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)

    print(f"Logged run for {feed_id}: {log_data.get('entries_added', 0)} added, {len(log_data.get('errors', []))} errors")


def generate_opml(config, base_url):
    """Generate an OPML file listing all user feeds."""
    feeds_dir, _ = get_dirs(config)

    opml = ET.Element("opml", version="2.0")
    head = ET.SubElement(opml, "head")
    ET.SubElement(head, "title").text = "RSS Research Feeds"
    ET.SubElement(head, "dateCreated").text = rfc822()

    body = ET.SubElement(opml, "body")
    for feed_def in config.get("feeds", []):
        feed_url = f"{base_url.rstrip('/')}/{feed_def['combined_feed']}.xml"
        ET.SubElement(body, "outline",
            type="rss",
            text=feed_def["feed_name"],
            title=feed_def["feed_name"],
            xmlUrl=feed_url,
            htmlUrl=base_url,
        )

    tree = ET.ElementTree(opml)
    opml_path = feeds_dir / "index.opml"
    write_xml(tree, opml_path)
    print(f"Generated OPML: {opml_path}")


def generate_index_html(config, base_url):
    """Generate a simple index.html listing all user feeds."""
    feeds_dir, state_dir = get_dirs(config)
    topics = config.get("topics", [])
    feed_defs = config.get("feeds", [])

    # Count total entries across all topics
    total_entries = 0
    for topic in topics:
        state = load_state(topic["id"], state_dir)
        total_entries += len(state.get("entries", []))

    # Build per-feed subscribe links
    feed_links = []
    for feed_def in feed_defs:
        feed_url = f"{base_url.rstrip('/')}/{feed_def['combined_feed']}.xml"
        feed_links.append(f'    <a href="{feed_url}">{html.escape(feed_def["feed_name"])}</a>')

    topic_list = ", ".join(t.get("name", t["id"]) for t in topics)

    subscribe_links = " &middot; ".join(feed_links)

    parts = [
        '<!DOCTYPE html>',
        '<html lang="en">',
        '<head>',
        '  <meta charset="utf-8">',
        '  <meta name="viewport" content="width=device-width, initial-scale=1">',
        '  <title>RSS Research Feeds</title>',
        '  <style>',
        '    body { font-family: -apple-system, system-ui, sans-serif; max-width: 700px; margin: 2rem auto; padding: 0 1rem; color: #333; }',
        '    h1 { border-bottom: 2px solid #e0e0e0; padding-bottom: 0.5rem; }',
        '    .subscribe { margin: 1.5rem 0; padding: 1rem; border: 1px solid #e0e0e0; border-radius: 6px; }',
        '    .subscribe a { color: #0066cc; text-decoration: none; font-weight: bold; }',
        '    .subscribe a:hover { text-decoration: underline; }',
        '    .topics { margin: 1rem 0; color: #666; font-size: 0.9rem; }',
        '    .meta { color: #999; font-size: 0.85rem; margin-top: 0.5rem; }',
        '    footer { margin-top: 2rem; padding-top: 1rem; border-top: 1px solid #e0e0e0; color: #999; font-size: 0.85rem; }',
        '  </style>',
        '</head>',
        '<body>',
        '  <h1>RSS Research Feeds</h1>',
        '  <p>Deep research briefings delivered as RSS feeds.</p>',
        '  <div class="subscribe">',
        f'    {subscribe_links}',
        f'    &middot; <a href="{base_url.rstrip("/")}/index.opml">Import (OPML)</a>',
        '  </div>',
        f'  <div class="topics"><strong>Topics:</strong> {html.escape(topic_list)}</div>',
        f'  <div class="meta">{total_entries} entries &middot; {datetime.now(timezone.utc).strftime("%Y-%m-%d")}</div>',
        f'  <footer>Generated by rss-research</footer>',
        '</body>',
        '</html>',
    ]

    index_path = feeds_dir / "index.html"
    with open(index_path, "w") as f:
        f.write("\n".join(parts))
    print(f"Generated index: {index_path}")


def backfill_images(feeds_dir, combined_feed):
    """Add og:image to existing entries that lack images."""
    path = feed_path(feeds_dir, combined_feed)
    if not path.exists():
        print(f"Feed not found: {path}", file=sys.stderr)
        return

    tree = ET.parse(path)
    root = tree.getroot()
    channel = root.find("channel")
    if channel is None:
        print("Invalid feed XML.", file=sys.stderr)
        return

    items = channel.findall("item")
    updated = 0
    skipped = 0
    failed = 0

    for item in items:
        # Skip items that already have an enclosure (image)
        if item.find("enclosure") is not None:
            skipped += 1
            continue

        # Get the first source URL from the link element
        link_el = item.find("link")
        if link_el is None or not link_el.text:
            failed += 1
            continue

        title_el = item.find("title")
        title = title_el.text if title_el is not None else "untitled"

        print(f"  Fetching image for: {title[:50]}...")
        image_url = fetch_og_image(link_el.text)

        if not image_url:
            print(f"    ❌ No og:image found")
            failed += 1
            continue

        # Add enclosure element
        ET.SubElement(item, "enclosure", url=image_url, type="image/jpeg", length="0")

        # Prepend figure to description
        desc_el = item.find("description")
        if desc_el is not None and desc_el.text:
            escaped_img = html.escape(image_url)
            escaped_title = html.escape(title)
            figure_html = f'<figure><img src="{escaped_img}" alt="{escaped_title}" style="max-width:100%;height:auto;" /></figure>\n'
            desc_el.text = figure_html + desc_el.text

        updated += 1
        print(f"    ✅ Added: {image_url[:60]}...")

    if updated > 0:
        write_xml(tree, path)

    print(f"\nBackfill complete: {updated} images added, {skipped} already had images, {failed} no image found.")


def main():
    parser = argparse.ArgumentParser(description="RSS feed helper for rss-research")
    parser.add_argument("--config", default="config.yaml", help="Path to config file (default: config.yaml)")
    sub = parser.add_subparsers(dest="command", required=True)

    # init
    sub.add_parser("init", help="Initialize all feed XMLs from config")

    # add
    p_add = sub.add_parser("add", help="Add an entry to a feed")
    p_add.add_argument("feed_id")
    p_add.add_argument("--title", required=True)
    p_add.add_argument("--content", required=True, help="HTML content of the entry")
    p_add.add_argument("--sources", default="", help="Comma-separated source URLs")
    p_add.add_argument("--image", default=None, help="URL of an image to include as figure and enclosure")
    p_add.add_argument("--run-id", default=None, help="Run identifier for rollback grouping")

    # prune
    p_prune = sub.add_parser("prune", help="Prune old entries from combined feed")
    p_prune.add_argument("--keep", type=int, default=50)

    # list
    p_list = sub.add_parser("list", help="List entries in a feed")
    p_list.add_argument("feed_id")

    # state
    p_state = sub.add_parser("state", help="Show raw state JSON for a feed")
    p_state.add_argument("feed_id")

    # knowledge
    p_knowledge = sub.add_parser("knowledge", help="Show knowledge brief for a feed")
    p_knowledge.add_argument("feed_id")

    # learn
    p_learn = sub.add_parser("learn", help="Update knowledge after research")
    p_learn.add_argument("feed_id")
    p_learn.add_argument("--brief", default=None, help="Updated knowledge brief (2-3 paragraphs)")
    p_learn.add_argument("--entities", default=None, help="Comma-separated key entities")
    p_learn.add_argument("--threads", default=None, help="JSON array of active thread objects")

    # rollback
    p_rollback = sub.add_parser("rollback", help="Remove entries from the most recent run")
    p_rollback.add_argument("feed_id")

    # status
    sub.add_parser("status", help="Show status dashboard for all feeds")

    # log
    p_log = sub.add_parser("log", help="Record a structured run log")
    p_log.add_argument("feed_id")
    p_log.add_argument("--started", required=True, help="ISO timestamp when run started")
    p_log.add_argument("--finished", required=True, help="ISO timestamp when run finished")
    p_log.add_argument("--queries", default="", help="Comma-separated search queries used")
    p_log.add_argument("--sources-consulted", type=int, default=0)
    p_log.add_argument("--entries-added", type=int, default=0)
    p_log.add_argument("--entries-skipped", type=int, default=0)
    p_log.add_argument("--threads-updated", default="", help="Comma-separated thread names")
    p_log.add_argument("--errors", default="", help="Comma-separated error descriptions")

    # opml
    p_opml = sub.add_parser("opml", help="Generate OPML file for all feeds")
    p_opml.add_argument("--base-url", required=True, help="Base URL where feeds are hosted")

    # index-html
    p_index = sub.add_parser("index-html", help="Generate index.html for all feeds")
    p_index.add_argument("--base-url", required=True, help="Base URL where feeds are hosted")

    # check-targets
    p_check = sub.add_parser("check-targets", help="Check if entry targets were met for a run")
    p_check.add_argument("--run-id", default=None, help="Run ID to check (default: today's entries)")

    # backfill-images
    sub.add_parser("backfill-images", help="Add og:image to existing entries that lack images")

    args = parser.parse_args()
    config = load_config(args.config)
    feeds_dir, state_dir = get_dirs(config)

    if args.command == "init":
        # Init all feed XMLs from config
        for feed_def in config.get("feeds", []):
            base_url = config.get("settings", {}).get("base_url")
            init_feed(feed_def["feed_name"], feed_def.get("feed_description", ""),
                      feeds_dir, feed_def["combined_feed"], base_url=base_url)
    elif args.command == "add":
        sources = split_csv(args.sources)
        # Auto-resolve target feeds from config
        subscriber_feeds = get_feeds_for_topic(config, args.feed_id)
        target_feeds = [f["combined_feed"] for f in subscriber_feeds]
        if not target_feeds:
            print(f"Warning: no feeds subscribe to {args.feed_id}", file=sys.stderr)
        add_entry(args.feed_id, args.title, args.content, sources, feeds_dir, state_dir,
                  target_feeds, run_id=args.run_id, image_url=args.image)
    elif args.command == "prune":
        # Prune all feed XMLs
        for combined_feed in get_all_feed_names(config):
            prune_feed(args.keep, feeds_dir, state_dir, combined_feed)
    elif args.command == "list":
        list_entries(args.feed_id, feeds_dir, state_dir)
    elif args.command == "state":
        show_state(args.feed_id, state_dir)
    elif args.command == "knowledge":
        show_knowledge(args.feed_id, state_dir)
    elif args.command == "learn":
        entities = split_csv(args.entities) or None
        update_knowledge(args.feed_id, state_dir, args.brief, entities, args.threads)
    elif args.command == "rollback":
        subscriber_feeds = get_feeds_for_topic(config, args.feed_id)
        target_feeds = [f["combined_feed"] for f in subscriber_feeds]
        rollback_feed(args.feed_id, feeds_dir, state_dir, target_feeds)
    elif args.command == "status":
        show_status(config)
    elif args.command == "log":
        log_run(args.feed_id, {
            "feed_id": args.feed_id,
            "started": args.started,
            "finished": args.finished,
            "queries": split_csv(args.queries),
            "sources_consulted": args.sources_consulted,
            "entries_added": args.entries_added,
            "entries_skipped": args.entries_skipped,
            "threads_updated": split_csv(args.threads_updated),
            "errors": split_csv(args.errors),
        })
    elif args.command == "opml":
        generate_opml(config, args.base_url)
    elif args.command == "index-html":
        generate_index_html(config, args.base_url)
    elif args.command == "check-targets":
        check_targets(config, args.run_id)
    elif args.command == "backfill-images":
        for combined_feed in get_all_feed_names(config):
            print(f"\nBackfilling images for {combined_feed}...")
            backfill_images(feeds_dir, combined_feed)


if __name__ == "__main__":
    main()
