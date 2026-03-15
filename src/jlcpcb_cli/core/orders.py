"""JLCPCB order data fetching and extraction."""

import time

from jlcpcb_cli.core.client import JlcpcbClient
from jlcpcb_cli.core.util import ms_to_iso as _ms_to_iso


def list_orders(
    client: JlcpcbClient,
    *,
    status: str | None = None,
    search: str | None = None,
    page: int = 1,
    limit: int = 15,
) -> dict:
    """List order batches with pagination.

    Each "batch" groups related orders (e.g., PCB + SMT in same shipment).
    """
    data = {
        "businessType": None,
        "orderStatisticsType": None,
        "searchKey": search or None,
        "businessTypeStr": None,
        "waitPayOrSupplement": None,
        "waitBizConfirm": None,
        "inProduction": None,
        "shipped": None,
        "batchStatus": _map_status_filter(status),
        "fromType": 3,
        "orderBusinessSystemType": "0",
        "timeStamp": int(time.time() * 1000),
        "currentPage": page,
        "pageRows": limit,
        "prevBatchNum": None,
    }

    result = client.api_post(
        "/api/overseas-core-platform/orderCenter/selectPersonBatch", data
    )

    page_data = result["data"]
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


def get_order(client: JlcpcbClient, batch_num: str) -> dict:
    """Get detailed order information for a batch."""
    result = client.api_post(
        "/api/overseas-core-platform/orderCenter/selectPersonOrder",
        {"batchNum": batch_num, "paySuccess": True},
    )

    data = result["data"]
    orders = data.get("unionOrderInfoVOList") or []

    return {
        "batchNum": batch_num,
        "orders": [_extract_order_detail(o) for o in orders],
    }


def _map_status_filter(status: str | None) -> str | None:
    """Map CLI status names to API batch status values."""
    if status is None or status == "all":
        return None
    mapping = {
        "shipped": "shipped",
        "production": "inProduction",
        "cancelled": "cancelled",
        "unpaid": "waitPay",
        "review": "waitReview",
    }
    return mapping.get(status)


def _extract_batch(batch: dict) -> dict:
    """Extract a summary from a batch list item."""
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


def _extract_order_detail(order: dict) -> dict:
    """Extract structured order detail from a unionOrderInfoVO."""
    order_type = order.get("orderTypeStr", "")
    record = order.get("myOrdersRecord") or {}
    tdp_info = order.get("tdpOrderInfoDTO") or {}

    base = {
        "orderCode": order.get("orderCode"),
        "orderType": order_type,
        "status": order.get("orderStatus"),
        "quantity": order.get("quantity"),
        "createTime": _ms_to_iso(order.get("createTime")),
        "payTime": _ms_to_iso(order.get("payTime")),
        "deliverTime": _ms_to_iso(order.get("deliverTime")),
    }

    if order_type == "order_pcb":
        base.update(_extract_pcb_detail(record))
    elif order_type == "order_smt":
        base.update(_extract_smt_detail(record))
    elif order_type == "order_tdp":
        base.update(_extract_tdp_detail(tdp_info))

    return base


def _extract_files(record: dict) -> dict:
    """Extract downloadable file URLs from an order record."""
    files = {}
    if record.get("orderImgUrl"):
        files["boardImage"] = record["orderImgUrl"]
    if record.get("orderFileUrl"):
        files["gerbers"] = record["orderFileUrl"]
    if record.get("bomFileUrl"):
        files["bom"] = record["bomFileUrl"]
    if record.get("coordinateFileUrl"):
        files["coordinates"] = record["coordinateFileUrl"]
    return files or None


def _extract_pcb_detail(record: dict) -> dict:
    """Extract PCB-specific order details."""
    detail = record.get("detail") or {}
    pcb = detail.get("pcbDetail") or {}
    costs = detail.get("orderCountTolls") or {}

    return {
        "fileName": record.get("orderFileName"),
        "produceCode": record.get("produceCode"),
        "trackingNumber": record.get("expressNo"),
        "weight": record.get("weight"),
        "shippingMethod": record.get("freightModeName"),
        "company": record.get("companyName"),
        "country": record.get("country"),
        "files": _extract_files(record),
        "specs": {
            "layers": pcb.get("stencilLayer"),
            "thickness": pcb.get("stencilPly"),
            "width": pcb.get("stencilWidth"),
            "length": pcb.get("stencilLength"),
            "quantity": pcb.get("stencilCounts"),
            "soldermaskColor": pcb.get("adornColor"),
            "silkscreenColor": pcb.get("charFontColor"),
            "surfaceFinish": pcb.get("adornPut"),
            "copperWeight": pcb.get("cuprumThickness"),
            "impedanceControl": pcb.get("impedanceFlag"),
        },
        "costs": {
            "engineering": costs.get("projectMoney"),
            "pcb": costs.get("dummyMoney"),
            "surfaceFinish": costs.get("adornPutMoney"),
            "stencil": costs.get("stencilMoney"),
            "testing": costs.get("testsMoney"),
            "subtotal": costs.get("paiclMoney"),
            "shipping": costs.get("carriageMoney"),
            "tariff": costs.get("tariffChargesMoney"),
        },
    }


def _extract_smt_detail(record: dict) -> dict:
    """Extract SMT assembly-specific order details."""
    return {
        "fileName": record.get("orderFileName"),
        "produceCode": record.get("produceCode"),
        "trackingNumber": record.get("expressNo"),
        "bomFileName": record.get("bomFileName"),
        "coordinateFileName": record.get("coordinateFileName"),
        "shippingMethod": record.get("freightModeName"),
        "files": _extract_files(record),
        "costs": {
            "engineering": record.get("projectMoney"),
            "assembly": record.get("dummyMoney"),
            "subtotal": record.get("paiclMoney"),
            "shipping": record.get("carriageMoney"),
            "tariff": record.get("tariffChargesMoney"),
        },
    }


def _extract_tdp_detail(tdp: dict) -> dict:
    """Extract 3D printing-specific order details."""
    product = tdp.get("productInfo") or {}

    return {
        "fileName": tdp.get("fileName"),
        "material": product.get("materialName"),
        "color": product.get("materialColor"),
        "technology": product.get("materialTechnicsName"),
        "quantity": product.get("quantity"),
        "dimensions": {
            "x": product.get("sizeX"),
            "y": product.get("sizeY"),
            "z": product.get("sizeZ"),
        },
        "costs": {
            "product": tdp.get("productFee"),
            "subtotal": tdp.get("orderTotal"),
            "shipping": tdp.get("shippingCharge"),
            "tariff": tdp.get("tariffChargesMoney"),
        },
    }
