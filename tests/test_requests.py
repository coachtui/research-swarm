"""Tests for API request schemas."""
import pytest
from pydantic import ValidationError
from api.models.requests import AnalyzeRequest, BatchAnalyzeRequest


def test_hyphenated_ticker_accepted():
    req = AnalyzeRequest(ticker="BRK-B")
    assert req.ticker == "BRK-B"


def test_dotted_ticker_still_accepted():
    req = AnalyzeRequest(ticker="BRK.B")
    assert req.ticker == "BRK.B"


def test_simple_ticker_accepted():
    req = AnalyzeRequest(ticker="aapl")
    assert req.ticker == "AAPL"  # uppercased


def test_invalid_ticker_double_separator_rejected():
    with pytest.raises(ValidationError):
        AnalyzeRequest(ticker="BRK--B")


def test_invalid_ticker_too_many_letters_rejected():
    with pytest.raises(ValidationError):
        AnalyzeRequest(ticker="TOOLONG")


def test_batch_hyphenated_ticker_accepted():
    req = BatchAnalyzeRequest(tickers=["BRK-B", "AAPL"])
    assert "BRK-B" in req.tickers
