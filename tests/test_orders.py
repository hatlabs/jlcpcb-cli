"""Tests for order data extraction functions."""

from jlcpcb_cli.core.orders import (
    _extract_batch,
    _extract_order_detail,
    _ms_to_iso,
)


def test_ms_to_iso_none():
    assert _ms_to_iso(None) is None


def test_ms_to_iso_valid():
    # 2025-12-28T21:36:39Z
    result = _ms_to_iso(1766928999000)
    assert result.startswith("2025-12-28")


def test_extract_batch_minimal():
    batch = {
        "batchNum": "W2025122821367552",
        "batchCreateTime": 1766928999000,
        "batchStatus": "shipped",
        "payUnionSecondVO": {
            "orderInfoVOList": [
                {"orderCode": "Y41", "orderType": "order_pcb", "payType": "ADYEN_CARD"},
                {"orderCode": "SMT025122860611", "orderType": "order_smt", "payType": "ADYEN_CARD"},
            ],
            "productFee": 400.0,
            "carriageFee": 42.36,
            "tariffFee": 0,
            "totalFee": 468.38,
        },
        "expressInfoVO": {
            "expressNo": "887780540122",
            "freightModeName": "FedEx International Priority",
        },
        "settleCurrencyInfoVO": {
            "settleCurrency": "EUR",
            "settleExchangeRate": 0.8532,
        },
    }

    result = _extract_batch(batch)

    assert result["batchNum"] == "W2025122821367552"
    assert result["status"] == "shipped"
    assert result["orderTypes"] == ["order_pcb", "order_smt"]
    assert result["orderCodes"] == ["Y41", "SMT025122860611"]
    assert result["totalFee"] == 468.38
    assert result["currency"] == "EUR"
    assert result["trackingNumber"] == "887780540122"
    assert result["shippingMethod"] == "FedEx International Priority"
    assert result["paymentMethod"] == "ADYEN_CARD"


def test_extract_batch_empty_orders():
    batch = {
        "batchNum": "W123",
        "batchCreateTime": None,
        "batchStatus": "cancelled",
        "payUnionSecondVO": {"orderInfoVOList": [], "totalFee": 0},
        "expressInfoVO": {},
        "settleCurrencyInfoVO": {},
    }

    result = _extract_batch(batch)

    assert result["batchNum"] == "W123"
    assert result["orderTypes"] == []
    assert result["paymentMethod"] is None


def test_extract_order_detail_pcb():
    order = {
        "orderCode": "Y41",
        "orderTypeStr": "order_pcb",
        "orderStatus": "shipped",
        "quantity": 10,
        "createTime": 1766928999000,
        "payTime": 1766929067000,
        "deliverTime": 1768017242000,
        "myOrdersRecord": {
            "orderFileName": "gerbers_Y41",
            "produceCode": "Y41",
            "expressNo": "887780540122",
            "weight": 1.65,
            "freightModeName": "FedEx International Priority",
            "companyName": "Hat Labs Oy",
            "country": "FI",
            "detail": {
                "pcbDetail": {
                    "stencilLayer": 4,
                    "stencilPly": 1.6,
                    "stencilWidth": 194.3,
                    "stencilLength": 255.3,
                    "stencilCounts": 10,
                    "adornColor": "Green",
                    "charFontColor": "White",
                    "adornPut": "ENIG",
                    "cuprumThickness": 1,
                    "impedanceFlag": "yes",
                },
                "orderCountTolls": {
                    "projectMoney": 24,
                    "dummyMoney": 102.2,
                    "adornPutMoney": 27.1,
                    "stencilMoney": 51.1,
                    "testsMoney": 0,
                    "paiclMoney": 144.56,
                    "carriageMoney": 42.36,
                    "tariffChargesMoney": 0,
                },
            },
        },
        "tdpOrderInfoDTO": None,
    }

    result = _extract_order_detail(order)

    assert result["orderCode"] == "Y41"
    assert result["orderType"] == "order_pcb"
    assert result["status"] == "shipped"
    assert result["fileName"] == "gerbers_Y41"
    assert result["specs"]["layers"] == 4
    assert result["specs"]["surfaceFinish"] == "ENIG"
    assert result["costs"]["engineering"] == 24
    assert result["costs"]["subtotal"] == 144.56


def test_extract_order_detail_smt():
    order = {
        "orderCode": "SMT025122860611",
        "orderTypeStr": "order_smt",
        "orderStatus": "shipped",
        "quantity": 10,
        "createTime": 1766928939000,
        "payTime": None,
        "deliverTime": None,
        "myOrdersRecord": {
            "orderFileName": "gerbers_Y41",
            "produceCode": "SMT025122860611",
            "expressNo": None,
            "bomFileName": "bom.csv",
            "coordinateFileName": "pos.csv",
            "freightModeName": None,
            "projectMoney": 50,
            "dummyMoney": 322.44,
            "paiclMoney": 407.52,
            "carriageMoney": 0,
            "tariffChargesMoney": 0,
        },
        "tdpOrderInfoDTO": None,
    }

    result = _extract_order_detail(order)

    assert result["orderCode"] == "SMT025122860611"
    assert result["orderType"] == "order_smt"
    assert result["bomFileName"] == "bom.csv"
    assert result["costs"]["assembly"] == 322.44


def test_extract_order_detail_tdp():
    order = {
        "orderCode": "D2026010511500095",
        "orderTypeStr": "order_tdp",
        "orderStatus": "shipped",
        "quantity": 3,
        "createTime": 1767606386000,
        "payTime": 1767628561000,
        "deliverTime": 1767858773000,
        "myOrdersRecord": None,
        "tdpOrderInfoDTO": {
            "fileName": "HALPI2 light pipe press jig v6.step",
            "productFee": 19.35,
            "orderTotal": 19.19,
            "shippingCharge": 0.85,
            "tariffChargesMoney": 1.97,
            "productInfo": {
                "materialName": "PLA",
                "materialColor": "Red",
                "materialTechnicsName": "FDM(Plastic)",
                "quantity": 3,
                "sizeX": 8.57,
                "sizeY": 5.49,
                "sizeZ": 5.29,
            },
        },
    }

    result = _extract_order_detail(order)

    assert result["orderCode"] == "D2026010511500095"
    assert result["orderType"] == "order_tdp"
    assert result["material"] == "PLA"
    assert result["color"] == "Red"
    assert result["dimensions"]["x"] == 8.57
