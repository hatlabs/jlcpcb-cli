"""Order detail via JLCPCB web API."""

from jlcpcb_cli.core.web_client import WebClient

_ORDER_DETAIL_PATH = (
    "/overseas-core-platform/orderCenter/selectPersonOrderDetail"
)

# orderType values in the web API
_TYPE_PCB = 1
_TYPE_SMT = 4
_TYPE_3DP = 7


def get_order(client: WebClient, batch_num: str) -> dict:
    """Get detailed order information for a batch."""
    result = client.api_get(_ORDER_DETAIL_PATH, {"batchNum": batch_num})
    items = (result.get("data") or {}).get("unionOrderDetailVOList") or []
    return {
        "batchNum": batch_num,
        "orders": [_extract_order(item) for item in items],
    }


def _extract_order(item: dict) -> dict:
    order_type = item.get("orderType")
    rd = item.get("recordsDetail") or {}
    detail = rd.get("detail") or {}

    base = {
        "orderCode": rd.get("produceCode") or item.get("orderCode"),
        "orderType": _type_label(order_type),
        "status": rd.get("orderStatus"),
        "fileName": rd.get("orderFileName"),
        "quantity": rd.get("stencilNumber"),
        "orderDate": rd.get("orderDate"),
        "produceTime": rd.get("produceTime"),
        "deliveryTime": rd.get("deliveryTime"),
        "weight": rd.get("weight"),
        "productCost": rd.get("dummyMoney"),
        "shippingCost": rd.get("carriageMoney"),
        "totalCost": rd.get("paiclMoney"),
        "shippingMethod": rd.get("freightModeName"),
        "trackingNumber": rd.get("expressNo"),
        "paymentMethod": rd.get("paymentMode"),
        "fileUrl": rd.get("orderFileUrl"),
    }

    pcb = detail.get("pcbDetail")
    smt = detail.get("smtDetail")

    if pcb and order_type == _TYPE_PCB:
        base["specs"] = _extract_pcb_specs(pcb)
        base["costBreakdown"] = _extract_cost_breakdown(detail.get("orderCountTolls"))
    elif smt and order_type == _TYPE_SMT:
        base["specs"] = _extract_smt_specs(smt)
        base["orderCode"] = smt.get("smtOrderCode") or base["orderCode"]

    return base


def _extract_pcb_specs(pcb: dict) -> dict:
    return {
        "layers": pcb.get("stencilLayer"),
        "thickness": pcb.get("stencilPly"),
        "width": pcb.get("stencilWidth"),
        "length": pcb.get("stencilLength"),
        "quantity": pcb.get("stencilCounts"),
        "soldermaskColor": pcb.get("adornColor"),
        "silkscreenColor": pcb.get("charFontColor"),
        "surfaceFinish": pcb.get("adornPut"),
        "copperWeight": pcb.get("cuprumThickness"),
        "innerCopperWeight": pcb.get("insideCuprumThickness"),
        "material": pcb.get("showTagValue"),
        "impedanceControl": pcb.get("impedanceFlag") == "yes",
        "goldFingerBevel": pcb.get("goldFingerBevel"),
        "goldThickness": pcb.get("goldThickness"),
        "halfHole": pcb.get("halfHole") == "yes",
        "panelX": pcb.get("panelX"),
        "panelY": pcb.get("panelY"),
        "panelType": pcb.get("stencilType"),
    }


def _extract_smt_specs(smt: dict) -> dict:
    return {
        "pcbOrderCode": smt.get("produceOrderCode"),
        "pasteCount": smt.get("pasteNumber"),
        "patchSide": smt.get("patchLocation"),
        "bomFile": smt.get("bomFileName"),
        "posFile": smt.get("coordinateFileName"),
    }


def _extract_cost_breakdown(tolls: dict | None) -> dict | None:
    if not tolls:
        return None
    return {
        "pcbCost": tolls.get("projectMoney"),
        "surfaceFinishCost": tolls.get("adornPutMoney"),
        "stencilCost": tolls.get("stencilMoney"),
        "testCost": tolls.get("testsMoney"),
        "subtotal": tolls.get("dummyMoney"),
        "shippingCost": tolls.get("carriageMoney"),
        "total": tolls.get("paiclMoney"),
        "discount": tolls.get("discountMoney"),
    }


def _type_label(code: int | None) -> str:
    return {
        _TYPE_PCB: "pcb",
        _TYPE_SMT: "smt",
        _TYPE_3DP: "3dp",
    }.get(code, f"unknown({code})")
