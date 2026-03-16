"""Tests for parts inventory data extraction."""

from jlcpcb_cli.core.parts import _extract_component


def test_extract_component():
    comp = {
        "lcscComponentId": 106577,
        "componentCode": "C105362",
        "componentModel": "FMF06FTHR010-LH",
        "componentBrand": "PSA(Prosperity Dielectrics)",
        "componentType": "Resistors",
        "componentSpecification": "1206",
        "description": "10mΩ 1W Current Sense Resistor",
        "privateStockCount": 104,
        "rohsFlag": 1,
    }

    result = _extract_component(comp)

    assert result["lcscPart"] == "C105362"
    assert result["mfrPart"] == "FMF06FTHR010-LH"
    assert result["manufacturer"] == "PSA(Prosperity Dielectrics)"
    assert result["category"] == "Resistors"
    assert result["package"] == "1206"
    assert result["stock"] == 104
    assert result["rohs"] is True


def test_extract_component_no_rohs():
    comp = {
        "componentCode": "C12345",
        "componentModel": "XYZ",
        "rohsFlag": 0,
    }

    result = _extract_component(comp)

    assert result["lcscPart"] == "C12345"
    assert result["rohs"] is False
