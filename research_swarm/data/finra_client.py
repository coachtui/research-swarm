"""
FINRA OTC Transparency Portal client for dark pool (ATS) activity data.

Fetches alternative trading systems (ATS) volume data to track institutional
positioning through dark pool activity.

Data Source: https://otctransparency.finra.org/otctransparency/AtsIssueData
"""
import math
import requests
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from research_swarm.logger import logger
from research_swarm.data.cache import cache
from research_swarm.data.rate_limiter import rate_limiter


class FINRAClient:
    """Client for fetching FINRA dark pool (ATS) activity data."""

    # FINRA API endpoint for OTC Transparency data
    # Reference: https://developer.finra.org/docs/api-explorer/query_api-equity-weekly_summary
    API_BASE_URL = "https://api.finra.org/data/group/otcMarket/name"
    WEEKLY_SUMMARY_ENDPOINT = f"{API_BASE_URL}/weeklySummary"

    def __init__(self):
        self.headers = {
            "User-Agent": "ResearchSwarm/0.1.0 (Educational/Research)",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        # Register FINRA rate limit (2 seconds between requests)
        if "finra" not in rate_limiter.limits:
            rate_limiter.limits["finra"] = {"calls": 1, "period": 2}  # 1 call per 2 seconds

    def get_dark_pool_activity(self, ticker: str, weeks_back: int = 13) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch dark pool activity for a ticker over the last N weeks.

        Args:
            ticker: Stock ticker symbol
            weeks_back: Number of weeks to look back (default: 4)

        Returns:
            List of weekly records with ATS volume data, or None if unavailable:
            [{
                "week_ending": "2026-02-14",
                "total_shares": 150000000,
                "ats_shares": 52500000,  # Off-exchange volume
                "ats_pct": 35.0,         # % traded off-exchange
                "venues": ["VIRTU", "CITADEL", "UBS"],
                "venue_concentration": 0.65  # Top 3 venues as % of total
            }]
        """
        cache_key = f"{ticker.upper()}_darkpool_{weeks_back}w"

        # Check cache first (7-day TTL for weekly data)
        cached = cache.get("finra_darkpool", cache_key)
        if cached:
            logger.debug(f"Cache hit for FINRA dark pool: {ticker}")
            return cached

        try:
            # Rate limit FINRA requests
            rate_limiter.wait_if_needed("finra")

            # Fetch dark pool data from FINRA API
            data = self._fetch_finra_data(ticker, weeks_back)

            if data:
                # Enrich with total market volume to calculate ATS %
                # This combines FINRA ATS data with yfinance total volume
                enriched_data = self._enrich_with_market_volume(data, ticker)

                # Cache for 7 days (weekly data updates)
                cache.set("finra_darkpool", cache_key, enriched_data, ttl_days=7)
                logger.success(f"✓ Fetched FINRA dark pool data for {ticker} ({len(enriched_data)} weeks)")
                return enriched_data
            else:
                logger.warning(f"No FINRA dark pool data available for {ticker}")
                return None

        except Exception as e:
            logger.warning(f"Failed to fetch FINRA dark pool data for {ticker}: {e}")
            return None

    def _fetch_finra_data(self, ticker: str, weeks_back: int) -> Optional[List[Dict[str, Any]]]:
        """
        Fetch raw FINRA ATS data from the official FINRA API.

        Uses FINRA's Query API to retrieve weekly OTC (ATS) transparency data.
        API Reference: https://developer.finra.org/docs/api-explorer/query_api-equity-weekly_summary

        Args:
            ticker: Stock ticker symbol
            weeks_back: Number of weeks to look back

        Returns:
            List of weekly ATS records, or None if unavailable
        """
        try:
            # Calculate date range (last N weeks + extra buffer for FINRA's 2-4 week delay)
            end_date = datetime.now() - timedelta(weeks=3)  # Account for FINRA delay
            start_date = end_date - timedelta(weeks=weeks_back)

            # Try multiple summaryTypeCodes - ATS data may be under different codes
            # ATS_W_SMBL_FIRM = Weekly ATS data by firm and symbol (most granular, includes venue names)
            # ATS_W_SMBL = Weekly ATS data aggregated by symbol (no firm breakdown, no venue info)
            # Prioritize FIRM first to get venue-level detail
            summary_type_codes = ["ATS_W_SMBL_FIRM", "ATS_W_SMBL"]

            for summary_type in summary_type_codes:
                payload = {
                    "compareFilters": [
                        {
                            "fieldName": "issueSymbolIdentifier",
                            "compareType": "equal",
                            "fieldValue": ticker.upper()
                        },
                        {
                            "fieldName": "weekStartDate",
                            "compareType": "greater",
                            "fieldValue": start_date.strftime("%Y-%m-%d")
                        },
                        {
                            "fieldName": "summaryTypeCode",
                            "compareType": "equal",
                            "fieldValue": summary_type
                        }
                    ],
                    "fields": [
                        "issueSymbolIdentifier",
                        "weekStartDate",
                        "totalWeeklyShareQuantity",
                        "totalWeeklyTradeCount",
                        "marketParticipantName",
                        "MPID",
                        "summaryTypeCode"
                    ],
                    "limit": 1000,
                    "offset": 0
                }

                logger.debug(f"Fetching FINRA ATS data for {ticker} (summary_type={summary_type})...")

                # Make POST request to FINRA API
                response = requests.post(
                    self.WEEKLY_SUMMARY_ENDPOINT,
                    json=payload,
                    headers=self.headers,
                    timeout=15
                )

                # Check for authentication errors
                if response.status_code == 401:
                    logger.warning(
                        f"FINRA API authentication required (HTTP 401). "
                        f"API key may be needed. Visit https://developer.finra.org for access. "
                        f"Gracefully degrading to 13F-only institutional score."
                    )
                    return None
                elif response.status_code == 403:
                    logger.warning(
                        f"FINRA API access forbidden (HTTP 403). "
                        f"Check API permissions or contact FINRA support. "
                        f"Gracefully degrading to 13F-only institutional score."
                    )
                    return None
                elif response.status_code == 204:
                    # No content - try next summary type
                    logger.debug(f"No data for {ticker} with summary_type={summary_type}, trying next...")
                    continue
                elif response.status_code != 200:
                    logger.warning(
                        f"FINRA API returned status {response.status_code}: {response.text[:200]}"
                    )
                    continue

                # Parse JSON response
                data = response.json()

                # Debug: Log first record to see available fields
                if isinstance(data, list) and len(data) > 0:
                    logger.debug(f"Sample FINRA record fields: {list(data[0].keys())}")
                elif isinstance(data, dict) and "data" in data and len(data["data"]) > 0:
                    logger.debug(f"Sample FINRA record fields: {list(data['data'][0].keys())}")

                # Parse and aggregate the response into weekly records
                parsed_data = self._parse_finra_response(data, weeks_back)
                if parsed_data:
                    logger.debug(f"Successfully fetched data with summary_type={summary_type}")
                    return parsed_data

            # If we get here, no data was found with any summary type
            logger.debug(f"No FINRA ATS data found for {ticker} with any summary type")
            return None

        except requests.exceptions.Timeout:
            logger.warning(f"FINRA API request timeout for {ticker}")
            return None
        except requests.exceptions.RequestException as e:
            logger.warning(f"FINRA API request failed for {ticker}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching FINRA data for {ticker}: {e}")
            return None

    def _parse_finra_response(self, api_response: Any, weeks_back: int) -> Optional[List[Dict[str, Any]]]:
        """
        Parse FINRA API response into weekly ATS records.

        The API returns granular records (one per ATS firm per week).
        This method aggregates them into weekly totals with venue details.

        Args:
            api_response: JSON response from FINRA API
            weeks_back: Number of weeks requested (for validation)

        Returns:
            List of weekly records with ATS metrics
        """
        try:
            # Handle both list and dict responses
            if isinstance(api_response, dict):
                records = api_response.get("data", [])
            elif isinstance(api_response, list):
                records = api_response
            else:
                logger.warning(f"Unexpected FINRA API response format: {type(api_response)}")
                return None

            if not records:
                logger.debug("No FINRA ATS records found in API response")
                return None

            # Group records by week (weekStartDate)
            from collections import defaultdict
            weekly_data = defaultdict(lambda: {
                "total_shares": 0,
                "ats_shares": 0,
                "venues": [],
                "venue_shares": defaultdict(int)
            })

            for record in records:
                week_start = record.get("weekStartDate", "")
                if not week_start:
                    continue

                # ATS shares (off-exchange volume)
                ats_shares = int(record.get("totalWeeklyShareQuantity", 0))

                # Venue name (market participant)
                venue_name = record.get("marketParticipantName", "") or record.get("MPID", "UNKNOWN")

                # Aggregate by week
                weekly_data[week_start]["ats_shares"] += ats_shares
                weekly_data[week_start]["venues"].append(venue_name)
                weekly_data[week_start]["venue_shares"][venue_name] += ats_shares

            # Convert to final format
            # Note: We only have ATS volume, not total market volume
            # ATS % can only be calculated if we have total volume from another source
            # For now, we'll track absolute ATS volume and venue concentration
            weekly_records = []
            for week_start, week_data in sorted(weekly_data.items()):
                # Calculate venue concentration (Herfindahl index)
                total_ats = week_data["ats_shares"]
                if total_ats > 0:
                    venue_shares = week_data["venue_shares"]
                    # Get top 3 venues by volume
                    top_venues = sorted(venue_shares.items(), key=lambda x: x[1], reverse=True)[:3]
                    major_venues = [v[0] for v in top_venues]
                    top3_total = sum(v[1] for v in top_venues)
                    venue_concentration = top3_total / total_ats if total_ats > 0 else 0
                else:
                    major_venues = []
                    venue_concentration = 0

                # Calculate week ending date (week starts on Monday, ends on Sunday)
                week_start_dt = datetime.strptime(week_start, "%Y-%m-%d")
                week_ending_dt = week_start_dt + timedelta(days=6)

                weekly_records.append({
                    "week_ending": week_ending_dt.strftime("%Y-%m-%d"),
                    "week_starting": week_start,
                    "total_shares": None,  # Not available from FINRA ATS data alone
                    "ats_shares": total_ats,
                    "ats_pct": None,  # Cannot calculate without total market volume
                    "venues": major_venues,
                    "venue_concentration": round(venue_concentration, 2)
                })

            if not weekly_records:
                logger.debug("No weekly records after parsing FINRA data")
                return None

            logger.debug(f"Parsed {len(weekly_records)} weeks of FINRA ATS data")
            return weekly_records

        except Exception as e:
            logger.error(f"Error parsing FINRA API response: {e}")
            return None

    def _enrich_with_market_volume(self, dark_pool_data: List[Dict[str, Any]], ticker: str) -> List[Dict[str, Any]]:
        """
        Enrich FINRA ATS data with total market volume from yfinance to calculate ATS %.

        Args:
            dark_pool_data: List of weekly ATS records from FINRA
            ticker: Stock ticker symbol

        Returns:
            Enriched data with total_shares and ats_pct calculated
        """
        try:
            import yfinance as yf
            import pandas as pd

            # Fetch historical volume data from yfinance
            stock = yf.Ticker(ticker)
            # Get data covering the date range of dark pool records
            if dark_pool_data:
                start_date = min(week["week_starting"] for week in dark_pool_data)
                end_date = max(week["week_ending"] for week in dark_pool_data)

                # Fetch daily volume data
                hist = stock.history(start=start_date, end=end_date, interval="1d")

                if hist.empty:
                    logger.warning(f"No market volume data from yfinance for {ticker}")
                    return dark_pool_data

                # Aggregate volume by week (Monday to Sunday)
                # Create week identifiers based on start date (Monday)
                hist_reset = hist.reset_index()
                hist_reset['Date'] = pd.to_datetime(hist_reset['Date'])
                hist_reset['WeekStart'] = hist_reset['Date'] - pd.to_timedelta(hist_reset['Date'].dt.dayofweek, unit='d')
                hist_reset['WeekStart'] = hist_reset['WeekStart'].dt.date
                weekly_volume = hist_reset.groupby('WeekStart')['Volume'].sum()

                # Match FINRA weeks with yfinance weeks and calculate ATS %
                for week_record in dark_pool_data:
                    week_starting = week_record.get("week_starting")
                    if not week_starting:
                        continue

                    # Parse week start date
                    week_start_dt = datetime.strptime(week_starting, "%Y-%m-%d").date()

                    # Find matching week in yfinance data
                    matching_volume = weekly_volume.get(week_start_dt)

                    if matching_volume and matching_volume > 0:
                        week_record["total_shares"] = int(matching_volume)
                        ats_shares = week_record.get("ats_shares", 0)
                        week_record["ats_pct"] = round((ats_shares / matching_volume) * 100, 2)
                        logger.debug(f"Matched week {week_starting}: {ats_shares:,} ATS / {int(matching_volume):,} total = {week_record['ats_pct']}%")
                    else:
                        # If no matching volume, use absolute ATS volume only
                        week_record["total_shares"] = None
                        week_record["ats_pct"] = None
                        logger.debug(f"No market volume found for week {week_starting}")

                logger.debug(f"Enriched FINRA data with yfinance volume for {ticker}")
                return dark_pool_data

        except Exception as e:
            logger.warning(f"Failed to enrich with market volume for {ticker}: {e}")
            # Return original data without enrichment
            return dark_pool_data

    def calculate_dark_pool_metrics(self, dark_pool_data: List[Dict[str, Any]], ticker: str) -> Dict[str, Any]:
        """
        Calculate aggregate metrics from raw dark pool data.

        Args:
            dark_pool_data: List of weekly dark pool records
            ticker: Stock ticker symbol

        Returns:
            Dict with calculated metrics (handles missing ats_pct gracefully)
        """
        if not dark_pool_data or len(dark_pool_data) < 2:
            logger.warning(f"Insufficient dark pool data for {ticker} - need at least 2 weeks")
            return {}

        try:
            # Calculate metrics based on available data
            # Prefer ATS % if available, otherwise use absolute ATS volume trends

            # Check if we have ATS percentages
            ats_pcts = [week["ats_pct"] for week in dark_pool_data if week.get("ats_pct") is not None]
            has_ats_pct = len(ats_pcts) > 0

            if has_ats_pct:
                # Use ATS % for calculations
                avg_ats_pct = sum(ats_pcts) / len(ats_pcts)

                # Calculate trend
                mid_point = len(ats_pcts) // 2
                recent_avg = sum(ats_pcts[mid_point:]) / len(ats_pcts[mid_point:]) if mid_point < len(ats_pcts) else 0
                prior_avg = sum(ats_pcts[:mid_point]) / len(ats_pcts[:mid_point]) if mid_point > 0 else 0

                if prior_avg > 0:
                    trend_pct_change = ((recent_avg - prior_avg) / prior_avg) * 100
                else:
                    trend_pct_change = 0.0

                # Find peak week
                peak_week_data = max(dark_pool_data, key=lambda x: x.get("ats_pct", 0) or 0)
                peak_ats_pct = peak_week_data.get("ats_pct", 0.0)
                peak_week = peak_week_data.get("week_ending", "")

                # --- Stock-specific baseline (requires >= 5 weeks) ---
                # Split: recent = last 4 weeks, baseline = everything older
                if len(ats_pcts) >= 5:
                    recent_window = ats_pcts[-4:]
                    baseline_window = ats_pcts[:-4]
                    recent_avg_pct = sum(recent_window) / len(recent_window)
                    b_avg = sum(baseline_window) / len(baseline_window)
                    variance = sum((x - b_avg) ** 2 for x in baseline_window) / len(baseline_window)
                    b_std = math.sqrt(variance) if variance > 0 else 1.0
                    baseline_avg_ats_pct = round(b_avg, 2)
                    baseline_std_ats_pct = round(b_std, 2)
                    z_score = round((recent_avg_pct - b_avg) / b_std, 2) if b_std > 0 else 0.0
                    if z_score > 1.0:
                        relative_level = "elevated"
                    elif z_score < -1.0:
                        relative_level = "depressed"
                    else:
                        relative_level = "normal"
                else:
                    baseline_avg_ats_pct = None
                    baseline_std_ats_pct = None
                    z_score = None
                    relative_level = "unknown"

            else:
                # Fallback: Use absolute ATS volume trends
                ats_volumes = [week["ats_shares"] for week in dark_pool_data if week.get("ats_shares", 0) > 0]

                if ats_volumes:
                    mid_point = len(ats_volumes) // 2
                    recent_avg_vol = sum(ats_volumes[mid_point:]) / len(ats_volumes[mid_point:]) if mid_point < len(ats_volumes) else 0
                    prior_avg_vol = sum(ats_volumes[:mid_point]) / len(ats_volumes[:mid_point]) if mid_point > 0 else 0

                    if prior_avg_vol > 0:
                        trend_pct_change = ((recent_avg_vol - prior_avg_vol) / prior_avg_vol) * 100
                    else:
                        trend_pct_change = 0.0

                    # Use volume-based metrics
                    avg_ats_pct = None  # Not available
                    peak_week_data = max(dark_pool_data, key=lambda x: x.get("ats_shares", 0))
                    peak_ats_pct = None
                    peak_week = peak_week_data.get("week_ending", "")
                else:
                    # No data available
                    avg_ats_pct = None
                    trend_pct_change = 0.0
                    peak_ats_pct = None
                    peak_week = ""

                # No ATS % → baseline stats unavailable
                baseline_avg_ats_pct = None
                baseline_std_ats_pct = None
                z_score = None
                relative_level = "unknown"

            # Determine trend direction
            if trend_pct_change > 5.0:
                trend = "increasing"
            elif trend_pct_change < -5.0:
                trend = "decreasing"
            else:
                trend = "stable"

            # Aggregate venues across all weeks
            all_venues = []
            for week in dark_pool_data:
                all_venues.extend(week.get("venues", []))

            # Get top 3 unique venues by frequency
            from collections import Counter
            venue_counts = Counter(all_venues)
            major_venues = [venue for venue, _ in venue_counts.most_common(3)]

            # Calculate venue concentration
            total_venues = len(set(all_venues))
            if total_venues > 0 and sum(venue_counts.values()) > 0:
                top3_pct = sum(count for _, count in venue_counts.most_common(3)) / sum(venue_counts.values())
                if top3_pct > 0.6:
                    venue_concentration = "high"
                elif top3_pct > 0.4:
                    venue_concentration = "medium"
                else:
                    venue_concentration = "low"
            else:
                venue_concentration = "medium"

            metrics = {
                "avg_ats_pct": round(avg_ats_pct, 2) if avg_ats_pct is not None else None,
                "trend": trend,
                "trend_pct_change": round(trend_pct_change, 2),
                "peak_week": peak_week,
                "peak_ats_pct": round(peak_ats_pct, 2) if peak_ats_pct is not None else None,
                "major_venues": major_venues,
                "venue_concentration": venue_concentration,
                # Stock-specific baseline (populated when >= 5 weeks of ATS % data available)
                "baseline_avg_ats_pct": baseline_avg_ats_pct,
                "baseline_std_ats_pct": baseline_std_ats_pct,
                "z_score": z_score,
                "relative_level": relative_level,
            }

            logger.debug(f"Calculated dark pool metrics for {ticker}: {metrics}")
            return metrics

        except Exception as e:
            logger.error(f"Error calculating dark pool metrics for {ticker}: {e}")
            return {}


# Global singleton instance
finra_client = FINRAClient()
