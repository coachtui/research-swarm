#!/usr/bin/env python3
"""Check what's currently in the database."""

import asyncio
from api.lib.db import get_db

async def check_results():
    db = await get_db()

    # Check counts
    users = await db.user.count()
    print(f'👥 Users in database: {users}')

    runs = await db.run.count()
    print(f'🏃 Runs in database: {runs}')

    results = await db.stockresult.count()
    print(f'📊 Stock results: {results}')

    costs = await db.costlog.count()
    print(f'💰 Cost logs: {costs}')

    # Show latest results if any
    if results > 0:
        latest = await db.stockresult.find_first(
            order_by={'createdAt': 'desc'}
        )
        print(f'\n📈 Latest Analysis:')
        print(f'   Ticker: {latest.ticker}')
        print(f'   Status: {latest.status}')
        if latest.moatScore:
            print(f'   Moat Score: {latest.moatScore:.1f}/10')
            print(f'   Watchlist: {"Yes" if latest.isWatchlistCandidate else "No"}')
            print(f'   Cost: ${latest.costUsd:.3f}')
            print(f'   Processing time: {latest.processingTimeSeconds:.1f}s')
        if latest.errorMessage:
            print(f'   ❌ Error: {latest.errorMessage}')

    # Show all users
    if users > 0:
        print('\n👥 Users:')
        all_users = await db.user.find_many()
        for user in all_users:
            print(f'   - {user.email} ({user.tier})')

    await db.disconnect()

asyncio.run(check_results())
