"""
Database client and helper functions.

This module provides the Prisma database client and utility functions
for interacting with the Neon Postgres database.
"""

from prisma import Prisma
from typing import Optional
from contextlib import asynccontextmanager
import json
import logging

logger = logging.getLogger(__name__)

# Global Prisma client instance
_db_client: Optional[Prisma] = None

async def get_db() -> Prisma:
    """
    Get or create the database client with automatic reconnection.

    This is the dependency injection function for FastAPI routes.
    Usage:
        db: Prisma = Depends(get_db)
    """
    global _db_client

    if _db_client is None:
        # Create Prisma client with extended timeouts (60s connect, 120s query)
        _db_client = Prisma(
            http={'timeout': 120.0}  # 120 second timeout for long queries
        )
        await _db_client.connect()
    else:
        # Check if connection is still alive
        try:
            if not _db_client.is_connected():
                await _db_client.disconnect()
                await _db_client.connect()
        except Exception:
            # Connection is stale, recreate client
            try:
                await _db_client.disconnect()
            except:
                pass
            _db_client = Prisma(
                http={'timeout': 120.0}
            )
            await _db_client.connect()

    return _db_client

@asynccontextmanager
async def db_session():
    """
    Context manager for database sessions.

    Usage:
        async with db_session() as db:
            user = await db.user.find_unique(where={"id": user_id})
    """
    db = await get_db()
    try:
        yield db
    finally:
        # Connection is kept alive (connection pooling)
        pass

async def close_db():
    """
    Close the database connection.
    Call this on application shutdown.
    """
    global _db_client

    if _db_client is not None:
        await _db_client.disconnect()
        _db_client = None

# Helper functions for common operations

async def create_test_user(email: str = "test@example.com", full_name: str = "Test User") -> dict:
    """
    Create a test user in the database.
    Useful for development and testing.
    """
    db = await get_db()

    # Check if user already exists
    existing = await db.user.find_unique(where={"email": email})
    if existing:
        return {
            "id": existing.id,
            "email": existing.email,
            "full_name": existing.fullName,
            "tier": existing.tier,
            "created": False
        }

    # Create new user
    user = await db.user.create(
        data={
            "clerkId": f"test_{email.split('@')[0]}",
            "email": email,
            "fullName": full_name,
            "tier": "starter",
            "monthlyBudgetUsd": 200.0,
            "isActive": True
        }
    )

    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.fullName,
        "tier": user.tier,
        "created": True
    }

async def create_pending_run(user_id: str, ticker: str, news_days_back: int = 30) -> str:
    """
    Create a Run record with status 'running' and return its ID immediately.
    Used by the background task pattern so the API can return a run_id before
    the analysis completes.
    """
    db = await get_db()
    run = await db.run.create(
        data={
            "userId": user_id,
            "tickers": [ticker],
            "status": "running",
            "totalStocks": 1,
            "completedCount": 0,
            "failedCount": 0,
            "progressPercent": 0.0,
            "newsDaysBack": news_days_back,
            "quarters": [],
        }
    )
    return run.id


async def update_run_failed(run_id: str, error_message: str) -> None:
    """Mark a Run as failed with an error message."""
    from datetime import datetime
    global _db_client
    # Force fresh connection — this is called after a long analysis
    if _db_client:
        try:
            await _db_client.disconnect()
        except Exception:
            pass
    _db_client = None
    db = await get_db()
    await db.run.update(
        where={"id": run_id},
        data={
            "status": "failed",
            "completedAt": datetime.utcnow(),
            "progressPercent": 100.0,
            "failedCount": 1,
        }
    )
    # Create a minimal failed StockResult so the results page can show the error
    run = await db.run.find_unique(where={"id": run_id})
    ticker = run.tickers[0] if run and run.tickers else "UNKNOWN"
    await db.stockresult.create(
        data={
            "runId": run_id,
            "ticker": ticker,
            "status": "failed",
            "errorMessage": error_message,
        }
    )


async def save_analysis_result(
    user_id: str,
    ticker: str,
    result: dict,
    run_id: Optional[str] = None
) -> dict:
    """
    Save stock analysis result to database.

    Args:
        user_id: User ID who requested the analysis
        ticker: Stock ticker symbol
        result: Analysis result from analysis_service
        run_id: Optional run ID (creates new run if not provided)

    Returns:
        Dictionary with run_id and result_id
    """
    global _db_client

    # CRITICAL: Force fresh connection BEFORE saving
    # Stock analysis takes 4+ minutes, exceeding Prisma connection timeout
    print(f"⚠️  Forcing fresh database connection for {ticker}...")
    if _db_client:
        try:
            await _db_client.disconnect()
        except Exception as e:
            print(f"   (Disconnect error ignored: {e})")
    _db_client = None

    # Get brand new connection
    db = await get_db()
    print(f"✅ Fresh database connection established")

    # Retry logic for connection timeouts
    max_retries = 2
    for attempt in range(max_retries):
        try:
            # Use the fresh connection we created above
            if attempt > 0:
                print(f"⚠️  Retry {attempt}/{max_retries}: Re-attempting save...")
                # Connection is already fresh, just retry the operation

            # Create or update run
            final_status = "completed" if result['status'] == 'completed' else "failed"
            if run_id is None:
                run = await db.run.create(
                    data={
                        "userId": user_id,
                        "tickers": [ticker],
                        "status": final_status,
                        "totalStocks": 1,
                        "completedCount": 1 if result['status'] == 'completed' else 0,
                        "failedCount": 0 if result['status'] == 'completed' else 1,
                        "progressPercent": 100.0,
                        "totalCostUsd": result.get('cost_usd', 0.0),
                        "quarters": [],
                        "newsDaysBack": 30
                    }
                )
                run_id = run.id
            else:
                # Update the pre-existing "running" run to completed/failed
                from datetime import datetime
                await db.run.update(
                    where={"id": run_id},
                    data={
                        "status": final_status,
                        "completedAt": datetime.utcnow(),
                        "progressPercent": 100.0,
                        "completedCount": 1 if result['status'] == 'completed' else 0,
                        "failedCount": 0 if result['status'] == 'completed' else 1,
                        "totalCostUsd": result.get('cost_usd', 0.0),
                    }
                )

            # --- Longitudinal Delta Tracking ---
            # Query for the most recent prior completed analysis by this user for the same ticker.
            # Compute delta metrics and inject into full_output before saving.
            if user_id and result.get('status') == 'completed':
                try:
                    prior_results = await db.stockresult.find_many(
                        where={
                            "ticker": ticker,
                            "userId": user_id,
                            "status": "completed",
                        },
                        order={"createdAt": "desc"},
                        take=1,
                    )
                    if prior_results:
                        prior = prior_results[0]
                        prior_fo_raw = prior.fullOutput
                        if prior_fo_raw:
                            prior_fo = prior_fo_raw if isinstance(prior_fo_raw, dict) else json.loads(prior_fo_raw)

                            from datetime import datetime, timezone
                            prior_date = prior.createdAt
                            now = datetime.now(timezone.utc)
                            if prior_date.tzinfo is None:
                                prior_date = prior_date.replace(tzinfo=timezone.utc)
                            days_since = max(0, (now - prior_date).days)

                            # Extract comparable metrics
                            prior_di = prior_fo.get('decision_intelligence') or {}
                            cur_fo = result.get('full_output') or {}
                            cur_di = cur_fo.get('decision_intelligence') or {}

                            prior_rating = prior_di.get('rating', 'HOLD')
                            cur_rating = cur_di.get('rating', 'HOLD')
                            prior_price = prior_di.get('current_price') or 0.0
                            cur_price = cur_di.get('current_price') or 0.0

                            def _sm_score(fo: dict) -> Optional[float]:
                                sb = fo.get('signal_breakdown') or {}
                                inst = sb.get('institutional_score')
                                ins = sb.get('insider_score')
                                dp = sb.get('dark_pool_score')
                                if inst is not None and ins is not None and dp is not None:
                                    return round((inst + ins + dp) / 3, 1)
                                return None

                            prior_sm = _sm_score(prior_fo)
                            cur_sm = _sm_score(cur_fo)
                            prior_moat = prior_fo.get('moat_score') or prior.moatScore
                            cur_moat = result.get('moat_score')

                            rating_map = {
                                'STRONG BUY': 5, 'BUY': 4, 'HOLD': 3, 'SELL': 2, 'STRONG SELL': 1
                            }
                            prior_rv = rating_map.get(prior_rating, 3)
                            cur_rv = rating_map.get(cur_rating, 3)

                            if abs(cur_rv - prior_rv) >= 2:
                                thesis_direction = 'reversed'
                            elif cur_rv > prior_rv:
                                thesis_direction = 'strengthened'
                            elif cur_rv < prior_rv:
                                thesis_direction = 'weakened'
                            else:
                                thesis_direction = 'held'

                            price_change_pct = (
                                round((cur_price - prior_price) / prior_price * 100, 1)
                                if prior_price and prior_price > 0 else None
                            )

                            # ── Sensitivity Attribution (item 1: "What Changed?") ──
                            prior_sb = prior_fo.get('signal_breakdown') or {}
                            cur_sb = cur_fo.get('signal_breakdown') or {}

                            prior_overall_score = prior_sb.get('overall_score')
                            cur_overall_score = cur_sb.get('overall_score')
                            prior_signal_stability = prior_sb.get('signal_stability')
                            cur_signal_stability = cur_sb.get('signal_stability')
                            prior_signal_spread = prior_sb.get('signal_spread')
                            cur_signal_spread = cur_sb.get('signal_spread')
                            prior_vol_trend = (prior_sb.get('volatility_regime_dynamics') or {}).get('vol_trend')
                            cur_vol_trend = (cur_sb.get('volatility_regime_dynamics') or {}).get('vol_trend')
                            prior_ev_conf = (prior_sb.get('confidence_integrity') or {}).get('ev_confidence_level')
                            cur_ev_conf = (cur_sb.get('confidence_integrity') or {}).get('ev_confidence_level')

                            attribution = []
                            if prior_signal_stability is not None and cur_signal_stability is not None:
                                stab_delta = float(cur_signal_stability) - float(prior_signal_stability)
                                if abs(stab_delta) >= 0.5:
                                    direction = "improved" if stab_delta > 0 else "degraded"
                                    attribution.append(
                                        f"Signal stability {direction} "
                                        f"({prior_signal_stability:.1f} \u2192 {cur_signal_stability:.1f}/10)"
                                    )
                            if prior_signal_spread is not None and cur_signal_spread is not None:
                                spread_delta = float(cur_signal_spread) - float(prior_signal_spread)
                                if abs(spread_delta) >= 0.2:
                                    direction = "expanded" if spread_delta > 0 else "compressed"
                                    attribution.append(
                                        f"Signal spread {direction} "
                                        f"(\u03c3: {prior_signal_spread:.2f} \u2192 {cur_signal_spread:.2f})"
                                    )
                            if prior_overall_score is not None and cur_overall_score is not None:
                                score_delta = float(cur_overall_score) - float(prior_overall_score)
                                if abs(score_delta) >= 0.3:
                                    direction = "strengthened" if score_delta > 0 else "weakened"
                                    attribution.append(
                                        f"Divergence signal {direction} "
                                        f"({prior_overall_score:.1f} \u2192 {cur_overall_score:.1f}/10)"
                                    )
                            if prior_vol_trend and cur_vol_trend and prior_vol_trend != cur_vol_trend:
                                attribution.append(
                                    f"Volatility regime shifted: {prior_vol_trend} \u2192 {cur_vol_trend}"
                                )
                            if prior_ev_conf and cur_ev_conf and prior_ev_conf != cur_ev_conf:
                                attribution.append(
                                    f"Model confidence changed: {prior_ev_conf} \u2192 {cur_ev_conf}"
                                )
                            if prior_price and cur_price and prior_price > 0:
                                px_pct = (cur_price - prior_price) / prior_price * 100
                                if abs(px_pct) >= 3.0:
                                    attribution.append(
                                        f"Price movement ({px_pct:+.1f}%) may have shifted distance factors"
                                    )

                            # ── Probabilistic Module Drift (Sensitivity Attribution & Drift Diagnostics) ──
                            prior_stop_data = (prior_sb.get('stop_probability') or {})
                            cur_stop_data = (cur_sb.get('stop_probability') or {})
                            prior_ev_stab = (prior_sb.get('ev_stability') or {})
                            cur_ev_stab = (cur_sb.get('ev_stability') or {})
                            prior_conf_int = (prior_sb.get('confidence_integrity') or {})
                            cur_conf_int = (cur_sb.get('confidence_integrity') or {})
                            prior_noise = (prior_sb.get('noise_filter') or {})
                            cur_noise = (cur_sb.get('noise_filter') or {})
                            prior_scenario_wd = (prior_sb.get('scenario_weight_diagnostics') or {})
                            cur_scenario_wd = (cur_sb.get('scenario_weight_diagnostics') or {})

                            prior_stop_pct = prior_stop_data.get('effective_stop_probability_pct')
                            cur_stop_pct = cur_stop_data.get('effective_stop_probability_pct')
                            prior_instability = prior_ev_stab.get('instability_score')
                            cur_instability = cur_ev_stab.get('instability_score')
                            prior_conf_pct = prior_conf_int.get('effective_confidence_pct')
                            cur_conf_pct = cur_conf_int.get('effective_confidence_pct')
                            prior_noise_score = prior_noise.get('noise_score')
                            cur_noise_score = cur_noise.get('noise_score')
                            prior_stab_class = prior_ev_stab.get('stability_class')
                            cur_stab_class = cur_ev_stab.get('stability_class')

                            # Scenario weights (bear/base/bull effective probabilities)
                            prior_scenario_weights = None
                            cur_scenario_weights = None
                            if prior_scenario_wd:
                                prior_scenario_weights = {
                                    'bear': prior_scenario_wd.get('effective_bear_prob', 0.25),
                                    'base': prior_scenario_wd.get('effective_base_prob', 0.50),
                                    'bull': prior_scenario_wd.get('effective_bull_prob', 0.25),
                                }
                            if cur_scenario_wd:
                                cur_scenario_weights = {
                                    'bear': cur_scenario_wd.get('effective_bear_prob', 0.25),
                                    'base': cur_scenario_wd.get('effective_base_prob', 0.50),
                                    'bull': cur_scenario_wd.get('effective_bull_prob', 0.25),
                                }

                            # Model drift level — composite severity score
                            drift_score = 0
                            if prior_stop_pct is not None and cur_stop_pct is not None:
                                sd = abs(float(cur_stop_pct) - float(prior_stop_pct))
                                drift_score += 3 if sd >= 15 else 2 if sd >= 8 else 1 if sd >= 3 else 0
                            if prior_instability is not None and cur_instability is not None:
                                id_ = abs(float(cur_instability) - float(prior_instability))
                                drift_score += 2 if id_ >= 3 else 1 if id_ >= 1.5 else 0
                            if prior_conf_pct is not None and cur_conf_pct is not None:
                                cd = abs(float(cur_conf_pct) - float(prior_conf_pct))
                                drift_score += 2 if cd >= 20 else 1 if cd >= 10 else 0
                            if prior_stab_class and cur_stab_class and prior_stab_class != cur_stab_class:
                                drift_score += 2
                            model_drift_level = (
                                'Significant' if drift_score >= 5 else
                                'Moderate' if drift_score >= 3 else
                                'Modest' if drift_score >= 1 else
                                'Stable'
                            )

                            # Scenario rotation label from current rotation index
                            scenario_rotation_label = None
                            if cur_scenario_wd:
                                rot_idx = cur_scenario_wd.get('scenario_rotation_index', 0)
                                scenario_rotation_label = (
                                    'SIGNIFICANT' if rot_idx >= 15 else
                                    'MODERATE' if rot_idx >= 5 else
                                    'STABLE'
                                )

                            # EV change attribution — component-level drivers
                            ev_attribution = []
                            if prior_stop_pct is not None and cur_stop_pct is not None:
                                sd = float(cur_stop_pct) - float(prior_stop_pct)
                                if abs(sd) >= 3:
                                    ev_attribution.append({
                                        'driver': 'Stop Probability Drift',
                                        'delta': round(sd, 1),
                                        'direction': 'bearish' if sd > 0 else 'bullish',
                                    })
                            if prior_vol_trend and cur_vol_trend and prior_vol_trend != cur_vol_trend:
                                ev_attribution.append({
                                    'driver': 'Volatility Regime Shift',
                                    'delta': None,
                                    'direction': 'bearish' if cur_vol_trend == 'expanding' else 'bullish',
                                })
                            if prior_signal_spread is not None and cur_signal_spread is not None:
                                sp_d = float(cur_signal_spread) - float(prior_signal_spread)
                                if abs(sp_d) >= 0.3:
                                    ev_attribution.append({
                                        'driver': 'ConflictFactor Adjustment',
                                        'delta': round(sp_d, 2),
                                        'direction': 'bearish' if sp_d > 0 else 'bullish',
                                    })
                            if prior_price and cur_price and prior_price > 0:
                                px = (cur_price - prior_price) / prior_price * 100
                                if abs(px) >= 3:
                                    ev_attribution.append({
                                        'driver': 'Price Movement Impact',
                                        'delta': round(px, 1),
                                        'direction': 'neutral',
                                    })
                            if prior_conf_pct is not None and cur_conf_pct is not None:
                                cp_d = float(cur_conf_pct) - float(prior_conf_pct)
                                if abs(cp_d) >= 8:
                                    ev_attribution.append({
                                        'driver': 'Probability Reweighting',
                                        'delta': round(cp_d, 1),
                                        'direction': 'bearish' if cp_d < 0 else 'bullish',
                                    })
                            if prior_signal_stability is not None and cur_signal_stability is not None:
                                ss_d = float(cur_signal_stability) - float(prior_signal_stability)
                                if abs(ss_d) >= 0.8:
                                    ev_attribution.append({
                                        'driver': 'DistanceFactor Decay' if ss_d < 0 else 'Signal Stability Improvement',
                                        'delta': round(ss_d, 1),
                                        'direction': 'bearish' if ss_d < 0 else 'bullish',
                                    })

                            # Stop probability drift decomposition (per-component deltas)
                            stop_prob_drift_decomposition = None
                            if prior_stop_data and cur_stop_data:
                                stop_prob_drift_decomposition = {
                                    'base_delta': round(
                                        float(cur_stop_data.get('base_stop_risk_pct', 25)) -
                                        float(prior_stop_data.get('base_stop_risk_pct', 25)), 1),
                                    'volatility_pressure_delta': round(
                                        float(cur_stop_data.get('volatility_pressure_pct', 0)) -
                                        float(prior_stop_data.get('volatility_pressure_pct', 0)), 1),
                                    'trend_modifier_delta': round(
                                        float(cur_stop_data.get('trend_modifier_pct', 0)) -
                                        float(prior_stop_data.get('trend_modifier_pct', 0)), 1),
                                    'support_modifier_delta': round(
                                        float(cur_stop_data.get('support_modifier_pct', 0)) -
                                        float(prior_stop_data.get('support_modifier_pct', 0)), 1),
                                    'prior_stop_label': prior_stop_data.get('stop_probability_label'),
                                    'current_stop_label': cur_stop_data.get('stop_probability_label'),
                                }

                            delta = {
                                'prior_run_id': str(prior.runId),
                                'prior_analysis_date': prior.createdAt.isoformat(),
                                'prior_recommendation': prior_rating,
                                'current_recommendation': cur_rating,
                                'prior_price': prior_price if prior_price else None,
                                'current_price': cur_price if cur_price else None,
                                'price_change_pct': price_change_pct,
                                'prior_smart_money_score': prior_sm,
                                'current_smart_money_score': cur_sm,
                                'prior_moat_score': float(prior_moat) if prior_moat is not None else None,
                                'current_moat_score': float(cur_moat) if cur_moat is not None else None,
                                'thesis_direction': thesis_direction,
                                'days_since_last': days_since,
                                # Sensitivity attribution
                                'prior_overall_score': float(prior_overall_score) if prior_overall_score is not None else None,
                                'current_overall_score': float(cur_overall_score) if cur_overall_score is not None else None,
                                'prior_signal_stability': float(prior_signal_stability) if prior_signal_stability is not None else None,
                                'current_signal_stability': float(cur_signal_stability) if cur_signal_stability is not None else None,
                                'prior_signal_spread': float(prior_signal_spread) if prior_signal_spread is not None else None,
                                'current_signal_spread': float(cur_signal_spread) if cur_signal_spread is not None else None,
                                'prior_vol_trend': prior_vol_trend,
                                'current_vol_trend': cur_vol_trend,
                                'sensitivity_attribution': attribution,
                                # Probabilistic module drift fields
                                'prior_stop_probability_pct': float(prior_stop_pct) if prior_stop_pct is not None else None,
                                'current_stop_probability_pct': float(cur_stop_pct) if cur_stop_pct is not None else None,
                                'prior_confidence_pct': float(prior_conf_pct) if prior_conf_pct is not None else None,
                                'current_confidence_pct': float(cur_conf_pct) if cur_conf_pct is not None else None,
                                'prior_stability_score': float(prior_instability) if prior_instability is not None else None,
                                'current_stability_score': float(cur_instability) if cur_instability is not None else None,
                                'prior_noise_score': float(prior_noise_score) if prior_noise_score is not None else None,
                                'current_noise_score': float(cur_noise_score) if cur_noise_score is not None else None,
                                'prior_stability_class': prior_stab_class,
                                'current_stability_class': cur_stab_class,
                                'prior_scenario_weights': prior_scenario_weights,
                                'current_scenario_weights': cur_scenario_weights,
                                'model_drift_level': model_drift_level,
                                'scenario_rotation_label': scenario_rotation_label,
                                'ev_attribution': ev_attribution if ev_attribution else None,
                                'stop_prob_drift_decomposition': stop_prob_drift_decomposition,
                            }

                            # Inject delta into full_output dict
                            if isinstance(result.get('full_output'), dict):
                                result['full_output']['previous_analysis_delta'] = delta
                            logger.info(f"Delta computed for {ticker}: {thesis_direction} over {days_since} days")

                except Exception as delta_err:
                    logger.warning(f"Delta computation failed (non-critical) for {ticker}: {delta_err}")

            # Create stock result (excluding supply chain per user request)
            # Serialize full_output to JSON if it exists
            full_output = result.get('full_output')
            if full_output and isinstance(full_output, dict):
                full_output = json.dumps(full_output)

            # Serialize investment_thesis if it's a Pydantic model
            investment_thesis = result.get('investment_thesis')
            if investment_thesis is not None:
                # Check if it's a Pydantic model (has model_dump method)
                if hasattr(investment_thesis, 'model_dump'):
                    investment_thesis = json.dumps(investment_thesis.model_dump())
                elif isinstance(investment_thesis, dict):
                    investment_thesis = json.dumps(investment_thesis)
                # If it's already a string, leave it as is

            stock_result = await db.stockresult.create(
                data={
                    "runId": run_id,
                    "ticker": ticker,
                    "status": result['status'],
                    "moatScore": result.get('moat_score'),
                    "financialHealthScore": result.get('financial_health_score'),
                    "businessModelMoatScore": result.get('business_model_moat_score'),
                    "sentimentScore": result.get('sentiment_score'),
                    "technicalScore": result.get('technical_score'),
                    # supplyChainScore excluded - not used
                    "isWatchlistCandidate": result.get('watchlist_candidate', False),
                    "investmentThesis": investment_thesis,
                    "fullOutput": full_output,
                    "tokensUsed": result.get('tokens_used', 0),
                    "costUsd": result.get('cost_usd', 0.0),
                    "processingTimeSeconds": result.get('processing_time_seconds'),
                    "errorMessage": result.get('error_message')
                }
            )

            # Log costs
            if result.get('cost_usd', 0) > 0:
                await db.costlog.create(
                    data={
                        "userId": user_id,
                        "runId": run_id,
                        "ticker": ticker,
                        "agent": "manager",  # Full analysis uses manager
                        "tokensTotal": result.get('tokens_used', 0),
                        "costUsd": result.get('cost_usd', 0.0)
                    }
                )

            print(f"✅ Successfully saved analysis for {ticker} to database")
            return {
                "run_id": run_id,
                "result_id": stock_result.id,
                "ticker": ticker,
                "status": result['status']
            }

        except Exception as e:
            error_msg = str(e)
            # Check if it's a connection error
            if "connection" in error_msg.lower() or "closed" in error_msg.lower():
                if attempt < max_retries - 1:
                    print(f"❌ Database connection error (attempt {attempt + 1}/{max_retries}): {e}")
                    continue
                else:
                    print(f"❌ Failed after {max_retries} attempts: {e}")
                    raise
            else:
                # Not a connection error, raise immediately
                raise

async def get_user_monthly_cost(user_id: str) -> float:
    """
    Get user's total spending for the current month.
    """
    from datetime import datetime

    # Force reconnect to handle long-running timeouts
    global _db_client
    try:
        db = await get_db()

        # Ensure connection is active
        if not db.is_connected():
            print("⚠️  Database connection closed, reconnecting...")
            await db.disconnect()
            await db.connect()
    except Exception as conn_error:
        print(f"⚠️  Connection error: {conn_error}, creating fresh connection...")
        _db_client = None
        db = await get_db()

    # Get start of current month
    now = datetime.utcnow()
    month_start = datetime(now.year, now.month, 1)

    # Get all cost logs for this month
    costs = await db.costlog.find_many(
        where={
            "userId": user_id,
            "timestamp": {"gte": month_start}
        }
    )

    # Sum the costs
    total = sum(cost.costUsd for cost in costs) if costs else 0.0
    return total

async def get_or_create_cli_user() -> str:
    """
    Get or create the default CLI user for local analysis runs.

    This user is used when running analysis via the CLI instead of the API.
    All CLI-generated analyses are associated with this user so they appear
    in the frontend.

    Returns:
        str: The user ID of the CLI user
    """
    db = await get_db()

    # Ensure connection is active
    if not db.is_connected():
        await db.connect()

    CLI_USER_EMAIL = "cli@local.research-swarm"

    # Check if CLI user already exists
    user = await db.user.find_unique(where={"email": CLI_USER_EMAIL})

    if not user:
        # Create CLI user with enterprise tier (no budget limits)
        user = await db.user.create(
            data={
                "clerkId": "cli-local-user",
                "email": CLI_USER_EMAIL,
                "fullName": "CLI User",
                "tier": "enterprise",
                "monthlyBudgetUsd": 999999.0,
                "isActive": True
            }
        )

    return user.id
