"""JLCPCB Parts Manager order data fetching and extraction."""

import time

from jlcpcb_cli.core.client import JlcpcbClient
from jlcpcb_cli.core.util import ms_to_iso

PARTS_ORDER_LIST_PATH = (
    "/api/overseas-smt-component-order-platform/v1"
    "/overseasSmtComponentOrder/presaleOrder/selectPresaleOrderList"
)


def list_parts_orders(
    client: JlcpcbClient,
    *,
    status: str | None = None,
    search: str | None = None,
    page: int = 1,
    limit: int = 25,
) -> dict:
    """List parts order batches with pagination."""
    data = {
        "pageNum": page,
        "pageSize": limit,
        "orderType": None,
        "keyword": search or "",
        "orderStatus": _map_status_filter(status),
    }

    result = client.api_post(PARTS_ORDER_LIST_PATH, data)
    page_data = result["data"]
    batches = page_data.get("list") or []

    return {
        "pagination": {
            "page": page,
            "pageSize": limit,
            "total": page_data.get("total", 0),
        },
        "orders": [_extract_parts_batch(b) for b in batches],
    }


def get_parts_order(client: JlcpcbClient, batch_no: str) -> dict:
    """Get detailed parts order information for a batch.

    Fetches the full list and filters to the requested batch,
    since there is no single-batch detail endpoint.
    """
    # Fetch all (typically <20 batches total)
    data = {
        "pageNum": 1,
        "pageSize": 100,
        "orderType": None,
        "keyword": "",
        "orderStatus": "",
    }

    result = client.api_post(PARTS_ORDER_LIST_PATH, data)
    batches = result["data"].get("list") or []

    batch = next((b for b in batches if b.get("orderBatchNo") == batch_no), None)
    if batch is None:
        from jlcpcb_cli.core.client import JlcpcbAPIError
        raise JlcpcbAPIError(f"Parts order batch {batch_no} not found")

    return _extract_parts_batch_detail(batch)


def _map_status_filter(status: str | None) -> str:
    """Map CLI status names to API orderStatus values."""
    if status is None or status == "all":
        return ""
    mapping = {
        "paid": "paySuccess",
        "unpaid": "waitPay",
        "cancelled": "cancelled",
        "completed": "completed",
    }
    return mapping.get(status, "")


def _extract_parts_batch(batch: dict) -> dict:
    """Extract a summary from a parts order batch."""
    stock_list = batch.get("stockList") or []
    total_paid = sum(s.get("paidMoney") or 0 for s in stock_list)
    total_items = sum(
        len(s.get("presaleGoodsRecords") or []) for s in stock_list
    )

    return {
        "orderBatchNo": batch.get("orderBatchNo"),
        "date": ms_to_iso(batch.get("createTime")),
        "partsOrderCount": len(stock_list),
        "componentCount": total_items,
        "totalPaid": round(total_paid, 2),
    }


def _extract_parts_batch_detail(batch: dict) -> dict:
    """Extract full detail from a parts order batch."""
    stock_list = batch.get("stockList") or []

    return {
        "orderBatchNo": batch.get("orderBatchNo"),
        "date": ms_to_iso(batch.get("createTime")),
        "partsOrders": [_extract_parts_order(s) for s in stock_list],
    }


def _extract_parts_order(stock: dict) -> dict:
    """Extract a single parts order from the stockList."""
    goods = stock.get("presaleGoodsRecords") or []

    return {
        "presaleOrderNo": stock.get("presaleOrderNo"),
        "orderStatus": _status_label(stock.get("orderStatus")),
        "payStatus": stock.get("payStatus"),
        "paidMoney": stock.get("paidMoney"),
        "presaleType": stock.get("presaleType"),
        "paymentMethod": stock.get("paymentTypeCode"),
        "paymentTime": ms_to_iso(stock.get("paymentTime")),
        "completionTime": ms_to_iso(stock.get("completionTime")),
        "shipmentNumber": stock.get("shipmentNumber"),
        "components": [_extract_component(g) for g in goods],
    }


def _extract_component(goods: dict) -> dict:
    """Extract component detail from a presaleGoodsRecord."""
    return {
        "componentCode": goods.get("componentCode"),
        "name": goods.get("componentName"),
        "model": goods.get("componentModel"),
        "brand": goods.get("componentBrand"),
        "spec": goods.get("componentSpecification"),
        "description": goods.get("description"),
        "quantity": goods.get("presaleNumber"),
        "unitPrice": goods.get("goodsPrice"),
        "totalMoney": goods.get("goodsMoney"),
        "paidMoney": goods.get("goodsPaidMoney"),
        "inStorageNumber": goods.get("inStorageNumber"),
        "status": _goods_status_label(goods.get("goodsStatus")),
    }


def _status_label(code: int | None) -> str:
    """Map orderStatus numeric code to a label."""
    labels = {
        10: "unpaid",
        20: "paid",
        30: "completed",
        40: "cancelled",
    }
    return labels.get(code, f"unknown({code})")


def _goods_status_label(code: int | None) -> str:
    """Map goodsStatus numeric code to a label."""
    labels = {
        10: "pending",
        20: "in_storage",
        30: "cancelled",
    }
    return labels.get(code, f"unknown({code})")
