from decimal import Decimal
from ledger import Ledger

def test_ledger_operations_one():
    l = Ledger()
    l.deposit(Decimal("110"), "USDT", "t1", Decimal("10"))
    l.deposit(Decimal("110"), "USDT", "t2", Decimal("10"))

    l.withdraw(Decimal("150"), "USDT", Decimal("10"))

    assert l.balance()["USDT"] == Decimal(40)


def test_ledger_operations_two():
    l = Ledger()
    l.deposit(Decimal("110"), "USDT", "t1", Decimal("10"))
    l.deposit(Decimal("110"), "USDT", "t2", Decimal("10"))

    l.convert(Decimal("150"), "USDT", Decimal("300"), "ABC", 10)

    assert l.balance()["USDT"] == Decimal(40)
    assert l.balance()["ABC"] == Decimal(300)

    l.withdraw(Decimal("200"), "ABC", Decimal("20"))

    assert l.balance()["USDT"] == Decimal(40)
    assert l.balance()["ABC"] == Decimal(80)


def test_01():
    l = Ledger()
    l.deposit(Decimal("110"), "USDT", "t1", Decimal("10"))
    assert l.balance() == {"USDT": Decimal("100")}
    l.deposit(Decimal("110"), "USDT", "t2", Decimal("10"))
    assert l.balance() == {"USDT": Decimal("200")}

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


if __name__ == "__main__":
    test_ledger_operations_one()
    test_ledger_operations_two()

    test_01()

    print("All tests passed!")
