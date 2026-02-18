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
        ticker: str
    ) -> Dict[str, Any]:
        """
        Calculate insider activity score using layered approach.

        Layer 1 (Primary): Dollar volume scoring - runs first regardless of titles
        Layer 2: Transaction pattern scoring - buy/sell ratio, clustering
        Layer 3 (Amplifier): Title-based scoring - CEO/CFO activity amplifies signal

        Args:
            transactions: List of transaction dicts from get_insider_transactions
            ticker: Stock ticker

        Returns:
            Dict with score (0-10), buy/sell counts, net_value, sentiment, key_transactions
        """
        if not transactions:
            logger.debug(f"No insider transactions for {ticker} - returning neutral")
            return {
                'score': 5.0,
                'buy_transactions': 0,
                'sell_transactions': 0,
                'net_value': 0.0,
                'key_transactions': [],
                'sentiment': 'neutral',
                'has_data': False
            }

        # Initialize counters
        buy_count = 0
        sell_count = 0
        net_value = 0.0
        net_value_weighted = 0.0  # Weighted for 10b5-1 plan sales
        key_transactions = []

        # Track by role (for amplification layer)
        ceo_buys = 0
        cfo_buys = 0
        ceo_sells = 0
        cfo_sells = 0
        owner_10pct_buys = 0
        owner_10pct_sells = 0

        # Track clustering (for pattern layer)
        sell_dates = []
        buy_dates = []

        # Process transactions
        for txn in transactions:
            title_raw = txn['title']
            title = title_raw.lower()
            trade_type = txn['trade_type'].lower()
            value = txn['value']
            is_10b51 = txn['is_10b51']
            trade_date = txn.get('trade_date')

            # IGNORE certain transaction types (option exercises, gifts, etc.)
            if any(word in trade_type for word in ['option exercise', 'gift', 'automatic']):
                continue

            # Enhanced title detection
            is_ceo = any(pattern in title for pattern in ['ceo', 'chief executive officer', 'chief executive'])
            is_cfo = any(pattern in title for pattern in ['cfo', 'chief financial officer', 'chief financial'])
            is_10pct_owner = '10%' in title_raw or 'ten percent' in title
            is_director = 'director' in title and 'chief' not in title
            is_executive = any(word in title for word in ['president', 'evp', 'svp', 'chief', 'officer'])

            # Determine if buy or sell
            if trade_type == 'derivative':
                is_buy = value > 0
                is_sell = value < 0
            else:
                is_buy = any(word in trade_type for word in ['purchase', 'buy', 'acquisition'])
                is_sell = any(word in trade_type for word in ['sale', 'sell', 'disposition']) and not is_buy

            abs_value = abs(value)

            # Apply 10b5-1 weight (50% for planned sales)
            weighted_value = abs_value * 0.5 if (is_sell and is_10b51) else abs_value

            if is_buy:
                buy_count += 1
                net_value += abs_value
                net_value_weighted += weighted_value

                if trade_date:
                    buy_dates.append(trade_date)

                # Track role-based buys
                if is_ceo:
                    ceo_buys += 1
                    key_transactions.append(f"CEO {txn['insider_name']} bought ${abs_value:,.0f}")
                elif is_cfo:
                    cfo_buys += 1
                    key_transactions.append(f"CFO {txn['insider_name']} bought ${abs_value:,.0f}")
                elif is_10pct_owner:
                    owner_10pct_buys += 1
                    key_transactions.append(f"10% Owner {txn['insider_name']} bought ${abs_value:,.0f}")
                elif abs_value > 1_000_000:
                    key_transactions.append(f"{title_raw} {txn['insider_name']} bought ${abs_value:,.0f}")

            elif is_sell:
                sell_count += 1
                net_value -= abs_value
                net_value_weighted -= weighted_value

                if trade_date:
                    sell_dates.append(trade_date)

                # Track role-based sells
                if is_ceo:
                    ceo_sells += 1
                    sell_type = "10b5-1 plan" if is_10b51 else "discretionary"
                    key_transactions.append(f"CEO {txn['insider_name']} sold ${abs_value:,.0f} ({sell_type})")
                elif is_cfo:
                    cfo_sells += 1
                    sell_type = "10b5-1 plan" if is_10b51 else "discretionary"
                    key_transactions.append(f"CFO {txn['insider_name']} sold ${abs_value:,.0f} ({sell_type})")
                elif is_10pct_owner:
                    owner_10pct_sells += 1
                    key_transactions.append(f"10% Owner {txn['insider_name']} sold ${abs_value:,.0f}")
                elif abs_value > 5_000_000:
                    key_transactions.append(f"{title_raw} {txn['insider_name']} sold ${abs_value:,.0f}")

        # ========== LAYER 1: DOLLAR VOLUME SCORING (Primary) ==========
        score = 5.0  # Start neutral

        # Use weighted net value for scoring (accounts for 10b5-1 downweighting)
        if net_value_weighted < -500_000_000:  # >$500M net selling
            score = 1.5
            key_transactions.insert(0, f"HEAVY SELLING: Net ${net_value:,.0f} across {sell_count} transactions")
        elif net_value_weighted < -100_000_000:  # $100M-500M net selling
            score = 2.5
            key_transactions.insert(0, f"SIGNIFICANT SELLING: Net ${net_value:,.0f}")
        elif net_value_weighted < -50_000_000:  # $50M-100M net selling
            score = 3.5
        elif net_value_weighted < -10_000_000:  # $10M-50M net selling
            score = 4.0
        elif net_value_weighted > 500_000_000:  # >$500M net buying
            score = 9.0
            key_transactions.insert(0, f"HEAVY BUYING: Net ${net_value:,.0f}")
        elif net_value_weighted > 100_000_000:  # $100M-500M net buying
            score = 8.0
        elif net_value_weighted > 50_000_000:  # $50M-100M net buying
            score = 7.0
        elif net_value_weighted > 10_000_000:  # $10M-50M net buying
            score = 6.5

        # ========== LAYER 2: TRANSACTION PATTERN SCORING ==========

        # Pattern: One-sided activity (all sells or all buys)
        if sell_count >= 10 and buy_count == 0:
            score -= 1.0  # Heavy one-sided selling
            key_transactions.insert(0, f"ONE-SIDED: {sell_count} sells, 0 buys")
        elif buy_count >= 10 and sell_count == 0:
            score += 1.0  # Heavy one-sided buying

        # Pattern: Cluster selling (multiple sells in 30-day window)
        if sell_dates:
            sell_dates_sorted = sorted(sell_dates)
            for i in range(len(sell_dates_sorted) - 2):
                window_start = sell_dates_sorted[i]
                window_end = sell_dates_sorted[i + 2]  # 3rd transaction
                if (window_end - window_start).days <= 30:
                    score -= 0.5  # Cluster selling penalty
                    key_transactions.insert(0, "CLUSTER SELLING: Multiple insiders selling within 30 days")
                    break

        # Pattern: Cluster buying (multiple buys in 30-day window)
        if buy_dates:
            buy_dates_sorted = sorted(buy_dates)
            for i in range(len(buy_dates_sorted) - 2):
                window_start = buy_dates_sorted[i]
                window_end = buy_dates_sorted[i + 2]
                if (window_end - window_start).days <= 30:
                    score += 0.5  # Cluster buying bonus
                    key_transactions.insert(0, "CLUSTER BUYING: Multiple insiders buying within 30 days")
                    break

        # ========== LAYER 3: TITLE-BASED AMPLIFICATION ==========

        # CEO/CFO activity amplifies the existing signal
        if ceo_buys > 0:
            score += 1.5  # CEO buying is highly bullish
        if cfo_buys > 0:
            score += 1.0  # CFO buying is bullish
        if owner_10pct_buys > 0:
            score += 1.0  # 10% owner buying is significant

        if ceo_sells > 0:
            score -= 1.5  # CEO selling is bearish
        if cfo_sells > 0:
            score -= 1.0  # CFO selling is bearish
        if owner_10pct_sells > 0:
            score -= 0.5  # 10% owner selling (less significant than C-level)

        # Cap score at 0-10 range
        score = max(0.0, min(10.0, score))

        # Determine sentiment
        if score >= 7.0:
            sentiment = 'bullish'
        elif score <= 3.0:
            sentiment = 'bearish'
        else:
            sentiment = 'neutral'

        logger.info(f"Insider score for {ticker}: {score:.1f}/10 ({sentiment}) - {buy_count} buys, {sell_count} sells, net ${net_value:,.0f}")

        return {
            'score': round(score, 1),
            'buy_transactions': buy_count,
            'sell_transactions': sell_count,
            'net_value': round(net_value, 2),
            'key_transactions': key_transactions[:5],  # Top 5 most notable
            'sentiment': sentiment,
            'has_data': True
        }


# Global client instance
openinsider_client = OpenInsiderClient()
