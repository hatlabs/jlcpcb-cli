"""Personal parts inventory at JLCPCB via web API."""

import time

from jlcpcb_cli.core.web_client import WebClient

_INVENTORY_PATH = (
    "/overseas-smt-component-order-platform/v1"
    "/overseasSmtComponentOrder/myLibrary/getCustomerComponentStock"
)


def list_inventory(
    client: WebClient,
    *,
    search: str = "",
    page: int = 1,
    limit: int = 30,
) -> dict:
    """List components stored at JLCPCB."""
    result = client.api_get(
        _INVENTORY_PATH,
        {
            "pageNum": str(page),
            "pageSize": str(limit),
            "keyWord": search,
            "_t": str(int(time.time() * 1000)),
        },
    )

    data = result.get("data") or {}
    items = data.get("list") or []

    return {
        "pagination": {
            "page": page,
            "pageSize": limit,
            "total": data.get("total", 0),
        },
        "components": [_extract_component(c) for c in items],
    }


def _extract_component(comp: dict) -> dict:
    return {
        "lcscPart": comp.get("componentCode"),
        "mfrPart": comp.get("componentModel"),
        "manufacturer": comp.get("componentBrand"),
        "category": comp.get("componentType"),
        "package": comp.get("componentSpecification"),
        "description": comp.get("description"),
        "stock": comp.get("privateStockCount"),
        "rohs": bool(comp.get("rohsFlag")),
    }
