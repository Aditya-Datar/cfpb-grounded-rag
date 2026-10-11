import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cfpb.data.clean import (add_clean_columns, clean_narrative,  # noqa: E402
                             filter_narratives, redaction_density)


def test_dates_names_and_money():
    raw = "On XX/XX/XXXX I paid {$250.00} to XXXX XXXX at XXXX bank."
    assert clean_narrative(raw) == "On [DATE] I paid $250.00 to [REDACTED] at [REDACTED] bank."


def test_partial_year_date():
    assert clean_narrative("since XX/XX/2025 nothing") == "since [DATE] nothing"


def test_normal_words_with_x_untouched():
    assert clean_narrative("Xbox tax exam") == "Xbox tax exam"


@pytest.mark.parametrize("raw, expected", [
    # date-mask variants found in the FOIA archive
    ("in XX/XX/year> about", "in [DATE] about"),
    ("in XX/XX/year>, then", "in [DATE], then"),
    ("on XX/XX/scrub> 2024, then", "on [DATE] 2024, then"),
    ("dated XX/XX/scrub>/2025, my", "dated [DATE], my"),
    ("Date : XX/XX/scrub>/25 These", "Date : [DATE] These"),
    ("after XX/XX/scrub>XXXX 2023", "after [DATE] [REDACTED] 2023"),
    ("XX/XX/year>XXXX XXXX", "[DATE] [REDACTED]"),
    ("by XX/XX/25 ok", "by [DATE] ok"),
    ("since XX/2024 the", "since [DATE] the"),
    ("on XX/XX/, then", "on [DATE], then"),
    ("on XX/XX and", "on [DATE] and"),
    ("XXXX/DOFED loan", "[REDACTED]/DOFED loan"),
    # masks glued to other masks or words
    ("XXXXXX/XX/XXXX, ok", "[REDACTED] [DATE], ok"),
    ("XX/XX/XXXXXXXX ok", "[DATE] [REDACTED] ok"),
    ("informationXXXXReason", "information [REDACTED] Reason"),
    ("bureausXXXX, and", "bureaus [REDACTED], and"),
    ("XXXXbusiness-day", "[REDACTED] business-day"),
    ("XXXXXXXX.", "[REDACTED]."),
    ("SSN: XXX-XX-XXXX here", "SSN: [REDACTED] here"),
    ("ending xxxx1738", "ending [REDACTED] 1738"),
    # braces
    ("{$.99} fee", "$.99 fee"),
    ("over {>= $9,999,999} total", "over >= $9,999,999 total"),
    ("paid {$1200.00", "paid $1200.00"),
    ("a { {$9999.99} b", "a $9999.99 b"),
    ("name { XXXX } here", "name [REDACTED] here"),
    ("name { REMOVED } here", "name [REDACTED] here"),
])
def test_archive_variants(raw, expected):
    assert clean_narrative(raw) == expected


def test_no_raw_masks_survive():
    raw = "XX/XX/year> XXXX accountXXXX XX/XX/scrub>/25 {$5.00} xxxx"
    out = clean_narrative(raw)
    assert "XX" not in out and "xxxx" not in out and "{" not in out and ">" not in out


def test_ordinary_words_untouched():
    assert clean_narrative("XXL Xerox Exxon box tax") == "XXL Xerox Exxon box tax"


def test_non_string():
    assert clean_narrative(None) == ""


def test_redaction_density():
    assert redaction_density("[REDACTED] paid [DATE] ok") == 0.5
    assert redaction_density("") == 0.0


def test_filter_dedupes_copies_across_companies():
    text = "I disputed the late payment on my report " * 5
    df = pd.DataFrame({"narrative": [text, text, "too short"],
                       "company": ["EQUIFAX", "EXPERIAN", "X"]})
    out = filter_narratives(add_clean_columns(df), min_words=20)
    assert len(out) == 1
