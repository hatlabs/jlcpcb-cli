"""Tests for parts order data extraction from web API."""

from jlcpcb_cli.core.web_parts import (
    _all_sub_orders,
    _extract_parts_batch,
    _extract_parts_batch_detail,
    _extract_component,
)


def _make_sub_order(order_no, status=20, presale_type="stock", paid=10.0, goods=None):
    return {
        "presaleOrderNo": order_no,
        "orderStatus": status,
        "payStatus": "paySuccess",
        "paidMoney": paid,
        "presaleType": presale_type,
        "paymentTypeCode": "ADYEN_CARD",
        "paymentTime": 1772535670000,
        "completionTime": None,
        "shipmentNumber": None,
        "presaleGoodsRecords": goods or [{"componentCode": "C123"}],
    }


class TestAllSubOrders:
    def test_combines_stock_and_buy(self):
        batch = {
            "stockList": [_make_sub_order("PF001", presale_type="stock")],
            "buyList": [_make_sub_order("PF002", presale_type="buy")],
        }
        result = _all_sub_orders(batch)
        assert len(result) == 2
        assert result[0]["presaleOrderNo"] == "PF001"
        assert result[1]["presaleOrderNo"] == "PF002"

    def test_handles_missing_lists(self):
        batch = {"stockList": [_make_sub_order("PF001")]}
        result = _all_sub_orders(batch)
        assert len(result) == 1

    def test_empty_batch(self):
        assert _all_sub_orders({}) == []

    def test_includes_all_list_types(self):
        batch = {
            "stockList": [_make_sub_order("PF001")],
            "buyList": [_make_sub_order("PF002")],
            "overseasShopList": [_make_sub_order("PF003")],
            "idleOrderList": [_make_sub_order("PF004")],
        }
        result = _all_sub_orders(batch)
        assert len(result) == 4


class TestExtractPartsBatch:
    def test_counts_across_all_lists(self):
        batch = {
            "orderBatchNo": "POB001",
            "createTime": 1772535589000,
            "stockList": [_make_sub_order("PF001", paid=10.0)],
            "buyList": [_make_sub_order("PF002", paid=5.0)],
        }
        result = _extract_parts_batch(batch)
        assert result["partsOrderCount"] == 2
        assert result["componentCount"] == 2
        assert result["totalPaid"] == 15.0

    def test_stock_only_batch(self):
        batch = {
            "orderBatchNo": "POB001",
            "createTime": 1772535589000,
            "stockList": [_make_sub_order("PF001", paid=10.0)],
        }
        result = _extract_parts_batch(batch)
        assert result["partsOrderCount"] == 1


class TestExtractPartsBatchDetail:
    def test_includes_buy_orders(self):
        batch = {
            "orderBatchNo": "POB001",
            "createTime": 1772535589000,
            "stockList": [_make_sub_order("PF001", presale_type="stock")],
            "buyList": [_make_sub_order("PF002", presale_type="buy")],
        }
        result = _extract_parts_batch_detail(batch)
        assert len(result["partsOrders"]) == 2
        assert result["partsOrders"][0]["presaleType"] == "stock"
        assert result["partsOrders"][1]["presaleType"] == "buy"


class TestExtractComponent:
    def test_includes_estimated_delivery(self):
        goods = {
            "componentCode": "C2763055",
            "componentName": "USB Type-A",
            "presaleNumber": 380,
            "goodsStatus": 10,
            "deliveryDate": 1773736204000,
        }
        result = _extract_component(goods)
        assert result["estimatedDelivery"] is not None
        assert "2026-03" in result["estimatedDelivery"]

    def test_no_delivery_date(self):
        goods = {
            "componentCode": "C123",
            "goodsStatus": 20,
        }
        result = _extract_component(goods)
        assert "estimatedDelivery" not in result
