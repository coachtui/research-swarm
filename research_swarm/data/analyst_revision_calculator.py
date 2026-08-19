"""
Calculate analyst estimate revisions from upgrades/downgrades data.
"""
import pandas as pd
from typing import Dict, Any, Tuple
from loguru import logger


def calculate_revision_metrics(upgrades_downgrades: pd.DataFrame) -> Dict[str, Any]:
    """
    Calculate revision metrics from analyst upgrades/downgrades data.

    Args:
        upgrades_downgrades: DataFrame from yfinance with columns:
            - GradeDate: Date of the action
            - Firm: Analyst firm name
            - ToGrade: New rating
            - FromGrade: Previous rating (if available)
            - Action: upgrade, downgrade, init, maintain, reiterate
            - PriceTarget: New price target
            - PriorPriceTarget: Previous price target

    Returns:
        Dict with:
            - upward_revisions: Count of upgrades
            - downward_revisions: Count of downgrades
            - new_coverage: Count of coverage initiations
            - net_revision_direction: "Positive", "Negative", or "Neutral"
            - price_target_changes: Count of price target increases
            - avg_price_target_change_pct: Average % change in price targets
            - momentum: "Accelerating", "Stable", or "Decelerating"
    """
    if upgrades_downgrades is None or upgrades_downgrades.empty:
        return {
            "upward_revisions": 0,
            "downward_revisions": 0,
            "new_coverage": 0,
            "net_revision_direction": "Neutral",
            "price_target_increases": 0,
            "price_target_decreases": 0,
            "avg_price_target_change_pct": 0.0,
            "momentum": "Stable"
        }

    df = upgrades_downgrades.copy()

    # Ensure GradeDate is datetime
    if 'GradeDate' in df.columns:
        df['GradeDate'] = pd.to_datetime(df['GradeDate'])
        df = df.sort_values('GradeDate', ascending=False)

    # Count upgrades, downgrades, and new coverage initiations
    upward_revisions = 0
    downward_revisions = 0
    new_coverage = 0

    if 'Action' in df.columns:
        action_lower = df['Action'].str.lower()
        upward_revisions = action_lower.str.contains('up', na=False).sum()
        downward_revisions = action_lower.str.contains('down', na=False).sum()
        new_coverage = action_lower.str.contains('init', na=False).sum()

    # Analyze price target changes
    price_target_increases = 0
    price_target_decreases = 0
    price_target_changes = []

    # Check for both possible column name formats
    new_target_col = 'currentPriceTarget' if 'currentPriceTarget' in df.columns else 'PriceTarget'
    old_target_col = 'priorPriceTarget' if 'priorPriceTarget' in df.columns else 'PriorPriceTarget'

    if new_target_col in df.columns and old_target_col in df.columns:
        for _, row in df.iterrows():
            try:
                new_target = float(row[new_target_col]) if pd.notna(row[new_target_col]) else None
                old_target = float(row[old_target_col]) if pd.notna(row[old_target_col]) else None

                if new_target and old_target and old_target > 0:
                    change_pct = ((new_target - old_target) / old_target) * 100
                    price_target_changes.append(change_pct)

                    if change_pct > 0.5:  # More than 0.5% increase
                        price_target_increases += 1
                    elif change_pct < -0.5:  # More than 0.5% decrease
                        price_target_decreases += 1
            except (ValueError, TypeError):
                continue

    avg_price_target_change_pct = sum(price_target_changes) / len(price_target_changes) if price_target_changes else 0.0

    # Determine net direction
    net_score = upward_revisions - downward_revisions + price_target_increases - price_target_decreases

    if net_score >= 3:
        net_direction = "Strongly Positive"
    elif net_score >= 1:
        net_direction = "Positive"
    elif net_score <= -3:
        net_direction = "Strongly Negative"
    elif net_score <= -1:
        net_direction = "Negative"
    else:
        net_direction = "Neutral"

    # Determine momentum (recent trend)
    momentum = "Stable"
    if len(df) >= 5:
        # Split into recent half and older half
        midpoint = len(df) // 2
        recent_df = df.iloc[:midpoint]
        older_df = df.iloc[midpoint:]

        recent_upgrades = recent_df['Action'].str.lower().str.contains('up', na=False).sum() if 'Action' in recent_df.columns else 0
        recent_downgrades = recent_df['Action'].str.lower().str.contains('down', na=False).sum() if 'Action' in recent_df.columns else 0
        older_upgrades = older_df['Action'].str.lower().str.contains('up', na=False).sum() if 'Action' in older_df.columns else 0
        older_downgrades = older_df['Action'].str.lower().str.contains('down', na=False).sum() if 'Action' in older_df.columns else 0

        recent_net = recent_upgrades - recent_downgrades
        older_net = older_upgrades - older_downgrades

        if recent_net > older_net + 1:
            momentum = "Accelerating"
        elif recent_net < older_net - 1:
            momentum = "Decelerating"

    logger.info(f"Revision metrics: {upward_revisions} up, {downward_revisions} down, direction={net_direction}, momentum={momentum}")

    return {
        "upward_revisions": int(upward_revisions),
        "downward_revisions": int(downward_revisions),
        "new_coverage": int(new_coverage),
        "net_revision_direction": net_direction,
        "price_target_increases": int(price_target_increases),
        "price_target_decreases": int(price_target_decreases),
        "avg_price_target_change_pct": round(avg_price_target_change_pct, 2),
        "momentum": momentum
    }
