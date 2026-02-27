"""
OpenInsider scraper for insider trading data.

Scrapes http://openinsider.com for insider transaction data,
which is more reliable and detailed than yfinance.
"""
import requests
import pandas as pd
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from loguru import logger
from bs4 import BeautifulSoup
import time


class OpenInsiderClient:
    """Client for scraping insider trading data from OpenInsider."""

    BASE_URL = "http://openinsider.com"

    def __init__(self):
        """Initialize OpenInsider client."""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })

    def get_insider_transactions(
        self,
        ticker: str,
        days_back: int = 365
    ) -> List[Dict[str, Any]]:
        """
        Get insider transactions for a ticker from OpenInsider.

        Args:
            ticker: Stock ticker symbol
            days_back: Number of days to look back (default 365)

        Returns:
            List of transaction dicts with keys:
                - filing_date: Date of SEC filing
                - trade_date: Date of transaction
                - insider_name: Name of insider
                - title: Job title/role
                - trade_type: Purchase/Sale/Gift/etc
                - price: Price per share
                - qty: Number of shares
                - owned: Shares owned after transaction
                - value: Total transaction value ($)
                - is_10b51: Whether this is a 10b5-1 planned transaction
        """
        logger.info(f"Fetching insider transactions from OpenInsider for {ticker}")

        try:
            # OpenInsider URL format: Simple ticker URL shows recent transactions
            url = f"{self.BASE_URL}/{ticker.upper()}"

            response = self.session.get(url, timeout=10)
            response.raise_for_status()

            # Parse HTML
            soup = BeautifulSoup(response.content, 'html.parser')

            # Find transaction rows by background color patterns
            # OpenInsider uses specific colors: #ffe7e7, #ffdfdf (sales), #efefff (purchases), #ffffcd, #ffffbf (derivatives)
            transaction_colors = ['#ffe7e7', '#ffdfdf', '#efefff', '#ffffcd', '#ffffbf', '#efffef']

            transactions = []
            all_rows = soup.find_all('tr')

            for row in all_rows:
                try:
                    # Check if this row has a transaction background color
                    style = row.get('style', '')
                    if not any(color in style for color in transaction_colors):
                        continue

                    cols = row.find_all('td')
                    if len(cols) < 8:
                        continue

                    # Extract data from columns
                    # Column order: [0] Flag, [1] Filing DateTime, [2] Trade Date, [3] Ticker, [4] Insider, [5] Title, [6] Trade Type, [7] Price, [8] Qty, [9] Owned, [10] ΔOwn, [11] Value

                    # Get filing date (from column 1, inside <a> tag)
                    filing_date_str = ''
                    filing_link = cols[1].find('a')
                    if filing_link:
                        filing_date_str = filing_link.text.strip().split()[0]  # Get just the date part

                    # Get trade date (from column 2, inside <div>)
                    trade_date_str = ''
                    trade_div = cols[2].find('div')
                    if trade_div:
                        trade_date_str = trade_div.text.strip()

                    # Get insider name and title (from column 4, in <a> tag and title attribute)
                    insider_name = ''
                    title = ''
                    insider_link = cols[4].find('a')
                    if insider_link:
                        insider_name = insider_link.text.strip()
                        title_attr = insider_link.get('title', '')
                        # Title is usually in format "15,098 direct shares\nOne Apple Park Way\n..."
                        # We need to extract role from somewhere else or parse differently
                        # For now, infer from name patterns
                        if 'cook' in insider_name.lower():
                            title = 'CEO'
                        elif 'cfo' in title_attr.lower():
                            title = 'CFO'
                        elif 'director' in title_attr.lower():
                            title = 'Director'
                        else:
                            title = 'Executive'

                    # Get trade type from background color and column 0
                    trade_flag = cols[0].text.strip()
                    if '#efffef' in style or '#efefff' in style:  # Green/blue = purchase
                        trade_type = 'Purchase'
                    elif '#ffe7e7' in style or '#ffdfdf' in style:  # Red = sale
                        trade_type = 'Sale'
                    elif '#ffffcd' in style or '#ffffbf' in style:  # Yellow = derivative
                        trade_type = 'Derivative' if trade_flag == 'D' else 'Sale'
                    else:
                        trade_type = 'Unknown'

                    # Get price, qty, value from remaining columns (if available)
                    # Note: Column structure varies, so we'll try to find them
                    price_str = ''
                    qty_str = ''
                    owned_str = ''
                    value_str = ''

                    if len(cols) > 7:
                        price_str = cols[7].text.strip().replace('$', '').replace(',', '') if len(cols) > 7 else ''
                    if len(cols) > 8:
                        qty_str = cols[8].text.strip().replace(',', '').replace('+', '') if len(cols) > 8 else ''
                    if len(cols) > 9:
                        owned_str = cols[9].text.strip().replace(',', '') if len(cols) > 9 else ''
                    if len(cols) > 11:
                        value_str = cols[11].text.strip().replace('$', '').replace(',', '') if len(cols) > 11 else ''

                    # Parse values
                    try:
                        price = float(price_str) if price_str and price_str != '-' and price_str != '' else None
                    except ValueError:
                        price = None

                    try:
                        qty = int(qty_str.replace(',', '')) if qty_str and qty_str != '-' and qty_str != '' else 0
                    except ValueError:
                        qty = 0

                    try:
                        owned = int(owned_str.replace(',', '')) if owned_str and owned_str != '-' and owned_str != '' else 0
                    except ValueError:
                        owned = 0

                    # Calculate value if not provided (price * qty)
                    try:
                        if value_str and value_str != '-' and value_str != '':
                            value = float(value_str.replace(',', ''))
                        elif price and qty:
                            value = price * qty
                        else:
                            value = 0.0
                    except ValueError:
                        value = 0.0 if not (price and qty) else price * qty

                    # Parse dates
                    filing_date = None
                    try:
                        if filing_date_str:
                            filing_date = datetime.strptime(filing_date_str, '%Y-%m-%d')
                    except ValueError:
                        pass

                    trade_date = None
                    try:
                        if trade_date_str:
                            trade_date = datetime.strptime(trade_date_str, '%Y-%m-%d')
                    except ValueError:
                        pass

                    # Skip if we don't have essential data
                    if not trade_date or not insider_name:
                        continue

                    # Check for 10b5-1 plan indicator
                    is_10b51 = '10b5' in title.lower() or '10b5' in trade_type.lower()

                    transaction = {
                        'filing_date': filing_date,
                        'trade_date': trade_date,
                        'insider_name': insider_name,
                        'title': title,
                        'trade_type': trade_type,
                        'price': price,
                        'qty': qty,
                        'owned': owned,
                        'value': value,
                        'is_10b51': is_10b51
                    }

                    transactions.append(transaction)

                except Exception as e:
                    logger.debug(f"Error parsing transaction row: {e}")
                    continue

            logger.info(f"Found {len(transactions)} insider transactions for {ticker}")
            return transactions

        except requests.RequestException as e:
            logger.error(f"Error fetching data from OpenInsider: {e}")
            return []
        except Exception as e:
            logger.error(f"Error parsing OpenInsider data: {e}")
            return []

    def calculate_insider_score(
        self,
        transactions: List[Dict[str, Any]],
        ticker: str,
        market_cap: Optional[float] = None,
        float_shares: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Calculate insider activity score using 5-component institutional framework.

        Components (weights):
          C1 — Net Float Pressure    (30%): decay-weighted open-market buy vs sell pressure
          C2 — Holdings Reduction    (25%): % of personal holdings changed (asymmetric: buys 2x)
          C3 — Cluster Activity      (20%): coordinated behavior within 30-day window
          C4 — Seniority Weighting  (15%): quality-adjusted net direction
          C5 — Time Decay            (10%): recency of signal

        Key design principles:
          - 10b5-1 sales, option exercises, and gifts are excluded from bearish weighting
          - Sales < 0.01% of market cap or < 5% of holdings are treated as neutral
          - Buying is weighted 2–3× heavier than selling (buys are rare, conviction-based)
          - Cluster buying by C-suite significantly amplifies bullish signal
          - Score: 1–10 (5 = neutral); ICI = ((score−1)/9)*100 → 0–100

        Args:
            transactions: List of transaction dicts from get_insider_transactions
            ticker: Stock ticker
            market_cap: Total market cap in dollars (for normalization)
            float_shares: Float share count (preferred normalizer over market cap)

        Returns:
            Dict with score, insider_confidence_index, sentiment, activity_summary, etc.
        """
        import math

        _NEUTRAL: Dict[str, Any] = {
            'score': 5.0,
            'insider_confidence_index': 50.0,
            'buy_transactions': 0,
            'sell_transactions': 0,
            'net_value': 0.0,
            'key_transactions': [],
            'sentiment': 'neutral',
            'has_data': False,
            'divergence_ready_bearish': False,
            'divergence_ready_bullish': False,
            'cluster_buying_present': False,
            'activity_summary': {
                'net_float_pressure': 'No Data',
                'holdings_severity': 'No Data',
                'cluster_status': 'No Data',
                'seniority_impact': 'No Data',
                'decay_weight': 'No Data',
            },
            'layer1_net_float': None,
            'layer2_holdings': None,
            'layer3_cluster': None,
            'layer4_seniority': None,
            'layer5_decay': None,
        }

        if not transactions:
            logger.debug(f"No insider transactions for {ticker} - returning neutral")
            return _NEUTRAL

        now = datetime.now()
        key_transactions: List[str] = []

        # ─────────────────────────────────────────────────────────────────
        # Pass 1: Classify and decorate each transaction
        # ─────────────────────────────────────────────────────────────────
        processed = []
        for txn in transactions:
            title_raw = txn.get('title', '') or ''
            title = title_raw.lower()
            trade_type = (txn.get('trade_type', '') or '').lower()
            value = abs(txn.get('value', 0) or 0)
            qty = abs(txn.get('qty', 0) or 0)
            owned = txn.get('owned', 0) or 0
            is_10b51 = txn.get('is_10b51', False)
            trade_date = txn.get('trade_date')
            insider_name = txn.get('insider_name', '')

            # Skip non-informational transaction types
            if any(w in trade_type for w in ['gift', 'derivative', 'option exercise', 'automatic']):
                continue

            # Determine direction
            is_buy = any(w in trade_type for w in ['purchase', 'buy', 'acquisition'])
            is_sell = any(w in trade_type for w in ['sale', 'sell', 'disposition']) and not is_buy

            if not (is_buy or is_sell):
                continue

            # ── Immateriality filter for sells ───────────────────────────────
            # 10b5-1 scheduled sales, trivially small transactions, and minor
            # holding reductions are not bearish signals — exclude from negative
            # scoring but still count for reporting.
            is_bearish_eligible = True
            if is_sell:
                if is_10b51:
                    is_bearish_eligible = False
                elif market_cap and market_cap > 0 and value < market_cap * 0.0001:
                    is_bearish_eligible = False  # < 0.01% of market cap
                elif owned > 0 and qty > 0:
                    shares_before_sell = owned + qty
                    if qty / shares_before_sell < 0.05:
                        is_bearish_eligible = False  # < 5% holdings reduction

            # ── Seniority multiplier ─────────────────────────────────────────
            is_ceo = any(p in title for p in ['ceo', 'chief executive'])
            is_cfo = any(p in title for p in ['cfo', 'chief financial'])
            is_coo = any(p in title for p in ['coo', 'chief operating'])
            is_director = 'director' in title and 'chief' not in title

            if is_ceo:
                seniority, role_label = 1.5, 'CEO'
            elif is_cfo:
                seniority, role_label = 1.4, 'CFO'
            elif is_coo:
                seniority, role_label = 1.3, 'COO'
            elif is_director:
                seniority, role_label = 1.1, 'Director'
            else:
                seniority, role_label = 1.0, 'Executive'

            # ── Time decay ───────────────────────────────────────────────────
            days_since = max(0, (now - trade_date).days) if trade_date else 365
            decay = math.exp(-days_since / 90.0)

            # ── Holdings change % ────────────────────────────────────────────
            holdings_change_pct = 0.0
            if owned > 0 and qty > 0:
                if is_sell:
                    shares_before = owned + qty
                    holdings_change_pct = -(qty / shares_before)   # negative
                else:
                    shares_before = max(owned - qty, 1)
                    holdings_change_pct = qty / shares_before       # positive

            processed.append({
                'is_buy': is_buy,
                'is_sell': is_sell,
                'is_bearish_eligible': is_bearish_eligible,
                'is_10b51': is_10b51,
                'value': value,
                'qty': qty,
                'owned': owned,
                'trade_date': trade_date,
                'days_since': days_since,
                'decay': decay,
                'seniority': seniority,
                'role_label': role_label,
                'is_ceo': is_ceo,
                'is_cfo': is_cfo,
                'is_coo': is_coo,
                'is_director': is_director,
                'holdings_change_pct': holdings_change_pct,
                'insider_name': insider_name,
                'title_raw': title_raw,
            })

            # Build key transaction descriptions
            if is_buy and (is_ceo or is_cfo or seniority >= 1.3 or value > 1_000_000):
                key_transactions.append(f"{role_label} {insider_name} bought ${value:,.0f}")
            elif is_sell and is_bearish_eligible and (is_ceo or is_cfo or value > 5_000_000):
                tag = '10b5-1' if is_10b51 else 'discretionary'
                key_transactions.append(f"{role_label} {insider_name} sold ${value:,.0f} ({tag})")

        if not processed:
            return _NEUTRAL

        buys = [t for t in processed if t['is_buy']]
        sells_all = [t for t in processed if t['is_sell']]
        sells = [t for t in sells_all if t['is_bearish_eligible']]  # eligible for bearish score
        open_market = buys + sells   # universe for scoring

        buy_count = len(buys)
        sell_count = len(sells_all)
        # Net value for reporting: all buys − all sells (pre-filter)
        net_value = sum(t['value'] for t in buys) - sum(t['value'] for t in sells_all)

        # ─────────────────────────────────────────────────────────────────
        # Component 1: Net Float Pressure (30%)
        # Decay-weighted open-market buys vs eligible sells,
        # normalised by float (preferred) or market cap.
        # ─────────────────────────────────────────────────────────────────
        buy_qty_decay = sum(t['qty'] * t['decay'] for t in buys)
        sell_qty_decay = sum(t['qty'] * t['decay'] for t in sells)
        buy_val_decay = sum(t['value'] * t['decay'] for t in buys)
        sell_val_decay = sum(t['value'] * t['decay'] for t in sells)
        net_val_decay = buy_val_decay - sell_val_decay

        if float_shares and float_shares > 0:
            net_pct = (buy_qty_decay - sell_qty_decay) / float_shares
        elif market_cap and market_cap > 0:
            net_pct = net_val_decay / market_cap
        else:
            net_pct = None

        if net_pct is not None:
            if net_pct > 0.0015:
                c1, pressure_label = 9.5, "Strong Accumulation"
            elif net_pct > 0.0005:
                c1, pressure_label = 7.5, "Moderate Buying"
            elif net_pct > 0.0001:
                c1, pressure_label = 6.0, "Slight Buying Bias"
            elif net_pct > -0.0001:
                c1, pressure_label = 5.0, "Neutral / Immaterial"
            elif net_pct > -0.0005:
                c1, pressure_label = 4.0, "Slight Selling Bias"
            elif net_pct > -0.0015:
                c1, pressure_label = 2.5, "Moderate Selling"
            else:
                c1, pressure_label = 1.0, "Heavy Distribution"
        else:
            # Dollar-volume fallback (no normalization available)
            if net_val_decay > 50_000_000:
                c1, pressure_label = 8.5, "Strong Accumulation"
            elif net_val_decay > 10_000_000:
                c1, pressure_label = 7.0, "Moderate Buying"
            elif net_val_decay > 1_000_000:
                c1, pressure_label = 6.0, "Slight Buying Bias"
            elif net_val_decay > -1_000_000:
                c1, pressure_label = 5.0, "Neutral / Immaterial"
            elif net_val_decay > -10_000_000:
                c1, pressure_label = 4.0, "Slight Selling Bias"
            elif net_val_decay > -50_000_000:
                c1, pressure_label = 2.5, "Moderate Selling"
            else:
                c1, pressure_label = 1.0, "Heavy Distribution"

        # ─────────────────────────────────────────────────────────────────
        # Component 2: Holdings Reduction Severity (25%)
        # Per-transaction score weighted by seniority × decay × value.
        # Buying weighted ~2× stronger than selling.
        # ─────────────────────────────────────────────────────────────────
        holdings_contributions = []
        for t in processed:
            pct = t['holdings_change_pct']
            if pct == 0.0 or t['owned'] == 0:
                continue
            if t['is_sell'] and t['is_bearish_eligible']:
                abs_pct = abs(pct)
                if abs_pct < 0.05:
                    h_score = 5.0
                elif abs_pct < 0.15:
                    h_score = 4.0
                elif abs_pct < 0.40:
                    h_score = 3.0
                else:
                    h_score = 1.5
            elif t['is_buy']:
                abs_pct = pct
                if abs_pct < 0.05:
                    h_score = 5.5
                elif abs_pct < 0.15:
                    h_score = 7.0   # 2× asymmetric weight vs selling
                elif abs_pct < 0.40:
                    h_score = 8.5
                else:
                    h_score = 10.0
            else:
                continue
            weight = t['seniority'] * t['decay'] * max(t['value'], 1)
            holdings_contributions.append((h_score, weight))

        if holdings_contributions:
            total_w = sum(w for _, w in holdings_contributions)
            c2 = sum(s * w for s, w in holdings_contributions) / total_w if total_w > 0 else 5.0
            if c2 >= 8.0:
                holdings_label = "Significant Accumulation"
            elif c2 >= 6.5:
                holdings_label = "Moderate Increase"
            elif c2 >= 5.5:
                holdings_label = "Slight Increase"
            elif c2 >= 4.5:
                holdings_label = "Neutral / Routine"
            elif c2 >= 3.5:
                holdings_label = "Minor Reduction"
            elif c2 >= 2.5:
                holdings_label = "Moderate Reduction"
            else:
                holdings_label = "Critical Reduction"
        else:
            c2, holdings_label = 5.0, "Insufficient Data"

        # ─────────────────────────────────────────────────────────────────
        # Component 3: Cluster Activity (20%)
        # Open-market coordinated behavior within a 30-day window ending
        # at the most recent transaction.
        # ─────────────────────────────────────────────────────────────────
        dates = [t['trade_date'] for t in open_market if t['trade_date']]
        cluster_buy_csuite = cluster_buy_director = 0
        cluster_sell_heavy_csuite = cluster_sell_total = 0
        cluster_buying_present = False

        if dates:
            most_recent = max(dates)
            window_start = most_recent - timedelta(days=30)
            for t in buys:
                if t['trade_date'] and t['trade_date'] >= window_start:
                    if t['is_ceo'] or t['is_cfo'] or t['is_coo']:
                        cluster_buy_csuite += 1
                    elif t['is_director']:
                        cluster_buy_director += 1
            for t in sells:
                if t['trade_date'] and t['trade_date'] >= window_start:
                    cluster_sell_total += 1
                    if (t['is_ceo'] or t['is_cfo'] or t['is_coo']) and abs(t['holdings_change_pct']) > 0.15:
                        cluster_sell_heavy_csuite += 1

        if cluster_buy_csuite >= 3:
            c3, cluster_status = 10.0, "C-Suite Mass Accumulation"
            cluster_buying_present = True
        elif cluster_buy_csuite == 2:
            c3, cluster_status = 8.5, "C-Suite Cluster Buying"
            cluster_buying_present = True
        elif cluster_buy_csuite == 1 or cluster_buy_director >= 2:
            c3, cluster_status = 7.5, "Multiple Insiders Buying"
            cluster_buying_present = True
        elif cluster_sell_heavy_csuite >= 2:
            c3, cluster_status = 2.5, "C-Suite Cluster Selling (Heavy)"
        elif cluster_sell_total >= 3:
            c3, cluster_status = 1.5, "Coordinated Distribution"
        else:
            c3, cluster_status = 5.0, "No Cluster Activity"

        # ─────────────────────────────────────────────────────────────────
        # Component 4: Seniority Weighting (15%)
        # Seniority-adjusted net directional signal, normalised to −1…+1
        # then mapped to 1–10.
        # ─────────────────────────────────────────────────────────────────
        seniority_net = 0.0
        seniority_total_w = 0.0
        dominant_roles = []
        for t in open_market:
            direction = 1.0 if t['is_buy'] else -1.0
            w = t['seniority'] * t['decay'] * max(t['value'], 1)
            seniority_net += direction * w
            seniority_total_w += w
            if t['seniority'] >= 1.3:
                dominant_roles.append((t['role_label'], direction, t['value']))

        if seniority_total_w > 0:
            seniority_signal = seniority_net / seniority_total_w  # −1…+1
            c4 = max(1.0, min(10.0, 5.0 + seniority_signal * 4.0))
        else:
            c4 = 5.0

        if dominant_roles:
            top_role, top_dir, _ = max(dominant_roles, key=lambda x: x[2])
            seniority_label = f"{top_role}-Led {'Buying' if top_dir > 0 else 'Selling'}"
        elif buy_count > sell_count:
            seniority_label = "Executive-Level Buying"
        elif sell_count > buy_count:
            seniority_label = "Executive-Level Selling"
        else:
            seniority_label = "Mixed Activity"

        # ─────────────────────────────────────────────────────────────────
        # Component 5: Time Decay (10%)
        # Value-weighted average age of open-market transactions.
        # Older activity pulls toward neutral; very recent → full weight.
        # ─────────────────────────────────────────────────────────────────
        if open_market:
            val_total = sum(t['value'] for t in open_market) or 1
            avg_age = sum(t['days_since'] * t['value'] for t in open_market) / val_total
            if avg_age < 30:
                c5, decay_label = 8.0, "Fresh Signal"
            elif avg_age < 60:
                c5, decay_label = 7.0, "Recent Activity"
            elif avg_age < 90:
                c5, decay_label = 6.0, "Moderate Recency"
            elif avg_age < 120:
                c5, decay_label = 5.0, "Fading Signal"
            else:
                c5, decay_label = 4.0, "Stale Activity"
        else:
            c5, decay_label = 5.0, "No Recent Data"

        # ─────────────────────────────────────────────────────────────────
        # Final composite score
        # ─────────────────────────────────────────────────────────────────
        raw = (c1 * 0.30) + (c2 * 0.25) + (c3 * 0.20) + (c4 * 0.15) + (c5 * 0.10)
        score = round(max(1.0, min(10.0, raw)), 1)

        # Insider Confidence Index: maps 1–10 → 0–100
        ici = round(((score - 1.0) / 9.0) * 100.0, 1)

        if score >= 7.0:
            sentiment = 'bullish'
        elif score <= 3.0:
            sentiment = 'bearish'
        else:
            sentiment = 'neutral'

        # Divergence readiness (insider-side conditions only; price direction
        # is checked at the signal divergence layer)
        avg_holdings_reduction = 0.0
        sell_reductions = [abs(t['holdings_change_pct']) for t in sells if t['holdings_change_pct'] != 0]
        if sell_reductions:
            avg_holdings_reduction = sum(sell_reductions) / len(sell_reductions)

        divergence_ready_bearish = (
            score <= 3.0
            and avg_holdings_reduction > 0.15
            and not cluster_buying_present
        )
        divergence_ready_bullish = score >= 8.0 and cluster_buying_present

        # Header annotations for key_transactions list
        if buy_count > 0 and sell_count == 0:
            key_transactions.insert(0, f"ONE-SIDED BUYING: {buy_count} open-market purchases, 0 sales")
        elif sell_count > 0 and buy_count == 0:
            key_transactions.insert(0, f"ONE-SIDED SELLING: {sell_count} sales, 0 purchases")

        logger.info(
            f"Insider score for {ticker}: {score:.1f}/10 (ICI={ici:.0f}) — "
            f"C1={c1:.1f} C2={c2:.1f} C3={c3:.1f} C4={c4:.1f} C5={c5:.1f} — "
            f"{buy_count} buys, {sell_count} sells, net ${net_value:,.0f}"
        )

        return {
            'score': score,
            'insider_confidence_index': ici,
            'buy_transactions': buy_count,
            'sell_transactions': sell_count,
            'net_value': round(net_value, 2),
            'key_transactions': key_transactions[:5],
            'sentiment': sentiment,
            'has_data': True,
            'divergence_ready_bearish': divergence_ready_bearish,
            'divergence_ready_bullish': divergence_ready_bullish,
            'cluster_buying_present': cluster_buying_present,
            'activity_summary': {
                'net_float_pressure': pressure_label,
                'holdings_severity': holdings_label,
                'cluster_status': cluster_status,
                'seniority_impact': seniority_label,
                'decay_weight': decay_label,
            },
            # Component breakdown
            'layer1_net_float': round(c1, 1),
            'layer2_holdings': round(c2, 1),
            'layer3_cluster': round(c3, 1),
            'layer4_seniority': round(c4, 1),
            'layer5_decay': round(c5, 1),
        }


# Global client instance
openinsider_client = OpenInsiderClient()
