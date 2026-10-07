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

# Project window (CLAUDE.md). Narratives only exist up to 2026-08-14: the CFPB
# stopped publishing them that day and moved all previously published ones to
# the FOIA Reading Room narratives archive (verified 2026-10-06):
# https://www.consumerfinance.gov/foia-requests/foia-electronic-reading-room/cfpb-consumer-complaint-database-narratives-archive/
DATE_MIN = "2025-10-01"
DATE_MAX = "2026-10-01"
NARRATIVES_END = "2026-08-14"

ARCHIVE_DIR = RAW_DIR / "foia_archive"
ARCHIVE_BASE_URL = "https://files.consumerfinance.gov/f/documents/"
# Exports covering our window (13 starts Sept 2025; 21 is the last one).
# Exports 1-12 cover Dec 2011 - Aug 2025 if more history is ever needed.
ARCHIVE_FILES = [
    "CCDB_Export_13_September_2025_through_October_2025.zip",
    "CCDB_Export_14_November_2025_through_December_2025.zip",
    "CCDB_Export_15_January_2026_through_February_2026.zip",
    "CCDB_Export_16_March_2026.zip",
    "CCDB_Export_17_April_2026.zip",
    "CCDB_Export_18_May_2026.zip",
    "CCDB_Export_19_June_2026.zip",
    "CCDB_Export_20_July_2026.zip",
    "CCDB_Export_21_August_2026.zip",
]
