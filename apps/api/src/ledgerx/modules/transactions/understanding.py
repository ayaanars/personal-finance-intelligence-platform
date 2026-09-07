"""Deterministic advisory metadata; never alters imported financial facts."""

import re
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

RULE_VERSION = "understanding-v1"
NORMALIZATION_VERSION = "description-v1"


class Category(StrEnum):
    INCOME = "Income"
    GROCERIES = "Groceries"
    DINING = "Food & Dining"
    TRANSPORT = "Transport"
    SHOPPING = "Shopping"
    ENTERTAINMENT = "Entertainment"
    HOUSING = "Housing"
    UTILITIES = "Bills & Utilities"
    HEALTH = "Health"
    EDUCATION = "Education"
    TRAVEL = "Travel"
    TRANSFERS = "Transfers"
    CASH = "Cash / ATM"
    FEES = "Banking Fees"
    OTHER = "Other"


def normalize_description(raw: str) -> str:
    """Uppercase, collapse whitespace/repeated separators; strip only labeled numeric suffixes."""
    value = " ".join(raw.upper().split())
    value = re.sub(r"([|*_.!;:/-])\1+", r"\1", value)
    # Repeated labeled references can occur; remove to a fixed point for idempotency.
    while True:
        stripped = re.sub(r"\s+(?:REF|REFERENCE|TXN ID)\s*[:#-]?\s*\d{6,}\s*$", "", value)
        if stripped == value:
            return value
        value = stripped


@dataclass(frozen=True)
class MerchantRule:
    code: str
    name: str
    category: Category
    aliases: tuple[str, ...]
    specializes: tuple[str, ...] = ()


MERCHANTS = (
    MerchantRule("talabat", "Talabat", Category.DINING, ("TALABAT",)),
    MerchantRule("deliveroo", "Deliveroo", Category.DINING, ("DELIVEROO",)),
    MerchantRule("carrefour", "Carrefour", Category.GROCERIES, ("CARREFOUR",)),
    MerchantRule("lulu", "Lulu", Category.GROCERIES, ("LULU", "LU LU")),
    MerchantRule("enoc", "ENOC", Category.TRANSPORT, ("ENOC",)),
    MerchantRule("adnoc", "ADNOC", Category.TRANSPORT, ("ADNOC FUEL", "ADNOC STATION")),
    MerchantRule("uber_eats", "Uber Eats", Category.DINING, ("UBER EATS", "UBEREATS"), ("uber",)),
    MerchantRule("uber", "Uber", Category.TRANSPORT, ("UBER",)),
    MerchantRule("careem", "Careem", Category.TRANSPORT, ("CAREEM RIDE", "CAREEM TAXI")),
    MerchantRule("netflix", "Netflix", Category.ENTERTAINMENT, ("NETFLIX.COM", "NETFLIX")),
    MerchantRule("spotify", "Spotify", Category.ENTERTAINMENT, ("SPOTIFY",)),
    MerchantRule("amazon", "Amazon", Category.SHOPPING, ("AMAZON", "AMZN MKTPLACE")),
    MerchantRule("du", "Du", Category.UTILITIES, ("DU TELECOM", "DU")),
    MerchantRule("etisalat", "Etisalat", Category.UTILITIES, ("ETISALAT", "E& TELECOM")),
    MerchantRule("dewa", "DEWA", Category.UTILITIES, ("DEWA",)),
    MerchantRule(
        "emirates", "Emirates", Category.TRAVEL, ("EMIRATES AIRLINE", "EMIRATES AIRLINES")
    ),
    MerchantRule("etihad", "Etihad", Category.TRAVEL, ("ETIHAD AIRWAYS", "ETIHAD AIRLINE")),
    MerchantRule("booking", "Booking.com", Category.TRAVEL, ("BOOKING.COM",)),
)


def contains(description: str, phrase: str) -> bool:
    return re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", description) is not None


def merchant_match(description: str) -> MerchantRule | None:
    matches = [
        (len(alias), rule)
        for rule in MERCHANTS
        for alias in rule.aliases
        if contains(description, alias)
    ]
    # Alias groups explicitly declare specialization, e.g. Uber Eats / Uber.
    if not matches:
        return None
    candidates = {rule for _, rule in matches}
    specialized = {code for rule in candidates for code in rule.specializes}
    candidates = {rule for rule in candidates if rule.code not in specialized}
    return next(iter(candidates)) if len(candidates) == 1 else None


@dataclass(frozen=True)
class CategoryRule:
    code: str
    category: Category
    phrases: tuple[str, ...]
    direction: str = "outflow"


# Explicit tiers; within a tier conflicting categories conservatively fall back to Other.
MOVEMENTS = (
    CategoryRule(
        "transfer",
        Category.TRANSFERS,
        (
            "ACCOUNT TRANSFER",
            "BANK TRANSFER",
            "TRANSFER IN",
            "TRANSFER OUT",
            "INTERNAL TRANSFER",
            "CARD REPAYMENT",
            "CREDIT CARD PAYMENT",
        ),
        "either",
    ),
    CategoryRule("atm", Category.CASH, ("ATM WITHDRAWAL", "CASH WITHDRAWAL")),
    CategoryRule(
        "bank_fee",
        Category.FEES,
        ("BANK FEE", "BANKING FEE", "OVERDRAFT FEE", "ACCOUNT MAINTENANCE FEE"),
    ),
)
KEYWORDS = (
    CategoryRule("groceries", Category.GROCERIES, ("GROCERY", "GROCERIES", "SUPERMARKET")),
    CategoryRule("dining", Category.DINING, ("RESTAURANT", "CAFE", "COFFEE", "FOOD DELIVERY")),
    CategoryRule(
        "transport",
        Category.TRANSPORT,
        (
            "FUEL",
            "PETROL",
            "METRO",
            "PUBLIC TRANSPORT",
            "TAXI",
            "TOLL",
            "SALIK",
            "PARKING",
            "VEHICLE REPAIR",
            "CAR SERVICE",
        ),
    ),
    CategoryRule(
        "shopping",
        Category.SHOPPING,
        ("RETAIL", "E-COMMERCE", "ELECTRONICS", "CLOTHING", "HOME GOODS"),
    ),
    CategoryRule("entertainment", Category.ENTERTAINMENT, ("CINEMA", "GAMING", "STREAMING")),
    CategoryRule(
        "utilities",
        Category.UTILITIES,
        (
            "UTILITY",
            "UTILITIES",
            "ELECTRICITY",
            "WATER BILL",
            "TELECOM",
            "MOBILE BILL",
            "INTERNET BILL",
            "SOFTWARE SUBSCRIPTION",
            "INSURANCE PREMIUM",
        ),
    ),
    CategoryRule("housing", Category.HOUSING, ("RENT", "HOUSING", "PROPERTY MAINTENANCE")),
    CategoryRule(
        "health",
        Category.HEALTH,
        ("PHARMACY", "HOSPITAL", "CLINIC", "HEALTHCARE", "FITNESS", "GYM"),
    ),
    CategoryRule("education", Category.EDUCATION, ("UNIVERSITY", "COURSE", "TUITION", "SCHOOL")),
    CategoryRule("travel", Category.TRAVEL, ("AIRLINE", "AIRLINES", "FLIGHT", "HOTEL")),
    CategoryRule(
        "other_explicit",
        Category.OTHER,
        (
            "GOVERNMENT FEE",
            "CHARITY",
            "DONATION",
            "PROFESSIONAL SERVICES",
            "BUSINESS EXPENSE",
            "MISCELLANEOUS PURCHASE",
        ),
    ),
)
INCOME = (
    CategoryRule(
        "income",
        Category.INCOME,
        (
            "SALARY",
            "PAYROLL",
            "FREELANCE PAYMENT",
            "FREELANCE INCOME",
            "INTEREST CREDIT",
            "DIVIDEND",
            "INCOME CREDIT",
        ),
        "inflow",
    ),
)
RETURNS = ("REFUND", "REVERSAL", "REIMBURSEMENT", "CASHBACK")


@dataclass(frozen=True)
class Understanding:
    normalized_description: str
    merchant: str | None
    category: Category
    source: str
    reason: str
    rule_id: str


def understand(raw: str, amount: Decimal) -> Understanding:
    description = normalize_description(raw)
    merchant = merchant_match(description)

    def result(category: Category, source: str, reason: str, rule: str) -> Understanding:
        return Understanding(
            description, merchant.name if merchant else None, category, source, reason, rule
        )

    def match_group(rules: tuple[CategoryRule, ...]) -> Understanding | None:
        matches = [
            rule
            for rule in rules
            if (rule.direction == "either" or (amount > 0) == (rule.direction == "inflow"))
            and any(contains(description, phrase) for phrase in rule.phrases)
        ]
        if len({rule.category for rule in matches}) > 1:
            return result(
                Category.OTHER,
                "fallback",
                "Conflicting category evidence; used Other.",
                "ambiguous",
            )
        if matches:
            rule = min(matches, key=lambda rule: rule.code)
            return result(
                rule.category,
                "description_rule",
                f"Description matched {rule.code.replace('_', ' ')} rule.",
                rule.code,
            )
        return None

    # Returns must never become income, fees or a newly inferred transfer.
    if any(contains(description, phrase) for phrase in RETURNS):
        if merchant:
            return result(
                merchant.category,
                "merchant_rule",
                f"Return/reimbursement description matched {merchant.name} merchant rule.",
                "return_" + merchant.code,
            )
        return result(
            Category.OTHER,
            "fallback",
            "Return/reimbursement has no known category; used Other.",
            "return_unknown",
        )
    movement = match_group(MOVEMENTS)
    if movement:
        return movement
    if merchant:
        return result(
            merchant.category,
            "merchant_rule",
            f"Merchant matched {merchant.name} rule.",
            "merchant_" + merchant.code,
        )
    income = match_group(INCOME)
    if income:
        return income
    if amount < 0:
        keywords = match_group(KEYWORDS)
        if keywords:
            return keywords
    return result(Category.OTHER, "fallback", "No rule matched; fell back to Other.", "unmatched")
