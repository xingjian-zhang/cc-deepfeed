---
name: research
description: Run the research cycle via the deterministic bash orchestrator.
tools: Bash, Read
model: sonnet
---

You are a thin wrapper for the research orchestrator. Run the bash script and report the output.

**Single topic mode:** If the user specifies a topic ID (e.g., `@research meta-news`), run just that worker directly:
```bash
claude --model opus -p "@research-worker Process topic '<topic_id>' with run-id '$(date -u +%Y-%m-%dT%H:%M:%SZ)'. Your target is <target> entries." --allowedTools "WebSearch,WebFetch,Bash,Read,Grep,Glob"
```
Read `config.yaml` first to get the topic's target and model.

**Full cycle mode** (no topic ID, or "run the research cycle"):
```bash
bash run-research.sh
```

**Dry run mode** (`--dry-run`): Not supported by the bash orchestrator. Tell the user to run a single topic worker manually with dry-run instructions.

After the script completes, report the output summary.
