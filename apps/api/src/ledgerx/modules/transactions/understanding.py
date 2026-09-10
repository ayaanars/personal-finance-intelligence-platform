"""Deterministic advisory metadata; never alters imported financial facts."""

import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

RULE_VERSION = "understanding-v2"
NORMALIZATION_VERSION = "description-v2"


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
    value = " ".join(unicodedata.normalize("NFKC", raw).upper().split())
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
    MerchantRule("starbucks", "Starbucks", Category.DINING, ("STARBUCKS",)),
    MerchantRule("costa", "Costa Coffee", Category.DINING, ("COSTA COFFEE",)),
    MerchantRule("mcdonalds", "McDonald's", Category.DINING, ("MCDONALDS", "MCDONALD'S")),
    MerchantRule("spinneys", "Spinneys", Category.GROCERIES, ("SPINNEYS",)),
    MerchantRule("waitrose", "Waitrose", Category.GROCERIES, ("WAITROSE",)),
    MerchantRule(
        "union_coop", "Union Coop", Category.GROCERIES, ("UNION COOP", "UNION COOPERATIVE")
    ),
    MerchantRule("nesto", "Nesto", Category.GROCERIES, ("NESTO",)),
    MerchantRule("noon", "Noon", Category.SHOPPING, ("NOON",)),
    MerchantRule("ikea", "IKEA", Category.SHOPPING, ("IKEA",)),
    MerchantRule("namshi", "Namshi", Category.SHOPPING, ("NAMSHI",)),
    MerchantRule("gymnation", "GymNation", Category.HEALTH, ("GYMNATION", "GYM NATION")),
    MerchantRule("life_pharmacy", "Life Pharmacy", Category.HEALTH, ("LIFE PHARMACY",)),
    MerchantRule("aster", "Aster Pharmacy", Category.HEALTH, ("ASTER PHARMACY",)),
    MerchantRule("fitness_first", "Fitness First", Category.HEALTH, ("FITNESS FIRST",)),
    MerchantRule("vox", "VOX Cinemas", Category.ENTERTAINMENT, ("VOX CINEMAS",)),
    MerchantRule("reel", "Reel Cinemas", Category.ENTERTAINMENT, ("REEL CINEMAS",)),
    MerchantRule("flydubai", "flydubai", Category.TRAVEL, ("FLYDUBAI",)),
    MerchantRule("air_arabia", "Air Arabia", Category.TRAVEL, ("AIR ARABIA",)),
    MerchantRule("salik", "Salik", Category.TRANSPORT, ("SALIK",)),
    MerchantRule("talabat", "Talabat", Category.DINING, ("TALABAT",)),
    MerchantRule("deliveroo", "Deliveroo", Category.DINING, ("DELIVEROO",)),
    MerchantRule("carrefour", "Carrefour", Category.GROCERIES, ("CARREFOUR",)),
    MerchantRule("lulu", "Lulu", Category.GROCERIES, ("LULU", "LU LU")),
    MerchantRule("enoc", "ENOC", Category.TRANSPORT, ("ENOC",)),
    MerchantRule("adnoc", "ADNOC", Category.TRANSPORT, ("ADNOC",)),
    MerchantRule("uber_eats", "Uber Eats", Category.DINING, ("UBER EATS", "UBEREATS"), ("uber",)),
    MerchantRule("uber", "Uber", Category.TRANSPORT, ("UBER",)),
    MerchantRule("careem", "Careem", Category.TRANSPORT, ("CAREEM",)),
    MerchantRule("netflix", "Netflix", Category.ENTERTAINMENT, ("NETFLIX.COM", "NETFLIX")),
    MerchantRule("spotify", "Spotify", Category.ENTERTAINMENT, ("SPOTIFY",)),
    MerchantRule("amazon", "Amazon", Category.SHOPPING, ("AMAZON", "AMZN")),
    MerchantRule("du", "du", Category.UTILITIES, ("DU TELECOM", "DU")),
    MerchantRule("etisalat", "Etisalat", Category.UTILITIES, ("ETISALAT", "E& TELECOM")),
    MerchantRule("dewa", "DEWA", Category.UTILITIES, ("DEWA",)),
    MerchantRule("emirates", "Emirates", Category.TRAVEL, ("EMIRATES",)),
    MerchantRule("etihad", "Etihad", Category.TRAVEL, ("ETIHAD",)),
    MerchantRule("booking", "Booking.com", Category.TRAVEL, ("BOOKING.COM",)),
)


def contains(description: str, phrase: str) -> bool:
    return re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", description) is not None


def merchant_match(description: str) -> MerchantRule | None:
    description = normalize_description(description)
    description = " ".join(re.sub(r"[._*/-]+", " ", description).split())
    # Do not mistake unrelated institutions/retailers for airlines.
    if any(
        contains(description, phrase)
        for phrase in (
            "EMIRATES NBD",
            "EMIRATES ISLAMIC",
            "EMIRATES POST",
            "EMIRATES COOP",
            "ETIHAD CREDIT",
            "ETIHAD RAIL",
        )
    ):
        description = re.sub(r"\b(?:EMIRATES|ETIHAD)\b", "", description)
    matches = [
        (len(alias), rule)
        for rule in MERCHANTS
        for alias in rule.aliases
        if contains(description, re.sub(r"[._*/-]+", " ", alias))
    ]
    # Alias groups explicitly declare specialization, e.g. Uber Eats / Uber.
    if not matches:
        return None
    candidates = {rule for _, rule in matches}
    specialized = {code for rule in candidates for code in rule.specializes}
    candidates = {rule for rule in candidates if rule.code not in specialized}
    return next(iter(candidates)) if len(candidates) == 1 else None


def described_merchant(description: str) -> str | None:
    """Conservative fallback for explicitly labeled POS merchants, never used for learning."""
    # Conflicting known identities must not be repackaged as a single inferred name.
    if any(contains(description, alias) for rule in MERCHANTS for alias in rule.aliases):
        return None
    match = re.fullmatch(r"(?:POS PURCHASE|CARD PURCHASE)\s+(.+)", description)
    if match is None:
        return None
    name = re.sub(r"\s+(?:(?:AE|UAE)\s+)?\d+\s*$", "", match[1])
    words = name.split()
    generic = {"POS", "PURCHASE", "CARD", "TRANSACTION", "REF", "REFERENCE", "PAYMENT"}
    if not 2 <= len(words) <= 6 or any(word in generic for word in words):
        return None
    if not all(re.fullmatch(r"[A-Z][A-Z'&-]*", word) for word in words):
        return None
    return name.title()[:100]


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


def understand(
    raw: str, amount: Decimal, preferences: Mapping[str, Category] | None = None
) -> Understanding:
    description = normalize_description(raw)
    merchant = merchant_match(description)

    def result(category: Category, source: str, reason: str, rule: str) -> Understanding:
        if any(contains(description, phrase) for phrase in RETURNS) and not rule.startswith(
            "return_"
        ):
            rule = "return_" + rule
        return Understanding(
            description,
            merchant.name if merchant else described_merchant(description),
            category,
            source,
            reason,
            rule,
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

    if merchant and preferences and merchant.code in preferences:
        return result(
            preferences[merchant.code],
            "user_preference",
            f"Your saved category for {merchant.name}.",
            "preference_" + merchant.code,
        )

    # Specific product lines retain the same merchant identity.
    specifics = {
        "amazon": (("AMAZON FRESH", "AMZN FRESH"), Category.GROCERIES),
        "noon": (("NOON MINUTES", "NOON GROCERY"), Category.GROCERIES),
        "careem": (("CAREEM FOOD",), Category.DINING),
    }
    if merchant and merchant.code in specifics:
        phrases, specific_category = specifics[merchant.code]
        if any(contains(re.sub(r"[._*/-]+", " ", description), phrase) for phrase in phrases):
            return result(
                specific_category,
                "description_rule",
                f"Specific product matched for {merchant.name}.",
                "specific_" + merchant.code,
            )

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
