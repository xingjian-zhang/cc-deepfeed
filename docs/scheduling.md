# Scheduling Automatic Research Cycles

Run research cycles on a schedule so your feeds update automatically.

## Prerequisites

- Claude Code CLI (`claude`) installed and authenticated
- The project directory with a valid `config.yaml`

## macOS: launchd

Create a plist file at `~/Library/LaunchAgents/com.cc-deepfeed.plist`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.cc-deepfeed</string>

    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>/PATH/TO/cc-deepfeed/run-research.sh</string>
    </array>

    <key>WorkingDirectory</key>
    <string>/PATH/TO/cc-deepfeed</string>

    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>9</integer>
        <key>Minute</key>
        <integer>7</integer>
    </dict>

    <key>ExitTimeOut</key>
    <integer>1800</integer>

    <key>StandardOutPath</key>
    <string>/PATH/TO/cc-deepfeed/.logs/launchd-latest.log</string>
    <key>StandardErrorPath</key>
    <string>/PATH/TO/cc-deepfeed/.logs/launchd-latest.err</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
```

Replace `/PATH/TO/cc-deepfeed` with your actual project path. Make sure the `PATH` includes wherever `claude` is installed (check with `which claude`).

**Important:** The `ExitTimeOut` (30 min) kills the job if it runs too long — this prevents hung workers from blocking indefinitely. The script manages its own dated log files (`.logs/research-YYYY-MM-DD.log`) with 7-day rotation; the `launchd-latest.*` files are only a fallback. On macOS with Homebrew, add `/opt/homebrew/bin` to the PATH for GNU `timeout`.

Load and start:

```bash
launchctl load ~/Library/LaunchAgents/com.cc-deepfeed.plist
```

Unload:

```bash
launchctl unload ~/Library/LaunchAgents/com.cc-deepfeed.plist
```

## Linux: cron

```bash
crontab -e
```

Add:

```
7 9 * * * cd /path/to/cc-deepfeed && bash run-research.sh
```

This runs daily at 9:07 AM. The script manages its own log rotation — no need for shell redirects.

## Linux: systemd

Create two files:

**`~/.config/systemd/user/cc-deepfeed.service`**

```ini
[Unit]
Description=cc-deepfeed research cycle

[Service]
Type=oneshot
WorkingDirectory=/path/to/cc-deepfeed
ExecStart=/bin/bash run-research.sh
TimeoutStartSec=1800
```

**`~/.config/systemd/user/cc-deepfeed.timer`**

```ini
[Unit]
Description=Run cc-deepfeed daily

[Timer]
OnCalendar=*-*-* 09:07:00
Persistent=true

[Install]
WantedBy=timers.target
```

Enable and start:

```bash
systemctl --user daemon-reload
systemctl --user enable --now cc-deepfeed.timer
```

Check status:

```bash
systemctl --user status cc-deepfeed.timer
journalctl --user -u cc-deepfeed.service
```

## Manual / One-off

```bash
# Interactive (inside Claude Code)
@research

# Headless
claude -p "@research run the research cycle"

# Single topic
claude -p "@research meta-news"

# Or directly via the bash orchestrator
bash run-research.sh
```
