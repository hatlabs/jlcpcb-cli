"""Tests for order data extraction."""

from jlcpcb_cli.core.orders import _extract_order, _type_label


def test_type_label():
    assert _type_label(1) == "pcb"
    assert _type_label(4) == "smt"
    assert _type_label(7) == "3dp"
    assert _type_label(None) == "unknown(None)"
    assert _type_label(99) == "unknown(99)"


def test_extract_pcb_order():
    item = {
        "orderCode": "Y41",
        "orderType": 1,
        "recordsDetail": {
            "produceCode": "Y41",
            "orderFileName": "gerbers_Y41",
            "orderStatus": "shipped",
            "stencilNumber": 10,
            "orderDate": "2025-12-28 21:36:39",
            "produceTime": "2025-12-29 23:53:30",
            "deliveryTime": "2026-01-10 11:54:02",
            "weight": 1.65,
            "dummyMoney": 86.7,
            "carriageMoney": 35.94,
            "paiclMoney": 122.64,
            "freightModeName": "FedEx International Priority",
            "expressNo": "887780540122",
            "paymentMode": "ADYEN_CARD",
            "orderFileUrl": "/file/download?uuid=abc",
            "detail": {
                "orderCountTolls": {
                    "projectMoney": 20.36,
                    "adornPutMoney": 22.99,
                    "stencilMoney": 43.35,
                    "testsMoney": 0.0,
                    "dummyMoney": 86.7,
                    "carriageMoney": 35.94,
                    "paiclMoney": 144.56,
                    "discountMoney": 0.0,
                },
                "pcbDetail": {
                    "stencilLayer": 4,
                    "stencilPly": 1.6,
                    "stencilWidth": 194.3,
                    "stencilLength": 255.3,
                    "stencilCounts": 10,
                    "adornColor": "Green",
                    "charFontColor": "White",
                    "adornPut": "ENIG",
                    "cuprumThickness": 1.0,
                    "insideCuprumThickness": 0.5,
                    "showTagValue": "TG135",
                    "impedanceFlag": "yes",
                    "halfHole": "no",
                    "goldFingerBevel": "0",
                    "goldThickness": 1.0,
                    "panelX": 1,
                    "panelY": 1,
                    "stencilType": "veneer",
                },
            },
        },
    }

    result = _extract_order(item)

    assert result["orderCode"] == "Y41"
    assert result["orderType"] == "pcb"
    assert result["status"] == "shipped"
    assert result["productCost"] == 86.7
    assert result["specs"]["layers"] == 4
    assert result["specs"]["surfaceFinish"] == "ENIG"
    assert result["specs"]["soldermaskColor"] == "Green"
    assert result["specs"]["copperWeight"] == 1.0
    assert result["specs"]["impedanceControl"] is True
    assert result["costBreakdown"]["pcbCost"] == 20.36


def test_extract_smt_order():
    item = {
        "orderCode": "Y41",
        "orderType": 4,
        "recordsDetail": {
            "produceCode": "Y41",
            "orderStatus": "shipped",
            "dummyMoney": 335.16,
            "detail": {
                "smtDetail": {
                    "smtOrderCode": "SMT025122860611",
                    "produceOrderCode": "Y41",
                    "pasteNumber": 10,
                    "patchLocation": "TB",
                    "bomFileName": "bom.csv",
                    "coordinateFileName": "pos.csv",
                },
            },
        },
    }

    result = _extract_order(item)

    assert result["orderType"] == "smt"
    assert result["orderCode"] == "SMT025122860611"
    assert result["specs"]["pcbOrderCode"] == "Y41"
    assert result["specs"]["pasteCount"] == 10
    assert result["specs"]["patchSide"] == "TB"


def test_extract_3dp_order():
    item = {
        "orderCode": "D2026010511500095",
        "orderType": 7,
        "recordsDetail": {
            "produceCode": "D2026010511500095",
            "orderStatus": "shipped",
            "dummyMoney": 23.29,
            "detail": {},
        },
    }

    result = _extract_order(item)

    assert result["orderType"] == "3dp"
    assert result["orderCode"] == "D2026010511500095"
    assert "specs" not in result
