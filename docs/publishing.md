# Publishing Your Feeds

Feeds are RSS XML files in the `feeds/` directory. To make them accessible to feed readers, you need to serve them over HTTP.

## GitHub Pages (recommended)

The included `publish.sh` script handles this automatically.

### Setup

1. Enable GitHub Pages in your repo settings:
   - Go to Settings > Pages
   - Source: Deploy from a branch
   - Branch: `gh-pages`, root `/`
   - Save

2. Set your `base_url` in `config.yaml`:
   ```yaml
   settings:
     base_url: "https://yourusername.github.io/cc-deepfeed"
   ```
   If using a custom domain, set that instead.

3. Run `make publish` or `bash publish.sh` after each research cycle. The orchestrator (`run-research.sh`) does this automatically.

The `gh-pages` branch is created automatically on first publish — no manual setup needed.

### What publish.sh does

1. Generates `index.html` and OPML from your config (if base URL provided)
2. Creates a throwaway clone of the `gh-pages` branch in a temp directory
3. Replaces all content with the current `feeds/` files (stale feeds are removed automatically)
4. Commits and pushes, then deletes the clone
5. Pings WebSub hub (if configured) for instant reader updates

The main working tree is never modified. If the script fails at any point, only the temp directory is affected. A lock prevents concurrent publishes from interfering with each other.

## Alternative: Any Static Host

The `feeds/` directory contains plain XML files. Serve them from anywhere:

```bash
# rsync to a VPS
rsync -avz feeds/ user@server:/var/www/feeds/

# AWS S3
aws s3 sync feeds/ s3://my-bucket/feeds/ --content-type application/xml

# Netlify (drop feeds/ folder)
```

Set `base_url` to match wherever you host them.

## Local Testing

For development, serve feeds locally:

```bash
python -m http.server 8080 -d feeds/
# Add http://localhost:8080/daily-briefings.xml to your reader
```

Some RSS readers also support `file://` URLs directly.

## WebSub for Instant Updates

By default, feed readers poll for updates (typically every 30-60 minutes). WebSub makes updates instant.

Add to your `config.yaml`:

```yaml
settings:
  websub_hub: "https://pubsubhubbub.appspot.com"
```

This is Google's free WebSub hub, supported by Feedly, Inoreader, and other major readers. After each publish, the hub is pinged and readers fetch the new content immediately.
