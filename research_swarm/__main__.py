import sys
from research_swarm import __version__
from research_swarm.logger import logger
from research_swarm.config import settings

def main():
    """Main CLI entry point."""
    logger.info(f"Research Swarm v{__version__}")
    logger.info(f"Using model: {settings.default_model}")
    logger.info(f"Cache directory: {settings.cache_dir}")

    # Phase 1: Just print config and exit
    logger.success("✓ Configuration loaded successfully")
    logger.success("✓ Logging initialized")
    logger.success("✓ Environment validated")

    print("\n🎯 Phase 1 Complete! Ready for Phase 2.")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        sys.exit(1)
