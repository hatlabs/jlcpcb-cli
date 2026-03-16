"""JLCPCB Components API — public and private library."""

from jlcpcb_cli.core.client import JlcpcbClient

COMPONENT_INFO_PATH = "/overseas/openapi/component/getComponentInfos"


def list_components(
    client: JlcpcbClient,
    *,
    page: int = 1,
    limit: int = 30,
) -> dict:
    """List components from the JLCPCB component library."""
    result = client.api_post(
        COMPONENT_INFO_PATH, {"pageNum": page, "pageSize": limit}
    )

    data = result["data"]
    items = data.get("componentInfos") or []

    return {
        "pagination": {
            "page": page,
            "pageSize": limit,
            "total": len(items),  # API doesn't return total count
        },
        "components": [_extract_component(c) for c in items],
    }


def _extract_component(comp: dict) -> dict:
    """Extract component info from API response."""
    return {
        "lcscPart": comp.get("lcscPart"),
        "mfrPart": comp.get("mfrPart"),
        "manufacturer": comp.get("manufacturer"),
        "category": comp.get("firstCategory"),
        "subcategory": comp.get("secondCategory"),
        "package": comp.get("package"),
        "solderJoints": comp.get("solderJoint"),
        "libraryType": comp.get("libraryType"),
        "description": comp.get("description"),
        "stock": comp.get("stock"),
        "price": comp.get("price"),
        "datasheet": comp.get("datasheet"),
    }
