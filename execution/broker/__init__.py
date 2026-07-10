"""Broker layer for the autopilot execution engine."""
from typing import Any


async def sleeve_a_broker(db, state: Any):
    """Select the Sleeve A broker by SleeveState.mode — the single place both
    crons (weekly funnel + daily sweep) construct it, so the shadow/live switch
    lives in ONE spot.

    - mode == "shadow"  -> ShadowBrokerClient (the Phase 3D backtest replay
      engine; imagines fills from daily bars, touches no account).
    - anything else ("live") -> AlpacaFunnelBroker on the live paper account
      (owner ruling 2026-07-10: Sleeve A trades directly on Alpaca paper).

    The Alpaca client is built INSIDE this call (from the active linked account)
    so decrypted secrets never cross an Inngest step boundary."""
    from execution.constants import SLEEVE_A  # noqa: PLC0415

    sleeve = getattr(state, "sleeve", None) or SLEEVE_A
    if getattr(state, "mode", None) == "shadow":
        from execution.broker.shadow_client import ShadowBrokerClient  # noqa: PLC0415

        return ShadowBrokerClient(db, sleeve=sleeve)

    from execution.broker.alpaca_client import client_from_account  # noqa: PLC0415
    from execution.broker.alpaca_funnel_client import AlpacaFunnelBroker  # noqa: PLC0415
    from execution.broker.credentials import get_active_alpaca_account  # noqa: PLC0415

    account = await get_active_alpaca_account(db)
    return AlpacaFunnelBroker(db, client_from_account(account), sleeve=sleeve)
