import sys
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cfpb.regs.parse import parse_section, parse_supplement  # noqa: E402

SECTION = """<DIV8 N="1006.18" TYPE="SECTION" hierarchy_metadata='{"path":"/on/_SUBSTITUTE_DATE_/title-12/section-1006.18"}'>
<HEAD>§ 1006.18 False representations.</HEAD>
<P>(a) <I>In general.</I> A debt collector must not mislead.</P>
<P>(b) <I>Representations.</I> (1) A debt collector must not falsely represent that:</P>
<P>(i) It is vouched for by the United States.</P>
<P>(ii) It is a consumer reporting agency.</P>
<P>(c) <I>Next.</I> Something else.</P>
<CITA>[85 FR 76887]</CITA>
</DIV8>"""

# (h) followed by roman (i)/(ii) inside it, then a real top-level (i).
SECTION_H_I = """<DIV8 N="1026.13"><HEAD>§ 1026.13 Billing error resolution.</HEAD>
<P>(a) A.</P><P>(b) B.</P><P>(c) C.</P><P>(d) D.</P><P>(e) E.</P><P>(f) F.</P><P>(g) G.</P>
<P>(h) H. (1) list:</P><P>(i) roman one.</P><P>(ii) roman two.</P>
<P>(i) <I>Relation to Regulation E.</I> Top-level i.</P>
</DIV8>"""

SUPPLEMENT = """<DIV9 N="Supplement I"><HEAD>Supplement I to Part 1006—Official Interpretations</HEAD>
<HD2>Introduction</HD2><P>1. Official status. This commentary is the vehicle for interpretations of the rule here.</P>
<HD2>Subpart A—General</HD2>
<HD3>Section 1006.2—Definitions</HD3>
<HD3>2(b) Attempt To Communicate</HD3>
<P>1. Examples. Section 1006.2(b) defines an attempt to communicate as any act to initiate a communication.</P>
<P>i. Assume a debt collector places a telephone call.</P>
<P>Paragraph 2(j)(1).</P>
<P>1. Example. The following example illustrates a limited-content message for a consumer.</P>
</DIV9>"""


def test_section_paragraphs_and_romans():
    chunks = parse_section(ET.fromstring(SECTION), "1006", "F", "2026-10-13")
    assert [c.chunk_id for c in chunks] == ["R:1006.18(a)", "R:1006.18(b)", "R:1006.18(c)"]
    b = chunks[1]
    assert "(i) It is vouched" in b.text and "(ii) It is a consumer" in b.text
    assert "85 FR" not in b.text  # citations are not regulation text
    assert b.section == "1006.18" and b.source_url.endswith("/on/2026-10-13/title-12/section-1006.18")


def test_roman_i_vs_top_level_i():
    ids = [c.chunk_id for c in parse_section(ET.fromstring(SECTION_H_I), "1026", "Z", "d")]
    assert ids[-2:] == ["R:1026.13(h)", "R:1026.13(i)"]
    h = parse_section(ET.fromstring(SECTION_H_I), "1026", "Z", "d")[-2]
    assert "roman one" in h.text and "roman two" in h.text


def test_supplement_maps_comments_to_paragraphs():
    chunks = parse_supplement(ET.fromstring(SUPPLEMENT), "1006", "F", "d")
    refs = [(c.section, c.paragraph) for c in chunks]
    assert ("1006 Supplement I intro", "1006 Supplement I intro") in refs
    assert ("1006.2", "1006.2(b)") in refs
    assert ("1006.2", "1006.2(j)(1)") in refs
    b = next(c for c in chunks if c.paragraph == "1006.2(b)")
    assert "Assume a debt collector" in b.text and b.kind == "interpretation"


FCRA_HTML = """<html><body>
<!-- documentid:15_1681i  usckey:x -->
<h3 class="section-head">&sect;1681i. Procedure in case of disputed accuracy</h3>
<!-- field-start:statute -->
<h4 class="subsection-head">(a) Reinvestigations of disputed information</h4>
<h4 class="paragraph-head">(1) Reinvestigation required</h4>
<p class="statutory-body-2em">The agency shall conduct a reasonable reinvestigation.</p>
<h4 class="subsection-head">(b) Statement of dispute</h4>
<p class="statutory-body">If the reinvestigation does not resolve the dispute, the consumer may file a statement.</p>
<!-- field-end:statute -->
<!-- field-start:notes -->
<p class="note-body">Editorial note that must not appear in the corpus.</p>
<!-- documentid:15_1681c-2  usckey:y -->
<h3 class="section-head">&sect;1681c&#8211;2. Block of information resulting from identity theft</h3>
<!-- field-start:statute -->
<h4 class="subsection-head">(a) Block</h4>
<p class="statutory-body">A consumer reporting agency shall block the reporting of any information.</p>
<!-- field-end:statute -->
</body></html>"""


def test_fcra_sections_subsections_and_notes(tmp_path):
    from cfpb.regs.fcra import parse_fcra
    p = tmp_path / "fcra.htm"
    p.write_text(FCRA_HTML, encoding="utf-8")
    chunks, sections = parse_fcra(p)
    assert [s["section"] for s in sections] == ["1681i", "1681c-2"]
    assert sections[1]["title"] == "Block of information resulting from identity theft"
    assert [c.chunk_id for c in chunks] == ["S:1681i(a)", "S:1681i(b)", "S:1681c-2(a)"]
    assert all(c.kind == "statute" and c.regulation == "FCRA" for c in chunks)
    assert "Editorial note" not in " ".join(c.text for c in chunks)
    assert "section1681i" in chunks[0].source_url
