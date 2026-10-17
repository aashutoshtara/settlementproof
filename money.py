"""Exact, explicitly supported money conversion. No floating point amounts."""
from decimal import Decimal, InvalidOperation
import re

EXPONENT = {"USD": 2, "EUR": 2, "GBP": 2, "JPY": 0}

def minor(value, currency):
    if currency not in EXPONENT:
        raise ValueError(f"Unsupported currency: {currency}")
    if not isinstance(value, str):
        raise ValueError("Money must be supplied as a decimal string")
    if len(value) > 24 or not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", value):
        raise ValueError("Amount must be a plain decimal string of at most 24 characters")
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError("Invalid amount") from exc
    if not number.is_finite() or number < 0:
        raise ValueError("Amount must be finite and nonnegative")
    scaled = number * (10 ** EXPONENT[currency])
    if scaled != scaled.to_integral_value():
        raise ValueError("Amount exceeds currency precision")
    if scaled > 10**15:
        raise ValueError("Amount too large")
    return int(scaled)

def display(value, currency):
    return f"{Decimal(value) / (10 ** EXPONENT[currency]):.{EXPONENT[currency]}f}"
