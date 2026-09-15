"""Tests for SMT BOM and inventory usage extraction."""

import pytest

from jlcpcb_cli.core.smt import (
    _extract_bom_component,
    _extract_usage_row,
    _smt_orders,
    get_bom,
    get_usage,
)
from jlcpcb_cli.core.web_client import JlcpcbAPIError

_BOM_PATH = "/overseas-pcb-order/v1/smtOrder/getSmtOrderDetail"
_USAGE_PATH = "/overseas-pcb-order/v1/smtOrder/querySmtComponent"
_DETAIL_PATH = "/overseas-core-platform/orderCenter/selectPersonOrderDetail"

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


def _smt_item(order_code, access_id, quantity=75):
    return {
        "orderType": 4,
        "recordsDetail": {
            "stencilNumber": quantity,
            "detail": {
                "smtDetail": {
                    "smtOrderCode": order_code,
                    "smtOrderAccessId": access_id,
                }
            },
        },
    }


_ORDER_DETAIL = {
    "data": {
        "unionOrderDetailVOList": [
            {"orderType": 1, "recordsDetail": {"detail": {"pcbDetail": {}}}},
            _smt_item("SMT026082060917", "91ca537b"),
        ]
    }
}


class FakeClient:
    """Records calls and replays canned API responses.

    Responses are keyed by ``(path, smtOrderNum)`` so a test covering two
    SMT orders can prove each one was fetched with its own access id.
    """

    def __init__(self, get_results=None, post_results=None):
        self._get = get_results or {}
        self._post = post_results or {}
        self.calls = []

    def _lookup(self, table, path, payload):
        self.calls.append((path, payload))
        key = (path, payload.get("smtOrderNum")) if payload else (path, None)
        if key in table:
            return table[key]
        return table[path]

    def api_get(self, path, params=None):
        return self._lookup(self._get, path, params or {})

    def api_post(self, path, data):
        return self._lookup(self._post, path, data)


def test_extract_bom_component_from_preorder_stock():
    assert _extract_bom_component(_BOM_ROW) == {
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
        "unitsFromPreorder": 160,
        "unitsFromJlcpcb": 0,
        "unitsFree": 0,
        "unitsUnattributed": 0,
        "unitPrice": 0.0,
        "totalMoney": 0.0,
    }


def test_extract_bom_component_splits_units_between_sources():
    mixed = dict(
        _BOM_ROW,
        componentSource="preSaleAndShop",
        componentRealCount=620,
        presaleStock=610,
        shopStock=10,
        unitPrice=0.0126,
        extPrice=0.126,
    )
    row = _extract_bom_component(mixed)
    assert row["unitsFromPreorder"] == 610
    assert row["unitsFromJlcpcb"] == 10
    assert row["unitsUnattributed"] == 0
    assert row["totalMoney"] == 0.126


def test_extract_bom_component_reports_units_no_source_accounts_for():
    """Live rows exist where the source buckets fall short of the units used.

    JLCPCB charges only the shopStock units, so the shortfall is neither
    paid for in this order nor drawn from pre-ordered stock.
    """
    short = dict(
        _BOM_ROW,
        componentSource="shop",
        componentRealCount=770,
        presaleStock=None,
        shopStock=610,
        unitPrice=0.0055,
        extPrice=3.355,
    )
    row = _extract_bom_component(short)
    assert row["unitsFromJlcpcb"] == 610
    assert row["unitsUnattributed"] == 160


def test_extract_usage_row():
    assert _extract_usage_row(_USAGE_ROW) == {
        "componentCode": "C4260",
        "model": "0603WAF6201T5E",
        "smtOrderCode": "SMT026082060917",
        "orderBatchNo": "POB0202608061544407",
        "presaleOrderNo": "PF20260806003264",
        "quantity": 160,
        "unitPrice": 0.0064,
        "totalPrice": 1.03,
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


def test_smt_order_without_access_id_raises():
    data = {
        "unionOrderDetailVOList": [
            {
                "orderType": 4,
                "recordsDetail": {
                    "detail": {"smtDetail": {"smtOrderCode": "SMT1"}}
                },
            }
        ]
    }
    with pytest.raises(JlcpcbAPIError, match="SMT1 has no access id"):
        _smt_orders(data)


def _bom_client(bom_response, detail=_ORDER_DETAIL):
    return FakeClient(
        get_results={_DETAIL_PATH: detail, _BOM_PATH: bom_response}
    )


def test_get_bom_totals_and_rows():
    client = _bom_client(
        {
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
                "patchNum": 75,
                "patchLocation": "TB",
            }
        }
    )

    result = get_bom(client, "W2026082015506207")

    assert result["batchNum"] == "W2026082015506207"
    smt = result["smtOrders"][0]
    assert smt["orderCode"] == "SMT026082060917"
    assert smt["quantity"] == 75
    assert smt["assemblySide"] == "TB"
    assert smt["suppliedByJlcpcbTotal"] == 3.41
    assert [c["componentCode"] for c in smt["components"]] == ["C4184", "C2128"]
    assert (_BOM_PATH, {"smtOrderNum": "91ca537b"}) in client.calls


@pytest.mark.parametrize("patch_num_state", ["missing", "null"])
def test_get_bom_falls_back_to_batch_quantity(patch_num_state):
    data = {"smtBomResult": [_BOM_ROW], "patchLocation": "TB"}
    if patch_num_state == "null":
        data["patchNum"] = None
    detail = {
        "data": {
            "unionOrderDetailVOList": [_smt_item("SMT1", "a1", quantity=50)]
        }
    }
    smt = get_bom(_bom_client({"data": data}, detail), "W1")["smtOrders"][0]
    assert smt["quantity"] == 50


def test_get_bom_skips_unpriced_rows_in_the_total():
    unpriced = dict(_BOM_ROW, componentCode="C9", extPrice=None)
    priced = dict(_BOM_ROW, componentCode="C8", extPrice=2.5)
    smt = get_bom(
        _bom_client({"data": {"smtBomResult": [unpriced, priced], "patchNum": 75}}),
        "W1",
    )["smtOrders"][0]
    assert smt["suppliedByJlcpcbTotal"] == 2.5
    assert smt["components"][0]["totalMoney"] is None


def test_get_bom_covers_every_smt_order_in_the_batch():
    detail = {
        "data": {
            "unionOrderDetailVOList": [
                _smt_item("SMT1", "a1"),
                _smt_item("SMT2", "a2"),
            ]
        }
    }
    client = FakeClient(
        get_results={
            _DETAIL_PATH: detail,
            (_BOM_PATH, "a1"): {
                "data": {"smtBomResult": [_BOM_ROW], "patchNum": 75}
            },
            (_BOM_PATH, "a2"): {
                "data": {
                    "smtBomResult": [dict(_BOM_ROW, componentCode="C99")],
                    "patchNum": 20,
                }
            },
        }
    )

    smt_orders = get_bom(client, "W1")["smtOrders"]

    assert [o["orderCode"] for o in smt_orders] == ["SMT1", "SMT2"]
    assert smt_orders[1]["quantity"] == 20
    assert smt_orders[1]["components"][0]["componentCode"] == "C99"
    assert (_BOM_PATH, {"smtOrderNum": "a1"}) in client.calls
    assert (_BOM_PATH, {"smtOrderNum": "a2"}) in client.calls


@pytest.mark.parametrize("payload", [{"data": None}, {"data": {"patchNum": 75}}])
def test_get_bom_refuses_a_response_without_a_component_list(payload):
    with pytest.raises(JlcpcbAPIError, match="no smtBomResult"):
        get_bom(_bom_client(payload), "W1")


def _usage_client(usage_response, detail=_ORDER_DETAIL):
    return FakeClient(
        get_results={_DETAIL_PATH: detail},
        post_results={_USAGE_PATH: usage_response},
    )


def test_get_usage_totals_and_rows():
    client = _usage_client(
        {
            "data": {
                "previouslyList": [
                    _USAGE_ROW,
                    dict(_USAGE_ROW, componentCode="C1", componentMoney=6.07),
                ],
                "consignedList": [],
            }
        }
    )

    smt = get_usage(client, "W2026082015506207")["smtOrders"][0]

    assert smt["orderCode"] == "SMT026082060917"
    assert smt["totalFromInventory"] == 7.1
    assert [c["componentCode"] for c in smt["fromInventory"]] == ["C4260", "C1"]
    assert smt["consigned"] == []


def test_get_usage_passes_through_consigned_rows():
    client = _usage_client(
        {"data": {"previouslyList": [], "consignedList": [{"foo": 1}]}}
    )
    smt = get_usage(client, "W1")["smtOrders"][0]
    assert smt["consigned"] == [{"foo": 1}]
    assert smt["totalFromInventory"] == 0


def test_get_usage_refuses_a_response_without_a_component_list():
    with pytest.raises(JlcpcbAPIError, match="no previouslyList"):
        get_usage(_usage_client({"data": {"consignedList": []}}), "W1")


@pytest.mark.parametrize("func", [get_bom, get_usage])
def test_raises_when_batch_has_no_smt_order(func):
    client = FakeClient(
        get_results={
            _DETAIL_PATH: {"data": {"unionOrderDetailVOList": [{"orderType": 1}]}}
        }
    )
    with pytest.raises(JlcpcbAPIError, match="no SMT order"):
        func(client, "W2025122821367552")
