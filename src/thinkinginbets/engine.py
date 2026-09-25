"""Trading loop orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field

from thinkinginbets.domain import (
    MarketSnapshot,
    ModelProbability,
    Order,
    OrderStatus,
    RejectedIntent,
)
from thinkinginbets.paper import PaperBroker
from thinkinginbets.risk import RiskManager
from thinkinginbets.strategy import ValueStrategy


@dataclass
class TickReport:
    accepted_orders: list[Order] = field(default_factory=list)
    rejected_intents: list[RejectedIntent] = field(default_factory=list)
    filled_orders: list[Order] = field(default_factory=list)


@dataclass
class TradingEngine:
    strategy: ValueStrategy
    risk_manager: RiskManager
    broker: PaperBroker

    def on_tick(
        self,
        snapshot: MarketSnapshot,
        probabilities: list[ModelProbability],
    ) -> TickReport:
        report = TickReport()
        intents = self.strategy.propose(
            snapshot=snapshot,
            probabilities=probabilities,
            portfolio=self.broker.portfolio,
        )

        for intent in intents:
            rejection = self.risk_manager.review(self.broker.portfolio, intent)
            if rejection is not None:
                report.rejected_intents.append(rejection)
                continue

            order = Order(intent=intent, status=OrderStatus.ACCEPTED)
            report.accepted_orders.append(order)
            fill = self.broker.submit(order, snapshot)
            if fill is not None:
                report.filled_orders.append(order)

        return report
