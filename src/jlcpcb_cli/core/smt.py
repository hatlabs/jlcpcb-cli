"""SMT assembly BOM and Parts Manager inventory usage via the web API.

Both views hang off an SMT order's opaque access id, which the batch order
detail carries as ``smtOrderAccessId``.
"""

from jlcpcb_cli.core.orders import ORDER_DETAIL_PATH, TYPE_SMT
from jlcpcb_cli.core.web_client import JlcpcbAPIError, WebClient

_BOM_PATH = "/overseas-pcb-order/v1/smtOrder/getSmtOrderDetail"
_USAGE_PATH = "/overseas-pcb-order/v1/smtOrder/querySmtComponent"


def get_bom(client: WebClient, batch_num: str) -> dict:
    """Get the per-component BOM of every SMT order in a batch."""
    orders = []
    for smt in _batch_smt_orders(client, batch_num):
        data = _payload(
            client.api_get(_BOM_PATH, {"smtOrderNum": smt["accessId"]}),
            "smtBomResult",
            smt["orderCode"],
        )
        components = [
            _extract_bom_component(row) for row in data["smtBomResult"]
        ]
        orders.append(
            {
                "orderCode": smt["orderCode"],
                "quantity": data.get("patchNum") or smt["quantity"],
                "assemblySide": data.get("patchLocation"),
                "suppliedByJlcpcbTotal": round(
                    sum(c["totalMoney"] or 0 for c in components), 2
                ),
                "components": components,
            }
        )
    return {"batchNum": batch_num, "smtOrders": orders}


def get_usage(client: WebClient, batch_num: str) -> dict:
    """Get the Parts Manager stock each SMT order in a batch consumed."""
    orders = []
    for smt in _batch_smt_orders(client, batch_num):
        data = _payload(
            client.api_post(_USAGE_PATH, {"smtOrderNum": smt["accessId"]}),
            "previouslyList",
            smt["orderCode"],
        )
        rows = [_extract_usage_row(r) for r in data["previouslyList"]]
        orders.append(
            {
                "orderCode": smt["orderCode"],
                "totalFromInventory": round(
                    sum(r["totalPrice"] or 0 for r in rows), 2
                ),
                "fromInventory": rows,
                # Consigned stock (parts the customer ships to JLCPCB) has
                # never appeared in a response, so its fields are unmapped.
                # The rows pass through rather than being dropped, which
                # would understate what the assembly consumed.
                "consigned": data.get("consignedList") or [],
            }
        )
    return {"batchNum": batch_num, "smtOrders": orders}


def _payload(result: dict, list_key: str, order_code: str) -> dict:
    """Return the response payload, refusing one without its component list.

    An absent list is not an empty one: the totals derived from it would
    report a real assembly as costing nothing.
    """
    data = result.get("data") or {}
    if data.get(list_key) is None:
        raise JlcpcbAPIError(
            f"SMT order {order_code}: response carries no {list_key}"
        )
    return data


def _batch_smt_orders(client: WebClient, batch_num: str) -> list[dict]:
    result = client.api_get(ORDER_DETAIL_PATH, {"batchNum": batch_num})
    orders = _smt_orders(result.get("data") or {})
    if not orders:
        raise JlcpcbAPIError(f"Batch {batch_num} has no SMT order")
    return orders


def _smt_orders(data: dict) -> list[dict]:
    orders = []
    for item in data.get("unionOrderDetailVOList") or []:
        if item.get("orderType") != TYPE_SMT:
            continue
        records = item.get("recordsDetail") or {}
        smt = (records.get("detail") or {}).get("smtDetail") or {}
        if not smt.get("smtOrderAccessId"):
            raise JlcpcbAPIError(
                f"SMT order {smt.get('smtOrderCode')} has no access id, "
                "so its BOM cannot be read"
            )
        orders.append(
            {
                "orderCode": smt.get("smtOrderCode"),
                "accessId": smt["smtOrderAccessId"],
                "quantity": records.get("stencilNumber"),
            }
        )
    return orders


def _extract_bom_component(row: dict) -> dict:
    """Map one BOM row.

    ``componentNum`` counts placements over the whole order, and
    ``componentRealCount`` adds the loss allowance JLCPCB reserves.
    ``unitPrice`` and ``totalMoney`` cover only the units JLCPCB supplies;
    units drawn from Parts Manager stock were paid for in the pre-order.
    """
    used = row.get("componentRealCount")
    preorder = row.get("presaleStock") or 0
    jlcpcb = row.get("shopStock") or 0
    free = row.get("freeStock") or 0

    return {
        "componentCode": row.get("componentCode"),
        "name": row.get("componentNameEn"),
        "model": row.get("componentModelEn"),
        "description": row.get("describe"),
        "comment": row.get("comment"),
        "footprint": row.get("footPrint"),
        "library": row.get("componentLibraryType"),
        "process": row.get("assemblyProcess"),
        "side": row.get("patchLocation"),
        "designators": row.get("designator"),
        "placements": row.get("componentNum"),
        "unitsUsed": used,
        "lossUnits": row.get("lossNumber"),
        "unitsFromPreorder": preorder,
        "unitsFromJlcpcb": jlcpcb,
        "unitsFree": free,
        "unitsUnattributed": (
            used - preorder - jlcpcb - free if used is not None else None
        ),
        "unitPrice": row.get("unitPrice"),
        "totalMoney": row.get("extPrice"),
    }


def _extract_usage_row(row: dict) -> dict:
    return {
        "componentCode": row.get("componentCode"),
        "model": row.get("componentModel"),
        "smtOrderCode": row.get("smtOrderCode"),
        "orderBatchNo": row.get("orderBatchNo"),
        "presaleOrderNo": row.get("presaleOrderNo"),
        "quantity": row.get("componentNum"),
        "unitPrice": row.get("settleGoodsPrice"),
        "totalPrice": row.get("componentMoney"),
        "tariff": row.get("tariffMoney"),
        "remaining": row.get("remainNumber"),
    }
