import sys
from research_swarm import __version__
from research_swarm.logger import logger
from research_swarm.config import settings
from research_swarm.data import cache, sec_client

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

    logger.success("\n✓ Phase 2 Complete! Ready for Phase 3.")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)
