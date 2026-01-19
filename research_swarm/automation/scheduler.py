"""macOS launchd scheduler for automated runs."""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from research_swarm.automation.models import (
    LaunchdStatus,
    ScheduleConfig,
    ScheduleFrequency,
)
from research_swarm.logger import logger


class LaunchdScheduler:
    """Manages macOS launchd plist for scheduling."""

    PLIST_NAME = "com.research-swarm.automation"
    PLIST_DIR = Path.home() / "Library" / "LaunchAgents"

    def __init__(self, config: ScheduleConfig):
        self.config = config
        self.plist_path = self.PLIST_DIR / f"{self.PLIST_NAME}.plist"
        self.state_file = Path("./data/state/scheduler_state.json")

    def generate_plist(self) -> str:
        """Generate launchd plist XML content."""
        # Get paths
        python_path = sys.executable
        working_dir = Path.cwd()
        tickers_file = self.config.tickers_file.absolute()
        log_dir = working_dir / "data" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        # Map day_of_week (0=Mon) to launchd weekday (1=Mon, 7=Sun)
        launchd_weekday = self.config.day_of_week + 1
        if launchd_weekday == 7:
            launchd_weekday = 0  # Sunday in launchd is 0

        plist = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{self.PLIST_NAME}</string>

    <key>ProgramArguments</key>
    <array>
        <string>{python_path}</string>
        <string>-m</string>
        <string>research_swarm</string>
        <string>auto</string>
        <string>--tickers-file</string>
        <string>{tickers_file}</string>
    </array>

    <key>WorkingDirectory</key>
    <string>{working_dir}</string>

    <key>StartCalendarInterval</key>
    <dict>
        <key>Weekday</key>
        <integer>{launchd_weekday}</integer>
        <key>Hour</key>
        <integer>{self.config.hour}</integer>
        <key>Minute</key>
        <integer>{self.config.minute}</integer>
    </dict>

    <key>StandardOutPath</key>
    <string>{log_dir}/launchd_stdout.log</string>

    <key>StandardErrorPath</key>
    <string>{log_dir}/launchd_stderr.log</string>

    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:{Path(python_path).parent}</string>
    </dict>

    <key>RunAtLoad</key>
    <false/>
</dict>
</plist>'''
        return plist

    def install(self) -> bool:
        """Install and load the launchd job."""
        try:
            # Ensure directory exists
            self.PLIST_DIR.mkdir(parents=True, exist_ok=True)

            # Unload if already loaded
            if self.plist_path.exists():
                subprocess.run(
                    ["launchctl", "unload", str(self.plist_path)],
                    capture_output=True,
                )

            # Write plist
            plist_content = self.generate_plist()
            self.plist_path.write_text(plist_content)

            # Load job
            result = subprocess.run(
                ["launchctl", "load", str(self.plist_path)],
                capture_output=True,
                text=True,
            )

            if result.returncode != 0:
                logger.error(f"Failed to load launchd job: {result.stderr}")
                return False

            # Initialize state
            self._init_state()

            logger.info(f"Installed launchd job: {self.plist_path}")
            return True

        except Exception as e:
            logger.error(f"Install failed: {e}")
            return False

    def uninstall(self) -> bool:
        """Unload and remove the launchd job."""
        try:
            if self.plist_path.exists():
                subprocess.run(
                    ["launchctl", "unload", str(self.plist_path)],
                    capture_output=True,
                )
                self.plist_path.unlink()
                logger.info("Uninstalled launchd job")

            return True

        except Exception as e:
            logger.error(f"Uninstall failed: {e}")
            return False

    def get_status(self) -> LaunchdStatus:
        """Get current status of the scheduled job."""
        installed = self.plist_path.exists()

        if not installed:
            return LaunchdStatus(
                installed=False,
                enabled=False,
                status="not_installed",
            )

        # Check if loaded
        result = subprocess.run(
            ["launchctl", "list", self.PLIST_NAME],
            capture_output=True,
            text=True,
        )

        enabled = result.returncode == 0

        # Get last run from state
        state = self._load_state()
        last_run = None
        if state.get("last_run_timestamp"):
            last_run = datetime.fromisoformat(state["last_run_timestamp"])

        return LaunchdStatus(
            installed=True,
            enabled=enabled,
            plist_path=self.plist_path,
            last_run=last_run,
            status="waiting" if enabled else "disabled",
        )

    def should_run_today(self) -> bool:
        """Check if bi-weekly run should execute today.

        Since launchd doesn't support "every other week", we run weekly
        and check state to skip alternate weeks.
        """
        if self.config.frequency != ScheduleFrequency.BI_WEEKLY:
            return True  # Weekly/monthly always run

        state = self._load_state()

        if state.get("last_run_iso_week") is None:
            # First run - always execute
            return True

        now = datetime.now()
        current_week = now.isocalendar()[1]
        current_year = now.year

        last_week = state["last_run_iso_week"]
        last_year = state.get("last_run_year", current_year)

        # Handle year boundary
        if current_year != last_year:
            weeks_elapsed = (52 - last_week) + current_week
        else:
            weeks_elapsed = current_week - last_week

        return weeks_elapsed >= 2

    def update_last_run(self) -> None:
        """Update state file with current run info."""
        now = datetime.now()
        state = self._load_state()

        state["last_run_iso_week"] = now.isocalendar()[1]
        state["last_run_year"] = now.year
        state["last_run_timestamp"] = now.isoformat()
        state["run_count"] = state.get("run_count", 0) + 1

        self._save_state(state)

    def _init_state(self) -> None:
        """Initialize state file."""
        if not self.state_file.exists():
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            self._save_state(
                {
                    "frequency": self.config.frequency.value,
                    "initial_week": datetime.now().isocalendar()[1],
                    "run_count": 0,
                }
            )

    def _load_state(self) -> dict:
        """Load state from file."""
        if self.state_file.exists():
            return json.loads(self.state_file.read_text())
        return {}

    def _save_state(self, state: dict) -> None:
        """Save state to file."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(state, indent=2))
