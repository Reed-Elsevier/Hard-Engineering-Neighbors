"""Analyst decision log. DynamoDB in AWS, SQLite locally; DynamoDB errors fall back to SQLite.

    store = get_store()
    store.put(Decision(txn_id="TXN00000012", decision="escalate", note="ring member"))
    store.history("TXN00000012")
"""

import json
import logging
import sqlite3
import time
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal, Protocol

from botocore.exceptions import BotoCoreError, ClientError
from pydantic import BaseModel, Field

from sabwat.config import settings

log = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


class Decision(BaseModel):
    txn_id: str
    decision: Literal["escalate", "review", "dismiss"]
    note: str = ""
    score: float | None = None
    band: Literal["Low", "Med", "High"] | None = None
    layers_fired: list[str] = Field(default_factory=list)
    brief_source: Literal["claude", "template"] | None = None
    model_version: str | None = None
    decided_at: str = Field(default_factory=_now)


class DecisionStore(Protocol):
    name: str

    def put(self, d: Decision) -> str: ...  # returns the name of the backend that stored it
    def history(self, txn_id: str) -> list[Decision]: ...


class SqliteDecisionStore:
    name = "sqlite"

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self._conn() as c:
            c.execute(
                "CREATE TABLE IF NOT EXISTS decisions ("
                " txn_id TEXT NOT NULL, decided_at TEXT NOT NULL, body TEXT NOT NULL,"
                " PRIMARY KEY (txn_id, decided_at))"
            )

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def put(self, d: Decision) -> str:
        with self._conn() as c:
            c.execute("INSERT OR REPLACE INTO decisions VALUES (?, ?, ?)",
                      (d.txn_id, d.decided_at, d.model_dump_json()))
        return self.name

    def history(self, txn_id: str) -> list[Decision]:
        with self._conn() as c:
            rows = c.execute("SELECT body FROM decisions WHERE txn_id = ? ORDER BY decided_at",
                             (txn_id,)).fetchall()
        return [Decision.model_validate_json(r[0]) for r in rows]


class DynamoDecisionStore:
    """`table` is a boto3 DynamoDB Table resource (or anything with put_item/query)."""

    name = "dynamodb"

    def __init__(self, table):
        self.table = table

    def put(self, d: Decision) -> str:
        # DynamoDB rejects floats; round-trip through JSON to get Decimals; drop None attributes.
        item = json.loads(d.model_dump_json(exclude_none=True), parse_float=Decimal)
        self.table.put_item(Item=item)
        return self.name

    def history(self, txn_id: str) -> list[Decision]:
        from boto3.dynamodb.conditions import Key

        items = self.table.query(KeyConditionExpression=Key("txn_id").eq(txn_id))["Items"]
        return [Decision.model_validate(_undecimal(i)) for i in items]


class FallbackStore:
    """Try `primary`; on AWS errors (expired token, throttling, no network) use `fallback`."""

    def __init__(self, primary: DecisionStore, fallback: DecisionStore):
        self.primary, self.fallback = primary, fallback
        self.name = f"{primary.name}+{fallback.name}"

    def put(self, d: Decision) -> str:
        try:
            return self.primary.put(d)
        except (BotoCoreError, ClientError) as e:
            log.warning("decision log: %s failed (%s); writing to %s",
                        self.primary.name, e, self.fallback.name)
            return self.fallback.put(d)

    def history(self, txn_id: str) -> list[Decision]:
        local = self.fallback.history(txn_id)
        try:
            remote = self.primary.history(txn_id)
        except (BotoCoreError, ClientError) as e:
            log.warning("decision log: %s read failed (%s)", self.primary.name, e)
            remote = []
        merged = {(x.txn_id, x.decided_at): x for x in remote + local}
        return sorted(merged.values(), key=lambda x: x.decided_at)


def _undecimal(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, list):
        return [_undecimal(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _undecimal(v) for k, v in obj.items()}
    return obj


class BriefCache:
    """Caches Claude briefs in DynamoDB (sabwat-briefs) for 24 h, keyed by txn_id + evidence hash.

    Best effort: any AWS error just means a cache miss.
    """

    TTL_S = 24 * 3600

    def __init__(self):
        self.table = None
        if settings.db_backend == "dynamodb":
            try:
                import boto3

                self.table = boto3.resource("dynamodb", region_name=settings.aws_region).Table(
                    settings.ddb_table_briefs)
            except (BotoCoreError, ClientError) as e:
                log.warning("brief cache disabled: %s", e)

    def get(self, txn_id: str, key: str) -> dict | None:
        if self.table is None:
            return None
        try:
            item = self.table.get_item(Key={"txn_id": txn_id}).get("Item")
        except (BotoCoreError, ClientError) as e:
            log.warning("brief cache read failed: %s", e)
            return None
        if not item or item.get("key") != key or int(item.get("expires_at", 0)) < time.time():
            return None
        return json.loads(item["body"])

    def put(self, txn_id: str, key: str, body: dict) -> None:
        if self.table is None:
            return
        try:
            self.table.put_item(Item={"txn_id": txn_id, "key": key, "body": json.dumps(body),
                                      "expires_at": int(time.time()) + self.TTL_S})
        except (BotoCoreError, ClientError) as e:
            log.warning("brief cache write failed: %s", e)


def get_store() -> DecisionStore:
    sqlite_store = SqliteDecisionStore(settings.decisions_db)
    if settings.db_backend != "dynamodb":
        return sqlite_store
    try:
        import boto3

        table = boto3.resource("dynamodb", region_name=settings.aws_region).Table(
            settings.ddb_table_decisions)
    except (BotoCoreError, ClientError) as e:
        log.warning("decision log: DynamoDB unavailable (%s); using SQLite", e)
        return sqlite_store
    return FallbackStore(DynamoDecisionStore(table), sqlite_store)
