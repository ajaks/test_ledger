from decimal import Decimal

import pytest

from ledger import Ledger, InsufficientFundsError, InvalidOperationError


def test_deposit_and_balance():
    l = Ledger()
    l.deposit(Decimal("110"), "USDT", "t1", Decimal("10"))
    assert l.balance() == {"USDT": Decimal("100")}
    l.deposit(Decimal("110"), "USDT", "t2", Decimal("10"))
    assert l.balance() == {"USDT": Decimal("200")}


def test_withdraw_fifo_and_fee():
    l = Ledger()
    l.deposit(Decimal("110"), "USDT", "t1", Decimal("10"))
    l.deposit(Decimal("110"), "USDT", "t2", Decimal("10"))

    w01_res = l.withdraw(Decimal("150"), "USDT", Decimal("10"))
    assert w01_res == [
        {
            "original_amount": Decimal("110"),
            "amount_withdrawn": Decimal("93.75"),
            "original_currency": "USDT",
            "tx_id": "t1",
        },
        {
            "original_amount": Decimal("66"),
            "amount_withdrawn": Decimal("56.25"),
            "original_currency": "USDT",
            "tx_id": "t2",
        },
    ]
    assert l.balance() == {"USDT": Decimal("40")}

    w02_res = l.withdraw(Decimal("30"), "USDT", Decimal("10"))
    assert w02_res == [
        {
            "original_amount": Decimal("44"),
            "amount_withdrawn": Decimal("30"),
            "original_currency": "USDT",
            "tx_id": "t2",
        }
    ]
    assert l.balance() == {"USDT": Decimal("0")}


def test_convert_and_withdraw_after():
    l = Ledger()
    l.deposit(Decimal("110"), "USDT", "t1", Decimal("10"))
    l.deposit(Decimal("110"), "USDT", "t2", Decimal("10"))
    l.convert(Decimal("150"), "USDT", Decimal("300"), "ABC", Decimal("10"))
    assert l.balance() == {"USDT": Decimal("40"), "ABC": Decimal("300")}
    l.withdraw(Decimal("200"), "ABC", Decimal("20"))
    assert l.balance() == {"USDT": Decimal("40"), "ABC": Decimal("80")}


def test_exceptions():
    l = Ledger()
    with pytest.raises(InvalidOperationError):
        l.deposit(Decimal("-10"), "USDT", "tx", Decimal("1"))
    l.deposit(Decimal("50"), "USDT", "tx2", Decimal("5"))
    with pytest.raises(InsufficientFundsError):
        l.withdraw(Decimal("100"), "USDT", Decimal("1"))
    with pytest.raises(InvalidOperationError):
        l.deposit(Decimal("10"), "USDT", "tx3", Decimal("15"))


def test_history():
    l = Ledger()
    l.deposit(Decimal("100"), "EUR", "e1", Decimal("0"))
    l.deposit(Decimal("50"), "EUR", "e2", Decimal("0"))
    h = l.get_history("EUR")
    assert len(h) == 2
    assert h[0]["tx_id"] == "e1"
    assert h[1]["tx_id"] == "e2"


if __name__ == "__main__":
    import sys
    import logging

    logging.basicConfig(stream=sys.stdout, level=logging.INFO)
    import pytest

    pytest.main([__file__])
