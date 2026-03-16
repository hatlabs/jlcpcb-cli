"""Tests for component data extraction."""

from jlcpcb_cli.core.parts import _extract_component


def test_extract_component():
    comp = {
        "lcscPart": "C1002",
        "firstCategory": "Filters",
        "secondCategory": "Ferrite Beads",
        "mfrPart": "GZ1608D601TF",
        "solderJoint": "2",
        "manufacturer": "Sunlord",
        "libraryType": "base",
        "description": "",
        "datasheet": "https://lcsc.com/datasheet.pdf",
        "price": "20-3980:0.0122667",
        "stock": 642961,
        "package": "0603",
    }

    result = _extract_component(comp)

    assert result["lcscPart"] == "C1002"
    assert result["manufacturer"] == "Sunlord"
    assert result["category"] == "Filters"
    assert result["package"] == "0603"
    assert result["stock"] == 642961
