"""Tests for cache CLI commands."""

import pytest
from unittest.mock import Mock, patch, MagicMock, call
from pathlib import Path
import argparse
import sqlite3
from datetime import datetime, timedelta


class TestCacheStats:
    """Tests for cache stats command."""

    def test_cache_stats_shows_counts(self, tmp_path):
        """Verify stats command shows entry counts."""
        from research_swarm.data.cache import Cache
        from research_swarm.__main__ import cmd_cache_stats

        # Create cache with test data
        cache_db = tmp_path / "test_cache.db"
        cache = Cache(db_path=cache_db)

        # Add some entries
        cache.set("test", "key1", {"data": "value1"}, ttl_days=7)
        cache.set("test", "key2", {"data": "value2"}, ttl_days=7)

        # Add expired entry
        with sqlite3.connect(cache_db) as conn:
            expired_time = (datetime.now() - timedelta(days=1)).isoformat()
            conn.execute(
                "INSERT INTO cache (key, value, created_at, expires_at) VALUES (?, ?, ?, ?)",
                ("expired_key", '{"data": "expired"}', expired_time, expired_time)
            )

        # Mock args
        args = Mock()

        # Patch the cache import in the function
        with patch('research_swarm.data.cache.cache', cache):
            with patch('research_swarm.__main__.logger') as mock_logger:
                result = cmd_cache_stats(args)

                assert result == 0

                # Verify stats were logged
                calls = [str(call) for call in mock_logger.info.call_args_list]
                assert any("Total Entries:   3" in str(call) for call in calls)
                assert any("Valid Entries:   2" in str(call) for call in calls)
                assert any("Expired Entries: 1" in str(call) for call in calls)

    def test_cache_stats_shows_db_size(self, tmp_path):
        """Verify stats command shows database size."""
        from research_swarm.data.cache import Cache
        from research_swarm.__main__ import cmd_cache_stats

        cache_db = tmp_path / "test_cache.db"
        cache = Cache(db_path=cache_db)
        cache.set("test", "key1", {"data": "value1"}, ttl_days=7)

        args = Mock()

        with patch('research_swarm.data.cache.cache', cache):
            with patch('research_swarm.__main__.logger') as mock_logger:
                result = cmd_cache_stats(args)

                assert result == 0

                # Verify database path and size were logged
                calls = [str(call) for call in mock_logger.info.call_args_list]
                assert any("Database:" in str(call) for call in calls)
                assert any("Size:" in str(call) for call in calls)

    def test_cache_stats_empty_cache(self, tmp_path):
        """Verify stats command handles empty cache."""
        from research_swarm.data.cache import Cache
        from research_swarm.__main__ import cmd_cache_stats

        cache_db = tmp_path / "test_cache.db"
        cache = Cache(db_path=cache_db)

        args = Mock()

        with patch('research_swarm.data.cache.cache', cache):
            with patch('research_swarm.__main__.logger') as mock_logger:
                result = cmd_cache_stats(args)

                assert result == 0

                calls = [str(call) for call in mock_logger.info.call_args_list]
                assert any("Total Entries:   0" in str(call) for call in calls)


class TestCacheClear:
    """Tests for cache clear command."""

    def test_clear_expired_removes_old_entries(self, tmp_path):
        """Verify clear removes only expired entries."""
        from research_swarm.data.cache import Cache
        from research_swarm.__main__ import cmd_cache_clear

        cache_db = tmp_path / "test_cache.db"
        cache = Cache(db_path=cache_db)

        # Add valid entry
        cache.set("test", "valid", {"data": "valid"}, ttl_days=7)

        # Add expired entry
        with sqlite3.connect(cache_db) as conn:
            expired_time = (datetime.now() - timedelta(days=1)).isoformat()
            conn.execute(
                "INSERT INTO cache (key, value, created_at, expires_at) VALUES (?, ?, ?, ?)",
                ("expired_key", '{"data": "expired"}', expired_time, expired_time)
            )

        args = Mock()
        args.all = False
        args.force = False

        with patch('research_swarm.data.cache.cache', cache):
            with patch('research_swarm.__main__.logger') as mock_logger:
                result = cmd_cache_clear(args)

                assert result == 0

                # Verify only expired entry was deleted
                stats = cache.stats()
                assert stats['total_entries'] == 1
                assert stats['valid_entries'] == 1
                assert stats['expired_entries'] == 0

                # Verify success message
                mock_logger.success.assert_called_once()
                assert "1 expired cache entries" in str(mock_logger.success.call_args)

    def test_clear_all_requires_confirmation(self, tmp_path):
        """Verify --all without --force prompts."""
        from research_swarm.data.cache import Cache
        from research_swarm.__main__ import cmd_cache_clear

        cache_db = tmp_path / "test_cache.db"
        cache = Cache(db_path=cache_db)
        cache.set("test", "key1", {"data": "value1"}, ttl_days=7)

        args = Mock()
        args.all = True
        args.force = False

        with patch('research_swarm.data.cache.cache', cache):
            with patch('research_swarm.__main__.logger') as mock_logger:
                with patch('builtins.input', return_value='n'):
                    result = cmd_cache_clear(args)

                    assert result == 0

                    # Verify cancellation
                    mock_logger.info.assert_called_once_with("Cancelled")

                    # Verify cache still has entry
                    stats = cache.stats()
                    assert stats['total_entries'] == 1

    def test_clear_all_with_force_skips_prompt(self, tmp_path):
        """Verify --all --force clears without prompt."""
        from research_swarm.data.cache import Cache
        from research_swarm.__main__ import cmd_cache_clear

        cache_db = tmp_path / "test_cache.db"
        cache = Cache(db_path=cache_db)
        cache.set("test", "key1", {"data": "value1"}, ttl_days=7)
        cache.set("test", "key2", {"data": "value2"}, ttl_days=7)

        args = Mock()
        args.all = True
        args.force = True

        with patch('research_swarm.data.cache.cache', cache):
            with patch('research_swarm.__main__.logger') as mock_logger:
                result = cmd_cache_clear(args)

                assert result == 0

                # Verify all entries deleted
                stats = cache.stats()
                assert stats['total_entries'] == 0

                # Verify success message
                mock_logger.success.assert_called_once()
                assert "2 cache entries (all)" in str(mock_logger.success.call_args)

    def test_clear_all_with_confirmation_yes(self, tmp_path):
        """Verify --all with 'y' confirmation clears cache."""
        from research_swarm.data.cache import Cache
        from research_swarm.__main__ import cmd_cache_clear

        cache_db = tmp_path / "test_cache.db"
        cache = Cache(db_path=cache_db)
        cache.set("test", "key1", {"data": "value1"}, ttl_days=7)

        args = Mock()
        args.all = True
        args.force = False

        with patch('research_swarm.data.cache.cache', cache):
            with patch('research_swarm.__main__.logger') as mock_logger:
                with patch('builtins.input', return_value='y'):
                    result = cmd_cache_clear(args)

                    assert result == 0

                    # Verify cache cleared
                    stats = cache.stats()
                    assert stats['total_entries'] == 0


class TestStartupCleanup:
    """Tests for cache cleanup on startup."""

    def test_main_calls_clear_expired(self, tmp_path):
        """Verify cache cleanup runs on startup."""
        from research_swarm.data.cache import Cache

        cache_db = tmp_path / "test_cache.db"
        cache = Cache(db_path=cache_db)

        # Add expired entry
        with sqlite3.connect(cache_db) as conn:
            expired_time = (datetime.now() - timedelta(days=1)).isoformat()
            conn.execute(
                "INSERT INTO cache (key, value, created_at, expires_at) VALUES (?, ?, ?, ?)",
                ("expired_key", '{"data": "expired"}', expired_time, expired_time)
            )

        with patch('research_swarm.data.cache.cache', cache):
            with patch('research_swarm.__main__.logger') as mock_logger:
                with patch('sys.argv', ['research-swarm', '--version']):
                    with pytest.raises(SystemExit):
                        from research_swarm.__main__ import main
                        main()

                # Verify debug log was called for cleanup
                debug_calls = [str(call) for call in mock_logger.debug.call_args_list]
                assert any("Cleaned up" in str(call) and "expired cache entries" in str(call)
                          for call in debug_calls)

    def test_main_handles_cache_cleanup_error(self):
        """Verify main continues if cache cleanup fails."""
        with patch('research_swarm.data.cache.cache') as mock_cache:
            mock_cache.clear_expired.side_effect = Exception("Cache error")

            with patch('research_swarm.__main__.logger') as mock_logger:
                with patch('sys.argv', ['research-swarm', '--version']):
                    with pytest.raises(SystemExit):
                        from research_swarm.__main__ import main
                        main()

                # Verify error was logged but main continued
                debug_calls = [str(call) for call in mock_logger.debug.call_args_list]
                assert any("Cache cleanup skipped" in str(call) for call in debug_calls)


class TestCacheCommandParsing:
    """Tests for cache command argument parsing."""

    def test_cache_stats_subcommand_exists(self):
        """Verify cache stats subcommand is registered."""
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")

        parser_cache = subparsers.add_parser("cache")
        cache_subparsers = parser_cache.add_subparsers(dest="cache_command", required=True)

        parser_cache_stats = cache_subparsers.add_parser("stats")

        args = parser.parse_args(["cache", "stats"])

        assert args.command == "cache"
        assert args.cache_command == "stats"

    def test_cache_clear_subcommand_exists(self):
        """Verify cache clear subcommand with flags."""
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")

        parser_cache = subparsers.add_parser("cache")
        cache_subparsers = parser_cache.add_subparsers(dest="cache_command", required=True)

        parser_cache_clear = cache_subparsers.add_parser("clear")
        parser_cache_clear.add_argument("--all", action="store_true")
        parser_cache_clear.add_argument("--force", "-f", action="store_true")

        args = parser.parse_args(["cache", "clear", "--all", "--force"])

        assert args.command == "cache"
        assert args.cache_command == "clear"
        assert args.all is True
        assert args.force is True

    def test_cache_clear_without_flags(self):
        """Verify cache clear defaults without flags."""
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")

        parser_cache = subparsers.add_parser("cache")
        cache_subparsers = parser_cache.add_subparsers(dest="cache_command", required=True)

        parser_cache_clear = cache_subparsers.add_parser("clear")
        parser_cache_clear.add_argument("--all", action="store_true")
        parser_cache_clear.add_argument("--force", "-f", action="store_true")

        args = parser.parse_args(["cache", "clear"])

        assert args.command == "cache"
        assert args.cache_command == "clear"
        assert args.all is False
        assert args.force is False
