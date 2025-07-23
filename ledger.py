from collections import deque, defaultdict
from decimal import Decimal
from typing import Any, Dict, List


class Party:
    __slots__ = ("tx_id", "current_amount", "original_amount", "original_currency")

    def __init__(
        self,
        tx_id: Any,
        current_amount: Decimal,
        original_amount: Decimal,
        original_currency: str,
    ):
        self.tx_id = tx_id
        self.current_amount = current_amount
        self.original_amount = original_amount
        self.original_currency = original_currency


class Ledger:
    def __init__(self):
        self.ledger = defaultdict(deque)
        self.total_deposited = defaultdict(Decimal)

    def deposit(self, amount: Decimal, currency: str, tx_id: Any, fee: Decimal):
        """Пополнение кошелька с учетом комиссии"""
        net_amount = amount - fee
        if net_amount < Decimal("0"):
            net_amount = Decimal("0")

        party = Party(tx_id, net_amount, amount, currency)
        self.ledger[currency].append(party)
        self.total_deposited[currency] += amount

    def _spend_funds(self, currency: str, total_amount: Decimal, fee: Decimal):
        """Внутренний метод для списания средств с пропорциональным распределением комиссии"""
        if self.balance().get(currency, Decimal("0")) < total_amount + fee:
            raise ValueError(f"Insufficient funds in {currency}")

        remaining_amount = total_amount
        remaining_fee = fee
        sources = []

        while remaining_amount + remaining_fee > Decimal("0"):
            if not self.ledger[currency]:
                break

            party = self.ledger[currency][0]
            available = party.current_amount

            # Рассчитываем пропорции для текущей партии
            if remaining_amount + remaining_fee <= available:
                # Достаточно текущей партии
                total_to_take = remaining_amount + remaining_fee

                # Пропорциональное распределение
                if total_to_take > Decimal("0"):
                    ratio = remaining_amount / total_to_take
                    amount_taken = remaining_amount
                    fee_taken = remaining_fee
                else:
                    amount_taken = Decimal("0")
                    fee_taken = Decimal("0")

                party.current_amount -= total_to_take
                remaining_amount = Decimal("0")
                remaining_fee = Decimal("0")
            else:
                # Берем всю текущую партию
                total_to_take = available

                # Пропорциональное распределение
                if total_to_take > Decimal("0"):
                    ratio = remaining_amount / (remaining_amount + remaining_fee)
                    amount_taken = ratio * total_to_take
                    fee_taken = total_to_take - amount_taken
                else:
                    amount_taken = Decimal("0")
                    fee_taken = Decimal("0")

                remaining_amount -= amount_taken
                remaining_fee -= fee_taken
                party.current_amount = Decimal("0")
            # Сохраняем информацию о списании
            if total_to_take > Decimal("0"):
                original_used = (
                    party.original_amount * (total_to_take / available)
                    if available > 0
                    else Decimal("0")
                )

                sources.append(
                    {
                        "tx_id": party.tx_id,
                        "amount_taken": amount_taken,
                        "fee_taken": fee_taken,
                        "original_used": original_used,
                        "original_currency": party.original_currency,
                    }
                )
                party.original_amount -= original_used

            # Удаляем исчерпанную партию
            if party.current_amount <= Decimal("0"):
                self.ledger[currency].popleft()
        return sources

    def convert(
        self,
        amount_from: Decimal,
        currency_from: str,
        amount_to: Decimal,
        currency_to: str,
        fee: Decimal,
    ):
        """Конвертация средств между валютами с учетом комиссии"""
        sources = self._spend_funds(currency_from, amount_from, fee)

        # Создаем новые партии в целевой валюте
        if currency_to not in self.ledger:
            self.ledger[currency_to] = deque()

        for source in sources:
            if source["amount_taken"] > Decimal("0"):
                ratio = (
                    source["amount_taken"] / amount_from
                    if amount_from > 0
                    else Decimal("0")
                )
                converted_amount = ratio * amount_to

                new_party = Party(
                    tx_id=source["tx_id"],
                    current_amount=converted_amount,
                    original_amount=source["original_used"],
                    original_currency=source["original_currency"],
                )
                self.ledger[currency_to].append(new_party)

    def withdraw(self, amount: Decimal, currency: str, fee: Decimal) -> List[Dict]:
        """Снятие средств с возвратом информации об источниках"""
        sources = self._spend_funds(currency, amount, fee)

        result = []
        for source in sources:
            result.append(
                {
                    "tx_id": source["tx_id"],
                    "amount_withdrawn": round(source["amount_taken"], 6),
                    "original_amount": round(source["original_used"], 6),
                    "original_currency": source["original_currency"],
                }
            )

        return result

    def balance(self) -> Dict[str, Decimal]:
        """Возвращает баланс по всем валютам с округлением"""
        balances = {}
        for currency, queue in self.ledger.items():
            total = sum(party.current_amount for party in queue)
            balances[currency] = round(total, 6)
        return balances
