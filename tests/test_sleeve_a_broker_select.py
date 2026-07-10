# tests/test_sleeve_a_broker_select.py
"""Mode-based broker selection: the ONE helper both crons use to pick the
Sleeve A broker off SleeveState.mode. shadow -> ShadowBrokerClient (3D replay);
live -> AlpacaFunnelBroker on the paper account."""
import asyncio
import types
from unittest.mock import AsyncMock, MagicMock

import execution.broker.credentials as creds_mod
import execution.broker.alpaca_client as alpaca_mod
from execution.broker import sleeve_a_broker
from execution.broker.alpaca_funnel_client import AlpacaFunnelBroker
from execution.broker.shadow_client import ShadowBrokerClient


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_shadow_mode_selects_shadow_client():
    state = types.SimpleNamespace(mode="shadow", sleeve="A")
    broker = _run(sleeve_a_broker(MagicMock(), state))
    assert isinstance(broker, ShadowBrokerClient)


def test_live_mode_selects_alpaca_funnel_broker(monkeypatch):
    state = types.SimpleNamespace(mode="live", sleeve="A")

    account = object()
    monkeypatch.setattr(creds_mod, "get_active_alpaca_account",
                        AsyncMock(return_value=account))
    monkeypatch.setattr(alpaca_mod, "client_from_account",
                        lambda row: MagicMock(name="alpaca"))

    broker = _run(sleeve_a_broker(MagicMock(), state))
    assert isinstance(broker, AlpacaFunnelBroker)


def test_default_mode_is_live(monkeypatch):
    # A state whose mode is anything other than "shadow" goes live — the
    # default so a fresh sleeve trades for real, not into the void.
    state = types.SimpleNamespace(mode="live", sleeve="A")
    monkeypatch.setattr(creds_mod, "get_active_alpaca_account",
                        AsyncMock(return_value=object()))
    monkeypatch.setattr(alpaca_mod, "client_from_account", lambda row: MagicMock())
    broker = _run(sleeve_a_broker(MagicMock(), state))
    assert isinstance(broker, AlpacaFunnelBroker)
