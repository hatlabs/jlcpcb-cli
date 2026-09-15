"""Tests for SMT BOM and inventory usage extraction."""

import pytest

from jlcpcb_cli.core.smt import (
    _extract_bom_component,
    _extract_usage_row,
    _smt_orders,
    _source_label,
    get_bom,
    get_usage,
)
from jlcpcb_cli.core.web_client import JlcpcbAPIError

_BOM_ROW = {
    "componentCode": "C4184",
    "describe": "100mW 20kΩ Thick Film Resistor 0603",
    "componentNum": 150,
    "unitPrice": 0.0,
    "extPrice": 0.0,
    "componentLibraryType": "base",
    "componentRealCount": 160,
    "designator": "R127",
    "lossNumber": 10,
    "assemblyProcess": "SMT",
    "componentNameEn": "0603WAF2002T5E",
    "componentModelEn": "0603WAF2002T5E",
    "comment": "20k",
    "footPrint": "Resistor_SMD:R_0603_1608Metric",
    "patchLocation": "B",
    "componentSource": "preSale",
    "presaleStock": 160,
    "shopStock": None,
    "freeStock": None,
}

_USAGE_ROW = {
    "smtOrderCode": "SMT026082060917",
    "orderBatchNo": "POB0202608061544407",
    "presaleOrderNo": "PF20260806003264",
    "componentCode": "C4260",
    "componentModel": "0603WAF6201T5E",
    "componentNum": 160,
    "remainNumber": None,
    "settleGoodsPrice": 0.0064,
    "componentMoney": 1.03,
    "stockType": 0,
    "tariffMoney": 0.0,
}

_ORDER_DETAIL = {
    "data": {
        "unionOrderDetailVOList": [
            {"orderType": 1, "recordsDetail": {"detail": {"pcbDetail": {}}}},
            {
                "orderType": 4,
                "recordsDetail": {
                    "stencilNumber": 75,
                    "detail": {
                        "smtDetail": {
                            "smtOrderCode": "SMT026082060917",
                            "smtOrderAccessId": "91ca537b",
                        }
                    },
                },
            },
        ]
    }
}


class FakeClient:
    """Records calls and replays canned API responses."""

    def __init__(self, get_results=None, post_results=None):
        self._get = get_results or {}
        self._post = post_results or {}
        self.calls = []

    def api_get(self, path, params=None):
        self.calls.append(("GET", path, params))
        return self._get[path]

    def api_post(self, path, data):
        self.calls.append(("POST", path, data))
        return self._post[path]


def test_source_label():
    assert _source_label("preSale") == "preorder"
    assert _source_label("shop") == "jlcpcb"
    assert _source_label("preSaleAndShop") == "mixed"
    assert _source_label(None) == "unknown(None)"


def test_extract_bom_component_preorder():
    row = _extract_bom_component(_BOM_ROW)
    assert row == {
        "componentCode": "C4184",
        "name": "0603WAF2002T5E",
        "model": "0603WAF2002T5E",
        "description": "100mW 20kΩ Thick Film Resistor 0603",
        "comment": "20k",
        "footprint": "Resistor_SMD:R_0603_1608Metric",
        "library": "base",
        "process": "SMT",
        "side": "B",
        "designators": "R127",
        "placements": 150,
        "unitsUsed": 160,
        "lossUnits": 10,
        "source": "preorder",
        "unitsFromPreorder": 160,
        "unitsFromJlcpcb": None,
        "unitsFree": None,
        "unitPrice": 0.0,
        "lineTotal": 0.0,
    }


def test_extract_bom_component_mixed_source_prices_only_jlcpcb_units():
    mixed = dict(
        _BOM_ROW,
        componentSource="preSaleAndShop",
        presaleStock=610,
        shopStock=10,
        unitPrice=0.0126,
        extPrice=0.126,
    )
    row = _extract_bom_component(mixed)
    assert row["source"] == "mixed"
    assert row["unitsFromPreorder"] == 610
    assert row["unitsFromJlcpcb"] == 10
    assert row["lineTotal"] == 0.126


def test_extract_usage_row():
    assert _extract_usage_row(_USAGE_ROW) == {
        "componentCode": "C4260",
        "model": "0603WAF6201T5E",
        "preorderBatchNo": "POB0202608061544407",
        "presaleOrderNo": "PF20260806003264",
        "quantity": 160,
        "unitPrice": 0.0064,
        "totalMoney": 1.03,
        "tariff": 0.0,
        "remaining": None,
    }


def test_smt_orders_finds_access_id():
    assert _smt_orders(_ORDER_DETAIL["data"]) == [
        {"orderCode": "SMT026082060917", "accessId": "91ca537b", "quantity": 75}
    ]


def test_smt_orders_ignores_non_smt_items():
    data = {"unionOrderDetailVOList": [{"orderType": 1, "recordsDetail": {}}]}
    assert _smt_orders(data) == []


def test_get_bom_totals_and_rows():
    client = FakeClient(
        get_results={
            "/overseas-core-platform/orderCenter/selectPersonOrderDetail": _ORDER_DETAIL,
            "/overseas-pcb-order/v1/smtOrder/getSmtOrderDetail": {
                "data": {
                    "smtBomResult": [
                        _BOM_ROW,
                        dict(
                            _BOM_ROW,
                            componentCode="C2128",
                            componentSource="shop",
                            presaleStock=None,
                            shopStock=160,
                            unitPrice=0.0213,
                            extPrice=3.408,
                        ),
                    ],
                    "totalPrice": 875.89,
                    "patchNum": 75,
                    "patchLocation": "TB",
                }
            },
        }
    )

    result = get_bom(client, "W2026082015506207")

    assert result["batchNum"] == "W2026082015506207"
    smt = result["smtOrders"][0]
    assert smt["orderCode"] == "SMT026082060917"
    assert smt["quantity"] == 75
    assert smt["assemblySide"] == "TB"
    assert smt["suppliedByJlcpcbTotal"] == 3.41
    assert smt["totalPrice"] == 875.89
    assert [c["componentCode"] for c in smt["components"]] == ["C4184", "C2128"]
    assert (
        "GET",
        "/overseas-pcb-order/v1/smtOrder/getSmtOrderDetail",
        {"smtOrderNum": "91ca537b"},
    ) in client.calls


def test_get_usage_totals_and_rows():
    client = FakeClient(
        get_results={
            "/overseas-core-platform/orderCenter/selectPersonOrderDetail": _ORDER_DETAIL,
        },
        post_results={
            "/overseas-pcb-order/v1/smtOrder/querySmtComponent": {
                "data": {
                    "previouslyList": [
                        _USAGE_ROW,
                        dict(_USAGE_ROW, componentCode="C1", componentMoney=6.07),
                    ],
                    "consignedList": [],
                }
            }
        },
    )

    result = get_usage(client, "W2026082015506207")

    smt = result["smtOrders"][0]
    assert smt["orderCode"] == "SMT026082060917"
    assert smt["totalFromInventory"] == 7.1
    assert [c["componentCode"] for c in smt["fromInventory"]] == ["C4260", "C1"]
    assert "consigned" not in smt


def test_get_usage_passes_through_consigned_rows():
    client = FakeClient(
        get_results={
            "/overseas-core-platform/orderCenter/selectPersonOrderDetail": _ORDER_DETAIL,
        },
        post_results={
            "/overseas-pcb-order/v1/smtOrder/querySmtComponent": {
                "data": {"previouslyList": [], "consignedList": [{"foo": 1}]}
            }
        },
    )

    smt = get_usage(client, "W2026082015506207")["smtOrders"][0]
    assert smt["consigned"] == [{"foo": 1}]


@pytest.mark.parametrize("func", [get_bom, get_usage])
def test_raises_when_batch_has_no_smt_order(func):
    client = FakeClient(
        get_results={
            "/overseas-core-platform/orderCenter/selectPersonOrderDetail": {
                "data": {"unionOrderDetailVOList": [{"orderType": 1}]}
            }
        }
    )
    with pytest.raises(JlcpcbAPIError, match="no SMT order"):
        func(client, "W2025122821367552")
