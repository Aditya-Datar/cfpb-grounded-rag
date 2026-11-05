from pathlib import Path
import xml.etree.ElementTree as ET

xml_path = Path("data/raw/ECFR-title12.xml")
output_dir = Path("data/parts")
output_dir.mkdir(parents=True, exist_ok=True)

root = ET.parse(xml_path).getroot()
wanted_parts = {"1005", "1026", "1022", "1006"}
found_parts = set()

for element in root.iter():
    if (
        element.get("TYPE") == "PART"
        and element.get("N") in wanted_parts
    ):
        part_number = element.get("N")
        found_parts.add(part_number)

        ET.ElementTree(element).write(
            output_dir / f"part-{part_number}.xml",
            encoding="utf-8",
            xml_declaration=True,
        )

missing = wanted_parts - found_parts
if missing:
    raise ValueError(f"Parts not found: {sorted(missing)}")