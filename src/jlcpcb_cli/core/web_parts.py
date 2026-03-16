"""Parts order history via JLCPCB web API.

The official API doesn't have parts order endpoints.
"""

from jlcpcb_cli.core.web_client import WebClient


_PARTS_ORDER_PATH = (
    "/overseas-smt-component-order-platform/v1"
    "/overseasSmtComponentOrder/presaleOrder/selectPresaleOrderList"
)


def list_parts_orders(
    client: WebClient,
    *,
    status: str | None = None,
    search: str | None = None,
    page: int = 1,
    limit: int = 25,
) -> dict:
    """List parts order batches via the web API."""
    data = {
        "pageNum": page,
        "pageSize": limit,
        "orderType": None,
        "keyword": search or "",
        "orderStatus": _map_status(status),
    }

    result = client.api_post(_PARTS_ORDER_PATH, data)
    page_data = result.get("data") or {}
    batches = page_data.get("list") or []

    return {
        "pagination": {
            "page": page,
            "pageSize": limit,
            "total": page_data.get("total", 0),
        },
        "orders": [_extract_parts_batch(b) for b in batches],
    }


def get_parts_order(client: WebClient, batch_no: str) -> dict:
    """Get detailed parts order info for a batch."""
    data = {
        "pageNum": 1,
        "pageSize": 100,
        "orderType": None,
        "keyword": "",
        "orderStatus": "",
    }

    result = client.api_post(_PARTS_ORDER_PATH, data)
    batches = (result.get("data") or {}).get("list") or []
    batch = next((b for b in batches if b.get("orderBatchNo") == batch_no), None)

    if batch is None:
        from jlcpcb_cli.core.client import JlcpcbAPIError
        raise JlcpcbAPIError(f"Parts order batch {batch_no} not found")

    return _extract_parts_batch_detail(batch)


def _map_status(status: str | None) -> str:
    if status is None or status == "all":
        return ""
    return {
        "paid": "paySuccess",
        "unpaid": "waitPay",
        "cancelled": "cancelled",
        "completed": "completed",
    }.get(status, "")


def _extract_parts_batch(batch: dict) -> dict:
    stock_list = batch.get("stockList") or []
    total_paid = sum(s.get("paidMoney") or 0 for s in stock_list)
    total_items = sum(
        len(s.get("presaleGoodsRecords") or []) for s in stock_list
    )

    return {
        "orderBatchNo": batch.get("orderBatchNo"),
        "date": _ms_to_iso(batch.get("createTime")),
        "partsOrderCount": len(stock_list),
        "componentCount": total_items,
        "totalPaid": round(total_paid, 2),
    }


def _extract_parts_batch_detail(batch: dict) -> dict:
    stock_list = batch.get("stockList") or []

    return {
        "orderBatchNo": batch.get("orderBatchNo"),
        "date": _ms_to_iso(batch.get("createTime")),
        "partsOrders": [_extract_parts_order(s) for s in stock_list],
    }


def _extract_parts_order(stock: dict) -> dict:
    goods = stock.get("presaleGoodsRecords") or []

    return {
        "presaleOrderNo": stock.get("presaleOrderNo"),
        "orderStatus": _status_label(stock.get("orderStatus")),
        "payStatus": stock.get("payStatus"),
        "paidMoney": stock.get("paidMoney"),
        "presaleType": stock.get("presaleType"),
        "paymentMethod": stock.get("paymentTypeCode"),
        "paymentTime": _ms_to_iso(stock.get("paymentTime")),
        "completionTime": _ms_to_iso(stock.get("completionTime")),
        "shipmentNumber": stock.get("shipmentNumber"),
        "components": [_extract_component(g) for g in goods],
    }


def _extract_component(goods: dict) -> dict:
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
    return {10: "unpaid", 20: "paid", 30: "completed", 40: "cancelled"}.get(
        code, f"unknown({code})"
    )


def _goods_status_label(code: int | None) -> str:
    return {10: "pending", 20: "in_storage", 30: "cancelled"}.get(
        code, f"unknown({code})"
    )


def _ms_to_iso(ms: int | None) -> str | None:
    if ms is None:
        return None
    from datetime import datetime, timezone
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()
