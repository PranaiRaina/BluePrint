"""Redaction must remove identifiers without eating the prose around them.

The recognisers were written against statements, which are tables and numbers.
Agreements, KYC records and disclosures use words like "account" and
"transaction" in ordinary sentences, and a rule that fires on the bare word
deletes the sentence with it.
"""

import pytest

from RAG_PIPELINE.src.ingestion import remove_pii

# --- prose must survive intact ---------------------------------------------

PROSE = [
    "Closing the account does not affect your obligation to pay any "
    "outstanding balance.",
    "A spouse beneficiary may treat the account as their own.",
    "You may close your account at any time by calling the number on the back "
    "of your card.",
    "Accounts for politically exposed persons require senior management "
    "approval before the relationship is established.",
    "Risk rating is based on expected transaction volume and product type.",
    "Transaction monitoring runs continuously and generates alerts for review.",
    "The customer must state the origin of the funds being deposited.",
    "Contributions may not exceed your taxable compensation for the year.",
    # A short token right after the label used to read as an identifier.
    "Your account 401k contributions are capped.",
    "Transfers from the account 2024 forward are free.",
]


@pytest.mark.parametrize("sentence", PROSE)
def test_prose_is_not_redacted(sentence):
    assert remove_pii(sentence) == sentence


def test_the_word_account_mid_sentence_keeps_its_words():
    """The exact damage seen in stored chunks."""
    text = "A spouse beneficiary may treat the account as their own."
    cleaned = remove_pii(text)
    assert "<BANK_ACCOUNT_NUMBER>" not in cleaned
    assert "as their own" in cleaned


def test_financial_terms_are_not_places():
    text = "Change in Market Value was 3,142.77 for the period."
    assert "Market Value" in remove_pii(text)


# --- identifiers must still go ----------------------------------------------


@pytest.mark.parametrize(
    "text,placeholder",
    [
        ("Account Number: VPS-4471-8820", "<BANK_ACCOUNT_NUMBER>"),
        ("Account No. 000123456789", "<BANK_ACCOUNT_NUMBER>"),
        ("Acct #: 4471-8820-11", "<BANK_ACCOUNT_NUMBER>"),
        ("Account: NG-IRA-3390", "<BANK_ACCOUNT_NUMBER>"),
        ("Routing Number: 021000021", "<US_ROUTING_NUMBER>"),
        ("Member ID: MTB-88231", "<MEMBER_ID>"),
        ("Transaction ID: TXN-9982213", "<TRANSACTION_REFERENCE_ID>"),
        ("Zelle Reference Number: ZL8823391", "<TRANSACTION_REFERENCE_ID>"),
    ],
)
def test_identifiers_are_redacted(text, placeholder):
    cleaned = remove_pii(text)
    assert placeholder in cleaned, cleaned


def test_a_bolded_name_is_still_redacted():
    """Markdown emphasis used to break tokenisation and leak the name."""
    assert "Jane Sample" not in remove_pii("Account Holder: Jane Sample")


def test_an_address_is_still_redacted():
    text = "400 Harbour Street, Suite 1200, Boston MA 02110"
    assert "Harbour Street" not in remove_pii(text)


def test_empty_text_is_returned_unchanged():
    assert remove_pii("") == ""
