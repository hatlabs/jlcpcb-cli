"""Order listing via JLCPCB web API (browser-based).

The official API only supports order detail by batch number.
Order listing requires the web API, accessed through a headless browser.
"""

import time

from jlcpcb_cli.core.browser import BrowserClient


def list_orders(
    browser: BrowserClient,
    *,
    status: str | None = None,
    search: str | None = None,
    page: int = 1,
    limit: int = 15,
) -> dict:
    """List order batches via the web API."""
    data = {
        "businessType": None,
        "orderStatisticsType": None,
        "searchKey": search or None,
        "businessTypeStr": None,
        "waitPayOrSupplement": None,
        "waitBizConfirm": None,
        "inProduction": None,
        "shipped": None,
        "batchStatus": _map_status(status),
        "fromType": 3,
        "orderBusinessSystemType": "0",
        "timeStamp": int(time.time() * 1000),
        "currentPage": page,
        "pageRows": limit,
        "prevBatchNum": None,
    }

    result = browser.api_post(
        "/overseas-core-platform/orderCenter/selectPersonBatch", data
    )

    page_data = result.get("data") or {}
    batches = page_data.get("list") or []

    return {
        "pagination": {
            "page": page_data.get("pageNum", page),
            "pageSize": page_data.get("pageSize", limit),
            "total": page_data.get("total", 0),
            "pages": page_data.get("pages", 0),
            "hasNextPage": page_data.get("hasNextPage", False),
        },
        "orders": [_extract_batch(b) for b in batches],
    }


def _map_status(status: str | None) -> str | None:
    if status is None or status == "all":
        return None
    return {
        "shipped": "shipped",
        "production": "inProduction",
        "cancelled": "cancelled",
        "unpaid": "waitPay",
        "review": "waitReview",
    }.get(status)


def _extract_batch(batch: dict) -> dict:
    pay_vo = batch.get("payUnionSecondVO") or {}
    express_vo = batch.get("expressInfoVO") or {}
    currency_vo = batch.get("settleCurrencyInfoVO") or {}
    order_items = pay_vo.get("orderInfoVOList") or []

    return {
        "batchNum": batch.get("batchNum"),
        "date": _ms_to_iso(batch.get("batchCreateTime")),
        "status": batch.get("batchStatus"),
        "orderTypes": [o.get("orderType") for o in order_items],
        "orderCodes": [o.get("orderCode") for o in order_items],
        "productFee": pay_vo.get("productFee"),
        "shippingFee": pay_vo.get("carriageFee"),
        "tariffFee": pay_vo.get("tariffFee"),
        "totalFee": pay_vo.get("totalFee"),
        "currency": currency_vo.get("settleCurrency"),
        "exchangeRate": currency_vo.get("settleExchangeRate"),
        "trackingNumber": express_vo.get("expressNo"),
        "shippingMethod": express_vo.get("freightModeName"),
        "paymentMethod": order_items[0].get("payType") if order_items else None,
    }


def _ms_to_iso(ms: int | None) -> str | None:
    if ms is None:
        return None
    from datetime import datetime, timezone
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()
