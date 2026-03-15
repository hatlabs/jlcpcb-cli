"""Tests for parts order data extraction functions."""

from jlcpcb_cli.core.parts import (
    _extract_parts_batch,
    _extract_parts_batch_detail,
    _extract_component,
    _status_label,
    _goods_status_label,
)


def test_status_labels():
    assert _status_label(10) == "unpaid"
    assert _status_label(20) == "paid"
    assert _status_label(30) == "completed"
    assert _status_label(40) == "cancelled"
    assert _status_label(99) == "unknown(99)"


def test_goods_status_labels():
    assert _goods_status_label(10) == "pending"
    assert _goods_status_label(20) == "in_storage"
    assert _goods_status_label(30) == "cancelled"


def test_extract_component():
    goods = {
        "componentCode": "C20625731",
        "componentName": "ABRACON ABM8-272-T3",
        "componentModel": "ABM8-272-T3",
        "componentBrand": "Abracon LLC",
        "componentSpecification": "SMD3225-4P",
        "description": "12MHz Crystal Oscillator",
        "presaleNumber": 100,
        "goodsPrice": 0.1926,
        "goodsMoney": 19.26,
        "goodsPaidMoney": 22.57,
        "inStorageNumber": 100,
        "goodsStatus": 20,
    }

    result = _extract_component(goods)

    assert result["componentCode"] == "C20625731"
    assert result["name"] == "ABRACON ABM8-272-T3"
    assert result["model"] == "ABM8-272-T3"
    assert result["brand"] == "Abracon LLC"
    assert result["quantity"] == 100
    assert result["unitPrice"] == 0.1926
    assert result["totalMoney"] == 19.26
    assert result["status"] == "in_storage"


def test_extract_parts_batch():
    batch = {
        "orderBatchNo": "POB0202603031859897",
        "createTime": 1772535589000,
        "payFlag": False,
        "stockList": [
            {
                "paidMoney": 22.57,
                "presaleGoodsRecords": [{"componentCode": "C20625731"}],
            },
            {
                "paidMoney": 0.14,
                "presaleGoodsRecords": [{"componentCode": "C23179"}],
            },
        ],
    }

    result = _extract_parts_batch(batch)

    assert result["orderBatchNo"] == "POB0202603031859897"
    assert result["partsOrderCount"] == 2
    assert result["componentCount"] == 2
    assert result["totalPaid"] == 22.71


def test_extract_parts_batch_empty():
    batch = {
        "orderBatchNo": "POB0202512210034947",
        "createTime": 1766248470000,
        "payFlag": False,
        "stockList": [],
    }

    result = _extract_parts_batch(batch)

    assert result["partsOrderCount"] == 0
    assert result["componentCount"] == 0
    assert result["totalPaid"] == 0


def test_extract_parts_batch_detail():
    batch = {
        "orderBatchNo": "POB0202603031859897",
        "createTime": 1772535589000,
        "stockList": [
            {
                "presaleOrderNo": "PF20260303002861",
                "orderStatus": 30,
                "payStatus": "paySuccess",
                "paidMoney": 22.57,
                "presaleType": "stock",
                "paymentTypeCode": "ADYEN_CARD",
                "paymentTime": 1772535670000,
                "completionTime": 1772535698000,
                "shipmentNumber": None,
                "presaleGoodsRecords": [
                    {
                        "componentCode": "C20625731",
                        "componentName": "ABRACON ABM8-272-T3",
                        "componentModel": "ABM8-272-T3",
                        "componentBrand": "Abracon LLC",
                        "componentSpecification": "SMD3225-4P",
                        "description": "12MHz Crystal",
                        "presaleNumber": 100,
                        "goodsPrice": 0.1926,
                        "goodsMoney": 19.26,
                        "goodsPaidMoney": 22.57,
                        "inStorageNumber": 100,
                        "goodsStatus": 20,
                    }
                ],
            }
        ],
    }

    result = _extract_parts_batch_detail(batch)

    assert result["orderBatchNo"] == "POB0202603031859897"
    assert len(result["partsOrders"]) == 1

    order = result["partsOrders"][0]
    assert order["presaleOrderNo"] == "PF20260303002861"
    assert order["orderStatus"] == "completed"
    assert order["paymentMethod"] == "ADYEN_CARD"
    assert len(order["components"]) == 1
    assert order["components"][0]["componentCode"] == "C20625731"
