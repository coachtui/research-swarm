import sys
from research_swarm import __version__
from research_swarm.logger import logger
from research_swarm.config import settings
from research_swarm.data import cache, sec_client
from research_swarm.agents import analyze_company, analyze_company_news, analyze_swarm

def main():
    """Main CLI entry point."""
    logger.info(f"Research Swarm v{__version__}")
    logger.info(f"Using model: {settings.default_model}")

    # Phase 1: Configuration
    logger.success("✓ Configuration loaded")
    logger.success("✓ Logging initialized")

    # Phase 2: Data pipeline demo
    logger.info("\n--- Phase 2: Data Pipeline Demo ---")

    # Test cache
    stats = cache.stats()
    logger.info(f"Cache stats: {stats}")

    # Test SEC client
    logger.info("Testing SEC Edgar client...")
    cik = sec_client.get_company_cik("AAPL")
    if cik:
        logger.success(f"✓ CIK lookup works: AAPL -> {cik}")

    logger.success("✓ Phase 2 Complete!")

    # Phase 3: Fundamentalist Agent Demo
    logger.info("\n--- Phase 3: Fundamentalist Agent Demo ---")

    try:
        # Analyze AAPL fiscal year 2023
        logger.info("Analyzing AAPL fiscal year 2023...")
        result = analyze_company("AAPL", 2023)

        # Display results
        logger.info("\n=== Analysis Results ===")
        logger.info(f"Company: {result.ticker}")
        logger.info(f"Fiscal Year: {result.fiscal_year}")
        logger.info(f"Filing Date: {result.filing_date}")
        logger.info(f"\nFinancial Health Score: {result.financial_health_score:.2f}/10")
        logger.info(f"Confidence: {result.confidence:.2%}")

        logger.info("\nScore Breakdown:")
        logger.info(f"  Profitability: {result.score_breakdown.profitability:.1f}/10")
        logger.info(f"  Growth: {result.score_breakdown.growth:.1f}/10")
        logger.info(f"  Balance Sheet: {result.score_breakdown.balance_sheet:.1f}/10")
        logger.info(f"  Cash Flow: {result.score_breakdown.cash_flow:.1f}/10")
        logger.info(f"  Supply Chain: {result.score_breakdown.supply_chain:.1f}/10")

        logger.info(f"\nProcessing Time: {result.processing_time:.1f}s")
        logger.info(f"Tokens Used: {result.tokens_used:,}")

        logger.success("\n✓ Phase 3 Complete!")

    except Exception as e:
        logger.error(f"Phase 3 demo failed: {e}")
        logger.info("This is expected if you haven't completed Phase 3 implementation yet.")

    # Phase 4: News Hound Agent Demo
    logger.info("\n--- Phase 4: News Hound Agent Demo ---")

    try:
        # Analyze NVDA news (last 30 days)
        ticker = "NVDA"
        logger.info(f"Analyzing news for {ticker} (last 30 days)...")
        result = analyze_company_news(ticker, days_back=30)

        # Display results using the summary method
        logger.info("\n" + result.summary())

        # Display additional details
        logger.info("\n=== Sentiment Analysis ===")
        logger.info(result.sentiment_analysis[:500] + "..." if len(result.sentiment_analysis) > 500 else result.sentiment_analysis)

        logger.success("\n✓ Phase 4 Complete!")

    except Exception as e:
        logger.error(f"Phase 4 demo failed: {e}")
        logger.info("This is expected if you haven't completed Phase 4 implementation yet.")

    # Phase 6: Manager Agent (Swarm Analysis) Demo
    logger.info("\n--- Phase 6: Manager Agent Demo (Full Swarm Analysis) ---")

    try:
        # Run full swarm analysis on NVDA
        ticker = "NVDA"
        logger.info(f"Running full swarm analysis on {ticker}...")
        logger.info("This will orchestrate Fundamentalist, News Hound, and Quant agents...")

        result = analyze_swarm(ticker=ticker, fiscal_year=2024, news_days_back=30)

        # Display results
        logger.info("\n=== SWARM ANALYSIS RESULTS ===")
        logger.info(f"Company: {result.ticker}")
        logger.info(f"Analysis Date: {result.analysis_date}")

        logger.info("\n--- Component Scores ---")
        logger.info(f"  Financial Health: {result.moat_breakdown.financial_health:.2f}/10 (30% weight)")
        logger.info(f"  Sentiment/Catalysts: {result.moat_breakdown.sentiment_catalysts:.2f}/10 (20% weight)")
        logger.info(f"  Technical Strength: {result.moat_breakdown.technical_strength:.2f}/10 (20% weight)")
        logger.info(f"  Supply Chain Position: {result.moat_breakdown.supply_chain_position:.2f}/10 (30% weight)")

        logger.info("\n--- MOAT SCORE ---")
        logger.info(f"  Final Score: {result.moat_score:.2f}/10")
        logger.info(f"  Confidence: {result.confidence:.0%}")
        logger.info(f"  Watchlist Candidate: {'YES ✓' if result.is_watchlist_candidate else 'NO'}")

        logger.info("\n--- Key Insights ---")
        for i, insight in enumerate(result.key_insights, 1):
            logger.info(f"  {i}. {insight}")

        logger.info("\n--- Risk Factors ---")
        for i, risk in enumerate(result.risk_factors, 1):
            logger.info(f"  {i}. {risk}")

        logger.info("\n--- Investment Thesis ---")
        logger.info(result.investment_thesis)

        logger.info("\n--- Performance Metrics ---")
        logger.info(f"  Total Processing Time: {result.processing_time:.1f}s")
        if result.agent_processing_times:
            logger.info("  Agent Breakdown:")
            for agent, time_taken in result.agent_processing_times.items():
                logger.info(f"    - {agent.capitalize()}: {time_taken:.1f}s")
        logger.info(f"  Total Tokens Used: {result.tokens_used:,}")
        logger.info(f"  Estimated Cost: ~${result.tokens_used * 0.003 / 1000:.3f}")

        logger.success("\n✓ Phase 6 Complete!")

    except Exception as e:
        logger.error(f"Phase 6 demo failed: {e}")
        logger.info("This is expected if you haven't completed Phase 6 implementation yet.")

    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)
