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
    data = result.get("data") or {}
    items = data.get("unionOrderDetailVOList") or []
    address = data.get("orderAddress") or {}

    out: dict = {
        "batchNum": batch_num,
    }

    # Batch-level totals (if the web API provides them)
    if data.get("totalMoney") is not None:
        out["totalOrder"] = data["totalMoney"]
    if data.get("totalDummyMoney") is not None:
        out["totalProduct"] = data["totalDummyMoney"]
    if data.get("totalCarriageMoney") is not None:
        out["totalShipping"] = data["totalCarriageMoney"]
    if data.get("shippingMethod") is not None:
        out["shippingMethod"] = data["shippingMethod"]
    if data.get("paymentMethod") is not None:
        out["paymentMethod"] = data["paymentMethod"]
    if address:
        out["address"] = {
            "company": address.get("companyName"),
            "street": address.get("linkAddress"),
            "city": address.get("city"),
            "province": address.get("province"),
            "postalCode": address.get("postalCode"),
            "country": address.get("country"),
        }

    out["orders"] = [_extract_order(item) for item in items]
    return out


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
