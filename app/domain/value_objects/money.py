"""Money and token usage value objects."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal


@dataclass(frozen=True, slots=True)
class Money:
    """Immutable money value in micro-units (1/1,000,000)."""

    micro_units: int

    def __post_init__(self) -> None:
        if not isinstance(self.micro_units, int):
            raise TypeError("micro_units must be an integer")
        if self.micro_units < 0:
            raise ValueError("micro_units cannot be negative")

    @classmethod
    def from_decimal(cls, amount: Decimal) -> Money:
        """Create Money from Decimal dollars."""
        micro = int((amount * Decimal("1_000_000")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        return cls(micro)

    @classmethod
    def from_float(cls, amount: float) -> Money:
        """Create Money from float dollars (approximate)."""
        return cls.from_decimal(Decimal(str(amount)))

    def to_decimal(self) -> Decimal:
        """Convert to Decimal dollars."""
        return Decimal(self.micro_units) / Decimal("1_000_000")

    def __add__(self, other: Money) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        return Money(self.micro_units + other.micro_units)

    def __sub__(self, other: Money) -> Money:
        if not isinstance(other, Money):
            return NotImplemented
        result = self.micro_units - other.micro_units
        if result < 0:
            raise ValueError("Result would be negative")
        return Money(result)

    def __mul__(self, factor: int) -> Money:
        if not isinstance(factor, int):
            return NotImplemented
        return Money(self.micro_units * factor)

    def __lt__(self, other: Money) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        return self.micro_units < other.micro_units

    def __le__(self, other: Money) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        return self.micro_units <= other.micro_units

    def __str__(self) -> str:
        return f"${self.to_decimal():.6f}"


@dataclass(frozen=True, slots=True)
class TokenUsage:
    """Immutable token usage record."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

    def __post_init__(self) -> None:
        if self.prompt_tokens < 0 or self.completion_tokens < 0:
            raise ValueError("Token counts cannot be negative")
        if self.total_tokens != self.prompt_tokens + self.completion_tokens:
            raise ValueError("total_tokens must equal prompt + completion")

    def __add__(self, other: TokenUsage) -> TokenUsage:
        if not isinstance(other, TokenUsage):
            return NotImplemented
        return TokenUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
        )
