# Autopilot Phase 2: Broker Link + Sleeve B Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Link one Alpaca paper account (encrypted keys), stand up the order layer, and run Sleeve B — the mechanical sector-ETF rotation (30% of capital) — live on paper, with daily position snapshots, reconciliation, circuit breakers, and app-level failure alerts.

**Architecture:** All trading math is pure functions in `execution/engine/` (`(outlook, positions, equity) → targets → orders`), unit-tested with no I/O. Thin DB-edge modules (`execution/sleeve_service.py`, `execution/broker/credentials.py`) follow the `outlook_service.py` pattern. Two new Inngest crons (`execution_daily`, `execution_weekly`) follow the `weekly_outlook.py` guarded-registration pattern; paid/irreversible actions (order submission) live in their own memoized steps so Inngest retries can never double-trade (lesson from the 2026-07-08 batch double-billing incident).

**Tech Stack:** FastAPI, Prisma (Python client, Neon Postgres), Inngest (inngest-py 0.5.x), alpaca-py (paper `TradingClient`), cryptography (Fernet), pytest.

## Global Constraints

- Python 3.9-compatible typing everywhere (`Optional[X]`, `List[X]` — never `X | None`); the local test env is py3.9 and `api.index` is already unimportable there for this reason.
- Heavy imports (alpaca, prisma, resend, inngest, research_swarm agents) are lazy — inside functions/steps — so every module stays importable in any environment.
- Inngest function registration is guarded (`_register_inngest_function()` in `try/except`, module attr `None` on failure) — same pattern as `weekly_outlook.py`.
- Inngest step returns must be JSON-serializable, and **never contain decrypted API keys** (Inngest persists step results). Any step needing the broker rebuilds the client inside the step.
- Order submission steps are separate from persistence steps (retry of a persist step must never re-submit an order).
- `requirements.txt` is the ONLY file Railway installs — every runtime dep goes there.
- Migrations: hand-write SQL + `npx prisma migrate deploy --schema db/schema.prisma`. NEVER `prisma migrate dev` (shadow-DB baseline always fails).
- Email posture: alerts send only when `RESEND_API_KEY` and `OWNER_EMAIL` are both set; otherwise log + `{"status": "skipped"}`. Never fail a job because email is unconfigured.
- Cron schedule ordering: outlook Sunday 20:00 UTC → weekly batch Monday 03:00 UTC → **Sleeve B rebalance Monday 15:00 UTC** (regular NYSE hours year-round) → daily snapshot weekdays 21:15 UTC (≥15 min after close year-round).
- Sleeve B parameters (tunable constants, all in `execution/constants.py`): `SLEEVE_B_FRACTION=0.30`, top 3 ETFs, base weights `(0.5, 0.3, 0.2)`, hysteresis 2 ranks, regime invested fraction `risk_on=1.0 / neutral=0.7 / risk_off=0.4` (risk_off holds only the best defensive ETF from XLP/XLU/XLV), `MIN_TRADE_NOTIONAL=$50`, sector cap 35% of account, circuit breaker −15pp vs SPY since inception.
- Guardrails are hard-coded; the engine cannot override them. Failure posture: degrade to inaction + alert, never guess.

---

### Task 1: Schema + Migration (5 new tables)

**Files:**
- Modify: `db/schema.prisma` (append models; add back-relation on `User`)
- Create: `db/migrations/20260709000001_add_autopilot_execution/migration.sql`

**Interfaces:**
- Produces: Prisma models `LinkedBrokerAccount`, `EngineTrade`, `EnginePosition`, `SleeveSnapshot`, `SleeveState` — accessed later as `db.linkedbrokeraccount`, `db.enginetrade`, `db.engineposition`, `db.sleevesnapshot`, `db.sleevestate` (Prisma Python client lowercases model names).
- Column conventions follow `MarketOutlook`: camelCase column names, `cuid()` ids, `TIMESTAMP(3)`, `JSONB` for Json.

- [ ] **Step 1: Append models to `db/schema.prisma`**

Add to the `User` model's relation fields (next to the `UserPreferences` back-relation):

```prisma
  linkedBrokerAccounts LinkedBrokerAccount[]
```

Append at the end of the file (after `MarketOutlook`):

```prisma
// ── Autopilot execution layer (Phase 2) ─────────────────────────────────────
// Nothing in the research flow reads or writes these tables.

model LinkedBrokerAccount {
  id                 String    @id @default(cuid())
  userId             String
  user               User      @relation(fields: [userId], references: [id], onDelete: Cascade)
  provider           String    @default("alpaca")
  mode               String    @default("paper") // "paper" | "live" (live out of scope v1)
  apiKeyEncrypted    String    // Fernet ciphertext — key lives in BROKER_KEY_ENCRYPTION_KEY env
  apiSecretEncrypted String
  status             String    @default("active") // "active" | "error" | "revoked"
  lastVerifiedAt     DateTime?
  createdAt          DateTime  @default(now())
  updatedAt          DateTime  @updatedAt

  @@unique([userId, provider, mode])
}

model EngineTrade {
  id            String   @id @default(cuid())
  sleeve        String   // "A" | "B"
  symbol        String
  side          String   // "buy" | "sell"
  qty           Float
  notional      Float?   // requested notional (buys)
  fillPrice     Float?
  brokerOrderId String?
  status        String   // "filled" | "canceled" | "rejected" | "expired" | "timeout"
  journal       Json     // decision journal: outlook snapshot, weights, guardrail notes
  createdAt     DateTime @default(now())

  @@index([sleeve, createdAt])
}

model EnginePosition {
  id            String   @id @default(cuid())
  sleeve        String
  symbol        String
  qty           Float
  avgEntryPrice Float
  thesis        Json     // opening journal (outlook id, regime, weight)
  openedAt      DateTime @default(now())
  updatedAt     DateTime @updatedAt

  @@unique([sleeve, symbol])
}

model SleeveSnapshot {
  id             String   @id @default(cuid())
  snapshotDate   DateTime // UTC calendar date of the snapshot
  sleeve         String
  equity         Float    // cashBalance + positionsValue
  cash           Float
  positionsValue Float
  spyClose       Float    // benchmark close for the same date
  createdAt      DateTime @default(now())

  @@unique([snapshotDate, sleeve])
}

model SleeveState {
  id                String   @id @default(cuid())
  sleeve            String   @unique // "A" | "B"
  status            String   @default("active") // "active" | "halted" (circuit breaker) | "frozen" (reconciliation mismatch)
  statusReason      String?
  cashBalance       Float    // sleeve-internal cash ledger (one broker account, per-sleeve books)
  inceptionDate     DateTime
  inceptionEquity   Float
  inceptionSpyClose Float
  createdAt         DateTime @default(now())
  updatedAt         DateTime @updatedAt
}
```

- [ ] **Step 2: Hand-write the migration SQL**

Create `db/migrations/20260709000001_add_autopilot_execution/migration.sql`:

```sql
-- CreateTable
CREATE TABLE "LinkedBrokerAccount" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "provider" TEXT NOT NULL DEFAULT 'alpaca',
    "mode" TEXT NOT NULL DEFAULT 'paper',
    "apiKeyEncrypted" TEXT NOT NULL,
    "apiSecretEncrypted" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'active',
    "lastVerifiedAt" TIMESTAMP(3),
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "LinkedBrokerAccount_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "EngineTrade" (
    "id" TEXT NOT NULL,
    "sleeve" TEXT NOT NULL,
    "symbol" TEXT NOT NULL,
    "side" TEXT NOT NULL,
    "qty" DOUBLE PRECISION NOT NULL,
    "notional" DOUBLE PRECISION,
    "fillPrice" DOUBLE PRECISION,
    "brokerOrderId" TEXT,
    "status" TEXT NOT NULL,
    "journal" JSONB NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "EngineTrade_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "EnginePosition" (
    "id" TEXT NOT NULL,
    "sleeve" TEXT NOT NULL,
    "symbol" TEXT NOT NULL,
    "qty" DOUBLE PRECISION NOT NULL,
    "avgEntryPrice" DOUBLE PRECISION NOT NULL,
    "thesis" JSONB NOT NULL,
    "openedAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "EnginePosition_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "SleeveSnapshot" (
    "id" TEXT NOT NULL,
    "snapshotDate" TIMESTAMP(3) NOT NULL,
    "sleeve" TEXT NOT NULL,
    "equity" DOUBLE PRECISION NOT NULL,
    "cash" DOUBLE PRECISION NOT NULL,
    "positionsValue" DOUBLE PRECISION NOT NULL,
    "spyClose" DOUBLE PRECISION NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "SleeveSnapshot_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "SleeveState" (
    "id" TEXT NOT NULL,
    "sleeve" TEXT NOT NULL,
    "status" TEXT NOT NULL DEFAULT 'active',
    "statusReason" TEXT,
    "cashBalance" DOUBLE PRECISION NOT NULL,
    "inceptionDate" TIMESTAMP(3) NOT NULL,
    "inceptionEquity" DOUBLE PRECISION NOT NULL,
    "inceptionSpyClose" DOUBLE PRECISION NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "SleeveState_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "LinkedBrokerAccount_userId_provider_mode_key" ON "LinkedBrokerAccount"("userId", "provider", "mode");

-- CreateIndex
CREATE INDEX "EngineTrade_sleeve_createdAt_idx" ON "EngineTrade"("sleeve", "createdAt");

-- CreateIndex
CREATE UNIQUE INDEX "EnginePosition_sleeve_symbol_key" ON "EnginePosition"("sleeve", "symbol");

-- CreateIndex
CREATE UNIQUE INDEX "SleeveSnapshot_snapshotDate_sleeve_key" ON "SleeveSnapshot"("snapshotDate", "sleeve");

-- CreateIndex
CREATE UNIQUE INDEX "SleeveState_sleeve_key" ON "SleeveState"("sleeve");

-- AddForeignKey
ALTER TABLE "LinkedBrokerAccount" ADD CONSTRAINT "LinkedBrokerAccount_userId_fkey" FOREIGN KEY ("userId") REFERENCES "users"("id") ON DELETE CASCADE ON UPDATE CASCADE;
```

> **Amendment (2026-07-09 final review):** FK must reference the physical table `"users"` (User model is `@@map("users")`); the original block said `"User"` and would fail migrate deploy.

- [ ] **Step 3: Validate the schema**

Run: `npx prisma validate --schema db/schema.prisma`
Expected: `The schema at db/schema.prisma is valid 🚀`

(Do NOT run `migrate deploy` here — that happens against prod in Task 13.)

- [ ] **Step 4: Commit**

```bash
git add db/schema.prisma db/migrations/20260709000001_add_autopilot_execution/
git commit -m "feat(autopilot): schema for broker link, trades, positions, sleeve snapshots/state"
```

---

### Task 2: Dependencies + Encrypted Credentials Module

**Files:**
- Modify: `requirements.txt` (add `alpaca-py`, explicit `cryptography`)
- Create: `execution/broker/__init__.py`
- Create: `execution/broker/credentials.py`
- Test: `tests/test_execution_credentials.py`

**Interfaces:**
- Produces: `encrypt_secret(plaintext: str) -> str`, `decrypt_secret(ciphertext: str) -> str`, `CredentialsError(Exception)`, `async get_active_alpaca_account(db) -> Optional[row]`, `async upsert_alpaca_account(db, user_id: str, api_key: str, api_secret: str) -> row`.
- Consumes: Task 1's `LinkedBrokerAccount` model (`db.linkedbrokeraccount`).
- Env var: `BROKER_KEY_ENCRYPTION_KEY` — a Fernet key (generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`).

- [ ] **Step 1: Add runtime deps to `requirements.txt`**

Append (near the other API deps):

```
alpaca-py>=0.33.0
cryptography>=42.0.0
```

(`cryptography` is already pulled in transitively by `python-jose[cryptography]` — make it explicit because Fernet is now a first-class dependency.)

- [ ] **Step 2: Write the failing tests**

Create `tests/test_execution_credentials.py`:

```python
"""Tests for execution/broker/credentials.py — Fernet round-trip + DB edge."""
from unittest.mock import AsyncMock, MagicMock

import pytest
from cryptography.fernet import Fernet

from execution.broker.credentials import (
    CredentialsError,
    decrypt_secret,
    encrypt_secret,
    get_active_alpaca_account,
    upsert_alpaca_account,
)


@pytest.fixture
def fernet_env(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("BROKER_KEY_ENCRYPTION_KEY", key)
    return key


class TestEncryptDecrypt:
    def test_round_trip(self, fernet_env):
        ciphertext = encrypt_secret("PKTEST123")
        assert ciphertext != "PKTEST123"
        assert decrypt_secret(ciphertext) == "PKTEST123"

    def test_missing_key_raises(self, monkeypatch):
        monkeypatch.delenv("BROKER_KEY_ENCRYPTION_KEY", raising=False)
        with pytest.raises(CredentialsError):
            encrypt_secret("PKTEST123")


class TestDbEdge:
    @pytest.mark.asyncio
    async def test_get_active_account_queries_alpaca_paper(self):
        db = MagicMock()
        db.linkedbrokeraccount.find_first = AsyncMock(return_value="row")
        assert await get_active_alpaca_account(db) == "row"
        db.linkedbrokeraccount.find_first.assert_awaited_once_with(
            where={"provider": "alpaca", "mode": "paper", "status": "active"}
        )

    @pytest.mark.asyncio
    async def test_upsert_encrypts_both_secrets(self, fernet_env):
        db = MagicMock()
        db.linkedbrokeraccount.upsert = AsyncMock(return_value="row")
        await upsert_alpaca_account(db, "user1", "key-abc", "secret-xyz")

        kwargs = db.linkedbrokeraccount.upsert.await_args.kwargs
        create = kwargs["data"]["create"]
        assert create["userId"] == "user1"
        assert create["apiKeyEncrypted"] != "key-abc"
        assert decrypt_secret(create["apiKeyEncrypted"]) == "key-abc"
        assert decrypt_secret(create["apiSecretEncrypted"]) == "secret-xyz"
        assert kwargs["where"] == {
            "userId_provider_mode": {
                "userId": "user1", "provider": "alpaca", "mode": "paper",
            }
        }
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_execution_credentials.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'execution.broker'`

- [ ] **Step 4: Implement**

Create `execution/broker/__init__.py` (empty file) and `execution/broker/credentials.py`:

```python
"""Encrypt/decrypt broker API credentials and load linked accounts.

Secrets are encrypted at rest with Fernet (symmetric). The Fernet key lives
ONLY in the BROKER_KEY_ENCRYPTION_KEY env var — never in the database, never
in an Inngest step result.
"""
import os
from datetime import datetime, timezone
from typing import Any, Optional


class CredentialsError(Exception):
    """Encryption key missing or ciphertext invalid."""


def _fernet():
    from cryptography.fernet import Fernet  # lazy — runtime dep

    key = os.getenv("BROKER_KEY_ENCRYPTION_KEY", "")
    if not key:
        raise CredentialsError("BROKER_KEY_ENCRYPTION_KEY not set")
    return Fernet(key.encode())


def encrypt_secret(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode()).decode()


async def get_active_alpaca_account(db) -> Optional[Any]:
    """The single active linked Alpaca paper account row, or None."""
    return await db.linkedbrokeraccount.find_first(
        where={"provider": "alpaca", "mode": "paper", "status": "active"}
    )


async def upsert_alpaca_account(db, user_id: str, api_key: str, api_secret: str) -> Any:
    payload = {
        "apiKeyEncrypted": encrypt_secret(api_key),
        "apiSecretEncrypted": encrypt_secret(api_secret),
        "status": "active",
        "lastVerifiedAt": datetime.now(timezone.utc),
    }
    return await db.linkedbrokeraccount.upsert(
        where={
            "userId_provider_mode": {
                "userId": user_id, "provider": "alpaca", "mode": "paper",
            }
        },
        data={
            "create": {"userId": user_id, "provider": "alpaca", "mode": "paper", **payload},
            "update": payload,
        },
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_execution_credentials.py -v`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add requirements.txt execution/broker/ tests/test_execution_credentials.py
git commit -m "feat(autopilot): encrypted broker credentials module + alpaca-py dep"
```

---

### Task 3: Broker Layer (interface + AlpacaPaperClient)

**Files:**
- Create: `execution/broker/base.py`
- Create: `execution/broker/alpaca_client.py`
- Test: `tests/test_execution_broker.py`

**Interfaces:**
- Produces (base.py): `BrokerPosition(symbol: str, qty: float, market_value: float, current_price: float, avg_entry_price: float)` and `BrokerOrderResult(order_id: str, symbol: str, side: str, status: str, filled_qty: float, filled_avg_price: Optional[float])` dataclasses, each with `.to_dict()`.
- Produces (alpaca_client.py): `AlpacaPaperClient(api_key, api_secret)` with **synchronous** methods (callers use `asyncio.to_thread`): `get_account_summary() -> Dict[str, float]` (keys `equity`, `cash`), `get_positions() -> List[BrokerPosition]`, `is_market_open() -> bool`, `submit_market_buy_notional(symbol, notional) -> BrokerOrderResult`, `submit_market_sell_qty(symbol, qty) -> BrokerOrderResult`. Plus module fn `client_from_account(row) -> AlpacaPaperClient` (decrypts a `LinkedBrokerAccount` row).
- All alpaca imports happen in `__init__` and are stored on `self` (`self._MarketOrderRequest`, `self._OrderSide`, `self._TimeInForce`) so tests can build an instance via `__new__` and inject fakes without alpaca-py installed.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_execution_broker.py`:

```python
"""Tests for the broker layer. alpaca-py is NOT installed in this env, so
tests build AlpacaPaperClient via __new__ and inject fakes for the SDK
attributes the constructor would normally set."""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from execution.broker.alpaca_client import AlpacaPaperClient
from execution.broker.base import BrokerOrderResult, BrokerPosition


def _bare_client(fake_trading_client):
    client = AlpacaPaperClient.__new__(AlpacaPaperClient)
    client._client = fake_trading_client
    client._MarketOrderRequest = lambda **kw: SimpleNamespace(**kw)
    client._OrderSide = SimpleNamespace(BUY="buy", SELL="sell")
    client._TimeInForce = SimpleNamespace(DAY="day")
    return client


def _fake_order(status="filled", filled_qty="2", filled_avg_price="101.5"):
    return SimpleNamespace(
        id="ord-1", symbol="XLK", side="buy", status=status,
        filled_qty=filled_qty, filled_avg_price=filled_avg_price,
    )


class TestAccountAndPositions:
    def test_get_account_summary_floats(self):
        fake = MagicMock()
        fake.get_account.return_value = SimpleNamespace(equity="100000.5", cash="30000.25")
        client = _bare_client(fake)
        assert client.get_account_summary() == {"equity": 100000.5, "cash": 30000.25}

    def test_get_positions_maps_to_dataclass(self):
        fake = MagicMock()
        fake.get_all_positions.return_value = [
            SimpleNamespace(symbol="XLE", qty="10.5", market_value="945.0",
                            current_price="90.0", avg_entry_price="88.0"),
        ]
        positions = _bare_client(fake).get_positions()
        assert positions == [BrokerPosition(
            symbol="XLE", qty=10.5, market_value=945.0,
            current_price=90.0, avg_entry_price=88.0,
        )]

    def test_is_market_open(self):
        fake = MagicMock()
        fake.get_clock.return_value = SimpleNamespace(is_open=True)
        assert _bare_client(fake).is_market_open() is True


class TestOrders:
    def test_buy_notional_submits_and_returns_fill(self):
        fake = MagicMock()
        fake.submit_order.return_value = _fake_order()
        fake.get_order_by_id.return_value = _fake_order()
        result = _bare_client(fake).submit_market_buy_notional("XLK", 500.129)

        request = fake.submit_order.call_args.kwargs["order_data"]
        assert request.symbol == "XLK"
        assert request.notional == 500.13  # rounded to cents
        assert request.side == "buy"
        assert result == BrokerOrderResult(
            order_id="ord-1", symbol="XLK", side="buy", status="filled",
            filled_qty=2.0, filled_avg_price=101.5,
        )

    def test_sell_qty_never_notional(self):
        fake = MagicMock()
        fake.submit_order.return_value = _fake_order()
        fake.get_order_by_id.return_value = _fake_order(status="filled")
        _bare_client(fake).submit_market_sell_qty("XLK", 3.25)
        request = fake.submit_order.call_args.kwargs["order_data"]
        assert request.qty == 3.25
        assert request.side == "sell"
        assert not hasattr(request, "notional")

    def test_wait_for_fill_times_out_to_timeout_status(self, monkeypatch):
        fake = MagicMock()
        fake.submit_order.return_value = _fake_order(status="accepted")
        fake.get_order_by_id.return_value = _fake_order(
            status="accepted", filled_qty="0", filled_avg_price=None
        )
        monkeypatch.setattr("execution.broker.alpaca_client._FILL_TIMEOUT_S", 0)
        result = _bare_client(fake).submit_market_buy_notional("XLK", 100)
        assert result.status == "timeout"
        assert result.filled_qty == 0.0
        assert result.filled_avg_price is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_execution_broker.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'execution.broker.base'`

- [ ] **Step 3: Implement `execution/broker/base.py`**

```python
"""Broker-agnostic value types. Any future live/other-broker client returns
these same shapes, so the engine never sees an SDK object."""
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional


@dataclass
class BrokerPosition:
    symbol: str
    qty: float
    market_value: float
    current_price: float
    avg_entry_price: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class BrokerOrderResult:
    order_id: str
    symbol: str
    side: str
    status: str  # "filled" | "canceled" | "rejected" | "expired" | "timeout"
    filled_qty: float
    filled_avg_price: Optional[float]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
```

- [ ] **Step 4: Implement `execution/broker/alpaca_client.py`**

```python
"""Alpaca paper-account client (alpaca-py TradingClient wrapper).

All methods are synchronous — async callers must use asyncio.to_thread
(same convention as the yfinance calls in weekly_batch). SDK classes are
imported in __init__ and stored on self so unit tests can inject fakes via
__new__ without alpaca-py installed.
"""
import time
from typing import Dict, List, Optional

from execution.broker.base import BrokerOrderResult, BrokerPosition

_FILL_TIMEOUT_S = 30
_TERMINAL_STATUSES = ("filled", "canceled", "rejected", "expired")


def _enum_str(value) -> str:
    return str(value.value) if hasattr(value, "value") else str(value)


class AlpacaPaperClient:
    def __init__(self, api_key: str, api_secret: str):
        from alpaca.trading.client import TradingClient  # lazy — runtime dep
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import MarketOrderRequest

        self._client = TradingClient(api_key, api_secret, paper=True)
        self._MarketOrderRequest = MarketOrderRequest
        self._OrderSide = OrderSide
        self._TimeInForce = TimeInForce

    def get_account_summary(self) -> Dict[str, float]:
        account = self._client.get_account()
        return {"equity": float(account.equity), "cash": float(account.cash)}

    def get_positions(self) -> List[BrokerPosition]:
        return [
            BrokerPosition(
                symbol=p.symbol,
                qty=float(p.qty),
                market_value=float(p.market_value),
                current_price=float(p.current_price),
                avg_entry_price=float(p.avg_entry_price),
            )
            for p in self._client.get_all_positions()
        ]

    def is_market_open(self) -> bool:
        return bool(self._client.get_clock().is_open)

    def submit_market_buy_notional(self, symbol: str, notional: float) -> BrokerOrderResult:
        order = self._client.submit_order(
            order_data=self._MarketOrderRequest(
                symbol=symbol,
                notional=round(notional, 2),
                side=self._OrderSide.BUY,
                time_in_force=self._TimeInForce.DAY,
            )
        )
        return self._wait_for_fill(order.id)

    def submit_market_sell_qty(self, symbol: str, qty: float) -> BrokerOrderResult:
        order = self._client.submit_order(
            order_data=self._MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=self._OrderSide.SELL,
                time_in_force=self._TimeInForce.DAY,
            )
        )
        return self._wait_for_fill(order.id)

    def _wait_for_fill(self, order_id) -> BrokerOrderResult:
        """Poll until terminal status or timeout. Paper market orders fill
        near-instantly in regular hours; timeout is a safety valve, and a
        'timeout' result is journaled, never guessed at."""
        deadline = time.monotonic() + _FILL_TIMEOUT_S
        while True:
            order = self._client.get_order_by_id(order_id)
            status = _enum_str(order.status)
            timed_out = time.monotonic() >= deadline
            if status in _TERMINAL_STATUSES or timed_out:
                price = order.filled_avg_price
                return BrokerOrderResult(
                    order_id=str(order.id),
                    symbol=order.symbol,
                    side=_enum_str(order.side),
                    status=status if status in _TERMINAL_STATUSES else "timeout",
                    filled_qty=float(order.filled_qty or 0),
                    filled_avg_price=float(price) if price else None,
                )
            time.sleep(1.0)


def client_from_account(row) -> AlpacaPaperClient:
    """Build a client from a LinkedBrokerAccount row (decrypts in-process;
    plaintext keys must never cross an Inngest step boundary)."""
    from execution.broker.credentials import decrypt_secret

    return AlpacaPaperClient(
        decrypt_secret(row.apiKeyEncrypted),
        decrypt_secret(row.apiSecretEncrypted),
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_execution_broker.py -v`
Expected: 6 passed

- [ ] **Step 6: Commit**

```bash
git add execution/broker/base.py execution/broker/alpaca_client.py tests/test_execution_broker.py
git commit -m "feat(autopilot): broker layer — AlpacaPaperClient with fill polling"
```

---

### Task 4: Failure Alerts (deferred from Phase 1)

**Files:**
- Create: `execution/alerts.py`
- Test: `tests/test_execution_alerts.py`

**Interfaces:**
- Produces: `send_failure_alert(subject: str, body: str) -> Dict[str, str]` — returns `{"status": "sent"|"skipped"|"error"}`. Never raises (alerting must never break the engine).
- Consumes env: `RESEND_API_KEY`, `OWNER_EMAIL` (both currently unset in prod — alerts log+skip until Tui configures Resend; that is the intended posture).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_execution_alerts.py`:

```python
"""Tests for execution/alerts.py — dormant-email failure alerts."""
import sys
import types
from unittest.mock import MagicMock

from execution.alerts import send_failure_alert


def test_skips_when_email_unconfigured(monkeypatch):
    monkeypatch.delenv("RESEND_API_KEY", raising=False)
    monkeypatch.delenv("OWNER_EMAIL", raising=False)
    assert send_failure_alert("subj", "body") == {"status": "skipped"}


def test_sends_when_configured(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_123")
    monkeypatch.setenv("OWNER_EMAIL", "tui@example.com")
    fake_resend = types.ModuleType("resend")
    fake_resend.Emails = MagicMock()
    monkeypatch.setitem(sys.modules, "resend", fake_resend)

    assert send_failure_alert("daily cron failed", "trace") == {"status": "sent"}
    payload = fake_resend.Emails.send.call_args.args[0]
    assert payload["to"] == ["tui@example.com"]
    assert "[Autopilot alert]" in payload["subject"]


def test_never_raises_on_send_error(monkeypatch):
    monkeypatch.setenv("RESEND_API_KEY", "re_123")
    monkeypatch.setenv("OWNER_EMAIL", "tui@example.com")
    fake_resend = types.ModuleType("resend")
    fake_resend.Emails = MagicMock()
    fake_resend.Emails.send.side_effect = RuntimeError("api down")
    monkeypatch.setitem(sys.modules, "resend", fake_resend)

    assert send_failure_alert("subj", "body") == {"status": "error"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_execution_alerts.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'execution.alerts'`

- [ ] **Step 3: Implement `execution/alerts.py`**

```python
"""App-level failure alerts for the execution layer (deferred from Phase 1).

Same dormant-email posture as the outlook email: sends only when both
RESEND_API_KEY and OWNER_EMAIL are set; otherwise logs and reports
"skipped". NEVER raises — a broken alert channel must not break the engine
(the engine's failure posture is inaction + alert, and inaction still
happened).
"""
import html
import logging
import os
from typing import Dict

logger = logging.getLogger(__name__)


def send_failure_alert(subject: str, body: str) -> Dict[str, str]:
    owner_email = os.getenv("OWNER_EMAIL", "")
    api_key = os.getenv("RESEND_API_KEY", "")
    if not owner_email or not api_key:
        logger.warning("Autopilot alert skipped (email unconfigured): %s — %s", subject, body)
        return {"status": "skipped"}
    try:
        import resend  # lazy — only needed when email is actually enabled

        resend.api_key = api_key
        resend.Emails.send({
            "from": "DVRG Autopilot <digest@dvrg.co>",
            "to": [owner_email],
            "subject": f"[Autopilot alert] {subject}",
            "html": f"<pre style='font-family:monospace'>{html.escape(body)}</pre>",
        })
        return {"status": "sent"}
    except Exception:
        logger.exception("Autopilot alert failed to send: %s", subject)
        return {"status": "error"}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_execution_alerts.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add execution/alerts.py tests/test_execution_alerts.py
git commit -m "feat(autopilot): app-level failure alerts (dormant-email posture)"
```

---

### Task 5: Sleeve B Selection + Targets (pure engine core)

**Files:**
- Modify: `execution/constants.py` (append Sleeve B parameters)
- Create: `execution/engine/__init__.py`
- Create: `execution/engine/sleeve_b.py`
- Test: `tests/test_execution_sleeve_b.py`

**Interfaces:**
- Produces (constants.py): `SLEEVE_B = "B"`, `SLEEVE_B_FRACTION = 0.30`, `SLEEVE_B_TOP_N = 3`, `SLEEVE_B_BASE_WEIGHTS = (0.5, 0.3, 0.2)`, `HYSTERESIS_RANKS = 2`, `REGIME_INVESTED_FRACTION = {"risk_on": 1.0, "neutral": 0.7, "risk_off": 0.4}`, `DEFENSIVE_ETFS = ("XLP", "XLU", "XLV")`, `MIN_TRADE_NOTIONAL = 50.0`, `MAX_SECTOR_PCT_OF_ACCOUNT = 0.35`, `CIRCUIT_BREAKER_VS_SPY = -0.15`, `POSITION_QTY_TOLERANCE = 0.01`, `OUTLOOK_MAX_AGE_DAYS = 8`.
- Produces (sleeve_b.py): `select_etfs(rankings, held, regime) -> List[str]`, `compute_weights(selection, conviction) -> Dict[str, float]`, `compute_targets(outlook: Dict, held: Sequence[str], sleeve_equity: float) -> Dict` returning `{"targets": {etf: notional}, "journal": {...}}`.
- Consumes: `outlook` dict shaped like a serialized `MarketOutlook` row — `regime: str`, `conviction: Optional[float]`, `sectorRankings: List[{etf, sector, rank_1m, rank_change, score, ...}]`, `id: str`.

- [ ] **Step 1: Append parameters to `execution/constants.py`**

```python
# ── Sleeve B (mechanical ETF rotation — Phase 2) ────────────────────────────
SLEEVE_B = "B"
SLEEVE_B_FRACTION = 0.30           # share of total account equity Sleeve B manages
SLEEVE_B_TOP_N = 3                 # ETFs held in risk_on / neutral
SLEEVE_B_BASE_WEIGHTS = (0.5, 0.3, 0.2)  # rank-proportional base weights
HYSTERESIS_RANKS = 2               # challenger must out-rank an incumbent by >= this
REGIME_INVESTED_FRACTION = {"risk_on": 1.0, "neutral": 0.7, "risk_off": 0.4}
DEFENSIVE_ETFS = ("XLP", "XLU", "XLV")  # risk_off holds only the best of these
MIN_TRADE_NOTIONAL = 50.0          # ignore dust rebalances below this
MAX_SECTOR_PCT_OF_ACCOUNT = 0.35   # hard guardrail: one sector across both sleeves
CIRCUIT_BREAKER_VS_SPY = -0.15     # sleeve return minus SPY return since inception
POSITION_QTY_TOLERANCE = 0.01      # relative qty tolerance for reconciliation
OUTLOOK_MAX_AGE_DAYS = 8           # rebalance refuses an outlook older than this
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_execution_sleeve_b.py`:

```python
"""Tests for the pure Sleeve B rotation logic."""
from execution.engine.sleeve_b import compute_targets, compute_weights, select_etfs


def _rankings(order):
    """Build sectorRankings with rank_1m = position in `order` (1-based)."""
    return [{"etf": etf, "sector": etf, "rank_1m": i + 1, "rank_change": 0, "score": 1.0 - i * 0.1}
            for i, etf in enumerate(order)]


RANKINGS = _rankings(["XLK", "XLE", "XLF", "XLI", "XLV", "XLY", "XLP", "XLU", "XLB", "XLRE", "XLC"])


class TestSelectEtfs:
    def test_fresh_start_takes_top_3(self):
        assert select_etfs(RANKINGS, held=[], regime="risk_on") == ["XLK", "XLE", "XLF"]

    def test_incumbent_survives_one_rank_slip(self):
        # XLF slipped to rank 4; challenger XLI is rank 3 — only 1 better: hold.
        rankings = _rankings(["XLK", "XLE", "XLI", "XLF", "XLV", "XLY", "XLP", "XLU", "XLB", "XLRE", "XLC"])
        assert select_etfs(rankings, held=["XLK", "XLE", "XLF"], regime="risk_on") == ["XLK", "XLE", "XLF"]

    def test_challenger_displaces_on_clear_margin(self):
        # XLF slipped to rank 5; challenger XLI is rank 3 — 2 better: displace.
        rankings = _rankings(["XLK", "XLE", "XLI", "XLV", "XLF", "XLY", "XLP", "XLU", "XLB", "XLRE", "XLC"])
        assert select_etfs(rankings, held=["XLK", "XLE", "XLF"], regime="risk_on") == ["XLK", "XLE", "XLI"]

    def test_risk_off_single_best_defensive(self):
        # Best-ranked defensive in RANKINGS is XLV (rank 5).
        assert select_etfs(RANKINGS, held=["XLK", "XLE", "XLF"], regime="risk_off") == ["XLV"]


class TestComputeWeights:
    def test_full_conviction_uses_base_weights(self):
        assert compute_weights(["XLK", "XLE", "XLF"], conviction=1.0) == {
            "XLK": 0.5, "XLE": 0.3, "XLF": 0.2,
        }

    def test_zero_conviction_equal_weights(self):
        weights = compute_weights(["XLK", "XLE", "XLF"], conviction=0.0)
        assert all(abs(w - 1 / 3) < 1e-6 for w in weights.values())

    def test_none_conviction_blends_halfway(self):
        weights = compute_weights(["XLK", "XLE", "XLF"], conviction=None)
        assert abs(weights["XLK"] - (0.5 * 0.5 + 0.5 / 3)) < 1e-6

    def test_single_etf_gets_full_weight(self):
        assert compute_weights(["XLV"], conviction=0.8) == {"XLV": 1.0}


class TestComputeTargets:
    def test_neutral_regime_holds_30pct_cash(self):
        outlook = {"id": "o1", "regime": "neutral", "conviction": 1.0, "sectorRankings": RANKINGS}
        result = compute_targets(outlook, held=[], sleeve_equity=30000.0)
        assert sum(result["targets"].values()) == 21000.0  # 70% invested
        assert result["targets"]["XLK"] == 10500.0  # 0.5 * 21000

    def test_risk_off_majority_cash(self):
        outlook = {"id": "o1", "regime": "risk_off", "conviction": 0.9, "sectorRankings": RANKINGS}
        result = compute_targets(outlook, held=["XLK"], sleeve_equity=30000.0)
        assert result["targets"] == {"XLV": 12000.0}  # 40% invested, 60% cash

    def test_journal_is_complete(self):
        outlook = {"id": "o1", "regime": "risk_on", "conviction": 0.7, "sectorRankings": RANKINGS}
        journal = compute_targets(outlook, held=["XLE"], sleeve_equity=30000.0)["journal"]
        for key in ("outlook_id", "regime", "conviction", "invested_fraction",
                    "sleeve_equity", "selection", "weights", "held_before"):
            assert key in journal
        assert journal["outlook_id"] == "o1"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_execution_sleeve_b.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'execution.engine'`

- [ ] **Step 4: Implement**

Create `execution/engine/__init__.py` (empty) and `execution/engine/sleeve_b.py`:

```python
"""Sleeve B — mechanical sector-ETF rotation (pure functions, no I/O).

The control group: top-N sector ETFs by outlook 1-month rank,
conviction-weighted, hysteresis against rank jitter, regime gate on the
invested fraction. No LLM sits between the ranking and the orders.
"""
from typing import Any, Dict, List, Optional, Sequence

from execution.constants import (
    DEFENSIVE_ETFS,
    HYSTERESIS_RANKS,
    REGIME_INVESTED_FRACTION,
    SLEEVE_B_BASE_WEIGHTS,
    SLEEVE_B_TOP_N,
)


def _rank_map(rankings: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    return {r["etf"]: r["rank_1m"] for r in rankings}


def select_etfs(
    rankings: Sequence[Dict[str, Any]],
    held: Sequence[str],
    regime: str,
) -> List[str]:
    """Pick Sleeve B's ETFs, best rank first.

    risk_off: single best-ranked defensive ETF (XLP/XLU/XLV).
    Otherwise: top N by rank_1m, except an incumbent holding keeps its slot
    unless the challenger out-ranks it by >= HYSTERESIS_RANKS (hysteresis
    against rank jitter).
    """
    rank = _rank_map(rankings)
    if regime == "risk_off":
        defensive = sorted((e for e in DEFENSIVE_ETFS if e in rank), key=lambda e: rank[e])
        return defensive[:1]

    top = sorted(rank, key=lambda e: rank[e])[:SLEEVE_B_TOP_N]
    selection = [e for e in top if e in held]
    challengers = [e for e in top if e not in held]
    incumbents_out = sorted(
        (e for e in held if e in rank and e not in top), key=lambda e: rank[e]
    )

    while len(selection) < SLEEVE_B_TOP_N and (challengers or incumbents_out):
        challenger = challengers[0] if challengers else None
        incumbent = incumbents_out[0] if incumbents_out else None
        challenger_wins = challenger is not None and (
            incumbent is None or rank[challenger] <= rank[incumbent] - HYSTERESIS_RANKS
        )
        if challenger_wins:
            selection.append(challengers.pop(0))
        else:
            selection.append(incumbents_out.pop(0))
    return sorted(selection, key=lambda e: rank[e])


def compute_weights(selection: List[str], conviction: Optional[float]) -> Dict[str, float]:
    """Rank-proportional base weights blended toward equal weight as
    strategist conviction falls: w = c*base + (1-c)*equal. Missing
    conviction (strategist fallback week) counts as 0.5."""
    n = len(selection)
    if n == 0:
        return {}
    base = list(SLEEVE_B_BASE_WEIGHTS[:n])
    total = sum(base)
    base = [b / total for b in base]
    c = 0.5 if conviction is None else max(0.0, min(1.0, conviction))
    return {etf: round(c * base[i] + (1 - c) / n, 6) for i, etf in enumerate(selection)}


def compute_targets(
    outlook: Dict[str, Any],
    held: Sequence[str],
    sleeve_equity: float,
) -> Dict[str, Any]:
    """(outlook, holdings, equity) -> target notionals + decision journal."""
    regime = outlook["regime"]
    selection = select_etfs(outlook["sectorRankings"], held, regime)
    weights = compute_weights(selection, outlook.get("conviction"))
    invested_fraction = REGIME_INVESTED_FRACTION.get(regime, REGIME_INVESTED_FRACTION["neutral"])
    invested = sleeve_equity * invested_fraction
    return {
        "targets": {etf: round(invested * w, 2) for etf, w in weights.items()},
        "journal": {
            "outlook_id": outlook.get("id"),
            "regime": regime,
            "conviction": outlook.get("conviction"),
            "invested_fraction": invested_fraction,
            "sleeve_equity": round(sleeve_equity, 2),
            "selection": selection,
            "weights": weights,
            "held_before": list(held),
        },
    }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_execution_sleeve_b.py -v`
Expected: 11 passed

- [ ] **Step 6: Commit**

```bash
git add execution/constants.py execution/engine/ tests/test_execution_sleeve_b.py
git commit -m "feat(autopilot): Sleeve B rotation core — selection, hysteresis, regime gate"
```

---

### Task 6: Order Construction + Guardrails (pure)

**Files:**
- Create: `execution/engine/orders.py`
- Create: `execution/engine/guardrails.py`
- Test: `tests/test_execution_orders.py`

**Interfaces:**
- Produces (orders.py): `diff_to_orders(targets: Dict[str, float], positions: Dict[str, Dict[str, float]]) -> List[Dict]`. `positions` maps symbol → `{"qty", "market_value", "current_price"}` (from `BrokerPosition.to_dict()`). Returns order dicts, **sells first**: sells are `{"symbol", "side": "sell", "qty", "est_notional"}`, buys are `{"symbol", "side": "buy", "notional"}`.
- Produces (guardrails.py): `enforce_guardrails(orders: List[Dict], account_equity: float, cash_available: float, allow_buys: bool = True) -> Tuple[List[Dict], List[str]]` — returns (adjusted orders, human-readable notes for the journal).
- Consumes: `MIN_TRADE_NOTIONAL`, `MAX_SECTOR_PCT_OF_ACCOUNT` from `execution.constants` (Task 5).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_execution_orders.py`:

```python
"""Tests for pure order construction and hard guardrails."""
from execution.engine.guardrails import enforce_guardrails
from execution.engine.orders import diff_to_orders


def _pos(qty, price):
    return {"qty": qty, "market_value": qty * price, "current_price": price}


class TestDiffToOrders:
    def test_fresh_start_all_buys(self):
        orders = diff_to_orders({"XLK": 10000.0, "XLE": 6000.0}, positions={})
        assert orders == [
            {"symbol": "XLE", "side": "buy", "notional": 6000.0},
            {"symbol": "XLK", "side": "buy", "notional": 10000.0},
        ]

    def test_sells_come_first_and_full_exit_sells_all_qty(self):
        orders = diff_to_orders(
            {"XLK": 10000.0},
            positions={"XLF": _pos(qty=50.0, price=40.0), "XLK": _pos(qty=80.0, price=100.0)},
        )
        assert orders[0] == {"symbol": "XLF", "side": "sell", "qty": 50.0, "est_notional": 2000.0}
        assert orders[1] == {"symbol": "XLK", "side": "buy", "notional": 2000.0}

    def test_trim_sells_partial_qty_never_short(self):
        orders = diff_to_orders({"XLK": 5000.0}, positions={"XLK": _pos(qty=80.0, price=100.0)})
        assert orders == [{"symbol": "XLK", "side": "sell", "qty": 30.0, "est_notional": 3000.0}]

    def test_dust_deltas_ignored(self):
        # $30 delta < MIN_TRADE_NOTIONAL ($50) in both directions
        assert diff_to_orders({"XLK": 8030.0}, positions={"XLK": _pos(qty=80.0, price=100.0)}) == []
        assert diff_to_orders({"XLK": 7970.0}, positions={"XLK": _pos(qty=80.0, price=100.0)}) == []


class TestGuardrails:
    def test_buys_capped_by_available_cash_including_sell_proceeds(self):
        orders = [
            {"symbol": "XLF", "side": "sell", "qty": 10.0, "est_notional": 1000.0},
            {"symbol": "XLK", "side": "buy", "notional": 2500.0},
        ]
        adjusted, notes = enforce_guardrails(orders, account_equity=100000.0, cash_available=2000.0)
        assert adjusted[1]["notional"] == 2500.0  # 2000 cash + 1000 proceeds covers it
        assert notes == []

        adjusted, notes = enforce_guardrails(orders, account_equity=100000.0, cash_available=1000.0)
        assert adjusted[1]["notional"] == 2000.0  # capped at 1000 + 1000
        assert len(notes) == 1

    def test_sector_cap_35pct_of_account(self):
        orders = [{"symbol": "XLK", "side": "buy", "notional": 40000.0}]
        adjusted, notes = enforce_guardrails(orders, account_equity=100000.0, cash_available=50000.0)
        assert adjusted[0]["notional"] == 35000.0
        assert len(notes) == 1

    def test_halted_sleeve_drops_buys_keeps_sells(self):
        orders = [
            {"symbol": "XLF", "side": "sell", "qty": 10.0, "est_notional": 1000.0},
            {"symbol": "XLK", "side": "buy", "notional": 500.0},
        ]
        adjusted, notes = enforce_guardrails(
            orders, account_equity=100000.0, cash_available=5000.0, allow_buys=False
        )
        assert adjusted == [orders[0]]
        assert any("halted" in n for n in notes)

    def test_penniless_buys_dropped(self):
        orders = [{"symbol": "XLK", "side": "buy", "notional": 100.0}]
        adjusted, notes = enforce_guardrails(orders, account_equity=100000.0, cash_available=0.0)
        assert adjusted == []
        assert len(notes) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_execution_orders.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'execution.engine.guardrails'`

- [ ] **Step 3: Implement `execution/engine/orders.py`**

```python
"""Turn target notionals into concrete market orders (pure).

Sells first (they free the cash the buys need). Full exits sell the whole
position qty; trims sell qty at current price; buys are notional (Alpaca
notional orders are DAY-only, which is what we use anyway).
"""
from typing import Any, Dict, List

from execution.constants import MIN_TRADE_NOTIONAL


def diff_to_orders(
    targets: Dict[str, float],
    positions: Dict[str, Dict[str, float]],
) -> List[Dict[str, Any]]:
    sells: List[Dict[str, Any]] = []
    buys: List[Dict[str, Any]] = []
    for symbol in sorted(set(targets) | set(positions)):
        target = targets.get(symbol, 0.0)
        pos = positions.get(symbol)
        current = pos["market_value"] if pos else 0.0
        delta = target - current

        if pos and delta < 0 and (target <= 0 or -delta >= MIN_TRADE_NOTIONAL):
            full_exit = target <= 0
            qty = pos["qty"] if full_exit else round(-delta / pos["current_price"], 4)
            qty = min(qty, pos["qty"])  # never short
            if qty > 0:
                sells.append({
                    "symbol": symbol,
                    "side": "sell",
                    "qty": qty,
                    "est_notional": round(qty * pos["current_price"], 2),
                })
        elif delta >= MIN_TRADE_NOTIONAL:
            buys.append({"symbol": symbol, "side": "buy", "notional": round(delta, 2)})
    return sells + buys
```

- [ ] **Step 4: Implement `execution/engine/guardrails.py`**

```python
"""Hard-coded guardrails the engine cannot override (pure).

Sells always pass (they only reduce exposure). Buys are capped by:
- the sleeve/sector concentration limit (35% of account equity per sector —
  each sector ETF is one sector), then
- available cash including estimated sell proceeds (no leverage, ever), then
- dropped when a halted sleeve forbids new buys (circuit breaker) or when
  less than $1 of cash remains (Alpaca's notional minimum).
"""
from typing import Any, Dict, List, Tuple

from execution.constants import MAX_SECTOR_PCT_OF_ACCOUNT

_ALPACA_MIN_NOTIONAL = 1.0


def enforce_guardrails(
    orders: List[Dict[str, Any]],
    account_equity: float,
    cash_available: float,
    allow_buys: bool = True,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    notes: List[str] = []
    adjusted: List[Dict[str, Any]] = []
    sector_cap = MAX_SECTOR_PCT_OF_ACCOUNT * account_equity
    cash = cash_available + sum(
        o.get("est_notional", 0.0) for o in orders if o["side"] == "sell"
    )

    for order in orders:
        if order["side"] == "sell":
            adjusted.append(order)
            continue
        if not allow_buys:
            notes.append(f"{order['symbol']}: buy dropped — sleeve halted (circuit breaker)")
            continue
        notional = order["notional"]
        if notional > sector_cap:
            notes.append(
                f"{order['symbol']}: buy capped at 35% sector limit "
                f"({notional:.2f} -> {sector_cap:.2f})"
            )
            notional = sector_cap
        if cash < _ALPACA_MIN_NOTIONAL:
            notes.append(f"{order['symbol']}: buy dropped — no cash available")
            continue
        if notional > cash:
            notes.append(
                f"{order['symbol']}: buy capped by available cash "
                f"({notional:.2f} -> {cash:.2f})"
            )
            notional = cash
        adjusted.append({**order, "notional": round(notional, 2)})
        cash -= notional
    return adjusted, notes
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_execution_orders.py -v`
Expected: 8 passed

- [ ] **Step 6: Commit**

```bash
git add execution/engine/orders.py execution/engine/guardrails.py tests/test_execution_orders.py
git commit -m "feat(autopilot): order construction + hard guardrails (no leverage, sector cap)"
```

---

### Task 7: Reconciliation + Circuit Breaker (pure)

**Files:**
- Create: `execution/engine/reconcile.py`
- Create: `execution/engine/circuit_breaker.py`
- Test: `tests/test_execution_reconcile.py`

**Interfaces:**
- Produces (reconcile.py): `find_mismatches(broker_qty: Dict[str, float], engine_qty: Dict[str, float]) -> List[str]` — empty list means clean; each entry is a human-readable mismatch line.
- Produces (circuit_breaker.py): `circuit_breaker_tripped(equity: float, inception_equity: float, spy_close: float, inception_spy_close: float) -> bool`.
- Consumes: `POSITION_QTY_TOLERANCE`, `CIRCUIT_BREAKER_VS_SPY` from `execution.constants`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_execution_reconcile.py`:

```python
"""Tests for reconciliation and circuit-breaker math."""
from execution.engine.circuit_breaker import circuit_breaker_tripped
from execution.engine.reconcile import find_mismatches


class TestFindMismatches:
    def test_clean_within_tolerance(self):
        # 1% relative tolerance absorbs fractional-share rounding drift
        assert find_mismatches({"XLK": 100.0}, {"XLK": 100.5}) == []

    def test_qty_drift_beyond_tolerance(self):
        result = find_mismatches({"XLK": 100.0}, {"XLK": 110.0})
        assert len(result) == 1 and "XLK" in result[0]

    def test_symbol_only_at_broker(self):
        result = find_mismatches({"XLK": 100.0, "AAPL": 5.0}, {"XLK": 100.0})
        assert len(result) == 1 and "AAPL" in result[0]

    def test_symbol_only_in_engine(self):
        result = find_mismatches({}, {"XLE": 10.0})
        assert len(result) == 1 and "XLE" in result[0]


class TestCircuitBreaker:
    def test_trips_at_minus_15pp_vs_spy(self):
        # sleeve -10%, SPY +5% -> -15pp: trips
        assert circuit_breaker_tripped(27000.0, 30000.0, 630.0, 600.0) is True

    def test_holds_above_threshold(self):
        # sleeve -10%, SPY +4% -> -14pp: holds
        assert circuit_breaker_tripped(27000.0, 30000.0, 624.0, 600.0) is False

    def test_absolute_loss_alone_does_not_trip(self):
        # sleeve -14%, SPY -14% -> 0pp relative: holds
        assert circuit_breaker_tripped(25800.0, 30000.0, 516.0, 600.0) is False

    def test_garbage_inception_never_trips(self):
        assert circuit_breaker_tripped(27000.0, 0.0, 630.0, 600.0) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_execution_reconcile.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement `execution/engine/reconcile.py`**

```python
"""Broker-vs-database position reconciliation (pure).

The paper account is dedicated to the engine, so every broker position must
match an EnginePosition row exactly (within fractional-share tolerance).
Any mismatch freezes trading until manually resolved — the engine never
'adopts' or 'corrects' positions it can't explain.
"""
from typing import Dict, List

from execution.constants import POSITION_QTY_TOLERANCE


def find_mismatches(
    broker_qty: Dict[str, float],
    engine_qty: Dict[str, float],
) -> List[str]:
    mismatches: List[str] = []
    for symbol in sorted(set(broker_qty) | set(engine_qty)):
        b = broker_qty.get(symbol, 0.0)
        e = engine_qty.get(symbol, 0.0)
        if abs(b - e) > POSITION_QTY_TOLERANCE * max(abs(b), abs(e), 1.0):
            mismatches.append(f"{symbol}: broker qty {b} != engine qty {e}")
    return mismatches
```

- [ ] **Step 4: Implement `execution/engine/circuit_breaker.py`**

```python
"""Per-sleeve circuit breaker (pure): halt new buys when the sleeve trails
SPY by 15 percentage points since inception. Resuming requires the manual
resume endpoint — the engine never un-halts itself."""
from execution.constants import CIRCUIT_BREAKER_VS_SPY


def circuit_breaker_tripped(
    equity: float,
    inception_equity: float,
    spy_close: float,
    inception_spy_close: float,
) -> bool:
    if inception_equity <= 0 or inception_spy_close <= 0:
        return False
    sleeve_return = equity / inception_equity - 1.0
    spy_return = spy_close / inception_spy_close - 1.0
    return (sleeve_return - spy_return) <= CIRCUIT_BREAKER_VS_SPY
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_execution_reconcile.py -v`
Expected: 8 passed

- [ ] **Step 6: Commit**

```bash
git add execution/engine/reconcile.py execution/engine/circuit_breaker.py tests/test_execution_reconcile.py
git commit -m "feat(autopilot): reconciliation + circuit-breaker math"
```

---

### Task 8: Sleeve DB Service (thin edge, like outlook_service)

**Files:**
- Create: `execution/sleeve_service.py`
- Test: `tests/test_execution_sleeve_service.py`

**Interfaces:**
- Produces:
  - `async get_sleeve_state(db, sleeve: str) -> Optional[row]`
  - `async init_sleeve_state(db, sleeve: str, cash: float, spy_close: float, inception_date: datetime) -> row`
  - `async set_sleeve_status(db, sleeve: str, status: str, reason: Optional[str] = None) -> row`
  - `async update_sleeve_cash(db, sleeve: str, cash_balance: float) -> row`
  - `async get_engine_positions(db, sleeve: str) -> List[row]`
  - `async store_snapshot(db, sleeve: str, snapshot_date: datetime, equity: float, cash: float, positions_value: float, spy_close: float) -> row` (upsert on `(snapshotDate, sleeve)`)
  - `async apply_fill(db, sleeve: str, fill: Dict, requested_notional: Optional[float], journal: Dict) -> float` — records the `EngineTrade`, upserts/deletes the `EnginePosition`, returns the **signed cash delta** (negative for buys) so the caller can update the ledger.
- Consumes: `fill` dicts shaped like `BrokerOrderResult.to_dict()` (Task 3); Prisma models from Task 1.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_execution_sleeve_service.py`:

```python
"""Tests for the sleeve DB edge. All prisma calls mocked (AsyncMock)."""
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from execution.sleeve_service import apply_fill, init_sleeve_state, store_snapshot

RUN_DATE = datetime(2026, 7, 13, tzinfo=timezone.utc)


def _db():
    db = MagicMock()
    for model in ("sleevestate", "sleevesnapshot", "enginetrade", "engineposition"):
        table = MagicMock()
        for op in ("create", "update", "upsert", "delete", "find_unique", "find_many", "find_first"):
            setattr(table, op, AsyncMock(return_value=SimpleNamespace(id="row1")))
        setattr(db, model, table)
    return db


@pytest.mark.asyncio
async def test_init_sleeve_state_sets_inception_baseline():
    db = _db()
    await init_sleeve_state(db, "B", cash=30000.0, spy_close=600.0, inception_date=RUN_DATE)
    data = db.sleevestate.create.await_args.kwargs["data"]
    assert data["sleeve"] == "B"
    assert data["cashBalance"] == 30000.0
    assert data["inceptionEquity"] == 30000.0
    assert data["inceptionSpyClose"] == 600.0
    assert data["status"] == "active"


@pytest.mark.asyncio
async def test_store_snapshot_upserts_on_date_and_sleeve():
    db = _db()
    await store_snapshot(db, "B", RUN_DATE, equity=31000.0, cash=9000.0,
                         positions_value=22000.0, spy_close=605.0)
    kwargs = db.sleevesnapshot.upsert.await_args.kwargs
    assert kwargs["where"] == {
        "snapshotDate_sleeve": {"snapshotDate": RUN_DATE, "sleeve": "B"}
    }
    assert kwargs["data"]["create"]["equity"] == 31000.0


@pytest.mark.asyncio
async def test_apply_fill_buy_creates_position_and_returns_negative_cash_delta():
    db = _db()
    db.engineposition.find_unique = AsyncMock(return_value=None)
    fill = {"order_id": "o1", "symbol": "XLK", "side": "buy", "status": "filled",
            "filled_qty": 10.0, "filled_avg_price": 100.0}
    delta = await apply_fill(db, "B", fill, requested_notional=1000.0, journal={"regime": "risk_on"})

    assert delta == -1000.0
    trade = db.enginetrade.create.await_args.kwargs["data"]
    assert trade["symbol"] == "XLK" and trade["side"] == "buy" and trade["qty"] == 10.0
    upsert = db.engineposition.upsert.await_args.kwargs
    assert upsert["data"]["create"]["qty"] == 10.0
    assert upsert["data"]["create"]["avgEntryPrice"] == 100.0


@pytest.mark.asyncio
async def test_apply_fill_buy_averages_into_existing_position():
    db = _db()
    db.engineposition.find_unique = AsyncMock(
        return_value=SimpleNamespace(qty=10.0, avgEntryPrice=90.0)
    )
    fill = {"order_id": "o2", "symbol": "XLK", "side": "buy", "status": "filled",
            "filled_qty": 10.0, "filled_avg_price": 110.0}
    await apply_fill(db, "B", fill, requested_notional=1100.0, journal={})
    update = db.engineposition.upsert.await_args.kwargs["data"]["update"]
    assert update["qty"] == 20.0
    assert update["avgEntryPrice"] == 100.0  # (10*90 + 10*110) / 20


@pytest.mark.asyncio
async def test_apply_fill_full_sell_deletes_position():
    db = _db()
    db.engineposition.find_unique = AsyncMock(
        return_value=SimpleNamespace(qty=10.0, avgEntryPrice=90.0)
    )
    fill = {"order_id": "o3", "symbol": "XLE", "side": "sell", "status": "filled",
            "filled_qty": 10.0, "filled_avg_price": 95.0}
    delta = await apply_fill(db, "B", fill, requested_notional=None, journal={})
    assert delta == 950.0
    db.engineposition.delete.assert_awaited_once()


@pytest.mark.asyncio
async def test_apply_fill_unfilled_order_records_trade_but_touches_nothing():
    db = _db()
    fill = {"order_id": "o4", "symbol": "XLK", "side": "buy", "status": "timeout",
            "filled_qty": 0.0, "filled_avg_price": None}
    delta = await apply_fill(db, "B", fill, requested_notional=500.0, journal={})
    assert delta == 0.0
    db.enginetrade.create.assert_awaited_once()  # journaled for the audit trail
    db.engineposition.upsert.assert_not_awaited()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_execution_sleeve_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'execution.sleeve_service'`

- [ ] **Step 3: Implement `execution/sleeve_service.py`**

```python
"""DB touchpoints for sleeve state, positions, trades, and snapshots.

Same edge-layer role outlook_service.py plays for MarketOutlook: all prisma
access for the execution engine funnels through here; everything above it
is pure. JSON columns are wrapped in prisma.Json at this edge only.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

_QTY_EPSILON = 1e-6


async def get_sleeve_state(db, sleeve: str) -> Optional[Any]:
    return await db.sleevestate.find_unique(where={"sleeve": sleeve})


async def init_sleeve_state(
    db, sleeve: str, cash: float, spy_close: float, inception_date: datetime
) -> Any:
    return await db.sleevestate.create(data={
        "sleeve": sleeve,
        "status": "active",
        "cashBalance": round(cash, 2),
        "inceptionDate": inception_date,
        "inceptionEquity": round(cash, 2),
        "inceptionSpyClose": spy_close,
    })


async def set_sleeve_status(db, sleeve: str, status: str, reason: Optional[str] = None) -> Any:
    return await db.sleevestate.update(
        where={"sleeve": sleeve},
        data={"status": status, "statusReason": reason},
    )


async def update_sleeve_cash(db, sleeve: str, cash_balance: float) -> Any:
    return await db.sleevestate.update(
        where={"sleeve": sleeve},
        data={"cashBalance": round(cash_balance, 2)},
    )


async def get_engine_positions(db, sleeve: str) -> List[Any]:
    return await db.engineposition.find_many(where={"sleeve": sleeve})


async def store_snapshot(
    db, sleeve: str, snapshot_date: datetime, equity: float,
    cash: float, positions_value: float, spy_close: float,
) -> Any:
    payload = {
        "equity": round(equity, 2),
        "cash": round(cash, 2),
        "positionsValue": round(positions_value, 2),
        "spyClose": spy_close,
    }
    return await db.sleevesnapshot.upsert(
        where={"snapshotDate_sleeve": {"snapshotDate": snapshot_date, "sleeve": sleeve}},
        data={
            "create": {"snapshotDate": snapshot_date, "sleeve": sleeve, **payload},
            "update": payload,
        },
    )


async def apply_fill(
    db, sleeve: str, fill: Dict[str, Any],
    requested_notional: Optional[float], journal: Dict[str, Any],
) -> float:
    """Record one broker fill: EngineTrade row (always — even unfilled
    orders belong in the audit trail) + EnginePosition upsert/delete.
    Returns the signed cash delta (negative for buys)."""
    from prisma import Json  # runtime-only dependency

    symbol = fill["symbol"]
    side = fill["side"]
    filled_qty = float(fill.get("filled_qty") or 0.0)
    fill_price = fill.get("filled_avg_price")

    await db.enginetrade.create(data={
        "sleeve": sleeve,
        "symbol": symbol,
        "side": side,
        "qty": filled_qty,
        "notional": requested_notional,
        "fillPrice": fill_price,
        "brokerOrderId": fill.get("order_id"),
        "status": fill["status"],
        "journal": Json(journal),
    })

    if filled_qty <= 0 or fill_price is None:
        return 0.0  # nothing actually traded

    notional = filled_qty * float(fill_price)
    existing = await db.engineposition.find_unique(
        where={"sleeve_symbol": {"sleeve": sleeve, "symbol": symbol}}
    )

    if side == "buy":
        if existing is None:
            new_qty, new_avg = filled_qty, float(fill_price)
        else:
            new_qty = existing.qty + filled_qty
            new_avg = (existing.qty * existing.avgEntryPrice + notional) / new_qty
        await db.engineposition.upsert(
            where={"sleeve_symbol": {"sleeve": sleeve, "symbol": symbol}},
            data={
                "create": {
                    "sleeve": sleeve, "symbol": symbol, "qty": new_qty,
                    "avgEntryPrice": round(new_avg, 4), "thesis": Json(journal),
                },
                "update": {"qty": new_qty, "avgEntryPrice": round(new_avg, 4)},
            },
        )
        return -round(notional, 2)

    # sell
    remaining = (existing.qty if existing else 0.0) - filled_qty
    if remaining <= _QTY_EPSILON:
        if existing is not None:
            await db.engineposition.delete(
                where={"sleeve_symbol": {"sleeve": sleeve, "symbol": symbol}}
            )
    else:
        await db.engineposition.update(
            where={"sleeve_symbol": {"sleeve": sleeve, "symbol": symbol}},
            data={"qty": remaining},
        )
    return round(notional, 2)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_execution_sleeve_service.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add execution/sleeve_service.py tests/test_execution_sleeve_service.py
git commit -m "feat(autopilot): sleeve DB service — state, snapshots, fills, cash ledger"
```

---

### Task 9: Daily Cron (snapshot + reconcile + circuit breaker)

**Files:**
- Create: `inngest_app/functions/execution_daily.py`
- Test: `tests/test_execution_daily.py`

**Interfaces:**
- Produces: module attr `execution_daily` (Inngest function or `None` when SDK absent); pure helper `build_sleeve_snapshot(state_cash: float, engine_symbols: List[str], broker_positions: List[Dict]) -> Dict` returning `{"positions_value": float, "equity": float}`.
- Consumes: `get_active_alpaca_account` (Task 2), `client_from_account` (Task 3), `send_failure_alert` (Task 4), `find_mismatches`/`circuit_breaker_tripped` (Task 7), sleeve_service fns (Task 8), `SLEEVE_B` constant, `api.lib.db.get_db`, `research_swarm.data.market_data_client.MarketDataClient` (SPY close).
- Cron: `15 21 * * 1-5` — 21:15 UTC weekdays (≥15 min after NYSE close in both EST and EDT).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_execution_daily.py`:

```python
"""Tests for execution_daily — pure helper + guarded registration."""
import importlib


def _sdk_available() -> bool:
    try:
        from inngest import Inngest  # noqa: F401
        return True
    except Exception:
        return False


def test_module_imports_without_sdk():
    mod = importlib.import_module("inngest_app.functions.execution_daily")
    if not _sdk_available():
        assert mod.execution_daily is None


def test_build_sleeve_snapshot_only_counts_engine_symbols():
    from inngest_app.functions.execution_daily import build_sleeve_snapshot

    broker_positions = [
        {"symbol": "XLK", "qty": 10.0, "market_value": 1000.0, "current_price": 100.0},
        {"symbol": "AAPL", "qty": 5.0, "market_value": 900.0, "current_price": 180.0},
    ]
    snap = build_sleeve_snapshot(
        state_cash=500.0, engine_symbols=["XLK"], broker_positions=broker_positions
    )
    assert snap == {"positions_value": 1000.0, "equity": 1500.0}


def test_build_sleeve_snapshot_empty_book():
    from inngest_app.functions.execution_daily import build_sleeve_snapshot

    assert build_sleeve_snapshot(9000.0, [], []) == {
        "positions_value": 0.0, "equity": 9000.0,
    }
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_execution_daily.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement `inngest_app/functions/execution_daily.py`**

```python
"""
Daily execution health cron — Autopilot Phase 2.

Cron: weekdays 21:15 UTC (>= 15 min after the NYSE close in EST and EDT).
Pipeline: linked account -> broker snapshot -> reconcile vs EnginePosition
-> SleeveSnapshot upsert -> circuit-breaker check. This cron NEVER trades.

Failure posture: reconciliation mismatch freezes the sleeve + alerts;
a tripped circuit breaker halts the sleeve + alerts (once, on the
active->halted transition); any unhandled step failure alerts via
on_failure. Never guesses, never trades.

Step results are JSON-serializable and never contain decrypted API keys —
any step that needs the broker rebuilds the client inside the step.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


# ── Pure helpers (unit-tested) ───────────────────────────────────────────────

def build_sleeve_snapshot(
    state_cash: float,
    engine_symbols: List[str],
    broker_positions: List[Dict[str, Any]],
) -> Dict[str, float]:
    """Sleeve equity = internal cash ledger + broker market value of the
    sleeve's symbols (broker prices are the ground truth for value)."""
    positions_value = sum(
        p["market_value"] for p in broker_positions if p["symbol"] in set(engine_symbols)
    )
    return {
        "positions_value": round(positions_value, 2),
        "equity": round(state_cash + positions_value, 2),
    }


# ── Inngest function (guarded registration, weekly_outlook.py pattern) ──────

def _register_inngest_function():
    import inngest as inngest_sdk  # noqa: PLC0415

    from inngest_app.client import inngest_client  # noqa: PLC0415

    async def _on_failure(ctx: "inngest_sdk.Context") -> None:
        from execution.alerts import send_failure_alert  # noqa: PLC0415

        send_failure_alert(
            "daily execution cron failed",
            f"execution-daily failed after retries: {ctx.event.data}",
        )

    @inngest_client.create_function(
        fn_id="execution-daily",
        trigger=inngest_sdk.TriggerCron(cron="15 21 * * 1-5"),  # weekdays 21:15 UTC
        name="Autopilot Daily Snapshot",
        retries=1,
        on_failure=_on_failure,
    )
    async def execution_daily(ctx: "inngest_sdk.Context") -> Dict[str, Any]:
        step = ctx.step

        async def run_date_step() -> str:
            return datetime.now(timezone.utc).isoformat()  # replay-safe: captured once

        run_date_iso = await step.run("run-date", run_date_step)

        # Step 1: is there a linked account + sleeve state at all?
        async def load_context() -> Dict[str, Any]:
            from api.lib.db import get_db  # noqa: PLC0415
            from execution.broker.credentials import get_active_alpaca_account  # noqa: PLC0415
            from execution.constants import SLEEVE_B  # noqa: PLC0415
            from execution.sleeve_service import get_engine_positions, get_sleeve_state  # noqa: PLC0415

            db = await get_db()
            account = await get_active_alpaca_account(db)
            if account is None:
                return {"linked": False}
            state = await get_sleeve_state(db, SLEEVE_B)
            positions = await get_engine_positions(db, SLEEVE_B)
            return {
                "linked": True,
                "has_state": state is not None,
                "status": state.status if state else None,
                "cash": state.cashBalance if state else 0.0,
                "inception_equity": state.inceptionEquity if state else 0.0,
                "inception_spy": state.inceptionSpyClose if state else 0.0,
                "engine_positions": {p.symbol: p.qty for p in positions},
            }

        context = await step.run("load-context", load_context)
        if not context["linked"] or not context["has_state"]:
            return {"status": "skipped", "reason": "no linked account or sleeve not bootstrapped"}

        # Step 2: broker snapshot (client built inside the step — no secrets out)
        async def broker_snapshot() -> Dict[str, Any]:
            import asyncio  # noqa: PLC0415

            from api.lib.db import get_db  # noqa: PLC0415
            from execution.broker.alpaca_client import client_from_account  # noqa: PLC0415
            from execution.broker.credentials import get_active_alpaca_account  # noqa: PLC0415

            db = await get_db()
            client = client_from_account(await get_active_alpaca_account(db))
            positions = await asyncio.to_thread(client.get_positions)
            summary = await asyncio.to_thread(client.get_account_summary)
            return {"positions": [p.to_dict() for p in positions], "account": summary}

        broker = await step.run("broker-snapshot", broker_snapshot)

        # Step 3: reconcile — mismatch freezes the sleeve, no snapshot written
        async def reconcile() -> Dict[str, Any]:
            from api.lib.db import get_db  # noqa: PLC0415
            from execution.alerts import send_failure_alert  # noqa: PLC0415
            from execution.constants import SLEEVE_B  # noqa: PLC0415
            from execution.engine.reconcile import find_mismatches  # noqa: PLC0415
            from execution.sleeve_service import set_sleeve_status  # noqa: PLC0415

            broker_qty = {p["symbol"]: p["qty"] for p in broker["positions"]}
            mismatches = find_mismatches(broker_qty, context["engine_positions"])
            if mismatches:
                db = await get_db()
                await set_sleeve_status(db, SLEEVE_B, "frozen", "; ".join(mismatches))
                send_failure_alert(
                    "position reconciliation mismatch — Sleeve B frozen",
                    "\n".join(mismatches),
                )
            return {"mismatches": mismatches}

        recon = await step.run("reconcile", reconcile)
        if recon["mismatches"]:
            return {"status": "frozen", "mismatches": recon["mismatches"]}

        # Step 4: snapshot sleeve equity + SPY benchmark
        async def snapshot() -> Dict[str, Any]:
            import asyncio  # noqa: PLC0415

            from api.lib.db import get_db  # noqa: PLC0415
            from execution.constants import BENCHMARK, SLEEVE_B  # noqa: PLC0415
            from execution.sleeve_service import store_snapshot  # noqa: PLC0415
            from research_swarm.data.market_data_client import MarketDataClient  # noqa: PLC0415

            def spy_close() -> float:
                df = MarketDataClient().get_historical_data(BENCHMARK, period="5d")
                return float(df["Close"].dropna().iloc[-1])

            spy = await asyncio.to_thread(spy_close)
            snap = build_sleeve_snapshot(
                context["cash"],
                list(context["engine_positions"].keys()),
                broker["positions"],
            )
            run_date = datetime.fromisoformat(run_date_iso)
            snapshot_date = run_date.replace(hour=0, minute=0, second=0, microsecond=0)
            db = await get_db()
            await store_snapshot(
                db, SLEEVE_B, snapshot_date,
                equity=snap["equity"], cash=context["cash"],
                positions_value=snap["positions_value"], spy_close=spy,
            )
            return {"equity": snap["equity"], "spy_close": spy}

        snap = await step.run("snapshot", snapshot)

        # Step 5: circuit breaker (alert only on the active->halted transition)
        async def breaker_check() -> Dict[str, Any]:
            from api.lib.db import get_db  # noqa: PLC0415
            from execution.alerts import send_failure_alert  # noqa: PLC0415
            from execution.constants import SLEEVE_B  # noqa: PLC0415
            from execution.engine.circuit_breaker import circuit_breaker_tripped  # noqa: PLC0415
            from execution.sleeve_service import set_sleeve_status  # noqa: PLC0415

            tripped = circuit_breaker_tripped(
                snap["equity"], context["inception_equity"],
                snap["spy_close"], context["inception_spy"],
            )
            if tripped and context["status"] == "active":
                db = await get_db()
                await set_sleeve_status(
                    db, SLEEVE_B, "halted", "circuit breaker: -15pp vs SPY since inception"
                )
                send_failure_alert(
                    "Sleeve B circuit breaker tripped",
                    f"equity={snap['equity']} inception={context['inception_equity']} "
                    f"spy={snap['spy_close']} inception_spy={context['inception_spy']}. "
                    "New buys halted; POST /api/autopilot/sleeve/B/resume to resume.",
                )
            return {"tripped": tripped}

        breaker = await step.run("circuit-breaker", breaker_check)
        return {"status": "ok", "equity": snap["equity"], "breaker_tripped": breaker["tripped"]}

    return execution_daily


try:
    execution_daily = _register_inngest_function()
except Exception:
    execution_daily = None  # type: ignore[assignment]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_execution_daily.py -v`
Expected: 3 passed

Note for the implementer: if inngest-py 0.5.19 rejects the `on_failure` kwarg (`TypeError` at registration — the guarded try/except would silently swallow it, so check explicitly with `python -c "import inspect, inngest; print('on_failure' in inspect.signature(inngest.Inngest.create_function).parameters)"` on an SDK-bearing env, or check the mount test on Railway), drop the kwarg and instead wrap each step body's exceptions with `send_failure_alert` before re-raising.

- [ ] **Step 5: Commit**

```bash
git add inngest_app/functions/execution_daily.py tests/test_execution_daily.py
git commit -m "feat(autopilot): daily snapshot cron — reconcile, SleeveSnapshot, circuit breaker"
```

---

### Task 10: Weekly Rebalance Cron (Sleeve B live)

**Files:**
- Create: `inngest_app/functions/execution_weekly.py`
- Test: `tests/test_execution_weekly.py`

**Interfaces:**
- Produces: module attr `execution_weekly` (or `None`); pure helpers `outlook_is_stale(outlook_run_date_iso: str, now_iso: str) -> bool` and `build_rebalance_plan(outlook: Dict, engine_positions: Dict[str, float], broker_positions: List[Dict], state: Dict) -> Dict` returning `{"orders": [...], "journal": {...}, "notes": [...]}`.
- Consumes: everything from Tasks 2–8; `get_latest_outlook` from `execution.outlook_service`; `SLEEVE_B_FRACTION`, `OUTLOOK_MAX_AGE_DAYS`, `SLEEVE_B` constants.
- Cron: `0 15 * * 1` — Monday 15:00 UTC (regular NYSE hours in both EST and EDT; after the Monday 03:00 UTC batch).
- Retry safety: each order submission is its own memoized step (`order-{i}-{side}-{symbol}`); persistence is a separate step. A retry of any step never re-submits a filled order.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_execution_weekly.py`:

```python
"""Tests for execution_weekly — pure plan builder + guarded registration."""
import importlib


def _sdk_available() -> bool:
    try:
        from inngest import Inngest  # noqa: F401
        return True
    except Exception:
        return False


def _rankings(order):
    return [{"etf": etf, "sector": etf, "rank_1m": i + 1, "rank_change": 0, "score": 1.0 - i * 0.1}
            for i, etf in enumerate(order)]


RANKINGS = _rankings(["XLK", "XLE", "XLF", "XLI", "XLV", "XLY", "XLP", "XLU", "XLB", "XLRE", "XLC"])


def test_module_imports_without_sdk():
    mod = importlib.import_module("inngest_app.functions.execution_weekly")
    if not _sdk_available():
        assert mod.execution_weekly is None


def test_outlook_is_stale():
    from inngest_app.functions.execution_weekly import outlook_is_stale

    assert outlook_is_stale("2026-07-05T20:00:00+00:00", "2026-07-14T15:00:00+00:00") is True
    assert outlook_is_stale("2026-07-12T20:00:00+00:00", "2026-07-13T15:00:00+00:00") is False


def test_build_rebalance_plan_fresh_book_buys_top3():
    from inngest_app.functions.execution_weekly import build_rebalance_plan

    outlook = {"id": "o1", "regime": "risk_on", "conviction": 1.0, "sectorRankings": RANKINGS}
    plan = build_rebalance_plan(
        outlook,
        engine_positions={},
        broker_positions=[],
        state={"cashBalance": 30000.0, "status": "active", "accountEquity": 100000.0},
    )
    assert [o["symbol"] for o in plan["orders"]] == ["XLE", "XLF", "XLK"]
    assert all(o["side"] == "buy" for o in plan["orders"])
    assert sum(o["notional"] for o in plan["orders"]) == 30000.0
    assert plan["journal"]["regime"] == "risk_on"


def test_build_rebalance_plan_halted_sleeve_only_sells():
    from inngest_app.functions.execution_weekly import build_rebalance_plan

    outlook = {"id": "o1", "regime": "risk_on", "conviction": 1.0, "sectorRankings": RANKINGS}
    plan = build_rebalance_plan(
        outlook,
        engine_positions={"XLB": 100.0},  # rank 9 — will be rotated out
        broker_positions=[{"symbol": "XLB", "qty": 100.0, "market_value": 8000.0,
                           "current_price": 80.0}],
        state={"cashBalance": 22000.0, "status": "halted", "accountEquity": 100000.0},
    )
    assert all(o["side"] == "sell" for o in plan["orders"])
    assert any("halted" in n for n in plan["notes"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_execution_weekly.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement `inngest_app/functions/execution_weekly.py`**

```python
"""
Weekly Sleeve B rebalance — Autopilot Phase 2.

Cron: Monday 15:00 UTC (inside regular NYSE hours in EST and EDT; after the
Sunday 20:00 outlook and the Monday 03:00 batch).

Pipeline: preflight (account, sleeve state, fresh outlook, market open)
-> bootstrap sleeve on first run -> reconcile -> pure plan (targets, orders,
guardrails) -> one memoized step per order (retries can never double-trade)
-> persist fills + cash ledger -> summary.

Failure posture: any precondition failure -> skip the week + alert.
Doing nothing for a week never hurts a long-horizon portfolio.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


# ── Pure helpers (unit-tested) ───────────────────────────────────────────────

def outlook_is_stale(outlook_run_date_iso: str, now_iso: str) -> bool:
    from execution.constants import OUTLOOK_MAX_AGE_DAYS

    outlook_dt = datetime.fromisoformat(outlook_run_date_iso)
    now_dt = datetime.fromisoformat(now_iso)
    return (now_dt - outlook_dt).days >= OUTLOOK_MAX_AGE_DAYS


def build_rebalance_plan(
    outlook: Dict[str, Any],
    engine_positions: Dict[str, float],
    broker_positions: List[Dict[str, Any]],
    state: Dict[str, Any],
) -> Dict[str, Any]:
    """(outlook, book, state) -> {orders, journal, notes}. Pure."""
    from execution.engine.guardrails import enforce_guardrails
    from execution.engine.orders import diff_to_orders
    from execution.engine.sleeve_b import compute_targets

    held = sorted(engine_positions.keys())
    sleeve_positions = {
        p["symbol"]: p for p in broker_positions if p["symbol"] in engine_positions
    }
    positions_value = sum(p["market_value"] for p in sleeve_positions.values())
    sleeve_equity = state["cashBalance"] + positions_value

    result = compute_targets(outlook, held, sleeve_equity)
    orders = diff_to_orders(result["targets"], sleeve_positions)
    orders, notes = enforce_guardrails(
        orders,
        account_equity=state["accountEquity"],
        cash_available=state["cashBalance"],
        allow_buys=state["status"] == "active",
    )
    journal = {**result["journal"], "guardrail_notes": notes}
    return {"orders": orders, "journal": journal, "notes": notes}


# ── Inngest function (guarded registration) ─────────────────────────────────

def _register_inngest_function():
    import inngest as inngest_sdk  # noqa: PLC0415

    from inngest_app.client import inngest_client  # noqa: PLC0415

    async def _on_failure(ctx: "inngest_sdk.Context") -> None:
        from execution.alerts import send_failure_alert  # noqa: PLC0415

        send_failure_alert(
            "weekly rebalance failed",
            f"execution-weekly failed after retries: {ctx.event.data}",
        )

    @inngest_client.create_function(
        fn_id="execution-weekly",
        trigger=inngest_sdk.TriggerCron(cron="0 15 * * 1"),  # Monday 15:00 UTC
        name="Autopilot Sleeve B Rebalance",
        retries=1,
        on_failure=_on_failure,
    )
    async def execution_weekly(ctx: "inngest_sdk.Context") -> Dict[str, Any]:
        step = ctx.step

        async def run_date_step() -> str:
            return datetime.now(timezone.utc).isoformat()

        run_date_iso = await step.run("run-date", run_date_step)

        # Step 1: preflight — account, outlook freshness, market open
        async def preflight() -> Dict[str, Any]:
            import asyncio  # noqa: PLC0415

            from api.lib.db import get_db  # noqa: PLC0415
            from execution.alerts import send_failure_alert  # noqa: PLC0415
            from execution.broker.alpaca_client import client_from_account  # noqa: PLC0415
            from execution.broker.credentials import get_active_alpaca_account  # noqa: PLC0415
            from execution.constants import SLEEVE_B  # noqa: PLC0415
            from execution.outlook_service import get_latest_outlook  # noqa: PLC0415
            from execution.sleeve_service import get_sleeve_state  # noqa: PLC0415

            db = await get_db()
            account = await get_active_alpaca_account(db)
            if account is None:
                return {"go": False, "reason": "no linked broker account"}

            outlook_row = await get_latest_outlook(db)
            if outlook_row is None:
                send_failure_alert("rebalance skipped", "no MarketOutlook row exists")
                return {"go": False, "reason": "no outlook"}
            outlook_iso = outlook_row.runDate.isoformat()
            if outlook_is_stale(outlook_iso, run_date_iso):
                send_failure_alert(
                    "rebalance skipped", f"latest outlook is stale ({outlook_iso})"
                )
                return {"go": False, "reason": "stale outlook"}

            state = await get_sleeve_state(db, SLEEVE_B)
            if state is not None and state.status == "frozen":
                send_failure_alert(
                    "rebalance skipped", f"Sleeve B frozen: {state.statusReason}"
                )
                return {"go": False, "reason": "sleeve frozen"}

            client = client_from_account(account)
            if not await asyncio.to_thread(client.is_market_open):
                send_failure_alert("rebalance skipped", "market closed (holiday?)")
                return {"go": False, "reason": "market closed"}

            return {
                "go": True,
                "outlook": {
                    "id": outlook_row.id,
                    "regime": outlook_row.regime,
                    "conviction": outlook_row.conviction,
                    "sectorRankings": outlook_row.sectorRankings,
                    "runDate": outlook_iso,
                },
                "has_state": state is not None,
                "sleeve_status": state.status if state else "active",
            }

        pre = await step.run("preflight", preflight)
        if not pre["go"]:
            return {"status": "skipped", "reason": pre["reason"]}

        # Step 2: bootstrap sleeve state on first ever run
        async def bootstrap() -> Dict[str, Any]:
            import asyncio  # noqa: PLC0415

            from api.lib.db import get_db  # noqa: PLC0415
            from execution.broker.alpaca_client import client_from_account  # noqa: PLC0415
            from execution.broker.credentials import get_active_alpaca_account  # noqa: PLC0415
            from execution.constants import BENCHMARK, SLEEVE_B, SLEEVE_B_FRACTION  # noqa: PLC0415
            from execution.sleeve_service import get_sleeve_state, init_sleeve_state  # noqa: PLC0415
            from research_swarm.data.market_data_client import MarketDataClient  # noqa: PLC0415

            db = await get_db()
            state = await get_sleeve_state(db, SLEEVE_B)
            if state is None:
                client = client_from_account(await get_active_alpaca_account(db))
                summary = await asyncio.to_thread(client.get_account_summary)

                def spy_close() -> float:
                    df = MarketDataClient().get_historical_data(BENCHMARK, period="5d")
                    return float(df["Close"].dropna().iloc[-1])

                spy = await asyncio.to_thread(spy_close)
                state = await init_sleeve_state(
                    db, SLEEVE_B,
                    cash=SLEEVE_B_FRACTION * summary["equity"],
                    spy_close=spy,
                    inception_date=datetime.fromisoformat(run_date_iso),
                )
                logger.info("Sleeve B bootstrapped: cash=%s", state.cashBalance)
            return {"cashBalance": state.cashBalance, "status": state.status}

        boot = await step.run("bootstrap-sleeve", bootstrap)

        # Step 3: broker book + reconcile
        async def load_book() -> Dict[str, Any]:
            import asyncio  # noqa: PLC0415

            from api.lib.db import get_db  # noqa: PLC0415
            from execution.alerts import send_failure_alert  # noqa: PLC0415
            from execution.broker.alpaca_client import client_from_account  # noqa: PLC0415
            from execution.broker.credentials import get_active_alpaca_account  # noqa: PLC0415
            from execution.constants import SLEEVE_B  # noqa: PLC0415
            from execution.engine.reconcile import find_mismatches  # noqa: PLC0415
            from execution.sleeve_service import (  # noqa: PLC0415
                get_engine_positions, set_sleeve_status,
            )

            db = await get_db()
            client = client_from_account(await get_active_alpaca_account(db))
            broker_positions = [
                p.to_dict() for p in await asyncio.to_thread(client.get_positions)
            ]
            summary = await asyncio.to_thread(client.get_account_summary)
            engine_rows = await get_engine_positions(db, SLEEVE_B)
            engine_qty = {p.symbol: p.qty for p in engine_rows}

            mismatches = find_mismatches(
                {p["symbol"]: p["qty"] for p in broker_positions}, engine_qty
            )
            if mismatches:
                await set_sleeve_status(db, SLEEVE_B, "frozen", "; ".join(mismatches))
                send_failure_alert(
                    "rebalance aborted — reconciliation mismatch, Sleeve B frozen",
                    "\n".join(mismatches),
                )
            return {
                "mismatches": mismatches,
                "broker_positions": broker_positions,
                "engine_positions": engine_qty,
                "account_equity": summary["equity"],
            }

        book = await step.run("load-book", load_book)
        if book["mismatches"]:
            return {"status": "frozen", "mismatches": book["mismatches"]}

        # Step 4: pure plan
        async def plan_step() -> Dict[str, Any]:
            return build_rebalance_plan(
                pre["outlook"],
                book["engine_positions"],
                book["broker_positions"],
                {
                    "cashBalance": boot["cashBalance"],
                    "status": boot["status"],
                    "accountEquity": book["account_equity"],
                },
            )

        plan = await step.run("build-plan", plan_step)
        if not plan["orders"]:
            return {"status": "no-op", "journal": plan["journal"]}

        # Step 5: one memoized step per order — a retry never re-submits
        fills: List[Dict[str, Any]] = []
        for i, order in enumerate(plan["orders"]):

            async def submit_order(order=order) -> Dict[str, Any]:
                import asyncio  # noqa: PLC0415

                from api.lib.db import get_db  # noqa: PLC0415
                from execution.broker.alpaca_client import client_from_account  # noqa: PLC0415
                from execution.broker.credentials import get_active_alpaca_account  # noqa: PLC0415

                db = await get_db()
                client = client_from_account(await get_active_alpaca_account(db))
                if order["side"] == "sell":
                    result = await asyncio.to_thread(
                        client.submit_market_sell_qty, order["symbol"], order["qty"]
                    )
                else:
                    result = await asyncio.to_thread(
                        client.submit_market_buy_notional, order["symbol"], order["notional"]
                    )
                return {**result.to_dict(), "requested_notional": order.get("notional")}

            fill = await step.run(
                f"order-{i}-{order['side']}-{order['symbol']}", submit_order
            )
            fills.append(fill)

        # Step 6: persist fills + cash ledger (separate from submission —
        # a retry here re-writes rows but never re-trades)
        async def persist() -> Dict[str, Any]:
            from api.lib.db import get_db  # noqa: PLC0415
            from execution.alerts import send_failure_alert  # noqa: PLC0415
            from execution.constants import SLEEVE_B  # noqa: PLC0415
            from execution.sleeve_service import apply_fill, update_sleeve_cash  # noqa: PLC0415

            db = await get_db()
            cash = boot["cashBalance"]
            unfilled = []
            for fill in fills:
                delta = await apply_fill(
                    db, SLEEVE_B, fill,
                    requested_notional=fill.get("requested_notional"),
                    journal=plan["journal"],
                )
                cash += delta
                if fill["status"] != "filled":
                    unfilled.append(f"{fill['side']} {fill['symbol']}: {fill['status']}")
            await update_sleeve_cash(db, SLEEVE_B, cash)
            if unfilled:
                send_failure_alert("rebalance had unfilled orders", "\n".join(unfilled))
            return {"cash_after": round(cash, 2), "unfilled": unfilled}

        persisted = await step.run("persist-fills", persist)

        summary = {
            "status": "rebalanced",
            "orders": len(plan["orders"]),
            "unfilled": persisted["unfilled"],
            "cash_after": persisted["cash_after"],
            "regime": pre["outlook"]["regime"],
        }
        logger.info("Sleeve B rebalance complete: %s", summary)
        return summary

    return execution_weekly


try:
    execution_weekly = _register_inngest_function()
except Exception:
    execution_weekly = None  # type: ignore[assignment]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_execution_weekly.py -v`
Expected: 4 passed

(Same `on_failure` caveat as Task 9 — if the SDK rejects the kwarg, drop it and alert inline.)

- [ ] **Step 5: Commit**

```bash
git add inngest_app/functions/execution_weekly.py tests/test_execution_weekly.py
git commit -m "feat(autopilot): weekly Sleeve B rebalance cron — per-order memoized steps"
```

---

### Task 11: API Endpoints (link, status, resume)

**Files:**
- Modify: `api/routes/autopilot.py` (append models + 3 endpoints)
- Test: `tests/test_autopilot_routes.py` (append test classes)

**Interfaces:**
- Produces: `POST /api/autopilot/broker/link` (body `{api_key, api_secret}` → validates against Alpaca, stores encrypted, returns `{status, account_equity}`), `GET /api/autopilot/broker/status` (→ `{linked, provider, mode, sleeves: [{sleeve, status, status_reason, cash_balance}], latest_snapshot}`), `POST /api/autopilot/sleeve/{sleeve}/resume` (→ `{sleeve, status}`). All admin-only via existing `require_admin`.
- Consumes: `upsert_alpaca_account`/`get_active_alpaca_account` (Task 2), `AlpacaPaperClient` (Task 3), `get_sleeve_state`/`set_sleeve_status` (Task 8), existing `get_db`, `require_admin`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_autopilot_routes.py` (it already stubs `prisma` and builds a minimal FastAPI app with `require_admin`/`get_db` overridden — follow its existing app-construction pattern; the `_app()`/client fixture at the top of the existing endpoint test class shows the exact override recipe):

```python
# ── Phase 2: broker link / status / resume ──────────────────────────────────

def _patch_db():
    """Patch autopilot's get_db to a MagicMock db (no real prisma)."""
    return patch("api.routes.autopilot.get_db", new=AsyncMock(return_value=MagicMock()))


class TestBrokerLink:
    def test_link_validates_and_stores_encrypted(self):
        app = _admin_app()
        fake_summary = {"equity": 100000.0, "cash": 100000.0}
        with _patch_db(), \
             patch("api.routes.autopilot._alpaca_client_factory") as factory, \
             patch("api.routes.autopilot.upsert_alpaca_account", new=AsyncMock()) as upsert:
            factory.return_value.get_account_summary.return_value = fake_summary
            client = TestClient(app)
            resp = client.post("/autopilot/broker/link",
                               json={"api_key": "PK123", "api_secret": "SEC456"})
        assert resp.status_code == 200
        assert resp.json() == {"status": "linked", "account_equity": 100000.0}
        upsert.assert_awaited_once()

    def test_link_rejects_bad_keys_without_storing(self):
        app = _admin_app()
        with _patch_db(), \
             patch("api.routes.autopilot._alpaca_client_factory") as factory, \
             patch("api.routes.autopilot.upsert_alpaca_account", new=AsyncMock()) as upsert:
            factory.return_value.get_account_summary.side_effect = RuntimeError("401")
            client = TestClient(app)
            resp = client.post("/autopilot/broker/link",
                               json={"api_key": "bad", "api_secret": "bad"})
        assert resp.status_code == 400
        upsert.assert_not_awaited()


class TestBrokerStatus:
    def test_status_unlinked(self):
        app = _admin_app()
        with _patch_db(), \
             patch("api.routes.autopilot.get_active_alpaca_account",
                   new=AsyncMock(return_value=None)):
            resp = TestClient(app).get("/autopilot/broker/status")
        assert resp.status_code == 200
        assert resp.json()["linked"] is False


class TestSleeveResume:
    def test_resume_reactivates_halted_sleeve(self):
        app = _admin_app()
        state = SimpleNamespace(sleeve="B", status="halted", statusReason="cb")
        with _patch_db(), \
             patch("api.routes.autopilot.get_sleeve_state",
                   new=AsyncMock(return_value=state)), \
             patch("api.routes.autopilot.set_sleeve_status", new=AsyncMock()) as setter:
            resp = TestClient(app).post("/autopilot/sleeve/B/resume")
        assert resp.status_code == 200
        assert resp.json() == {"sleeve": "B", "status": "active"}
        setter.assert_awaited_once()

    def test_resume_unknown_sleeve_404(self):
        app = _admin_app()
        resp = TestClient(app).post("/autopilot/sleeve/X/resume")
        assert resp.status_code == 404
```

Also add (near the existing app-builder in the file) an `_admin_app()` helper mirroring the existing endpoint-test app construction: a minimal `FastAPI()` including `router`, with `app.dependency_overrides[require_admin] = lambda: SimpleNamespace(id="admin1", is_admin=True)` and `get_db` patched to an `AsyncMock` returning a `MagicMock`.

```python
def _admin_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[require_admin] = lambda: SimpleNamespace(id="admin1", is_admin=True)
    return app
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_autopilot_routes.py -v`
Expected: new tests FAIL (404s / AttributeError — endpoints don't exist); existing tests still PASS.

- [ ] **Step 3: Implement — append to `api/routes/autopilot.py`**

```python
# ── Phase 2: broker linking + sleeve control ────────────────────────────────

import asyncio

from execution.broker.credentials import get_active_alpaca_account, upsert_alpaca_account
from execution.sleeve_service import get_sleeve_state, set_sleeve_status


def _alpaca_client_factory(api_key: str, api_secret: str):
    """Indirection so tests can patch client construction (alpaca-py is a
    runtime-only dep, not installed in the unit-test env)."""
    from execution.broker.alpaca_client import AlpacaPaperClient

    return AlpacaPaperClient(api_key, api_secret)


class BrokerLinkRequest(BaseModel):
    api_key: str
    api_secret: str


class BrokerLinkResponse(BaseModel):
    status: str
    account_equity: float


@router.post("/autopilot/broker/link", response_model=BrokerLinkResponse)
async def link_broker(body: BrokerLinkRequest, admin: User = Depends(require_admin)):
    """Validate Alpaca paper keys against the live API, then store them
    encrypted (Fernet). Bad keys are rejected before anything is stored."""
    try:
        client = _alpaca_client_factory(body.api_key, body.api_secret)
        summary = await asyncio.to_thread(client.get_account_summary)
    except Exception:
        raise HTTPException(status_code=400, detail="Alpaca rejected these keys")

    db = await get_db()
    await upsert_alpaca_account(db, admin.id, body.api_key, body.api_secret)
    return BrokerLinkResponse(status="linked", account_equity=summary["equity"])


@router.get("/autopilot/broker/status")
async def broker_status(admin: User = Depends(require_admin)):
    """Linked-account + sleeve health overview (admin dashboard / curl)."""
    db = await get_db()
    account = await get_active_alpaca_account(db)
    if account is None:
        return {"linked": False, "sleeves": [], "latest_snapshot": None}

    sleeves = []
    for sleeve in ("A", "B"):
        state = await get_sleeve_state(db, sleeve)
        if state is not None:
            sleeves.append({
                "sleeve": sleeve,
                "status": state.status,
                "status_reason": state.statusReason,
                "cash_balance": state.cashBalance,
            })
    latest = await db.sleevesnapshot.find_first(order={"snapshotDate": "desc"})
    snapshot = None
    if latest is not None:
        snapshot = {
            "date": latest.snapshotDate.isoformat(),
            "sleeve": latest.sleeve,
            "equity": latest.equity,
            "spy_close": latest.spyClose,
        }
    return {
        "linked": True,
        "provider": account.provider,
        "mode": account.mode,
        "sleeves": sleeves,
        "latest_snapshot": snapshot,
    }


@router.post("/autopilot/sleeve/{sleeve}/resume")
async def resume_sleeve(sleeve: str, admin: User = Depends(require_admin)):
    """Manual reset after a circuit-breaker halt or reconciliation freeze —
    the engine never un-halts itself (spec requirement)."""
    if sleeve not in ("A", "B"):
        raise HTTPException(status_code=404, detail="Unknown sleeve")
    db = await get_db()
    state = await get_sleeve_state(db, sleeve)
    if state is None:
        raise HTTPException(status_code=404, detail="Sleeve not initialized")
    await set_sleeve_status(db, sleeve, "active", reason=None)
    return {"sleeve": sleeve, "status": "active"}
```

Note: `execution.broker.credentials` and `execution.sleeve_service` are import-safe at module level (no prisma/alpaca imports at import time), so the top-of-file imports are fine under the test env's prisma stub.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_autopilot_routes.py -v`
Expected: all pass (existing + 5 new)

- [ ] **Step 5: Commit**

```bash
git add api/routes/autopilot.py tests/test_autopilot_routes.py
git commit -m "feat(autopilot): broker link/status endpoints + manual sleeve resume"
```

---

### Task 12: Registry, Mount Tests, Full Suite

**Files:**
- Modify: `inngest_app/index.py` (register the two new functions)
- Modify: `tests/test_inngest_mount.py` (roster + import-safety coverage)

**Interfaces:**
- Produces: `ACTIVE_FUNCTIONS == [weekly_market_outlook, weekly_batch, execution_daily, execution_weekly]` (Nones filtered).

- [ ] **Step 1: Update the mount test**

In `tests/test_inngest_mount.py`:

1. Add the two new modules to `test_all_function_modules_import_without_sdk`'s tuple:

```python
        "inngest_app.functions.execution_daily",
        "inngest_app.functions.execution_weekly",
```

2. In `test_active_functions_roster`, extend the expected roster:

```python
    daily_mod = importlib.import_module("inngest_app.functions.execution_daily")
    weekly_exec_mod = importlib.import_module("inngest_app.functions.execution_weekly")
    expected = [
        fn
        for fn in [
            outlook_mod.weekly_market_outlook,
            batch_mod.weekly_batch,
            daily_mod.execution_daily,
            weekly_exec_mod.execution_weekly,
        ]
        if fn is not None
    ]
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/test_inngest_mount.py -v`
Expected: `test_active_functions_roster` FAILS (roster mismatch)

- [ ] **Step 3: Register in `inngest_app/index.py`**

Add imports after the existing two:

```python
from inngest_app.functions.execution_daily import execution_daily
from inngest_app.functions.execution_weekly import execution_weekly
```

Update the roster:

```python
ACTIVE_FUNCTIONS = [
    fn
    for fn in [weekly_market_outlook, weekly_batch, execution_daily, execution_weekly]
    if fn is not None
]
```

Also update the module docstring's owner-decision paragraph to mention the two Phase 2 execution functions (registered 2026-07-09).

- [ ] **Step 4: Run the FULL suite**

Run: `python -m pytest tests/ -v`
Expected: all pass (existing 41+1 plus ~45 new), 0 failures. Fix anything that broke before committing.

- [ ] **Step 5: Commit**

```bash
git add inngest_app/index.py tests/test_inngest_mount.py
git commit -m "feat(autopilot): register execution_daily + execution_weekly crons"
```

---

### Task 13: Deploy + Go-Live Checklist (manual, prod)

**Files:** none (operational task)

**Interfaces:**
- Consumes: Railway CLI (`railway link --project shimmering-liberation --environment production --service web`), Neon `DATABASE_URL`, Inngest dashboard, Alpaca paper account keys (Tui generates at https://app.alpaca.markets → Paper account → API keys).

- [ ] **Step 1: Push and open PR**

```bash
git push -u origin autopilot-phase2
gh pr create --title "feat(autopilot): Phase 2 — broker link + Sleeve B rotation" \
  --body "Alpaca paper account linking (Fernet-encrypted keys), broker order layer, mechanical Sleeve B sector-ETF rotation on a Monday cron, daily snapshot/reconcile/circuit-breaker cron, failure alerts, admin link/status/resume endpoints. Per docs/superpowers/specs/2026-07-08-execution-layer-design.md Phase 2.

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
```

Wait for review/merge before the prod steps below.

- [ ] **Step 2: Set Railway env vars**

```bash
railway variables --service web --set "BROKER_KEY_ENCRYPTION_KEY=$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
```

(`OWNER_EMAIL`/`RESEND_API_KEY` stay unset — failure alerts log+skip by design until Resend is configured.)

- [ ] **Step 3: Apply the migration to Neon**

```bash
npx prisma migrate deploy --schema db/schema.prisma
```

Expected output ends with: `1 migration applied: 20260709000001_add_autopilot_execution` (NEVER `migrate dev` — shadow-DB baseline always fails on this project.)

- [ ] **Step 4: Verify deploy + Inngest sync**

After Railway redeploys from main: check `railway logs --service web` for a clean boot, then the Inngest dashboard (app `research-swarm`) shows 4 functions: weekly-market-outlook, the batch function, execution-daily, execution-weekly.

- [ ] **Step 5: Link the Alpaca paper account (real integration test of the broker layer)**

Tui creates paper API keys at Alpaca, then:

```bash
curl -X POST https://web-production-23a2f.up.railway.app/api/autopilot/broker/link \
  -H "Authorization: Bearer <admin JWT>" -H "Content-Type: application/json" \
  -d '{"api_key": "<PK...>", "api_secret": "<...>"}'
```

Expected: `{"status": "linked", "account_equity": <paper equity>}`. Then `GET /api/autopilot/broker/status` returns `linked: true` with no sleeves yet.

- [ ] **Step 6: Manually invoke execution-daily from the Inngest dashboard**

Expected: run returns `{"status": "skipped", "reason": "no linked account or sleeve not bootstrapped"}` — correct, Sleeve B bootstraps on the first weekly run.

- [ ] **Step 7: First live rebalance — manually invoke execution-weekly during market hours (Mon–Fri, after 15:00 UTC / before 20:00 UTC)**

Expected: run summary `{"status": "rebalanced", "orders": 3, ...}` (or `no-op`/`skipped` with a stated reason). Verify:
- Alpaca paper dashboard shows 3 ETF positions
- `SleeveState` row: sleeve B, active, cashBalance ≈ 30% equity minus invested
- `EngineTrade` rows carry a full decision journal (outlook id, regime, weights)
- `GET /api/autopilot/broker/status` shows the sleeve + snapshot after the next daily run

- [ ] **Step 8: Let the crons run one full week unattended**

Success criteria (from the spec): daily `SleeveSnapshot` rows appear each weekday; next Monday's rebalance runs on the fresh Sunday outlook with zero manual intervention.

---

## Out of Scope (explicitly deferred)

- Daily *indicator persistence*: the daily cron snapshots positions/equity/SPY only. Indicators are still computed on-the-fly from 1y price history by the Sunday outlook (its only consumer today); storing daily indicator rows waits until Phase 3's funnel actually reads them.
- Sleeve A funnel, candidate screening, engine-commissioned research → Phase 3 (needs its own plan; the replay/backtest harness lands there with it).
- `/autopilot` dashboard UI and weekly digest email → Phase 4 (in-app delivery preferred; Resend still unconfigured).
- Live (non-paper) trading, multi-user account linking → v2.
- Cost visibility for engine-commissioned research spend → Phase 3 ride-along (noted in memory).
