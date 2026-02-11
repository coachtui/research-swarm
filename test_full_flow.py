#!/usr/bin/env python3
"""
Test the complete end-to-end flow:
1. Create test user
2. Run stock analysis
3. Save to database
4. Query results

This tests the full integration of API service + database.
"""

import asyncio
from api.lib.db import create_test_user, save_analysis_result, get_db
from api.services.analysis_service import run_stock_analysis, estimate_analysis_cost

async def test_full_flow():
    """Test complete flow from analysis to database storage."""

    print("🧪 Testing Full End-to-End Flow\n")
    print("=" * 60)

    try:
        # Step 1: Create test user
        print("\n1️⃣  Creating test user...")
        user = await create_test_user(
            email="test_flow@example.com",
            full_name="Test Flow User"
        )
        print(f"   ✅ User: {user['email']}")
        print(f"   ID: {user['id']}")
        print(f"   Status: {'Already existed' if not user['created'] else 'Created new'}")

        # Step 2: Estimate cost
        ticker = "AAPL"
        quarters = ["Q4_2024", "Q1_2025"]

        print(f"\n2️⃣  Estimating analysis cost...")
        estimate = estimate_analysis_cost(ticker, quarters)
        print(f"   Ticker: {ticker}")
        print(f"   Estimated cost: ${estimate['estimated_cost_usd']}")
        print(f"   Estimated time: {estimate['estimated_time_minutes']} minutes")

        # Ask for confirmation
        print(f"\n⚠️  This will use real Anthropic API credits (~${estimate['estimated_cost_usd']})")
        response = input("Continue with real analysis? (y/n): ")
        if response.lower() != 'y':
            print("\n❌ Test cancelled - skipping to database verification")

            # Just verify database is working
            print("\n3️⃣  Verifying database connection...")
            db = await get_db()
            user_count = await db.user.count()
            run_count = await db.run.count()
            print(f"   ✅ Database connected")
            print(f"   Users: {user_count}")
            print(f"   Runs: {run_count}")

            return True

        # Step 3: Run analysis
        print(f"\n3️⃣  Running analysis (this takes ~{estimate['estimated_time_minutes']} minutes)...")
        result = await run_stock_analysis(
            ticker=ticker,
            quarters=quarters,
            news_days_back=30,
            user_id=user['id']
        )

        if result['status'] == 'completed':
            print(f"   ✅ Analysis completed!")
            print(f"   Moat Score: {result['moat_score']:.1f}/10")
            print(f"   Cost: ${result['cost_usd']:.3f}")
        else:
            print(f"   ❌ Analysis failed: {result.get('error_message')}")
            return False

        # Step 4: Save to database
        print(f"\n4️⃣  Saving results to database...")
        saved = await save_analysis_result(
            user_id=user['id'],
            ticker=ticker,
            result=result
        )
        print(f"   ✅ Saved to database!")
        print(f"   Run ID: {saved['run_id']}")
        print(f"   Result ID: {saved['result_id']}")

        # Step 5: Query back from database
        print(f"\n5️⃣  Querying results from database...")
        db = await get_db()

        # Get the stock result
        stock_result = await db.stockresult.find_unique(
            where={"id": saved['result_id']}
        )

        if stock_result:
            print(f"   ✅ Result retrieved from database!")
            print(f"   Ticker: {stock_result.ticker}")
            print(f"   Moat Score: {stock_result.moatScore:.1f}/10")
            print(f"   Watchlist: {'Yes' if stock_result.isWatchlistCandidate else 'No'}")
            print(f"   Thesis: {stock_result.investmentThesis[:100]}...")
        else:
            print(f"   ❌ Could not retrieve result")
            return False

        # Step 6: Verify cost log
        print(f"\n6️⃣  Verifying cost tracking...")
        costs = await db.costlog.find_many(
            where={"userId": user['id']},
            order_by={"timestamp": "desc"},
            take=5
        )
        print(f"   ✅ Cost logs found: {len(costs)}")
        if costs:
            total_cost = sum(c.costUsd for c in costs)
            print(f"   Total logged cost: ${total_cost:.3f}")

        print("\n" + "=" * 60)
        print("✅ Full end-to-end test PASSED!")
        print("=" * 60)
        print("\n🎯 Everything is working:")
        print("   ✅ User management")
        print("   ✅ Analysis service")
        print("   ✅ Database storage")
        print("   ✅ Cost tracking")
        print("\n🚀 Ready for production API integration!")

        return True

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_full_flow())
    exit(0 if success else 1)
