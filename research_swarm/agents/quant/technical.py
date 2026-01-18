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

            return VolumeAnalysis(
                avg_volume_20d=avg_volume_20d,
                current_volume=current_volume,
                volume_ratio=volume_ratio,
                volume_trend=volume_trend,
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

        return TechnicalIndicators(
            ticker=ticker,
            moving_averages=moving_averages,
            rsi=rsi,
            volume=volume,
            relative_strength=relative_strength,
        )
