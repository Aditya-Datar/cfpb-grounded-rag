"""Shared paths, column names, and the product -> regulation mapping."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
OUTPUT_DIR = ROOT / "outputs"

# Raw CFPB column -> snake_case name used everywhere downstream.
COLUMN_MAP = {
    "Date received": "date_received",
    "Product": "product",
    "Sub-product": "sub_product",
    "Issue": "issue",
    "Sub-issue": "sub_issue",
    "Consumer complaint narrative": "narrative",
    "Company public response": "company_public_response",
    "Company": "company",
    "State": "state",
    "ZIP code": "zip_code",
    "Tags": "tags",
    "Consumer consent provided?": "consumer_consent",
    "Submitted via": "submitted_via",
    "Date sent to company": "date_sent",
    "Company response to consumer": "company_response",
    "Timely response?": "timely_response",
    "Consumer disputed?": "consumer_disputed",
    "Complaint ID": "complaint_id",
}

# Columns we actually keep after loading (narrative is optional, see load.py).
KEEP_COLUMNS = [
    "complaint_id", "date_received", "product", "sub_product", "issue",
    "sub_issue", "company", "state", "submitted_via", "company_response",
    "timely_response", "narrative",
]

# Candidate regulation per CFPB product. This is a HEURISTIC used only to
# stratify the annotation sample (~30 per regulation, see CLAUDE.md Sec. 4).
# It is NOT a gold label: annotators assign the governing section by hand.
# Known gaps: much credit-reporting law lives in the FCRA statute (15 USC 1681),
# not Reg V; mortgages also fall under RESPA/Reg X; deposit accounts under
# Reg DD. Those are out of scope, so such complaints may get no in-scope section.
PRODUCT_TO_REGULATION = {
    "Credit reporting or other personal consumer reports": "V",  # 12 CFR 1022
    "Debt collection": "F",                                      # 12 CFR 1006
    "Credit card": "Z",                                          # 12 CFR 1026
    "Mortgage": "Z",
    "Vehicle loan or lease": "Z",
    "Student loan": "Z",
    "Payday loan, title loan, personal loan, or advance loan": "Z",
    "Checking or savings account": "E",                          # 12 CFR 1005
    "Money transfer, virtual currency, or money service": "E",
    "Prepaid card": "E",
    "Debt or credit management": None,  # no clear in-scope regulation
}

REGULATION_PARTS = {"E": "12 CFR 1005", "Z": "12 CFR 1026",
                    "V": "12 CFR 1022", "F": "12 CFR 1006"}

RANDOM_SEED = 544
