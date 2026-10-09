import json

import pandas as pd
import pytest
from conftest import SAMPLES

from sabwat.core.normalize import InputError, normalize, read_csv

FX = {"EUR": 1.08, "GBP": 1.27, "JPY": 0.006667, "PHP": 0.017857, "USD": 1.0}


def load(name):
    return json.loads((SAMPLES / name).read_text(encoding="utf-8"))


def test_good_input_passes_through():
    n = normalize(load("good.json"), FX)
    assert n.txn["account_id"] == "ACC0021473"
    assert n.txn["amount_usd"] == 9650.0
    assert n.txn["channel"] == "Online transfer"
    assert n.data_gaps == []


def test_php_form_is_cleaned_and_converted():
    n = normalize(load("php_form.json"), FX)
    assert n.txn["account_id"] == "ACC0046651"  # trimmed and UPPERCASED
    assert n.txn["currency"] == "PHP"
    assert n.txn["amount_usd"] == pytest.approx(540000 * 0.017857, rel=1e-6)
    assert n.txn["channel"] == "Mobile wallet"
    assert n.txn["merchant_category"] == "Crypto exchange"
    assert n.txn["is_cross_border"] is True
    assert n.txn["txn_ts"] == pd.Timestamp("2026-09-30")


def test_unknown_account_and_text_amount():
    n = normalize(load("unknown_account.json"), FX)
    assert n.txn["account_id"] == "ACC9999999"
    assert n.txn["amount_usd"] == 12500.0
    assert n.txn["txn_ts"] == pd.Timestamp("2026-09-29")


def test_invalid_amount_names_the_field():
    with pytest.raises(InputError) as e:
        normalize(load("invalid.json"), FX)
    assert e.value.field == "amount"


@pytest.mark.parametrize("record, field", [
    ({"account_id": "ACC1"}, "amount"),
    ({"amount": 10, "currency": "XYZ"}, "currency"),
    ({"amount": -5}, "amount"),
    ({"amount": 10, "txn_ts": "not a date"}, "txn_ts"),
    ({"amount": 10, "is_cross_border": "maybe"}, "is_cross_border"),
    ({"amount": 10, "rule_id": "R017", "alert_score": 3}, "alert_score"),
])
def test_errors_name_the_field(record, field):
    with pytest.raises(InputError) as e:
        normalize(record, FX)
    assert e.value.field == field


def test_missing_fields_become_data_gaps():
    n = normalize({"amount": "1,000"}, FX)
    assert n.txn["amount_usd"] == 1000.0
    assert any("currency" in g for g in n.data_gaps)
    assert any("account_id" in g for g in n.data_gaps)


def test_alert_context_is_split_out():
    n = normalize({"amount": 100, "rule": "r017", "alert score": "0.7"}, FX)
    assert n.alert == {"rule_id": "R017", "alert_score": 0.7}


def test_csv_drops_exact_duplicates():
    rows = read_csv((SAMPLES / "messy.csv").read_text(encoding="utf-8"))
    assert len(rows) == 5
    assert rows[0] == {"Transaction ID": "txn00000241"}


def test_csv_garbage_is_input_error():
    with pytest.raises(InputError):
        read_csv("")
