"""
SEC Edgar API client.
Free API, no key required.
"""
import requests
import re
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from bs4 import BeautifulSoup
from research_swarm.logger import logger
from research_swarm.data.cache import cache

class SECClient:
    """Client for SEC Edgar API (free)."""

    BASE_URL = "https://data.sec.gov"

    def __init__(self):
        # SEC requires User-Agent header
        self.headers = {
            "User-Agent": "ResearchSwarm/0.1.0 (contact@example.com)"
        }
        logger.info("SEC Edgar client initialized")

    def get_company_cik(self, ticker: str) -> Optional[str]:
        """
        Get company CIK (Central Index Key) from ticker.

        Args:
            ticker: Stock ticker (e.g., 'AAPL')

        Returns:
            CIK string or None if not found
        """
        ticker = ticker.upper()
        cache_key = f"{ticker}_cik"

        # Check cache (CIKs never change, cache forever)
        cached = cache.get("sec_cik", cache_key)
        if cached:
            return cached

        # For Phase 2, use a simple lookup table for common tickers
        # Phase 3 will implement full SEC API integration
        known_ciks = {
            "AAPL": "0000320193",
            "MSFT": "0000789019",
            "GOOGL": "0001652044",
            "AMZN": "0001018724",
            "TSLA": "0001318605",
            "META": "0001326801",
            "NVDA": "0001045810",
            "CRDO": "0001807794",
        }

        cik = known_ciks.get(ticker)
        if cik:
            cache.set("sec_cik", cache_key, cik, ttl_days=365)
            logger.info(f"Found CIK for {ticker}: {cik}")
            return cik

        # Automatic lookup: try SEC company tickers JSON API
        try:
            logger.info(f"Searching SEC database for ticker: {ticker}")
            url = "https://www.sec.gov/files/company_tickers.json"
            response = requests.get(url, headers=self.headers, timeout=15)
            response.raise_for_status()

            # Parse ticker data
            companies = response.json()

            # Search for matching ticker
            for company_data in companies.values():
                if company_data.get("ticker", "").upper() == ticker:
                    cik_int = company_data.get("cik_str")
                    # Format CIK with leading zeros (10 digits)
                    cik = str(cik_int).zfill(10)

                    # Cache it
                    cache.set("sec_cik", cache_key, cik, ttl_days=365)
                    logger.success(f"Found CIK for {ticker}: {cik} ({company_data.get('title', 'Unknown')})")
                    return cik

            logger.warning(f"No CIK found for ticker: {ticker} in SEC database")
            return None

        except Exception as e:
            logger.error(f"SEC API lookup failed for {ticker}: {e}")
            logger.warning(f"Could not find CIK for ticker: {ticker}")
            return None

    def get_10k_filing(self, ticker: str, year: int) -> Optional[Dict]:
        """
        Fetch 10-K filing text for a company.

        Args:
            ticker: Stock ticker
            year: Fiscal year (e.g., 2023)

        Returns:
            Dict with filing metadata and text, or None
        """
        cache_key = f"{ticker}_10K_{year}"

        # Check cache (10-Ks don't change, cache for 90 days)
        cached = cache.get("sec_10k", cache_key)
        if cached:
            # Validate cached data has sufficient content
            cached_text = cached.get("text", "")
            if len(cached_text) >= 1000:
                logger.info(f"Using cached 10-K for {ticker} year {year}")
                return cached
            else:
                logger.warning(f"Cached 10-K for {ticker} has insufficient content ({len(cached_text)} chars), refetching")

        cik = self.get_company_cik(ticker)
        if not cik:
            logger.error(f"Could not find CIK for {ticker}")
            return None

        try:
            # Step 1: Get company submissions index
            logger.info(f"Fetching 10-K for {ticker} (CIK: {cik}) year {year}")
            submissions_url = f"{self.BASE_URL}/submissions/CIK{cik}.json"
            response = requests.get(submissions_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            submissions = response.json()

            # Step 2: Find 10-K filing for the specified year
            filings = submissions.get("filings", {}).get("recent", {})
            forms = filings.get("form", [])
            filing_dates = filings.get("filingDate", [])
            accession_numbers = filings.get("accessionNumber", [])
            primary_documents = filings.get("primaryDocument", [])

            target_filing = None
            for i, form in enumerate(forms):
                if form == "10-K":
                    filing_date = filing_dates[i]
                    primary_doc = primary_documents[i]

                    # Extract fiscal year from document name (e.g., "aapl-20230930.htm" -> 2023)
                    # Document name format: {ticker}-YYYYMMDD.htm
                    match = re.search(r'-(\d{4})\d{4}\.', primary_doc)
                    if match:
                        fiscal_year = int(match.group(1))
                    else:
                        # Fallback: use filing date year
                        fiscal_year = int(filing_date.split("-")[0]) - 1

                    # Match by fiscal year
                    if fiscal_year == year:
                        target_filing = {
                            "accession_number": accession_numbers[i],
                            "filing_date": filing_date,
                            "primary_document": primary_doc
                        }
                        break

            if not target_filing:
                logger.error(f"No 10-K found for {ticker} year {year}")
                return None

            # Step 3: Download the actual filing document
            accession = target_filing["accession_number"].replace("-", "")
            doc_name = target_filing["primary_document"]
            doc_url = f"https://www.sec.gov/Archives/edgar/data/{cik.lstrip('0')}/{accession}/{doc_name}"

            logger.info(f"Downloading 10-K from: {doc_url}")
            doc_response = requests.get(doc_url, headers=self.headers, timeout=30)
            doc_response.raise_for_status()

            # Step 4: Extract text from HTML
            html_content = doc_response.text
            text = self._extract_text_from_html(html_content)

            if not text or len(text) < 1000:
                logger.error(f"Extracted text too short ({len(text)} chars) for {ticker} year {year}")
                return None

            result = {
                "ticker": ticker,
                "cik": cik,
                "year": year,
                "filing_type": "10-K",
                "filing_date": target_filing["filing_date"],
                "accession_number": target_filing["accession_number"],
                "text": text,
                "url": doc_url,
                "text_length": len(text)
            }

            # Cache for 90 days
            cache.set("sec_10k", cache_key, result, ttl_days=90)
            logger.success(f"✓ Downloaded 10-K for {ticker} year {year} ({len(text):,} chars)")
            return result

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error fetching 10-K for {ticker}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching 10-K for {ticker}: {e}")
            return None

    def get_10q_filing(self, ticker: str, year: int, quarter: int) -> Optional[Dict]:
        """
        Fetch 10-Q filing text for a company.

        Args:
            ticker: Stock ticker
            year: Calendar year (e.g., 2025)
            quarter: Quarter number (1, 2, or 3)
                    Note: Q4 data typically comes from 10-K, not 10-Q

        Returns:
            Dict with filing metadata and text, or None
        """
        if quarter not in [1, 2, 3]:
            logger.warning(f"Quarter {quarter} is not valid for 10-Q (only Q1-Q3). Q4 data is in 10-K.")
            return None

        cache_key = f"{ticker}_10Q_{year}Q{quarter}"

        # Check cache (10-Qs don't change, cache for 90 days)
        cached = cache.get("sec_10q", cache_key)
        if cached:
            cached_text = cached.get("text", "")
            if len(cached_text) >= 1000:
                logger.info(f"Using cached 10-Q for {ticker} {year} Q{quarter}")
                return cached
            else:
                logger.warning(f"Cached 10-Q for {ticker} has insufficient content, refetching")

        cik = self.get_company_cik(ticker)
        if not cik:
            logger.error(f"Could not find CIK for {ticker}")
            return None

        try:
            # Step 1: Get company submissions index
            logger.info(f"Fetching 10-Q for {ticker} (CIK: {cik}) {year} Q{quarter}")
            submissions_url = f"{self.BASE_URL}/submissions/CIK{cik}.json"
            response = requests.get(submissions_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            submissions = response.json()

            # Step 2: Find 10-Q filing for the specified quarter
            filings = submissions.get("filings", {}).get("recent", {})
            forms = filings.get("form", [])
            filing_dates = filings.get("filingDate", [])
            accession_numbers = filings.get("accessionNumber", [])
            primary_documents = filings.get("primaryDocument", [])

            target_filing = None
            for i, form in enumerate(forms):
                if form == "10-Q":
                    filing_date = filing_dates[i]
                    primary_doc = primary_documents[i]

                    # Extract fiscal period from document name (e.g., "aapl-20250630.htm")
                    match = re.search(r'-(\d{4})(\d{2})(\d{2})\.', primary_doc)
                    if match:
                        doc_year = int(match.group(1))
                        doc_month = int(match.group(2))

                        # Determine quarter from month
                        # Q1 ends Mar (3), Q2 ends Jun (6), Q3 ends Sep (9)
                        if doc_month in [3, 4]:  # Q1 (filed in Apr/May)
                            doc_quarter = 1
                        elif doc_month in [6, 7]:  # Q2 (filed in Jul/Aug)
                            doc_quarter = 2
                        elif doc_month in [9, 10]:  # Q3 (filed in Oct/Nov)
                            doc_quarter = 3
                        else:
                            continue  # Skip if month doesn't match typical quarter end

                        if doc_year == year and doc_quarter == quarter:
                            target_filing = {
                                "accession_number": accession_numbers[i],
                                "filing_date": filing_date,
                                "primary_document": primary_doc,
                                "fiscal_period_end": f"{doc_year}-{match.group(2)}-{match.group(3)}"
                            }
                            break
                    else:
                        # Fallback: parse filing date
                        filing_year = int(filing_date.split("-")[0])
                        filing_month = int(filing_date.split("-")[1])

                        # Estimate quarter from filing date (filings are ~45 days after quarter end)
                        if filing_month in [4, 5]:
                            doc_quarter = 1
                        elif filing_month in [7, 8]:
                            doc_quarter = 2
                        elif filing_month in [10, 11]:
                            doc_quarter = 3
                        else:
                            continue

                        # Match year and quarter
                        if filing_year == year and doc_quarter == quarter:
                            target_filing = {
                                "accession_number": accession_numbers[i],
                                "filing_date": filing_date,
                                "primary_document": primary_doc
                            }
                            break

            if not target_filing:
                logger.warning(f"No 10-Q found for {ticker} {year} Q{quarter}")
                return None

            # Step 3: Download the actual filing document
            accession = target_filing["accession_number"].replace("-", "")
            doc_name = target_filing["primary_document"]
            doc_url = f"https://www.sec.gov/Archives/edgar/data/{cik.lstrip('0')}/{accession}/{doc_name}"

            logger.info(f"Downloading 10-Q from: {doc_url}")
            doc_response = requests.get(doc_url, headers=self.headers, timeout=30)
            doc_response.raise_for_status()

            # Step 4: Extract text from HTML
            html_content = doc_response.text
            text = self._extract_text_from_html(html_content)

            if not text or len(text) < 1000:
                logger.error(f"Extracted text too short ({len(text)} chars) for {ticker} {year} Q{quarter}")
                return None

            result = {
                "ticker": ticker,
                "cik": cik,
                "year": year,
                "quarter": quarter,
                "quarter_label": f"Q{quarter}_{year}",
                "filing_type": "10-Q",
                "filing_date": target_filing["filing_date"],
                "fiscal_period_end": target_filing.get("fiscal_period_end"),
                "accession_number": target_filing["accession_number"],
                "text": text,
                "url": doc_url,
                "text_length": len(text)
            }

            # Cache for 90 days
            cache.set("sec_10q", cache_key, result, ttl_days=90)
            logger.success(f"✓ Downloaded 10-Q for {ticker} {year} Q{quarter} ({len(text):,} chars)")
            return result

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error fetching 10-Q for {ticker}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching 10-Q for {ticker}: {e}")
            return None

    def is_foreign_filer(self, ticker: str) -> bool:
        """
        Check if a company is a foreign private issuer (files 20-F instead of 10-K).

        Args:
            ticker: Stock ticker

        Returns:
            True if the company files 20-F (foreign), False if 10-K (domestic)
        """
        ticker = ticker.upper()
        cache_key = f"{ticker}_filer_type"

        cached = cache.get("sec_filer_type", cache_key)
        if cached is not None:
            return cached.get("is_foreign", False)

        cik = self.get_company_cik(ticker)
        if not cik:
            return False

        try:
            submissions_url = f"{self.BASE_URL}/submissions/CIK{cik}.json"
            response = requests.get(submissions_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            forms = response.json().get("filings", {}).get("recent", {}).get("form", [])

            is_foreign = "20-F" in forms
            cache.set("sec_filer_type", cache_key, {"is_foreign": is_foreign}, ttl_days=365)
            logger.info(f"{ticker} filer type: {'foreign (20-F)' if is_foreign else 'domestic (10-K)'}")
            return is_foreign

        except Exception as e:
            logger.error(f"Error checking filer type for {ticker}: {e}")
            return False

    def get_20f_filing(self, ticker: str, year: int) -> Optional[Dict]:
        """
        Fetch 20-F annual filing for a foreign private issuer.

        Args:
            ticker: Stock ticker (e.g., 'TSM')
            year: Fiscal year (e.g., 2024)

        Returns:
            Dict with filing metadata and text, or None
        """
        cache_key = f"{ticker}_20F_{year}"

        cached = cache.get("sec_20f", cache_key)
        if cached:
            cached_text = cached.get("text", "")
            if len(cached_text) >= 1000:
                logger.info(f"Using cached 20-F for {ticker} year {year}")
                return cached
            else:
                logger.warning(f"Cached 20-F for {ticker} has insufficient content ({len(cached_text)} chars), refetching")

        cik = self.get_company_cik(ticker)
        if not cik:
            logger.error(f"Could not find CIK for {ticker}")
            return None

        try:
            logger.info(f"Fetching 20-F for {ticker} (CIK: {cik}) year {year}")
            submissions_url = f"{self.BASE_URL}/submissions/CIK{cik}.json"
            response = requests.get(submissions_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            submissions = response.json()

            filings = submissions.get("filings", {}).get("recent", {})
            forms = filings.get("form", [])
            filing_dates = filings.get("filingDate", [])
            accession_numbers = filings.get("accessionNumber", [])
            primary_documents = filings.get("primaryDocument", [])

            target_filing = None
            for i, form in enumerate(forms):
                if form == "20-F":
                    filing_date = filing_dates[i]
                    primary_doc = primary_documents[i]

                    # Extract fiscal year from document name or filing date
                    match = re.search(r'-(\d{4})\d{4}\.', primary_doc)
                    if match:
                        fiscal_year = int(match.group(1))
                    else:
                        # 20-F filing date is typically 4-6 months after fiscal year end
                        fiscal_year = int(filing_date.split("-")[0]) - 1

                    if fiscal_year == year:
                        target_filing = {
                            "accession_number": accession_numbers[i],
                            "filing_date": filing_date,
                            "primary_document": primary_doc
                        }
                        break

            if not target_filing:
                # Try matching most recent 20-F if exact year not found
                for i, form in enumerate(forms):
                    if form == "20-F":
                        target_filing = {
                            "accession_number": accession_numbers[i],
                            "filing_date": filing_dates[i],
                            "primary_document": primary_documents[i]
                        }
                        logger.warning(f"No 20-F found for {ticker} year {year}, using most recent")
                        break

            if not target_filing:
                logger.error(f"No 20-F found for {ticker}")
                return None

            accession = target_filing["accession_number"].replace("-", "")
            doc_name = target_filing["primary_document"]
            doc_url = f"https://www.sec.gov/Archives/edgar/data/{cik.lstrip('0')}/{accession}/{doc_name}"

            logger.info(f"Downloading 20-F from: {doc_url}")
            doc_response = requests.get(doc_url, headers=self.headers, timeout=30)
            doc_response.raise_for_status()

            html_content = doc_response.text
            text = self._extract_text_from_html(html_content)

            if not text or len(text) < 1000:
                logger.error(f"Extracted text too short ({len(text)} chars) for {ticker} 20-F year {year}")
                return None

            result = {
                "ticker": ticker,
                "cik": cik,
                "year": year,
                "filing_type": "20-F",
                "filing_date": target_filing["filing_date"],
                "accession_number": target_filing["accession_number"],
                "text": text,
                "url": doc_url,
                "text_length": len(text)
            }

            cache.set("sec_20f", cache_key, result, ttl_days=90)
            logger.success(f"✓ Downloaded 20-F for {ticker} year {year} ({len(text):,} chars)")
            return result

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error fetching 20-F for {ticker}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching 20-F for {ticker}: {e}")
            return None

    def get_6k_filing(self, ticker: str, year: int, quarter: int) -> Optional[Dict]:
        """
        Fetch 6-K interim filing for a foreign private issuer.

        6-K filings don't follow a fixed quarterly cadence like 10-Q.
        We match by filing date falling within the target quarter's window.
        If multiple 6-K filings exist for a quarter, prefer the longest one
        (most likely to contain financial results vs a simple press release).

        Args:
            ticker: Stock ticker
            year: Calendar year
            quarter: Quarter number (1, 2, or 3)

        Returns:
            Dict with filing metadata and text, or None
        """
        if quarter not in [1, 2, 3]:
            logger.warning(f"Quarter {quarter} is not valid for 6-K (only Q1-Q3). Q4 data is in 20-F.")
            return None

        cache_key = f"{ticker}_6K_{year}Q{quarter}"

        cached = cache.get("sec_6k", cache_key)
        if cached:
            cached_text = cached.get("text", "")
            if len(cached_text) >= 1000:
                logger.info(f"Using cached 6-K for {ticker} {year} Q{quarter}")
                return cached
            else:
                logger.warning(f"Cached 6-K for {ticker} has insufficient content, refetching")

        cik = self.get_company_cik(ticker)
        if not cik:
            logger.error(f"Could not find CIK for {ticker}")
            return None

        # Define quarter date windows
        # Q1: Jan-Mar filings (filed ~Apr-Jun)
        # Q2: Apr-Jun filings (filed ~Jul-Sep)
        # Q3: Jul-Sep filings (filed ~Oct-Dec)
        quarter_windows = {
            1: ((year, 1, 1), (year, 6, 30)),   # Q1 results filed Jan-Jun
            2: ((year, 4, 1), (year, 9, 30)),    # Q2 results filed Apr-Sep
            3: ((year, 7, 1), (year, 12, 31)),   # Q3 results filed Jul-Dec
        }
        window_start, window_end = quarter_windows[quarter]
        start_date = datetime(window_start[0], window_start[1], window_start[2])
        end_date = datetime(window_end[0], window_end[1], window_end[2])

        try:
            logger.info(f"Fetching 6-K for {ticker} (CIK: {cik}) {year} Q{quarter}")
            submissions_url = f"{self.BASE_URL}/submissions/CIK{cik}.json"
            response = requests.get(submissions_url, headers=self.headers, timeout=10)
            response.raise_for_status()
            submissions = response.json()

            filings = submissions.get("filings", {}).get("recent", {})
            forms = filings.get("form", [])
            filing_dates = filings.get("filingDate", [])
            accession_numbers = filings.get("accessionNumber", [])
            primary_documents = filings.get("primaryDocument", [])

            # Collect all 6-K filings within the date window
            candidates = []
            for i, form in enumerate(forms):
                if form == "6-K":
                    filing_date_str = filing_dates[i]
                    try:
                        filing_dt = datetime.strptime(filing_date_str, "%Y-%m-%d")
                    except ValueError:
                        continue

                    if start_date <= filing_dt <= end_date:
                        candidates.append({
                            "index": i,
                            "accession_number": accession_numbers[i],
                            "filing_date": filing_date_str,
                            "primary_document": primary_documents[i]
                        })

            if not candidates:
                logger.warning(f"No 6-K found for {ticker} {year} Q{quarter}")
                return None

            # Try candidates, preferring the one with the most content
            best_result = None
            best_length = 0

            for candidate in candidates[:3]:  # Check up to 3 candidates to limit API calls
                accession = candidate["accession_number"].replace("-", "")
                doc_name = candidate["primary_document"]
                doc_url = f"https://www.sec.gov/Archives/edgar/data/{cik.lstrip('0')}/{accession}/{doc_name}"

                try:
                    doc_response = requests.get(doc_url, headers=self.headers, timeout=30)
                    doc_response.raise_for_status()
                    text = self._extract_text_from_html(doc_response.text)

                    if text and len(text) > best_length:
                        best_length = len(text)
                        best_result = {
                            "ticker": ticker,
                            "cik": cik,
                            "year": year,
                            "quarter": quarter,
                            "quarter_label": f"Q{quarter}_{year}",
                            "filing_type": "6-K",
                            "filing_date": candidate["filing_date"],
                            "accession_number": candidate["accession_number"],
                            "text": text,
                            "url": doc_url,
                            "text_length": len(text)
                        }
                except Exception as e:
                    logger.warning(f"Failed to download 6-K candidate: {e}")
                    continue

            if best_result and best_result["text_length"] >= 1000:
                best_result["source"] = "6-K"
                cache.set("sec_6k", cache_key, best_result, ttl_days=90)
                logger.success(f"✓ Downloaded 6-K for {ticker} {year} Q{quarter} ({best_length:,} chars)")
                return best_result
            else:
                logger.warning(f"No substantial 6-K content found for {ticker} {year} Q{quarter}")
                return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error fetching 6-K for {ticker}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching 6-K for {ticker}: {e}")
            return None

    def get_ttm_filings(
        self,
        ticker: str,
        end_quarter: Optional[str] = None
    ) -> Dict[str, Optional[Dict]]:
        """
        Fetch trailing 4 quarters of filings for TTM analysis.

        Args:
            ticker: Stock ticker
            end_quarter: End quarter in "Q#_YYYY" format (e.g., "Q3_2025")
                        Defaults to most recent quarter based on current date

        Returns:
            Dict mapping quarter labels to filing data:
            {
                "Q3_2025": {...},  # 10-Q
                "Q2_2025": {...},  # 10-Q
                "Q1_2025": {...},  # 10-Q
                "Q4_2024": {...}   # From 10-K (Q4 data)
            }
            Missing quarters will have None values.
        """
        # Determine trailing 4 quarters
        if end_quarter:
            # Parse end_quarter (e.g., "Q3_2025")
            match = re.match(r'Q(\d)_(\d{4})', end_quarter)
            if not match:
                logger.error(f"Invalid end_quarter format: {end_quarter}. Expected Q#_YYYY")
                return {}
            end_q = int(match.group(1))
            end_year = int(match.group(2))
        else:
            # Calculate most recent quarter from current date
            now = datetime.now()
            # Q1: Jan-Mar, Q2: Apr-Jun, Q3: Jul-Sep, Q4: Oct-Dec
            # Filings lag ~60 days, so be conservative about which quarter is available
            # Subtract 75 days to account for filing lag
            reference_date = now - timedelta(days=75)
            month = reference_date.month
            year = reference_date.year

            # Determine quarter from reference date
            if month in [1, 2, 3]:
                end_q = 4
                end_year = year - 1  # Q4 of previous year
            elif month in [4, 5, 6]:
                end_q = 1
                end_year = year
            elif month in [7, 8, 9]:
                end_q = 2
                end_year = year
            else:  # [10, 11, 12]
                end_q = 3
                end_year = year

        # Calculate trailing 4 quarters
        quarters_to_fetch: List[tuple] = []
        current_q = end_q
        current_year = end_year

        for _ in range(4):
            quarters_to_fetch.append((current_year, current_q))
            current_q -= 1
            if current_q == 0:
                current_q = 4
                current_year -= 1

        # Reverse to get chronological order (oldest first)
        quarters_to_fetch.reverse()

        # Check if foreign filer (20-F/6-K instead of 10-K/10-Q)
        is_foreign = self.is_foreign_filer(ticker)

        logger.info(f"Fetching TTM filings for {ticker} ({'foreign' if is_foreign else 'domestic'}): {[f'Q{q}_{y}' for y, q in quarters_to_fetch]}")

        results = {}
        data_quality = {}

        # For foreign filers, pre-fetch the 20-F (needed for Q4 and as fallback)
        annual_filing_20f = None
        if is_foreign:
            # Try the most recent year's 20-F first, then prior year
            for try_year in [quarters_to_fetch[-1][0], quarters_to_fetch[0][0]]:
                annual_filing_20f = self.get_20f_filing(ticker, try_year)
                if annual_filing_20f:
                    break

        for year, quarter in quarters_to_fetch:
            quarter_label = f"Q{quarter}_{year}"

            if is_foreign:
                # Foreign filer: 20-F for annual, 6-K for quarterly
                if quarter == 4:
                    if annual_filing_20f:
                        filing = dict(annual_filing_20f)  # Copy to avoid mutation
                        filing["quarter"] = 4
                        filing["quarter_label"] = quarter_label
                        filing["source"] = "20-F"
                        results[quarter_label] = filing
                        data_quality[quarter_label] = "20-F"
                    else:
                        results[quarter_label] = None
                        data_quality[quarter_label] = "missing"
                else:
                    # Try 6-K first for quarterly data
                    filing = self.get_6k_filing(ticker, year, quarter)
                    if filing:
                        filing["source"] = "6-K"
                        results[quarter_label] = filing
                        data_quality[quarter_label] = "6-K"
                    elif annual_filing_20f:
                        # Fallback: use 20-F annual data for this quarter slot
                        filing = dict(annual_filing_20f)
                        filing["quarter"] = quarter
                        filing["quarter_label"] = quarter_label
                        filing["source"] = "20-F"
                        results[quarter_label] = filing
                        data_quality[quarter_label] = "20-F_fallback"
                    else:
                        results[quarter_label] = None
                        data_quality[quarter_label] = "missing"
            else:
                # Domestic filer: 10-K for Q4, 10-Q for Q1-Q3
                if quarter == 4:
                    filing = self.get_10k_filing(ticker, year)
                    if filing:
                        filing["quarter"] = 4
                        filing["quarter_label"] = quarter_label
                        filing["source"] = "10-K"
                        results[quarter_label] = filing
                        data_quality[quarter_label] = "10-K"
                    else:
                        results[quarter_label] = None
                        data_quality[quarter_label] = "missing"
                else:
                    filing = self.get_10q_filing(ticker, year, quarter)
                    if filing:
                        filing["source"] = "10-Q"
                        results[quarter_label] = filing
                        data_quality[quarter_label] = "10-Q"
                    else:
                        results[quarter_label] = None
                        data_quality[quarter_label] = "missing"

        # Log summary
        available = sum(1 for v in results.values() if v is not None)
        logger.info(f"TTM filings for {ticker}: {available}/4 quarters available")
        logger.debug(f"Data quality: {data_quality}")

        # Add metadata to results
        results["_metadata"] = {
            "ticker": ticker,
            "analysis_period": f"TTM Q{quarters_to_fetch[0][1]} {quarters_to_fetch[0][0]} - Q{quarters_to_fetch[-1][1]} {quarters_to_fetch[-1][0]}",
            "quarters": [f"Q{q}_{y}" for y, q in quarters_to_fetch],
            "data_quality": data_quality,
            "available_quarters": available,
            "is_foreign": is_foreign
        }

        return results

    def _extract_text_from_html(self, html: str) -> str:
        """
        Extract clean text from HTML filing.

        Args:
            html: Raw HTML content

        Returns:
            Extracted text with basic cleaning
        """
        try:
            soup = BeautifulSoup(html, "html.parser")

            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()

            # Get text
            text = soup.get_text()

            # Clean up whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = '\n'.join(chunk for chunk in chunks if chunk)

            return text

        except Exception as e:
            logger.error(f"Error extracting text from HTML: {e}")
            # Fallback: use regex to strip HTML tags
            text = re.sub(r'<[^>]+>', '', html)
            text = re.sub(r'\s+', ' ', text)
            return text.strip()

# Global instance
sec_client = SECClient()
