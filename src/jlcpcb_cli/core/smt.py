"""SMT assembly BOM and Parts Manager inventory usage via the web API.

Both views hang off an SMT order's opaque access id, which the batch order
detail carries as ``smtOrderAccessId``.
"""

from jlcpcb_cli.core.web_client import JlcpcbAPIError, WebClient

_ORDER_DETAIL_PATH = (
    "/overseas-core-platform/orderCenter/selectPersonOrderDetail"
)
_BOM_PATH = "/overseas-pcb-order/v1/smtOrder/getSmtOrderDetail"
_USAGE_PATH = "/overseas-pcb-order/v1/smtOrder/querySmtComponent"

_TYPE_SMT = 4


def get_bom(client: WebClient, batch_num: str) -> dict:
    """Get the per-component BOM of every SMT order in a batch."""
    orders = []
    for smt in _batch_smt_orders(client, batch_num):
        data = client.api_get(_BOM_PATH, {"smtOrderNum": smt["accessId"]})
        data = data.get("data") or {}
        components = [
            _extract_bom_component(row) for row in data.get("smtBomResult") or []
        ]
        orders.append(
            {
                "orderCode": smt["orderCode"],
                "quantity": data.get("patchNum", smt["quantity"]),
                "assemblySide": data.get("patchLocation"),
                "suppliedByJlcpcbTotal": round(
                    sum(c["lineTotal"] or 0 for c in components), 2
                ),
                "totalPrice": data.get("totalPrice"),
                "components": components,
            }
        )
    return {"batchNum": batch_num, "smtOrders": orders}


def get_usage(client: WebClient, batch_num: str) -> dict:
    """Get the Parts Manager stock each SMT order in a batch consumed."""
    orders = []
    for smt in _batch_smt_orders(client, batch_num):
        data = client.api_post(_USAGE_PATH, {"smtOrderNum": smt["accessId"]})
        data = data.get("data") or {}
        rows = [_extract_usage_row(r) for r in data.get("previouslyList") or []]
        order = {
            "orderCode": smt["orderCode"],
            "totalFromInventory": round(
                sum(r["totalMoney"] or 0 for r in rows), 2
            ),
            "fromInventory": rows,
        }
        # Consigned stock (parts the customer ships to JLCPCB) has never been
        # observed in a response, so its fields are unmapped. Pass the rows
        # through rather than drop usage data silently.
        consigned = data.get("consignedList") or []
        if consigned:
            order["consigned"] = consigned
        orders.append(order)
    return {"batchNum": batch_num, "smtOrders": orders}


def _batch_smt_orders(client: WebClient, batch_num: str) -> list[dict]:
    result = client.api_get(_ORDER_DETAIL_PATH, {"batchNum": batch_num})
    orders = _smt_orders(result.get("data") or {})
    if not orders:
        raise JlcpcbAPIError(f"Batch {batch_num} has no SMT order")
    return orders


def _smt_orders(data: dict) -> list[dict]:
    orders = []
    for item in data.get("unionOrderDetailVOList") or []:
        if item.get("orderType") != _TYPE_SMT:
            continue
        records = item.get("recordsDetail") or {}
        smt = (records.get("detail") or {}).get("smtDetail") or {}
        if not smt.get("smtOrderAccessId"):
            continue
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
    ``unitPrice`` and ``lineTotal`` cover only the units JLCPCB supplies;
    units drawn from Parts Manager stock were paid for in the pre-order.
    """
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
        "unitsUsed": row.get("componentRealCount"),
        "lossUnits": row.get("lossNumber"),
        "source": _source_label(row.get("componentSource")),
        "unitsFromPreorder": row.get("presaleStock"),
        "unitsFromJlcpcb": row.get("shopStock"),
        "unitsFree": row.get("freeStock"),
        "unitPrice": row.get("unitPrice"),
        "lineTotal": row.get("extPrice"),
    }


def _extract_usage_row(row: dict) -> dict:
    return {
        "componentCode": row.get("componentCode"),
        "model": row.get("componentModel"),
        "preorderBatchNo": row.get("orderBatchNo"),
        "presaleOrderNo": row.get("presaleOrderNo"),
        "quantity": row.get("componentNum"),
        "unitPrice": row.get("settleGoodsPrice"),
        "totalMoney": row.get("componentMoney"),
        "tariff": row.get("tariffMoney"),
        "remaining": row.get("remainNumber"),
    }


def _source_label(code: str | None) -> str:
    return {
        "preSale": "preorder",
        "shop": "jlcpcb",
        "preSaleAndShop": "mixed",
    }.get(code, f"unknown({code})")
