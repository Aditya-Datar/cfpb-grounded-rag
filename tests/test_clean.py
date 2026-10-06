import sys
from pathlib import Path

import pandas as pd

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
