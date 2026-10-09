from decimal import Decimal

import pytest
from botocore.exceptions import ClientError

from sabwat.core.db import Decision, DynamoDecisionStore, FallbackStore, SqliteDecisionStore


class FakeTable:
    """Minimal stand-in for a boto3 DynamoDB Table: put_item + query on txn_id."""

    def __init__(self, fail: bool = False):
        self.items: list[dict] = []
        self.fail = fail

    def _maybe_fail(self):
        if self.fail:
            raise ClientError({"Error": {"Code": "ExpiredTokenException", "Message": "x"}}, "op")

    def put_item(self, Item):
        self._maybe_fail()
        assert not any(isinstance(v, float) for v in Item.values()), "floats must be Decimals"
        self.items.append(Item)

    def query(self, KeyConditionExpression):
        self._maybe_fail()
        txn = KeyConditionExpression.get_expression()["values"][1]
        return {"Items": [i for i in self.items if i["txn_id"] == txn]}


@pytest.fixture
def sqlite_store(tmp_path):
    return SqliteDecisionStore(tmp_path / "d.db")


def make(txn="TXN00000012", **kw):
    return Decision(txn_id=txn, decision="escalate", score=91.5, band="High",
                    layers_fired=["network"], **kw)


def test_sqlite_roundtrip(sqlite_store):
    d = make(note="ring member")
    assert sqlite_store.put(d) == "sqlite"
    assert sqlite_store.history("TXN00000012") == [d]
    assert sqlite_store.history("TXN00000099") == []


def test_dynamo_stores_decimals_and_reads_floats():
    table = FakeTable()
    store = DynamoDecisionStore(table)
    d = make()
    assert store.put(d) == "dynamodb"
    assert table.items[0]["score"] == Decimal("91.5")
    assert "brief_source" not in table.items[0]  # None attributes dropped
    assert store.history("TXN00000012") == [d]


def test_fallback_writes_to_sqlite_when_dynamo_fails(sqlite_store):
    store = FallbackStore(DynamoDecisionStore(FakeTable(fail=True)), sqlite_store)
    d = make()
    assert store.put(d) == "sqlite"
    assert store.history("TXN00000012") == [d]


def test_fallback_merges_both_backends(sqlite_store):
    table = FakeTable()
    store = FallbackStore(DynamoDecisionStore(table), sqlite_store)
    a, b = make(decided_at="2026-10-08T01:00:00.000+00:00"), make(decided_at="2026-10-08T02:00:00.000+00:00")
    store.put(a)
    sqlite_store.put(b)
    assert store.history("TXN00000012") == [a, b]


def test_invalid_decision_rejected():
    with pytest.raises(ValueError):
        Decision(txn_id="TXN1", decision="approve")
