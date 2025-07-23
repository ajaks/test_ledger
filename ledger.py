import logging
from collections import deque, defaultdict
from decimal import Decimal
from typing import Any, Dict, List, Optional

# Настройка базового логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LedgerError(Exception):
    """Базовое исключение для ошибок кошелька."""
    pass


class InsufficientFundsError(LedgerError):
    """Ошибка недостатка средств."""
    pass


class InvalidOperationError(LedgerError):
    """Ошибка некорректной операции."""
    pass


class Party:
    """
    Описывает одну партию средств (депозит).
    """
    __slots__ = ("tx_id", "current_amount", "original_amount", "original_currency")

    def __init__(
            self,
            tx_id: Any,
            current_amount: Decimal,
            original_amount: Decimal,
            original_currency: str,
    ) -> None:
        self.tx_id = tx_id
        self.current_amount = current_amount
        self.original_amount = original_amount
        self.original_currency = original_currency


class Ledger:
    """
    Мультивалютный FIFO-кошелек с пропорциональным учетом комиссий и историей происхождения средств.
    """

    def __init__(self) -> None:
        self.ledger: Dict[str, deque[Party]] = defaultdict(deque)
        self.total_deposited: Dict[str, Decimal] = defaultdict(Decimal)

    def deposit(self, amount: Decimal, currency: str, tx_id: Any, fee: Decimal) -> None:
        """
        Пополнение кошелька с учетом комиссии.
        :param amount: Сумма пополнения (>=0)
        :param currency: Валюта (строка)
        :param tx_id: Идентификатор транзакции
        :param fee: Комиссия (>=0, не больше суммы)
        """
        if amount < 0:
            raise InvalidOperationError("Deposit amount must be non-negative.")
        if fee < 0:
            raise InvalidOperationError("Fee must be non-negative.")
        if amount < fee:
            raise InvalidOperationError("Fee cannot exceed deposit amount.")

        net_amount = amount - fee
        party = Party(tx_id, net_amount, amount, currency)
        self.ledger[currency].append(party)
        self.total_deposited[currency] += amount
        logger.info(f"Deposited {amount} {currency} (fee {fee}), tx_id={tx_id}")

    def _spend_funds(
            self, currency: str, total_amount: Decimal, fee: Decimal
    ) -> List[Dict[str, Any]]:
        """
        Внутренний метод списания средств с пропорциональным распределением комиссии.
        :param currency: Валюта списания
        :param total_amount: Сумма списания
        :param fee: Комиссия
        :return: Список источников списания
        """
        if total_amount < 0 or fee < 0:
            raise InvalidOperationError("Amount and fee must be non-negative.")
        available_balance = self.balance().get(currency, Decimal("0"))
        if available_balance < total_amount + fee:
            raise InsufficientFundsError(
                f"Insufficient funds in {currency} ({available_balance} < {total_amount + fee})")

        remaining_amount = total_amount
        remaining_fee = fee
        sources: List[Dict[str, Any]] = []

        while remaining_amount + remaining_fee > Decimal("0"):
            if not self.ledger[currency]:
                break

            party = self.ledger[currency][0]
            available = party.current_amount

            if remaining_amount + remaining_fee <= available:
                total_to_take = remaining_amount + remaining_fee
                ratio = (remaining_amount / total_to_take) if total_to_take > 0 else Decimal("0")
                amount_taken = ratio * total_to_take
                fee_taken = total_to_take - amount_taken
                party.current_amount -= total_to_take
                remaining_amount = Decimal("0")
                remaining_fee = Decimal("0")
            else:
                total_to_take = available
                ratio = (remaining_amount / (remaining_amount + remaining_fee)) if (
                                                                                           remaining_amount + remaining_fee) > 0 else Decimal(
                    "0")
                amount_taken = ratio * total_to_take
                fee_taken = total_to_take - amount_taken
                remaining_amount -= amount_taken
                remaining_fee -= fee_taken
                party.current_amount = Decimal("0")

            original_used = (
                party.original_amount * (total_to_take / available)
                if available > 0 else Decimal("0")
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

            if party.current_amount <= Decimal("0"):
                self.ledger[currency].popleft()

        logger.info(f"Spent {total_amount} {currency} (fee {fee}), sources used: {len(sources)}")
        return sources

    def withdraw(self, amount: Decimal, currency: str, fee: Decimal) -> List[Dict[str, Any]]:
        """
        Снятие средств с возвратом информации об источниках.
        :param amount: Снимаемая сумма
        :param currency: Валюта
        :param fee: Комиссия
        :return: Список источников списания
        """
        sources = self._spend_funds(currency, amount, fee)
        result = [
            {
                "tx_id": src["tx_id"],
                "amount_withdrawn": round(src["amount_taken"], 6),
                "original_amount": round(src["original_used"], 6),
                "original_currency": src["original_currency"],
            }
            for src in sources
        ]
        logger.info(f"Withdrawn {amount} {currency} (fee {fee})")
        return result

    def convert(
            self,
            amount_from: Decimal,
            currency_from: str,
            amount_to: Decimal,
            currency_to: str,
            fee: Decimal,
    ) -> None:
        """
        Конвертация средств между валютами с учетом комиссии.
        :param amount_from: Сумма списания
        :param currency_from: Валюта списания
        :param amount_to: Сумма зачисления
        :param currency_to: Валюта зачисления
        :param fee: Комиссия
        """
        sources = self._spend_funds(currency_from, amount_from, fee)

        if currency_to not in self.ledger:
            self.ledger[currency_to] = deque()

        for source in sources:
            if source["amount_taken"] > Decimal("0"):
                ratio = (
                    source["amount_taken"] / amount_from
                    if amount_from > 0 else Decimal("0")
                )
                converted_amount = ratio * amount_to
                new_party = Party(
                    tx_id=source["tx_id"],
                    current_amount=converted_amount,
                    original_amount=source["original_used"],
                    original_currency=source["original_currency"],
                )
                self.ledger[currency_to].append(new_party)
        logger.info(f"Converted {amount_from} {currency_from} → {amount_to} {currency_to} (fee {fee})")

    def balance(self) -> Dict[str, Decimal]:
        """
        Возвращает баланс по всем валютам с округлением.
        :return: Словарь {валюта: сумма}
        """
        return {currency: round(sum(party.current_amount for party in queue), 6)
                for currency, queue in self.ledger.items()}

    def get_history(self, currency: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Получить историю партий по валюте или по всем.
        :param currency: Валюта или None для всех
        :return: Список партий
        """
        result = []
        currencies = [currency] if currency else self.ledger.keys()
        for curr in currencies:
            for party in self.ledger[curr]:
                result.append({
                    "tx_id": party.tx_id,
                    "current_amount": party.current_amount,
                    "original_amount": party.original_amount,
                    "original_currency": party.original_currency,
                })
        return result
