"""Turn messy input (form, JSON, CSV row) into one canonical transaction + optional alert context.

Never raises anything but InputError, whose message names the offending field.
"""

import io
import re
from dataclasses import dataclass, field

import pandas as pd

CHANNELS = ["ATM", "Branch", "Card", "Mobile wallet", "Online transfer", "Wire"]
MERCHANTS = ["Crypto exchange", "Dining", "Electronics", "Fuel", "Gaming", "Groceries",
             "Online marketplace", "Travel"]
ID_FIELDS = ("txn_id", "account_id", "counterparty_account_id", "device_id", "rule_id")
CURRENCY_SYMBOLS = {"₱": "PHP", "$": "USD", "€": "EUR", "£": "GBP", "¥": "JPY"}

# Keys are lowercased with every non-alphanumeric character removed.
ALIASES = {
    "txn_id": ["txnid", "transactionid", "txn", "transaction", "id"],
    "alert_id": ["alertid", "alert"],
    "account_id": ["accountid", "account", "acct", "acctid", "acc", "sender", "senderaccount",
                   "fromaccount", "sourceaccount"],
    "counterparty_account_id": ["counterpartyaccountid", "counterparty", "counterpartyaccount",
                                "cp", "toaccount", "beneficiary", "receiver", "recipient",
                                "destinationaccount"],
    "device_id": ["deviceid", "device"],
    "channel": ["channel", "txnchannel"],
    "merchant_category": ["merchantcategory", "merchant", "mcc", "category"],
    "currency": ["currency", "ccy", "cur"],
    "amount": ["amount", "amt", "value", "transactionamount", "txnamount"],
    "amount_usd": ["amountusd", "usdamount", "usd"],
    "txn_country": ["txncountry", "country"],
    "is_cross_border": ["iscrossborder", "crossborder", "international"],
    "txn_ts": ["txnts", "timestamp", "ts", "date", "datetime", "time", "txndate",
               "transactiondate", "createdat"],
    "rule_id": ["ruleid", "rule", "alertrule"],
    "alert_score": ["alertscore", "rulescore", "score"],
}
_LOOKUP = {alias: canon for canon, names in ALIASES.items() for alias in names}
_AMOUNT_CCY = re.compile(r"^(?:amount|amt)([a-z]{3})$")


class InputError(ValueError):
    def __init__(self, field_name: str, message: str):
        super().__init__(f"{field_name}: {message}")
        self.field = field_name


@dataclass
class Normalized:
    txn: dict
    alert: dict | None = None  # {"rule_id", "alert_score"} when supplied by the user
    data_gaps: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _key(k: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(k).lower())


def _blank(v) -> bool:
    return v is None or (isinstance(v, float) and pd.isna(v)) or (isinstance(v, str) and not v.strip())


def _parse_amount(raw, field_name: str) -> tuple[float, str | None]:
    """'₱12,000.50' -> (12000.5, 'PHP'); 'USD 9,500' -> (9500.0, 'USD')."""
    if isinstance(raw, (int, float)):
        val, ccy = float(raw), None
    else:
        s = str(raw).strip()
        ccy = next((c for sym, c in CURRENCY_SYMBOLS.items() if sym in s), None)
        m = re.search(r"\b([A-Za-z]{3})\b", s)
        if m:
            ccy = m.group(1).upper()
        num = re.sub(r"[^0-9.\-]", "", s)
        try:
            val = float(num)
        except ValueError:
            raise InputError(field_name, f"cannot read a number from {raw!r}") from None
    if val <= 0:
        raise InputError(field_name, f"must be positive, got {val}")
    return val, ccy


def _parse_bool(raw, field_name: str) -> bool:
    if isinstance(raw, bool):
        return raw
    s = str(raw).strip().lower()
    if s in {"true", "t", "yes", "y", "1"}:
        return True
    if s in {"false", "f", "no", "n", "0"}:
        return False
    raise InputError(field_name, f"expected yes/no, got {raw!r}")


def _match(raw: str, options: list[str]) -> str | None:
    by_key = {_key(o): o for o in options}
    return by_key.get(_key(raw))


def canonical_keys(record: dict) -> tuple[dict, list[str]]:
    """Map aliased keys to canonical names; returns (mapped, unknown_keys)."""
    out, unknown = {}, []
    for k, v in record.items():
        kk = _key(k)
        if kk in _LOOKUP:
            out[_LOOKUP[kk]] = v
        elif m := _AMOUNT_CCY.match(kk):
            out["amount"] = v
            out.setdefault("currency", m.group(1).upper())
        else:
            unknown.append(str(k))
    return out, unknown


def normalize(record: dict, fx: dict[str, float]) -> Normalized:
    """Normalize one record. `fx` maps currency -> USD rate."""
    if not isinstance(record, dict) or not record:
        raise InputError("input", "expected a non-empty object of transaction fields")
    rec, unknown = canonical_keys(record)
    rec = {k: v for k, v in rec.items() if not _blank(v)}
    out = Normalized(txn={})
    if unknown:
        out.warnings.append(f"Ignored unrecognised fields: {', '.join(unknown)}")

    for f in ID_FIELDS:
        if f in rec:
            out.txn[f] = str(rec[f]).strip().upper()

    # Amount and currency -> amount_usd
    ccy = str(rec["currency"]).strip().upper() if "currency" in rec else None
    if "amount" in rec:
        amount, sym_ccy = _parse_amount(rec["amount"], "amount")
        ccy = ccy or sym_ccy
    else:
        amount = None
    if ccy is not None and ccy not in fx:
        raise InputError("currency", f"unknown currency {ccy!r}; use one of {', '.join(sorted(fx))}")
    if "amount_usd" in rec:
        out.txn["amount_usd"], _ = _parse_amount(rec["amount_usd"], "amount_usd")
    elif amount is not None:
        if ccy is None:
            ccy = "USD"
            out.data_gaps.append("currency missing; assumed USD")
        out.txn["amount_usd"] = round(amount * fx[ccy], 2)
    else:
        raise InputError("amount", "required (amount with currency, or amount_usd)")
    out.txn["amount"] = amount if amount is not None else out.txn["amount_usd"]
    out.txn["currency"] = ccy or "USD"

    if "txn_ts" in rec:
        try:
            out.txn["txn_ts"] = pd.to_datetime(str(rec["txn_ts"]).strip(), format="mixed",
                                               dayfirst=False)
        except (ValueError, TypeError):
            raise InputError("txn_ts", f"cannot read a date from {rec['txn_ts']!r}") from None
    else:
        out.txn["txn_ts"] = pd.Timestamp.now().floor("s")
        out.data_gaps.append("txn_ts missing; used current time")

    if "channel" in rec:
        ch = _match(rec["channel"], CHANNELS)
        if ch is None:
            out.warnings.append(f"Unknown channel {rec['channel']!r}; treated as missing")
        out.txn["channel"] = ch
    else:
        out.txn["channel"] = None
        out.data_gaps.append("channel missing")
    if "merchant_category" in rec:
        mc = _match(rec["merchant_category"], MERCHANTS)
        if mc is None:
            out.warnings.append(f"Unknown merchant category {rec['merchant_category']!r}; ignored")
        out.txn["merchant_category"] = mc
    else:
        out.txn["merchant_category"] = None

    out.txn["is_cross_border"] = (_parse_bool(rec["is_cross_border"], "is_cross_border")
                                  if "is_cross_border" in rec else False)
    if "is_cross_border" not in rec:
        out.data_gaps.append("is_cross_border missing; assumed domestic")
    out.txn["txn_country"] = str(rec["txn_country"]).strip() if "txn_country" in rec else None
    out.txn.setdefault("counterparty_account_id", None)
    out.txn.setdefault("device_id", None)
    if "account_id" not in out.txn:
        out.txn["account_id"] = None
        out.data_gaps.append("account_id missing; no network lookup possible")

    if "rule_id" in out.txn or "alert_score" in rec:
        rule = out.txn.pop("rule_id", None)
        score = None
        if "alert_score" in rec:
            try:
                score = float(rec["alert_score"])
            except (TypeError, ValueError):
                raise InputError("alert_score", f"expected a number 0-1, got {rec['alert_score']!r}") from None
            if not 0 <= score <= 1:
                raise InputError("alert_score", f"expected a number 0-1, got {score}")
        out.alert = {"rule_id": rule, "alert_score": score}
    return out


def read_csv(text: str) -> list[dict]:
    """CSV text -> list of raw records (strings), exact-duplicate rows dropped."""
    try:
        df = pd.read_csv(io.StringIO(text), dtype=str, skipinitialspace=True)
    except (pd.errors.ParserError, pd.errors.EmptyDataError) as e:
        raise InputError("csv", f"could not parse CSV ({e})") from None
    if df.empty:
        raise InputError("csv", "no rows found")
    df = df.drop_duplicates()
    return [{k: v for k, v in r.items() if not _blank(v)} for r in df.to_dict("records")]
