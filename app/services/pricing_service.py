from __future__ import annotations


class PricingService:
    def __init__(self, price_per_template: float) -> None:
        self._price_per_template = max(0.01, float(price_per_template))

    @property
    def price_per_template(self) -> float:
        return self._price_per_template

    def calculate_templates_price(self, templates_count: int) -> float:
        safe_count = max(0, templates_count)
        return round(safe_count * self._price_per_template, 2)

    def estimate_creatable(self, balance: float) -> int:
        if balance <= 0:
            return 0
        return int(balance // self._price_per_template)

    @staticmethod
    def format_price(value: float) -> str:
        return f"{value:.2f}"

