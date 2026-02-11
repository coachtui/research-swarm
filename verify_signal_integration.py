#!/usr/bin/env python3
"""
Verification script for Signal Breakdown Report Integration.

This script verifies that all components of the signal breakdown
integration are properly connected and functional.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from research_swarm.logger import logger


def verify_imports():
    """Verify all required imports are available."""
    logger.info("Step 1: Verifying imports...")

    try:
        from research_swarm.reports.data_extractor import extract_signal_breakdown
        logger.success("✓ extract_signal_breakdown function imported")
    except ImportError as e:
        logger.error(f"✗ Failed to import extract_signal_breakdown: {e}")
        return False

    try:
        from research_swarm.visualization.signal_comparison import (
            revision_direction_to_score,
            sentiment_to_score,
            create_signal_comparison_chart,
        )
        logger.success("✓ Visualization functions imported")
    except ImportError as e:
        logger.error(f"✗ Failed to import visualization functions: {e}")
        return False

    try:
        from research_swarm.reports.models import StockReportData
        logger.success("✓ StockReportData model imported")
    except ImportError as e:
        logger.error(f"✗ Failed to import models: {e}")
        return False

    return True


def verify_signal_extraction():
    """Verify signal extraction logic."""
    logger.info("\nStep 2: Verifying signal extraction logic...")

    from research_swarm.reports.data_extractor import extract_signal_breakdown
    from research_swarm.visualization.signal_comparison import (
        revision_direction_to_score,
        sentiment_to_score,
    )

    # Create mock news_hound_output
    mock_output = {
        "sentiment_score": 7.5,
        "confidence": 0.85,
        "earnings_estimates": {
            "net_revision_direction": "Positive",
            "upward_revisions": 5,
            "downward_revisions": 2,
        },
        "analyst_consensus": {
            "consensus_rating": "Buy",
            "strong_buy": 3,
            "buy": 5,
            "hold": 2,
            "sell": 0,
            "strong_sell": 0,
        },
        "institutional_activity": {
            "institutional_sentiment": "Bullish",
            "institutional_ownership_pct": 65.0,
        },
        "insider_activity": {
            "insider_sentiment": "Neutral",
            "confidence": "medium",
        },
    }

    try:
        result = extract_signal_breakdown(mock_output)

        if result is None:
            logger.error("✗ extract_signal_breakdown returned None (visualization module not available?)")
            return False

        # Verify required fields
        required_fields = [
            "overall_score", "news_score", "earnings_score", "analyst_score",
            "institutional_score", "insider_score", "alignment_status",
            "has_divergence", "direction_consensus"
        ]

        for field in required_fields:
            if field not in result:
                logger.error(f"✗ Missing required field: {field}")
                return False

        logger.success(f"✓ Signal extraction successful:")
        logger.info(f"  - Overall Score: {result['overall_score']}/10")
        logger.info(f"  - News: {result['news_score']}/10 ({result['news_interpretation']})")
        logger.info(f"  - Earnings: {result['earnings_score']}/10 ({result['earnings_interpretation']})")
        logger.info(f"  - Analyst: {result['analyst_score']}/10 ({result['analyst_interpretation']})")
        logger.info(f"  - Institutional: {result['institutional_score']}/10 ({result['institutional_interpretation']})")
        logger.info(f"  - Insider: {result['insider_score']}/10 ({result['insider_interpretation']})")
        logger.info(f"  - Alignment: {result['alignment_status']}")

        return True

    except Exception as e:
        logger.error(f"✗ Signal extraction failed: {e}")
        return False


def verify_template():
    """Verify template has signal breakdown section."""
    logger.info("\nStep 3: Verifying template integration...")

    template_path = Path("research_swarm/reports/templates/stock_analysis.md.j2")

    if not template_path.exists():
        logger.error(f"✗ Template not found: {template_path}")
        return False

    content = template_path.read_text()

    # Check for signal breakdown section
    if "Signal Breakdown" not in content:
        logger.error("✗ Template missing 'Signal Breakdown' section")
        return False

    if "signal_breakdown" not in content:
        logger.error("✗ Template missing signal_breakdown variable reference")
        return False

    if "signal_breakdown.overall_score" not in content:
        logger.error("✗ Template missing signal score references")
        return False

    if "has_divergence" not in content:
        logger.error("✗ Template missing divergence detection")
        return False

    logger.success("✓ Template contains all required signal breakdown sections")
    return True


def verify_generator_integration():
    """Verify generator includes signal chart generation."""
    logger.info("\nStep 4: Verifying generator integration...")

    generator_path = Path("research_swarm/reports/generator.py")

    if not generator_path.exists():
        logger.error(f"✗ Generator not found: {generator_path}")
        return False

    content = generator_path.read_text()

    # Check for signal comparison chart generation
    if "signal_comparison_chart" not in content:
        logger.error("✗ Generator missing signal comparison chart generation")
        return False

    if "signal_breakdown" not in content:
        logger.error("✗ Generator missing signal_breakdown check")
        return False

    logger.success("✓ Generator includes signal comparison chart generation")
    return True


def verify_data_flow():
    """Verify data flows from extractor to model."""
    logger.info("\nStep 5: Verifying data flow...")

    from research_swarm.reports.data_extractor import DataExtractor
    from research_swarm.reports.models import StockReportData

    # Check that StockReportData has signal_breakdown field
    if not hasattr(StockReportData, 'model_fields'):
        logger.error("✗ StockReportData is not a Pydantic model")
        return False

    if 'signal_breakdown' not in StockReportData.model_fields:
        logger.error("✗ StockReportData missing signal_breakdown field")
        return False

    logger.success("✓ StockReportData has signal_breakdown field")

    # Verify extractor calls extract_signal_breakdown
    extractor_path = Path("research_swarm/reports/data_extractor.py")
    content = extractor_path.read_text()

    if "extract_signal_breakdown" not in content:
        logger.error("✗ DataExtractor doesn't call extract_signal_breakdown")
        return False

    if 'signal_breakdown = extract_signal_breakdown' not in content:
        logger.error("✗ DataExtractor doesn't assign signal_breakdown result")
        return False

    logger.success("✓ DataExtractor calls extract_signal_breakdown and assigns result")
    return True


def main():
    """Run all verification tests."""
    logger.info("="*70)
    logger.info("SIGNAL BREAKDOWN REPORT INTEGRATION VERIFICATION")
    logger.info("="*70 + "\n")

    tests = [
        ("Import Verification", verify_imports),
        ("Signal Extraction Logic", verify_signal_extraction),
        ("Template Integration", verify_template),
        ("Generator Integration", verify_generator_integration),
        ("Data Flow", verify_data_flow),
    ]

    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success))
        except Exception as e:
            logger.error(f"✗ {name} crashed: {e}")
            results.append((name, False))

    # Summary
    logger.info("\n" + "="*70)
    logger.info("VERIFICATION SUMMARY")
    logger.info("="*70)

    passed = sum(1 for _, success in results if success)
    total = len(results)

    for name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        logger.info(f"{status:10s} - {name}")

    logger.info("="*70)
    logger.info(f"Results: {passed}/{total} tests passed")
    logger.info("="*70)

    if passed == total:
        logger.success("\n🎉 ALL VERIFICATION TESTS PASSED!")
        logger.success("Signal breakdown report integration is COMPLETE and FUNCTIONAL!")
        logger.info("\nNext steps:")
        logger.info("1. Run an analysis to generate data: python -m research_swarm analyze <ticker>")
        logger.info("2. Generate a report: python -m research_swarm report <run_id>")
        logger.info("3. Check the report for Signal Breakdown section and charts!")
        return 0
    else:
        logger.error("\n❌ SOME VERIFICATION TESTS FAILED")
        logger.error("Please review the errors above and fix any issues.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
