import pytest

from ledgerx.modules.imports.mapping import ColumnMapping, MappedCSV, read_table
from ledgerx.modules.imports.normalization import normalize
from ledgerx.modules.imports.recognition import recognize


@pytest.mark.parametrize(
    "content",
    [
        b"Date,Details,Amount,CCY\n2026-01-07,Synthetic,-12.3456,AED\n",
        b"CCY,Net Amount,Payee,Txn Date\nAED,-12.3456,Synthetic,07-01-2026\n",
        b"Date,Memo,Amount (AED)\n2026-01-07,Synthetic,-12.3456\n",
        b"Date,Merchant,Withdrawal,Deposit,ISO\n2026-01-07,Synthetic,12.3456,,AED\n",
        b"transaction_date,description,amount,currency\n2026-01-07,Synthetic,12.3456,AED\n",
    ],
)
def test_automatic_recognition(content: bytes) -> None:
    table = read_table(content)
    result = recognize(table, [])
    assert result.state == "recognized" and result.mapping is not None
    assert not result.questions and result.evidence
    row = normalize(next(MappedCSV(result.mapping).table_candidates(table)))
    assert not row.errors
    assert row.currency == "AED" and str(row.amount).endswith("12.3456")


@pytest.mark.parametrize(
    "content,question,state",
    [
        (
            b"Date,Details,Amount,CCY\n03/04/2026,Synthetic,-12,AED\n",
            "date_format",
            "needs_confirmation",
        ),
        (b"Date,Details,Amount\n2026-01-07,Synthetic,-12\n", "currency", "needs_confirmation"),
        (
            b"Date,Details,Amount,CCY\n2026-01-07,Synthetic,12,AED\n",
            "sign_convention",
            "needs_confirmation",
        ),
        (
            b"Date,Posting Date,Details,Amount,CCY\n2026-01-07,2026-01-08,Synthetic,-12,AED\n",
            "transaction_date",
            "needs_mapping",
        ),
        (
            b"Date,Details,Amount,Debit,Credit,CCY\n2026-01-07,Synthetic,-12,12,,AED\n",
            "amount_mode",
            "needs_mapping",
        ),
    ],
)
def test_ambiguity_is_explicit(content: bytes, question: str, state: str) -> None:
    result = recognize(read_table(content), [])
    assert result.state == state and question in result.questions


def test_profiles_apply_or_conflict_without_arbitrary_selection() -> None:
    table = read_table(b"Date,Details,Amount\n03/04/2026,Synthetic,12\n")
    profile = ColumnMapping(
        transaction_date="Date",
        description="Details",
        amount="Amount",
        fixed_currency="GBP",
        date_format="DD/MM/YYYY",
    )
    result = recognize(table, [("Reviewed profile", profile)])
    assert result.mapping == profile and result.profile_name == "Reviewed profile"
    assert result.state == "recognized" and not result.questions
    conflict = recognize(
        table,
        [("First", profile), ("Second", profile.model_copy(update={"date_format": "MM/DD/YYYY"}))],
    )
    assert conflict.state == "needs_confirmation" and "profile" in conflict.questions
