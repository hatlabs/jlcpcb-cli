"""JLCPCB order data via official API."""

from jlcpcb_cli.core.client import JlcpcbClient

PCB_ORDER_DETAIL_PATH = "/overseas/openapi/pcb/order/detail"
PCB_WIP_PATH = "/overseas/openapi/pcb/wip/get"


def get_order(client: JlcpcbClient, batch_num: str) -> dict:
    """Get detailed order information for a batch."""
    result = client.api_post(PCB_ORDER_DETAIL_PATH, {"batchNum": batch_num})
    return _extract_order(batch_num, result["data"])


def _extract_order(batch_num: str, data: dict) -> dict:
    """Extract structured order data from the API response."""
    address = data.get("orderAddress") or {}
    items = data.get("orderItem") or []

    return {
        "batchNum": batch_num,
        "shippingMethod": data.get("shippingMethod"),
        "paymentMethod": data.get("paymentMethod"),
        "totalProduct": data.get("totalDummyMoney"),
        "totalShipping": data.get("totalCarriageMoney"),
        "totalOrder": data.get("totalMoney"),
        "address": {
            "company": address.get("companyName"),
            "street": address.get("linkAddress"),
            "city": address.get("city"),
            "province": address.get("province"),
            "postalCode": address.get("postalCode"),
            "country": address.get("country"),
        },
        "orders": [_extract_order_item(item) for item in items],
    }


def _extract_order_item(item: dict) -> dict:
    """Extract a single order item (PCB or SMT)."""
    order_type = item.get("orderType")
    pcb = item.get("pcbItem") or {}
    smt = item.get("smtItem") or {}

    if order_type == 1 and pcb.get("produceCode"):
        return _extract_pcb_item(pcb)
    elif smt.get("produceCode"):
        return _extract_smt_item(smt)
    else:
        return _extract_pcb_item(pcb)


def _extract_pcb_item(pcb: dict) -> dict:
    """Extract PCB order details."""
    return {
        "orderType": "pcb",
        "produceCode": pcb.get("produceCode"),
        "fileName": pcb.get("fileName"),
        "status": _order_status(pcb.get("orderStatus")),
        "quantity": pcb.get("count"),
        "orderDate": pcb.get("orderDate"),
        "deliveryTime": pcb.get("deliveryTime"),
        "buildTime": pcb.get("buildTime"),
        "price": pcb.get("price"),
        "fileUrl": pcb.get("orderFileUrl"),
        "specs": {
            "layers": pcb.get("layer"),
            "thickness": pcb.get("thickness"),
            "width": pcb.get("width"),
            "length": pcb.get("length"),
            "soldermaskColor": pcb.get("pcbColor"),
            "surfaceFinish": pcb.get("surfaceFinish"),
            "copperWeight": pcb.get("copperWeight"),
            "innerCopperWeight": pcb.get("insideCuprumThickness"),
            "material": pcb.get("materialDetails"),
            "panelized": bool(pcb.get("panelFlag")),
            "differentDesigns": pcb.get("differentDesign"),
            "halfHoles": pcb.get("halfHole"),
            "goldFinger": pcb.get("goldFinger"),
        },
    }


def _extract_smt_item(smt: dict) -> dict:
    """Extract SMT order details."""
    return {
        "orderType": "smt",
        "produceCode": smt.get("produceCode"),
        "fileName": smt.get("fileName"),
        "status": _order_status(smt.get("orderStatus")),
        "quantity": smt.get("count"),
        "orderDate": smt.get("orderDate"),
        "deliveryTime": smt.get("deliveryTime"),
        "buildTime": smt.get("buildTime"),
        "price": smt.get("price"),
        "fileUrl": smt.get("orderFileUrl"),
        "specs": {
            "width": smt.get("width"),
            "length": smt.get("length"),
            "stencilSide": smt.get("stencilSide"),
        },
    }


def _order_status(code: int | None) -> str:
    """Map numeric order status to label."""
    labels = {
        1: "unpaid",
        2: "pending_review",
        3: "in_production",
        4: "shipped",
        5: "completed",
        6: "cancelled",
    }
    if code is None:
        return "unknown"
    return labels.get(code, f"unknown({code})")
