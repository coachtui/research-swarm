"""
Technical analysis module for the Quant agent.

Provides pure Python implementations of technical indicators:
- Simple Moving Averages (SMA 50/200)
- Relative Strength Index (RSI)
- Volume analysis
- Relative strength vs sector/market
"""
from typing import Optional
import pandas as pd
import numpy as np
from loguru import logger
from datetime import datetime

from research_swarm.data import market_data_client
from .models import (
    MovingAverages,
    RSIData,
    VolumeAnalysis,
    RelativeStrength,
    TechnicalIndicators,
    CrossoverSignal,
    RSISignal,
    VolumeTrend,
    MACDData,
    MACDSignal,
    BollingerBands,
    BollingerPosition,
    StochasticData,
    StochasticSignal,
    VolumeProfile,
    VolumePriceLevel,
    EntryExitSignals,
    TradingSignal,
)


def calculate_sma(prices: pd.Series, period: int) -> pd.Series:
    """
    Calculate Simple Moving Average.

    Args:
        prices: Series of closing prices
        period: Number of periods for the moving average

    Returns:
        Series of SMA values
    """
    return prices.rolling(window=period, min_periods=period).mean()


def calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """
    Calculate Relative Strength Index.

    Formula:
    - Calculate price changes
    - Separate gains and losses
    - Calculate average gain and average loss over period
    - RS = avg_gain / avg_loss
    - RSI = 100 - (100 / (1 + RS))

    Args:
        prices: Series of closing prices
        period: RSI period (default 14)

    Returns:
        Series of RSI values (0-100)
    """
    # Calculate price changes
    delta = prices.diff()

    # Separate gains and losses
    gains = delta.where(delta > 0, 0.0)
    losses = -delta.where(delta < 0, 0.0)

    # Calculate average gain and loss using Wilder's smoothing
    avg_gain = gains.rolling(window=period, min_periods=period).mean()
    avg_loss = losses.rolling(window=period, min_periods=period).mean()

    # Calculate RS and RSI
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    return rsi


def calculate_ema(prices: pd.Series, period: int) -> pd.Series:
    """
    Calculate Exponential Moving Average.

    Args:
        prices: Series of closing prices
        period: Number of periods for the EMA

    Returns:
        Series of EMA values
    """
    return prices.ewm(span=period, adjust=False, min_periods=period).mean()


def calculate_macd(prices: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    Calculate MACD (Moving Average Convergence Divergence).

    Formula:
    - MACD Line = 12-EMA - 26-EMA
    - Signal Line = 9-EMA of MACD Line
    - Histogram = MACD Line - Signal Line

    Args:
        prices: Series of closing prices

    Returns:
        Tuple of (macd_line, signal_line, histogram)
    """
    # Calculate EMAs
    ema_12 = calculate_ema(prices, 12)
    ema_26 = calculate_ema(prices, 26)

    # MACD line
    macd_line = ema_12 - ema_26

    # Signal line (9-EMA of MACD)
    signal_line = calculate_ema(macd_line, 9)

    # Histogram
    histogram = macd_line - signal_line

    return macd_line, signal_line, histogram


def calculate_bollinger_bands(prices: pd.Series, period: int = 20, num_std: float = 2.0) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    Calculate Bollinger Bands.

    Formula:
    - Middle Band = 20-day SMA
    - Upper Band = Middle Band + (2 * standard deviation)
    - Lower Band = Middle Band - (2 * standard deviation)

    Args:
        prices: Series of closing prices
        period: Period for SMA and std dev (default 20)
        num_std: Number of standard deviations (default 2.0)

    Returns:
        Tuple of (upper_band, middle_band, lower_band)
    """
    middle_band = calculate_sma(prices, period)
    std_dev = prices.rolling(window=period, min_periods=period).std()

    upper_band = middle_band + (std_dev * num_std)
    lower_band = middle_band - (std_dev * num_std)

    return upper_band, middle_band, lower_band


def calculate_stochastic(df: pd.DataFrame, k_period: int = 14, d_period: int = 3) -> tuple[pd.Series, pd.Series]:
    """
    Calculate Stochastic Oscillator.

    Formula:
    - %K = 100 * (Current Close - Lowest Low) / (Highest High - Lowest Low)
    - %D = 3-period SMA of %K

    Args:
        df: DataFrame with High, Low, Close columns
        k_period: Period for %K calculation (default 14)
        d_period: Period for %D smoothing (default 3)

    Returns:
        Tuple of (k_values, d_values)
    """
    # Get highest high and lowest low over k_period
    lowest_low = df['Low'].rolling(window=k_period, min_periods=k_period).min()
    highest_high = df['High'].rolling(window=k_period, min_periods=k_period).max()

    # Calculate %K
    k_values = 100 * (df['Close'] - lowest_low) / (highest_high - lowest_low)

    # Calculate %D (SMA of %K)
    d_values = k_values.rolling(window=d_period, min_periods=d_period).mean()

    return k_values, d_values


class TechnicalAnalyzer:
    """
    Technical analysis engine for the Quant agent.

    Analyzes price action, momentum, volume, and relative strength.
    """

    def __init__(self):
        """Initialize the technical analyzer."""
        self.client = market_data_client

    def get_moving_averages(
        self,
        ticker: str,
        df: pd.DataFrame
    ) -> MovingAverages:
        """
        Calculate moving averages and detect crossovers.

        Args:
            ticker: Stock ticker
            df: DataFrame with OHLCV data

        Returns:
            MovingAverages model with SMA 50/200 and crossover signals
        """
        try:
            prices = df['Close']
            current_price = float(prices.iloc[-1])

            # Calculate SMAs
            sma_50_series = calculate_sma(prices, 50)
            sma_200_series = calculate_sma(prices, 200)

            # Get latest SMA values
            sma_50 = float(sma_50_series.iloc[-1]) if not pd.isna(sma_50_series.iloc[-1]) else None
            sma_200 = float(sma_200_series.iloc[-1]) if not pd.isna(sma_200_series.iloc[-1]) else None

            # 252-trading-day rolling high (≈1 calendar year)
            high_col = df['High'] if 'High' in df.columns else prices
            window = min(252, len(high_col))
            high_252d = float(high_col.iloc[-window:].max()) if window > 0 else None

            # Detect crossovers
            crossover_signal = CrossoverSignal.NONE
            days_since_crossover = None

            if sma_50 is not None and sma_200 is not None:
                # Look back up to 30 days for crossover
                lookback = min(30, len(sma_50_series) - 200)
                if lookback > 1:
                    for i in range(1, lookback + 1):
                        idx_current = -i
                        idx_previous = -i - 1

                        sma50_current = sma_50_series.iloc[idx_current]
                        sma50_previous = sma_50_series.iloc[idx_previous]
                        sma200_current = sma_200_series.iloc[idx_current]
                        sma200_previous = sma_200_series.iloc[idx_previous]

                        # Skip if any value is NaN
                        if pd.isna([sma50_current, sma50_previous, sma200_current, sma200_previous]).any():
                            continue

                        # Golden cross: SMA50 crosses above SMA200
                        if sma50_previous < sma200_previous and sma50_current > sma200_current:
                            crossover_signal = CrossoverSignal.GOLDEN_CROSS
                            days_since_crossover = i - 1
                            break

                        # Death cross: SMA50 crosses below SMA200
                        if sma50_previous > sma200_previous and sma50_current < sma200_current:
                            crossover_signal = CrossoverSignal.DEATH_CROSS
                            days_since_crossover = i - 1
                            break

            return MovingAverages(
                sma_50=sma_50,
                sma_200=sma_200,
                current_price=current_price,
                high_252d=high_252d,
                crossover_signal=crossover_signal,
                days_since_crossover=days_since_crossover,
            )

        except Exception as e:
            logger.error(f"Error calculating moving averages for {ticker}: {e}")
            return MovingAverages(
                crossover_signal=CrossoverSignal.NONE,
            )

    def get_rsi(
        self,
        ticker: str,
        df: pd.DataFrame
    ) -> RSIData:
        """
        Calculate RSI and interpret signals.

        Args:
            ticker: Stock ticker
            df: DataFrame with OHLCV data

        Returns:
            RSIData model with RSI value and signal interpretation
        """
        try:
            prices = df['Close']
            rsi_series = calculate_rsi(prices, period=14)

            # Get latest RSI
            rsi_value = float(rsi_series.iloc[-1]) if not pd.isna(rsi_series.iloc[-1]) else None

            # Determine signal
            if rsi_value is None:
                signal = RSISignal.NEUTRAL
                interpretation = "Insufficient data to calculate RSI"
            elif rsi_value < 30:
                signal = RSISignal.OVERSOLD
                interpretation = f"RSI at {rsi_value:.1f} indicates oversold conditions (potentially bullish reversal)"
            elif rsi_value > 70:
                signal = RSISignal.OVERBOUGHT
                interpretation = f"RSI at {rsi_value:.1f} indicates overbought conditions (potentially bearish reversal)"
            else:
                signal = RSISignal.NEUTRAL
                interpretation = f"RSI at {rsi_value:.1f} is in neutral territory"

            return RSIData(
                rsi_14=rsi_value,
                rsi_signal=signal,
                interpretation=interpretation,
            )

        except Exception as e:
            logger.error(f"Error calculating RSI for {ticker}: {e}")
            return RSIData(
                rsi_signal=RSISignal.NEUTRAL,
                interpretation=f"Error calculating RSI: {str(e)}",
            )

    def get_volume_analysis(
        self,
        ticker: str,
        df: pd.DataFrame
    ) -> VolumeAnalysis:
        """
        Analyze volume trends.

        Args:
            ticker: Stock ticker
            df: DataFrame with OHLCV data

        Returns:
            VolumeAnalysis model with volume metrics and trend
        """
        try:
            volumes = df['Volume']

            # Calculate 20-day average volume
            avg_volume = volumes.rolling(window=20, min_periods=20).mean()
            avg_volume_20d = float(avg_volume.iloc[-1]) if not pd.isna(avg_volume.iloc[-1]) else None
            current_volume = float(volumes.iloc[-1])

            # Calculate volume ratio
            volume_ratio = None
            if avg_volume_20d is not None and avg_volume_20d > 0:
                volume_ratio = current_volume / avg_volume_20d

            # Determine volume trend (comparing recent 5-day avg to previous 5-day avg)
            volume_trend = VolumeTrend.STABLE
            if len(volumes) >= 10:
                recent_avg = volumes.iloc[-5:].mean()
                previous_avg = volumes.iloc[-10:-5].mean()

                if previous_avg > 0:
                    change_pct = ((recent_avg - previous_avg) / previous_avg) * 100

                    if change_pct > 10:
                        volume_trend = VolumeTrend.INCREASING
                    elif change_pct < -10:
                        volume_trend = VolumeTrend.DECREASING

            # Volume data quality sanity gate
            # Rationale: volume_ratio < 10% is statistically implausible for any listed equity
            # on a normal trading day — almost always a data feed gap or partial-session artifact.
            # volume_ratio > 10x is elevated and warrants catalyst verification.
            volume_quality = "NORMAL"
            volume_quality_flag = None
            volume_exclude_from_scoring = False

            if volume_ratio is not None:
                if volume_ratio < 0.10:
                    volume_quality = "SUSPECT"
                    volume_quality_flag = (
                        f"Volume at {volume_ratio:.0%} of 20-day average — below minimum plausible "
                        "threshold for a listed equity on a normal trading session. "
                        "Likely cause: data feed gap, partial session, or pre/after-market-only data. "
                        "Volume-dependent signals excluded from scoring until verified."
                    )
                    volume_exclude_from_scoring = True
                elif volume_ratio > 10.0:
                    volume_quality = "ELEVATED"
                    volume_quality_flag = (
                        f"Volume at {volume_ratio:.0%} of 20-day average — unusually elevated. "
                        "Verify against a catalyst (earnings, major news, index rebalance) "
                        "before interpreting as a directional signal."
                    )

            return VolumeAnalysis(
                avg_volume_20d=avg_volume_20d,
                current_volume=current_volume,
                volume_ratio=volume_ratio,
                volume_trend=volume_trend,
                volume_quality=volume_quality,
                volume_quality_flag=volume_quality_flag,
                volume_exclude_from_scoring=volume_exclude_from_scoring,
            )

        except Exception as e:
            logger.error(f"Error analyzing volume for {ticker}: {e}")
            return VolumeAnalysis(
                volume_trend=VolumeTrend.STABLE,
            )

    def get_relative_strength(
        self,
        ticker: str,
        df: pd.DataFrame
    ) -> RelativeStrength:
        """
        Calculate relative strength vs sector and market.

        Args:
            ticker: Stock ticker
            df: DataFrame with OHLCV data for the ticker

        Returns:
            RelativeStrength model with comparative returns
        """
        try:
            # Get ticker returns
            prices = df['Close']
            ticker_return_1m = self._calculate_return(prices, days=21)  # ~1 month
            ticker_return_3m = self._calculate_return(prices, days=63)  # ~3 months

            # Get sector ETF
            sector_etf = self.client.get_sector_etf(ticker)

            # Get sector returns
            sector_return_1m = None
            sector_return_3m = None
            if sector_etf:
                try:
                    sector_df = self.client.get_historical_data(sector_etf, period="6mo")
                    if not sector_df.empty:
                        sector_return_1m = self._calculate_return(sector_df['Close'], days=21)
                        sector_return_3m = self._calculate_return(sector_df['Close'], days=63)
                except Exception as e:
                    logger.warning(f"Could not fetch sector data for {sector_etf}: {e}")

            # Get market (SPY) returns
            market_return_1m = None
            market_return_3m = None
            try:
                spy_df = self.client.get_historical_data("SPY", period="6mo")
                if not spy_df.empty:
                    market_return_1m = self._calculate_return(spy_df['Close'], days=21)
                    market_return_3m = self._calculate_return(spy_df['Close'], days=63)
            except Exception as e:
                logger.warning(f"Could not fetch market data (SPY): {e}")

            # Calculate outperformance
            vs_sector_1m = None
            vs_sector_3m = None
            if ticker_return_1m is not None and sector_return_1m is not None:
                vs_sector_1m = ticker_return_1m - sector_return_1m
            if ticker_return_3m is not None and sector_return_3m is not None:
                vs_sector_3m = ticker_return_3m - sector_return_3m

            vs_market_1m = None
            vs_market_3m = None
            if ticker_return_1m is not None and market_return_1m is not None:
                vs_market_1m = ticker_return_1m - market_return_1m
            if ticker_return_3m is not None and market_return_3m is not None:
                vs_market_3m = ticker_return_3m - market_return_3m

            return RelativeStrength(
                ticker_return_1m=ticker_return_1m,
                ticker_return_3m=ticker_return_3m,
                sector_return_1m=sector_return_1m,
                sector_return_3m=sector_return_3m,
                market_return_1m=market_return_1m,
                market_return_3m=market_return_3m,
                vs_sector_1m=vs_sector_1m,
                vs_sector_3m=vs_sector_3m,
                vs_market_1m=vs_market_1m,
                vs_market_3m=vs_market_3m,
            )

        except Exception as e:
            logger.error(f"Error calculating relative strength for {ticker}: {e}")
            return RelativeStrength()

    def _calculate_return(self, prices: pd.Series, days: int) -> Optional[float]:
        """
        Calculate return over specified number of days.

        Args:
            prices: Series of closing prices
            days: Number of days to look back

        Returns:
            Return as percentage, or None if insufficient data
        """
        try:
            if len(prices) < days + 1:
                return None

            end_price = prices.iloc[-1]
            start_price = prices.iloc[-days - 1]

            if pd.isna(end_price) or pd.isna(start_price) or start_price == 0:
                return None

            return float(((end_price - start_price) / start_price) * 100)

        except Exception:
            return None

    def get_macd(
        self,
        ticker: str,
        df: pd.DataFrame
    ) -> MACDData:
        """
        Calculate MACD and interpret signals.

        Args:
            ticker: Stock ticker
            df: DataFrame with OHLCV data

        Returns:
            MACDData model with MACD values and signal interpretation
        """
        try:
            prices = df['Close']
            macd_line_series, signal_line_series, histogram_series = calculate_macd(prices)

            # Get latest values
            macd_line = float(macd_line_series.iloc[-1]) if not pd.isna(macd_line_series.iloc[-1]) else None
            signal_line = float(signal_line_series.iloc[-1]) if not pd.isna(signal_line_series.iloc[-1]) else None
            histogram = float(histogram_series.iloc[-1]) if not pd.isna(histogram_series.iloc[-1]) else None

            # Determine signal
            if macd_line is None or signal_line is None:
                macd_signal = MACDSignal.NEUTRAL
                interpretation = "Insufficient data to calculate MACD"
            elif macd_line > signal_line and histogram > 0:
                macd_signal = MACDSignal.BULLISH
                interpretation = f"MACD ({macd_line:.2f}) above signal line ({signal_line:.2f}) - bullish momentum"
            elif macd_line < signal_line and histogram < 0:
                macd_signal = MACDSignal.BEARISH
                interpretation = f"MACD ({macd_line:.2f}) below signal line ({signal_line:.2f}) - bearish momentum"
            else:
                macd_signal = MACDSignal.NEUTRAL
                interpretation = f"MACD ({macd_line:.2f}) near signal line ({signal_line:.2f}) - neutral momentum"

            return MACDData(
                macd_line=macd_line,
                signal_line=signal_line,
                histogram=histogram,
                macd_signal=macd_signal,
                interpretation=interpretation,
            )

        except Exception as e:
            logger.error(f"Error calculating MACD for {ticker}: {e}")
            return MACDData(
                macd_signal=MACDSignal.NEUTRAL,
                interpretation=f"Error calculating MACD: {str(e)}",
            )

    def get_bollinger_bands(
        self,
        ticker: str,
        df: pd.DataFrame
    ) -> BollingerBands:
        """
        Calculate Bollinger Bands and interpret price position.

        Args:
            ticker: Stock ticker
            df: DataFrame with OHLCV data

        Returns:
            BollingerBands model with band values and position interpretation
        """
        try:
            prices = df['Close']
            current_price = float(prices.iloc[-1])

            upper_series, middle_series, lower_series = calculate_bollinger_bands(prices)

            # Get latest values
            upper_band = float(upper_series.iloc[-1]) if not pd.isna(upper_series.iloc[-1]) else None
            middle_band = float(middle_series.iloc[-1]) if not pd.isna(middle_series.iloc[-1]) else None
            lower_band = float(lower_series.iloc[-1]) if not pd.isna(lower_series.iloc[-1]) else None

            # Calculate bandwidth
            bandwidth = None
            if upper_band is not None and lower_band is not None and middle_band is not None and middle_band > 0:
                bandwidth = (upper_band - lower_band) / middle_band

            # Determine position
            position = BollingerPosition.MIDDLE
            interpretation = ""

            if upper_band is not None and lower_band is not None:
                band_range = upper_band - lower_band
                threshold = band_range * 0.1  # 10% of band range

                if current_price > upper_band:
                    position = BollingerPosition.ABOVE_UPPER
                    interpretation = f"Price (${current_price:.2f}) above upper band (${upper_band:.2f}) - potentially overbought"
                elif current_price > (upper_band - threshold):
                    position = BollingerPosition.NEAR_UPPER
                    interpretation = f"Price (${current_price:.2f}) near upper band (${upper_band:.2f}) - approaching overbought"
                elif current_price < lower_band:
                    position = BollingerPosition.BELOW_LOWER
                    interpretation = f"Price (${current_price:.2f}) below lower band (${lower_band:.2f}) - potentially oversold"
                elif current_price < (lower_band + threshold):
                    position = BollingerPosition.NEAR_LOWER
                    interpretation = f"Price (${current_price:.2f}) near lower band (${lower_band:.2f}) - approaching oversold"
                else:
                    position = BollingerPosition.MIDDLE
                    interpretation = f"Price (${current_price:.2f}) in middle range - normal volatility"

                if bandwidth is not None:
                    if bandwidth > 0.2:
                        interpretation += f" | High volatility (bandwidth: {bandwidth:.2%})"
                    elif bandwidth < 0.1:
                        interpretation += f" | Low volatility (bandwidth: {bandwidth:.2%}) - potential breakout setup"
            else:
                interpretation = "Insufficient data to calculate Bollinger Bands"

            return BollingerBands(
                upper_band=upper_band,
                middle_band=middle_band,
                lower_band=lower_band,
                current_price=current_price,
                position=position,
                bandwidth=bandwidth,
                interpretation=interpretation,
            )

        except Exception as e:
            logger.error(f"Error calculating Bollinger Bands for {ticker}: {e}")
            return BollingerBands(
                current_price=float(df['Close'].iloc[-1]) if not df.empty else None,
                position=BollingerPosition.MIDDLE,
                interpretation=f"Error calculating Bollinger Bands: {str(e)}",
            )

    def get_stochastic(
        self,
        ticker: str,
        df: pd.DataFrame
    ) -> StochasticData:
        """
        Calculate Stochastic Oscillator and interpret signals.

        Args:
            ticker: Stock ticker
            df: DataFrame with OHLCV data

        Returns:
            StochasticData model with %K, %D values and signal interpretation
        """
        try:
            k_series, d_series = calculate_stochastic(df)

            # Get latest values
            k_value = float(k_series.iloc[-1]) if not pd.isna(k_series.iloc[-1]) else None
            d_value = float(d_series.iloc[-1]) if not pd.isna(d_series.iloc[-1]) else None

            # Determine signal
            if k_value is None:
                stochastic_signal = StochasticSignal.NEUTRAL
                interpretation = "Insufficient data to calculate Stochastic"
            elif k_value < 20:
                stochastic_signal = StochasticSignal.OVERSOLD
                interpretation = f"Stochastic %K ({k_value:.1f}) in oversold territory (<20) - potential bullish reversal"
            elif k_value > 80:
                stochastic_signal = StochasticSignal.OVERBOUGHT
                interpretation = f"Stochastic %K ({k_value:.1f}) in overbought territory (>80) - potential bearish reversal"
            else:
                stochastic_signal = StochasticSignal.NEUTRAL
                interpretation = f"Stochastic %K ({k_value:.1f}) in neutral range"

            # Add %D crossover information
            if k_value is not None and d_value is not None:
                if k_value > d_value:
                    interpretation += f" | %K above %D ({d_value:.1f}) - bullish"
                elif k_value < d_value:
                    interpretation += f" | %K below %D ({d_value:.1f}) - bearish"

            return StochasticData(
                k_value=k_value,
                d_value=d_value,
                stochastic_signal=stochastic_signal,
                interpretation=interpretation,
            )

        except Exception as e:
            logger.error(f"Error calculating Stochastic for {ticker}: {e}")
            return StochasticData(
                stochastic_signal=StochasticSignal.NEUTRAL,
                interpretation=f"Error calculating Stochastic: {str(e)}",
            )

    def get_volume_profile(
        self,
        ticker: str,
        df: pd.DataFrame
    ) -> VolumeProfile:
        """
        Calculate Volume Profile (price levels with highest volume).

        Args:
            ticker: Stock ticker
            df: DataFrame with OHLCV data

        Returns:
            VolumeProfile model with key price levels and POC
        """
        try:
            # Use last 60 days for volume profile
            lookback = min(60, len(df))
            recent_df = df.tail(lookback).copy()
            current_price = float(df['Close'].iloc[-1])

            # Create price bins (use 20 bins)
            num_bins = 20
            price_min = recent_df['Low'].min()
            price_max = recent_df['High'].max()
            price_bins = np.linspace(price_min, price_max, num_bins + 1)

            # Assign volume to price bins
            volume_by_price = np.zeros(num_bins)

            for _, row in recent_df.iterrows():
                # Distribute volume across bins touched by this bar
                low_idx = np.searchsorted(price_bins, row['Low'], side='right') - 1
                high_idx = np.searchsorted(price_bins, row['High'], side='left')

                # Distribute volume evenly across touched bins
                bins_touched = max(1, high_idx - low_idx)
                volume_per_bin = row['Volume'] / bins_touched

                for i in range(low_idx, high_idx):
                    if 0 <= i < num_bins:
                        volume_by_price[i] += volume_per_bin

            # Normalize volume
            total_volume = volume_by_price.sum()
            if total_volume > 0:
                volume_concentration = volume_by_price / total_volume
            else:
                volume_concentration = volume_by_price

            # Find POC (Point of Control - price level with most volume)
            poc_idx = np.argmax(volume_by_price)
            poc = (price_bins[poc_idx] + price_bins[poc_idx + 1]) / 2

            # Find Value Area (70% of volume)
            sorted_indices = np.argsort(volume_by_price)[::-1]
            cumulative_volume = 0
            value_area_indices = []

            for idx in sorted_indices:
                value_area_indices.append(idx)
                cumulative_volume += volume_concentration[idx]
                if cumulative_volume >= 0.70:
                    break

            value_area_low = (price_bins[min(value_area_indices)] + price_bins[min(value_area_indices) + 1]) / 2
            value_area_high = (price_bins[max(value_area_indices)] + price_bins[max(value_area_indices) + 1]) / 2

            # Get top 5 price levels by volume
            top_indices = sorted_indices[:5]
            key_levels = []

            for idx in top_indices:
                price_level = (price_bins[idx] + price_bins[idx + 1]) / 2
                support_resistance = "support" if price_level < current_price else "resistance"

                key_levels.append(VolumePriceLevel(
                    price_level=float(price_level),
                    volume_concentration=float(volume_concentration[idx]),
                    support_resistance=support_resistance
                ))

            # Generate interpretation
            interpretation = f"POC at ${poc:.2f}, Value Area: ${value_area_low:.2f} - ${value_area_high:.2f}"

            if current_price > value_area_high:
                interpretation += " | Price above value area (bullish position)"
            elif current_price < value_area_low:
                interpretation += " | Price below value area (bearish position)"
            else:
                interpretation += " | Price within value area (balanced)"

            return VolumeProfile(
                key_levels=key_levels,
                poc=float(poc),
                value_area_high=float(value_area_high),
                value_area_low=float(value_area_low),
                interpretation=interpretation,
            )

        except Exception as e:
            logger.error(f"Error calculating Volume Profile for {ticker}: {e}")
            return VolumeProfile(
                key_levels=[],
                interpretation=f"Error calculating Volume Profile: {str(e)}",
            )

    def get_entry_exit_signals(
        self,
        ticker: str,
        df: pd.DataFrame,
        ma: MovingAverages,
        rsi: RSIData,
        macd: MACDData,
        bollinger: BollingerBands,
        stochastic: StochasticData,
        volume_profile: VolumeProfile
    ) -> EntryExitSignals:
        """
        Generate aggregated entry/exit signals from all indicators.

        Args:
            ticker: Stock ticker
            df: DataFrame with OHLCV data
            ma: Moving averages data
            rsi: RSI data
            macd: MACD data
            bollinger: Bollinger Bands data
            stochastic: Stochastic data
            volume_profile: Volume profile data

        Returns:
            EntryExitSignals model with overall signal and key levels
        """
        try:
            current_price = float(df['Close'].iloc[-1])
            bullish_factors = []
            bearish_factors = []

            # Analyze Moving Averages
            if ma.current_price and ma.sma_50 and ma.sma_200:
                if ma.current_price > ma.sma_50 > ma.sma_200:
                    bullish_factors.append("Price above SMA50 and SMA200 (strong uptrend)")
                elif ma.current_price < ma.sma_50 < ma.sma_200:
                    bearish_factors.append("Price below SMA50 and SMA200 (strong downtrend)")

            if ma.crossover_signal == CrossoverSignal.GOLDEN_CROSS:
                bullish_factors.append(f"Golden cross {ma.days_since_crossover} days ago")
            elif ma.crossover_signal == CrossoverSignal.DEATH_CROSS:
                bearish_factors.append(f"Death cross {ma.days_since_crossover} days ago")

            # Analyze RSI
            if rsi.rsi_signal == RSISignal.OVERSOLD:
                bullish_factors.append(f"RSI oversold ({rsi.rsi_14:.1f})")
            elif rsi.rsi_signal == RSISignal.OVERBOUGHT:
                bearish_factors.append(f"RSI overbought ({rsi.rsi_14:.1f})")

            # Analyze MACD
            if macd.macd_signal == MACDSignal.BULLISH:
                bullish_factors.append("MACD bullish (above signal line)")
            elif macd.macd_signal == MACDSignal.BEARISH:
                bearish_factors.append("MACD bearish (below signal line)")

            # Analyze Bollinger Bands
            if bollinger.position == BollingerPosition.BELOW_LOWER:
                bullish_factors.append("Price below lower Bollinger Band (oversold)")
            elif bollinger.position == BollingerPosition.ABOVE_UPPER:
                bearish_factors.append("Price above upper Bollinger Band (overbought)")

            # Analyze Stochastic
            if stochastic.stochastic_signal == StochasticSignal.OVERSOLD:
                bullish_factors.append(f"Stochastic oversold ({stochastic.k_value:.1f})")
            elif stochastic.stochastic_signal == StochasticSignal.OVERBOUGHT:
                bearish_factors.append(f"Stochastic overbought ({stochastic.k_value:.1f})")

            # Calculate overall signal
            bullish_count = len(bullish_factors)
            bearish_count = len(bearish_factors)
            total_signals = bullish_count + bearish_count

            if total_signals == 0:
                overall_signal = TradingSignal.NEUTRAL
                confidence = 0.5
            else:
                bullish_ratio = bullish_count / total_signals
                bearish_ratio = bearish_count / total_signals

                if bullish_ratio >= 0.7:
                    overall_signal = TradingSignal.STRONG_BUY
                    confidence = bullish_ratio
                elif bullish_ratio >= 0.55:
                    overall_signal = TradingSignal.BUY
                    confidence = bullish_ratio
                elif bearish_ratio >= 0.7:
                    overall_signal = TradingSignal.STRONG_SELL
                    confidence = bearish_ratio
                elif bearish_ratio >= 0.55:
                    overall_signal = TradingSignal.SELL
                    confidence = bearish_ratio
                else:
                    overall_signal = TradingSignal.NEUTRAL
                    confidence = 0.5

            # Determine key levels
            key_levels = {}

            # Entry level (for buy signals)
            if overall_signal in [TradingSignal.BUY, TradingSignal.STRONG_BUY]:
                # Use lower Bollinger Band or recent support
                if bollinger.lower_band:
                    key_levels["entry"] = bollinger.lower_band
                else:
                    key_levels["entry"] = current_price * 0.98  # 2% below current

                # Stop loss below value area low
                if volume_profile.value_area_low:
                    key_levels["stop_loss"] = volume_profile.value_area_low * 0.98
                else:
                    key_levels["stop_loss"] = current_price * 0.95  # 5% stop

                # Take profit at upper band or resistance
                if bollinger.upper_band:
                    key_levels["take_profit"] = bollinger.upper_band
                else:
                    key_levels["take_profit"] = current_price * 1.10  # 10% target

            # Entry level (for sell signals)
            elif overall_signal in [TradingSignal.SELL, TradingSignal.STRONG_SELL]:
                # Use upper Bollinger Band or recent resistance
                if bollinger.upper_band:
                    key_levels["entry"] = bollinger.upper_band
                else:
                    key_levels["entry"] = current_price * 1.02  # 2% above current

                # Stop loss above value area high
                if volume_profile.value_area_high:
                    key_levels["stop_loss"] = volume_profile.value_area_high * 1.02
                else:
                    key_levels["stop_loss"] = current_price * 1.05  # 5% stop

                # Take profit at lower band or support
                if bollinger.lower_band:
                    key_levels["take_profit"] = bollinger.lower_band
                else:
                    key_levels["take_profit"] = current_price * 0.90  # 10% target

            else:
                key_levels["entry"] = None
                key_levels["stop_loss"] = None
                key_levels["take_profit"] = None

            # Generate interpretation
            interpretation = f"{overall_signal.value.upper()} signal (confidence: {confidence:.0%})"

            if bullish_factors:
                interpretation += f"\n\nBullish factors ({bullish_count}):\n" + "\n".join([f"• {f}" for f in bullish_factors])

            if bearish_factors:
                interpretation += f"\n\nBearish factors ({bearish_count}):\n" + "\n".join([f"• {f}" for f in bearish_factors])

            if key_levels.get("entry"):
                interpretation += f"\n\nKey levels: Entry ${key_levels['entry']:.2f}, Stop ${key_levels['stop_loss']:.2f}, Target ${key_levels['take_profit']:.2f}"

            return EntryExitSignals(
                overall_signal=overall_signal,
                confidence=confidence,
                bullish_factors=bullish_factors,
                bearish_factors=bearish_factors,
                key_levels=key_levels,
                interpretation=interpretation,
            )

        except Exception as e:
            logger.error(f"Error generating entry/exit signals for {ticker}: {e}")
            return EntryExitSignals(
                overall_signal=TradingSignal.NEUTRAL,
                confidence=0.5,
                bullish_factors=[],
                bearish_factors=[],
                key_levels={},
                interpretation=f"Error generating signals: {str(e)}",
            )

    # ========================================================================
    # DIVERGENCE DETECTION METHODS (NEW)
    # ========================================================================

    def _find_local_minima(self, series: pd.Series, window: int = 5) -> list:
        """
        Find indices where value is minimum within window.

        Args:
            series: Price or indicator series
            window: Window size for local minimum detection

        Returns:
            List of indices where local minima occur
        """
        minima = []
        for i in range(window, len(series) - window):
            if series.iloc[i] == series.iloc[i-window:i+window+1].min():
                minima.append(i)
        return minima

    def _find_local_maxima(self, series: pd.Series, window: int = 5) -> list:
        """
        Find indices where value is maximum within window.

        Args:
            series: Price or indicator series
            window: Window size for local maximum detection

        Returns:
            List of indices where local maxima occur
        """
        maxima = []
        for i in range(window, len(series) - window):
            if series.iloc[i] == series.iloc[i-window:i+window+1].max():
                maxima.append(i)
        return maxima

    def _calculate_divergence_strength(
        self,
        val1_m1: float,
        val2_m1: float,
        val1_m2: float,
        val2_m2: float
    ) -> float:
        """
        Calculate divergence strength from % change mismatch.

        Args:
            val1_m1, val2_m1: Most recent values (price, indicator)
            val1_m2, val2_m2: Previous comparison values

        Returns:
            Strength (0-1), where 1.0 = maximum divergence (50%+ mismatch)
        """
        if val1_m2 == 0 or val2_m2 == 0:
            return 0.0

        pct_change_1 = (val1_m1 - val1_m2) / abs(val1_m2)
        pct_change_2 = (val2_m1 - val2_m2) / abs(val2_m2)
        divergence_gap = abs(pct_change_1 - pct_change_2)
        strength = min(1.0, divergence_gap / 0.5)  # 50% gap = max strength
        return strength

    def detect_rsi_divergence(
        self,
        df: pd.DataFrame,
        lookback_days: int = 60
    ) -> tuple:
        """
        Detect RSI divergence over lookback period.

        Bullish Divergence: Price makes lower low, RSI makes higher low (oversold bounce setup)
        Bearish Divergence: Price makes higher high, RSI makes lower high (overbought reversal)

        Args:
            df: DataFrame with OHLCV data
            lookback_days: Days to look back (default 60)

        Returns:
            Tuple of (divergence_type, pattern_description, strength)
        """
        from research_swarm.agents.quant.models import DivergenceType

        try:
            # Calculate RSI
            rsi = calculate_rsi(df['Close'])

            # Focus on recent period
            recent_df = df.tail(lookback_days)
            recent_rsi = rsi.tail(lookback_days)

            # Find local minima and maxima
            price_lows_idx = self._find_local_minima(recent_df['Close'].reset_index(drop=True))
            price_highs_idx = self._find_local_maxima(recent_df['Close'].reset_index(drop=True))

            # Reset index for consistent indexing
            recent_close = recent_df['Close'].reset_index(drop=True)
            recent_rsi_reset = recent_rsi.reset_index(drop=True)

            # Check for bullish divergence (need at least 2 lows)
            if len(price_lows_idx) >= 2:
                latest_low_idx = price_lows_idx[-1]
                prev_low_idx = price_lows_idx[-2]

                latest_price_low = recent_close.iloc[latest_low_idx]
                prev_price_low = recent_close.iloc[prev_low_idx]
                latest_rsi_low = recent_rsi_reset.iloc[latest_low_idx]
                prev_rsi_low = recent_rsi_reset.iloc[prev_low_idx]

                if latest_price_low < prev_price_low and latest_rsi_low > prev_rsi_low:
                    # Bullish divergence detected
                    strength = self._calculate_divergence_strength(
                        latest_price_low, latest_rsi_low, prev_price_low, prev_rsi_low
                    )
                    pattern = f"Price lower low at ${latest_price_low:.2f}, RSI higher low at {latest_rsi_low:.1f}"
                    return DivergenceType.BULLISH, pattern, strength

            # Check for bearish divergence (need at least 2 highs)
            if len(price_highs_idx) >= 2:
                latest_high_idx = price_highs_idx[-1]
                prev_high_idx = price_highs_idx[-2]

                latest_price_high = recent_close.iloc[latest_high_idx]
                prev_price_high = recent_close.iloc[prev_high_idx]
                latest_rsi_high = recent_rsi_reset.iloc[latest_high_idx]
                prev_rsi_high = recent_rsi_reset.iloc[prev_high_idx]

                if latest_price_high > prev_price_high and latest_rsi_high < prev_rsi_high:
                    # Bearish divergence detected
                    strength = self._calculate_divergence_strength(
                        latest_price_high, latest_rsi_high, prev_price_high, prev_rsi_high
                    )
                    pattern = f"Price higher high at ${latest_price_high:.2f}, RSI lower high at {latest_rsi_high:.1f}"
                    return DivergenceType.BEARISH, pattern, strength

            return DivergenceType.NONE, "No divergence detected", 0.0

        except Exception as e:
            logger.error(f"Error detecting RSI divergence: {e}")
            return DivergenceType.NONE, f"Error: {str(e)}", 0.0

    def detect_macd_divergence(
        self,
        df: pd.DataFrame,
        lookback_days: int = 60
    ) -> tuple:
        """
        Detect MACD histogram divergence.

        Bullish: Price declining, histogram rising (momentum improving)
        Bearish: Price rising, histogram falling (momentum weakening)

        Args:
            df: DataFrame with OHLCV data
            lookback_days: Days to look back (default 60)

        Returns:
            Tuple of (divergence_type, pattern_description, strength)
        """
        from research_swarm.agents.quant.models import DivergenceType

        try:
            # Calculate MACD
            macd_line, signal_line, histogram = calculate_macd(df['Close'])

            # Focus on recent period
            recent_df = df.tail(lookback_days)
            recent_histogram = histogram.tail(lookback_days)

            # Calculate price and histogram trends
            price_trend = (recent_df['Close'].iloc[-1] - recent_df['Close'].iloc[0]) / recent_df['Close'].iloc[0]

            # Handle zero histogram values
            if abs(recent_histogram.iloc[0]) < 0.001:
                return DivergenceType.NONE, "No divergence detected", 0.0

            histogram_trend = (recent_histogram.iloc[-1] - recent_histogram.iloc[0]) / abs(recent_histogram.iloc[0])

            # Divergence if trends opposite (threshold: 5% trend)
            if price_trend < -0.05 and histogram_trend > 0.05:
                # Bullish divergence
                strength = min(1.0, abs(price_trend - histogram_trend) / 0.2)
                pattern = f"Price declined {price_trend*100:.1f}%, MACD histogram improving"
                return DivergenceType.BULLISH, pattern, strength
            elif price_trend > 0.05 and histogram_trend < -0.05:
                # Bearish divergence
                strength = min(1.0, abs(price_trend - histogram_trend) / 0.2)
                pattern = f"Price rose {price_trend*100:.1f}%, MACD histogram weakening"
                return DivergenceType.BEARISH, pattern, strength

            return DivergenceType.NONE, "No divergence detected", 0.0

        except Exception as e:
            logger.error(f"Error detecting MACD divergence: {e}")
            return DivergenceType.NONE, f"Error: {str(e)}", 0.0

    def detect_volume_divergence(
        self,
        df: pd.DataFrame,
        lookback_days: int = 60
    ) -> tuple:
        """
        Detect volume divergence.

        Bearish: Price rising on declining volume (weak rally)
        Bullish: Price falling on declining volume (weak selloff)

        Args:
            df: DataFrame with OHLCV data
            lookback_days: Days to look back (default 60)

        Returns:
            Tuple of (divergence_type, pattern_description, strength)
        """
        from research_swarm.agents.quant.models import DivergenceType

        try:
            recent_df = df.tail(lookback_days)

            # Calculate 20-day volume moving average trend
            volume_ma = recent_df['Volume'].rolling(window=20).mean()
            price_trend = (recent_df['Close'].iloc[-1] - recent_df['Close'].iloc[0]) / recent_df['Close'].iloc[0]

            # Handle NaN or zero volume
            if volume_ma.iloc[0] == 0 or pd.isna(volume_ma.iloc[0]):
                return DivergenceType.NONE, "No divergence detected", 0.0

            volume_trend = (volume_ma.iloc[-1] - volume_ma.iloc[0]) / volume_ma.iloc[0]

            # Divergence if trends opposite (threshold: 5%)
            if price_trend > 0.05 and volume_trend < -0.05:
                # Bearish divergence (price up, volume down)
                strength = min(1.0, abs(price_trend - volume_trend) / 0.2)
                pattern = f"Price rose {price_trend*100:.1f}%, volume declined {volume_trend*100:.1f}%"
                return DivergenceType.BEARISH, pattern, strength
            elif price_trend < -0.05 and volume_trend < -0.05:
                # Bullish divergence (price down, volume down = weak selloff)
                strength = min(1.0, abs(volume_trend) / 0.2)
                pattern = f"Price fell {price_trend*100:.1f}%, volume declined {volume_trend*100:.1f}%"
                return DivergenceType.BULLISH, pattern, strength

            return DivergenceType.NONE, "No divergence detected", 0.0

        except Exception as e:
            logger.error(f"Error detecting volume divergence: {e}")
            return DivergenceType.NONE, f"Error: {str(e)}", 0.0

    def get_technical_divergence(
        self,
        ticker: str,
        df: pd.DataFrame,
        lookback_days: int = 60
    ):
        """
        Detect all technical divergences and generate overall score.

        Args:
            ticker: Stock ticker
            df: DataFrame with OHLCV data
            lookback_days: Days to look back (default 60)

        Returns:
            TechnicalDivergence model with all patterns + overall score
        """
        from research_swarm.agents.quant.models import (
            TechnicalDivergence,
            DivergencePattern,
            DivergenceType
        )

        try:
            # Detect all three types
            rsi_div, rsi_pattern, rsi_strength = self.detect_rsi_divergence(df, lookback_days)
            macd_div, macd_pattern, macd_strength = self.detect_macd_divergence(df, lookback_days)
            volume_div, volume_pattern, volume_strength = self.detect_volume_divergence(df, lookback_days)

            # Collect patterns
            patterns = []
            if rsi_div != DivergenceType.NONE:
                patterns.append(DivergencePattern(
                    indicator="RSI",
                    divergence_type=rsi_div,
                    description=rsi_pattern,
                    lookback_days=lookback_days,
                    strength=rsi_strength
                ))
            if macd_div != DivergenceType.NONE:
                patterns.append(DivergencePattern(
                    indicator="MACD",
                    divergence_type=macd_div,
                    description=macd_pattern,
                    lookback_days=lookback_days,
                    strength=macd_strength
                ))
            if volume_div != DivergenceType.NONE:
                patterns.append(DivergencePattern(
                    indicator="Volume",
                    divergence_type=volume_div,
                    description=volume_pattern,
                    lookback_days=lookback_days,
                    strength=volume_strength
                ))

            # Calculate overall bias (bullish vs bearish count)
            bullish_count = sum(1 for p in patterns if p.divergence_type == DivergenceType.BULLISH)
            bearish_count = sum(1 for p in patterns if p.divergence_type == DivergenceType.BEARISH)

            if bullish_count > bearish_count:
                overall_bias = DivergenceType.BULLISH
                divergence_score = 7.0 + (bullish_count * 0.5)  # 7.0-8.5 range
            elif bearish_count > bullish_count:
                overall_bias = DivergenceType.BEARISH
                divergence_score = 3.0 - (bearish_count * 0.5)  # 1.5-3.0 range
            else:
                overall_bias = DivergenceType.NONE
                divergence_score = 5.0  # Neutral

            # Calculate confidence (more patterns = higher confidence)
            confidence = min(1.0, len(patterns) * 0.33)  # Max confidence at 3 patterns

            # Generate interpretation
            if overall_bias == DivergenceType.BULLISH:
                bullish_indicators = ', '.join(p.indicator for p in patterns if p.divergence_type == DivergenceType.BULLISH)
                interpretation = f"Bullish divergence detected ({bullish_count} indicator(s)): {bullish_indicators}. Bottom likely forming."
            elif overall_bias == DivergenceType.BEARISH:
                bearish_indicators = ', '.join(p.indicator for p in patterns if p.divergence_type == DivergenceType.BEARISH)
                interpretation = f"Bearish divergence detected ({bearish_count} indicator(s)): {bearish_indicators}. Top likely forming."
            else:
                interpretation = "No significant technical divergences detected. Price and momentum aligned."

            return TechnicalDivergence(
                rsi_divergence=rsi_div,
                rsi_pattern=rsi_pattern,
                rsi_strength=rsi_strength,
                macd_divergence=macd_div,
                macd_pattern=macd_pattern,
                macd_strength=macd_strength,
                volume_divergence=volume_div,
                volume_pattern=volume_pattern,
                volume_strength=volume_strength,
                patterns=patterns,
                has_divergence=len(patterns) > 0,
                overall_bias=overall_bias,
                divergence_score=divergence_score,
                confidence=confidence,
                interpretation=interpretation
            )

        except Exception as e:
            logger.error(f"Error calculating technical divergence for {ticker}: {e}")
            # Return neutral divergence on error
            return TechnicalDivergence(
                rsi_divergence=DivergenceType.NONE,
                rsi_pattern="Error calculating",
                rsi_strength=0.0,
                macd_divergence=DivergenceType.NONE,
                macd_pattern="Error calculating",
                macd_strength=0.0,
                volume_divergence=DivergenceType.NONE,
                volume_pattern="Error calculating",
                volume_strength=0.0,
                patterns=[],
                has_divergence=False,
                overall_bias=DivergenceType.NONE,
                divergence_score=5.0,
                confidence=0.0,
                interpretation=f"Error calculating divergence: {str(e)}"
            )

    def analyze_ticker(
        self,
        ticker: str,
        period: str = "1y"
    ) -> TechnicalIndicators:
        """
        Perform full technical analysis on a ticker.

        Args:
            ticker: Stock ticker symbol
            period: Data period (default "1y" for 1 year)

        Returns:
            TechnicalIndicators model with all indicators
        """
        logger.info(f"Performing technical analysis for {ticker}")

        # Fetch historical data
        df = self.client.get_historical_data(ticker, period=period)

        if df.empty:
            logger.error(f"No data available for {ticker}")
            raise ValueError(f"No historical data available for {ticker}")

        # Calculate all indicators
        moving_averages = self.get_moving_averages(ticker, df)
        rsi = self.get_rsi(ticker, df)
        volume = self.get_volume_analysis(ticker, df)
        relative_strength = self.get_relative_strength(ticker, df)
        macd = self.get_macd(ticker, df)
        bollinger_bands = self.get_bollinger_bands(ticker, df)
        stochastic = self.get_stochastic(ticker, df)
        volume_profile = self.get_volume_profile(ticker, df)

        # Generate entry/exit signals (aggregates all indicators)
        entry_exit_signals = self.get_entry_exit_signals(
            ticker, df, moving_averages, rsi, macd,
            bollinger_bands, stochastic, volume_profile
        )

        # NEW: Detect technical divergences (RSI/MACD/Volume)
        technical_divergence = self.get_technical_divergence(ticker, df, lookback_days=60)

        return TechnicalIndicators(
            ticker=ticker,
            moving_averages=moving_averages,
            rsi=rsi,
            volume=volume,
            relative_strength=relative_strength,
            macd=macd,
            bollinger_bands=bollinger_bands,
            stochastic=stochastic,
            volume_profile=volume_profile,
            entry_exit_signals=entry_exit_signals,
            technical_divergence=technical_divergence,  # NEW
        )
