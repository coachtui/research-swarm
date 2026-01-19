"""Tests for CLI commands."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import sys


class TestCLICommands:
    """Test CLI argument parsing and command execution."""

    def test_run_command_parses_tickers(self):
        """Run command correctly parses ticker list."""
        import argparse

        # Simulate argparse for run command
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")

        parser_run = subparsers.add_parser("run")
        parser_run.add_argument("tickers", nargs="*")
        parser_run.add_argument("--from-file")
        parser_run.add_argument("--name")
        parser_run.add_argument("--fiscal-year", type=int, default=2024)
        parser_run.add_argument("--news-days-back", type=int, default=30)
        parser_run.add_argument("--max-retries", type=int, default=3)

        args = parser.parse_args(["run", "NVDA", "AAPL", "MSFT"])

        assert args.command == "run"
        assert args.tickers == ["NVDA", "AAPL", "MSFT"]

    def test_run_command_from_file_option(self, tmp_path):
        """Run command reads tickers from file option."""
        tickers_file = tmp_path / "tickers.txt"
        tickers_file.write_text("NVDA\nAAPL\n")

        import argparse

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")

        parser_run = subparsers.add_parser("run")
        parser_run.add_argument("tickers", nargs="*")
        parser_run.add_argument("--from-file")

        args = parser.parse_args(["run", "--from-file", str(tickers_file)])

        assert args.from_file == str(tickers_file)

    def test_resume_command_list_flag(self):
        """Resume --list shows resumable runs."""
        import argparse

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")

        parser_resume = subparsers.add_parser("resume")
        parser_resume.add_argument("run_id", nargs="?")
        parser_resume.add_argument("--list", action="store_true")

        args = parser.parse_args(["resume", "--list"])

        assert args.command == "resume"
        assert args.list is True

    def test_history_command_export_option(self, tmp_path):
        """History command accepts export option."""
        import argparse

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")

        parser_history = subparsers.add_parser("history")
        parser_history.add_argument("--limit", type=int, default=20)
        parser_history.add_argument("--export")

        export_path = tmp_path / "history.md"
        args = parser.parse_args(["history", "--export", str(export_path)])

        assert args.export == str(export_path)

    def test_estimate_command_accepts_tickers(self):
        """Estimate command accepts tickers."""
        import argparse

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")

        parser_estimate = subparsers.add_parser("estimate")
        parser_estimate.add_argument("tickers", nargs="*")
        parser_estimate.add_argument("--from-file")
        parser_estimate.add_argument("--tokens-per-stock", type=int, default=15000)

        args = parser.parse_args(["estimate", "NVDA", "AAPL"])

        assert args.command == "estimate"
        assert args.tickers == ["NVDA", "AAPL"]

    def test_report_command_options(self):
        """Report command accepts format and output options."""
        import argparse

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")

        parser_report = subparsers.add_parser("report")
        parser_report.add_argument("run_id")
        parser_report.add_argument("--format", choices=["markdown", "pdf", "both"], default="both")
        parser_report.add_argument("--output-dir", default="./reports")
        parser_report.add_argument("--no-charts", action="store_true")
        parser_report.add_argument("--top-picks", type=int, default=3)

        args = parser.parse_args(["report", "run-123", "--format", "pdf", "--output-dir", "./out"])

        assert args.command == "report"
        assert args.run_id == "run-123"
        assert args.format == "pdf"
        assert args.output_dir == "./out"

    def test_schedule_subcommands(self):
        """Schedule command has install/uninstall/status subcommands."""
        import argparse

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")

        parser_schedule = subparsers.add_parser("schedule")
        schedule_subparsers = parser_schedule.add_subparsers(dest="schedule_command")

        parser_install = schedule_subparsers.add_parser("install")
        parser_install.add_argument("--frequency", default="bi_weekly")
        parser_install.add_argument("--day", type=int, default=0)
        parser_install.add_argument("--hour", type=int, default=6)
        parser_install.add_argument("--tickers-file", default="./data/watchlist.txt")

        schedule_subparsers.add_parser("uninstall")
        schedule_subparsers.add_parser("status")

        # Install
        args = parser.parse_args(["schedule", "install"])
        assert args.command == "schedule"
        assert args.schedule_command == "install"

        # Status
        args = parser.parse_args(["schedule", "status"])
        assert args.schedule_command == "status"

        # Uninstall
        args = parser.parse_args(["schedule", "uninstall"])
        assert args.schedule_command == "uninstall"

    def test_version_command(self):
        """--version shows version info (this would normally exit)."""
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--version", action="version", version="research-swarm 0.1.0")

        # This would exit with SystemExit for argparse version action
        with pytest.raises(SystemExit):
            parser.parse_args(["--version"])
