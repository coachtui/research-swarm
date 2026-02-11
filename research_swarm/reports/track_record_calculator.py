"""
Track record calculator for comparing current analysis to previous reports.

Tracks performance, target achievement, and rating changes over time.
"""
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from research_swarm.logger import logger


class TrackRecordCalculator:
    """Calculates track record metrics comparing current vs previous analysis."""

    def calculate_track_record(
        self,
        ticker: str,
        current_price: float,
        current_analysis: Dict[str, Any],
        previous_report: Optional[Dict[str, Any]] = None,
        market_return: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Calculate track record comparing current to previous analysis.

        Args:
            ticker: Stock ticker
            current_price: Current stock price
            current_analysis: Current analysis data
            previous_report: Previous report data (if exists)
            market_return: S&P 500 return since last report (optional)

        Returns:
            Dict with track record metrics or None if no previous report
        """
        if not previous_report:
            logger.debug(f"No previous report found for {ticker}")
            return None

        try:
            # Extract previous report data
            prev_date = previous_report.get("analysis_date")
            prev_rating = previous_report.get("rating", "N/A")
            prev_price = previous_report.get("price_at_analysis", current_price)
            prev_target = previous_report.get("price_target", 0)

            if not prev_date or not prev_price:
                logger.warning(f"Incomplete previous report data for {ticker}")
                return None

            # Calculate stock performance
            stock_return = ((current_price - prev_price) / prev_price) * 100

            # Estimate S&P 500 return if not provided
            # Simple estimation: 10% annualized
            if market_return is None:
                try:
                    days_elapsed = (datetime.now() - datetime.fromisoformat(prev_date)).days
                    market_return = (10.0 / 365) * days_elapsed  # 10% annual
                except:
                    market_return = 5.0  # Default 5% if calculation fails

            # Calculate relative performance
            relative_performance = stock_return - market_return

            # Calculate target achievement
            if prev_target and prev_target > 0:
                target_achievement = (current_price / prev_target) * 100
            else:
                target_achievement = 100.0

            # Determine rating change
            current_rating = current_analysis.get("rating", "HOLD")

            if current_rating == prev_rating:
                rating_change = f"Maintained {current_rating}"
            else:
                rating_change = f"Changed from {prev_rating} to {current_rating}"

            # Generate rating change rationale
            rating_change_rationale = self._generate_rating_change_rationale(
                prev_rating=prev_rating,
                current_rating=current_rating,
                stock_return=stock_return,
                relative_performance=relative_performance,
                current_analysis=current_analysis
            )

            return {
                "previous_report_date": prev_date,
                "previous_rating": prev_rating,
                "previous_price": round(prev_price, 2),
                "previous_target": round(prev_target, 2) if prev_target else 0.0,
                "stock_performance_pct": round(stock_return, 1),
                "sp500_performance_pct": round(market_return, 1),
                "relative_performance_pct": round(relative_performance, 1),
                "target_achievement_pct": round(target_achievement, 1),
                "rating_change": rating_change,
                "rating_change_rationale": rating_change_rationale
            }

        except Exception as e:
            logger.error(f"Track record calculation failed for {ticker}: {e}")
            return None

    def _generate_rating_change_rationale(
        self,
        prev_rating: str,
        current_rating: str,
        stock_return: float,
        relative_performance: float,
        current_analysis: Dict[str, Any]
    ) -> str:
        """
        Generate rationale for rating change.

        Args:
            prev_rating: Previous rating
            current_rating: Current rating
            stock_return: Stock return percentage
            relative_performance: Return vs S&P 500
            current_analysis: Current analysis data

        Returns:
            Rationale string explaining rating change
        """
        rating_order = ["STRONG SELL", "SELL", "HOLD", "BUY", "STRONG BUY"]

        try:
            prev_idx = rating_order.index(prev_rating)
            curr_idx = rating_order.index(current_rating)
        except ValueError:
            # If rating not in standard list, just explain the change
            if prev_rating == current_rating:
                return "Rating maintained due to stable fundamentals"
            else:
                return f"Rating updated from {prev_rating} to {current_rating} based on updated analysis"

        # Rating improved (upgraded)
        if curr_idx > prev_idx:
            if stock_return > 20:
                return f"Upgraded to {current_rating} following strong {stock_return:+.1f}% performance and improved fundamentals"
            elif relative_performance > 10:
                return f"Upgraded to {current_rating} due to outperformance vs market (+{relative_performance:.1f}%) and strengthening moat"
            else:
                moat_score = current_analysis.get("moat_score", 0)
                return f"Upgraded to {current_rating} based on improved moat score ({moat_score:.1f}/10) and positive outlook"

        # Rating declined (downgraded)
        elif curr_idx < prev_idx:
            if stock_return < -20:
                return f"Downgraded to {current_rating} following {stock_return:+.1f}% decline and deteriorating fundamentals"
            elif relative_performance < -10:
                return f"Downgraded to {current_rating} due to significant underperformance vs market ({relative_performance:+.1f}%)"
            else:
                return f"Downgraded to {current_rating} based on increased risk factors and valuation concerns"

        # Rating maintained
        else:
            if abs(stock_return) < 5:
                return f"Rating maintained at {current_rating} - stock performance in line with expectations"
            elif relative_performance > 0:
                return f"Rating maintained at {current_rating} despite {stock_return:+.1f}% return, still see upside to targets"
            else:
                return f"Rating maintained at {current_rating} - fundamentals remain stable despite {stock_return:+.1f}% performance"


# Global calculator instance
track_record_calculator = TrackRecordCalculator()
