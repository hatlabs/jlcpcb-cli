"""Tests for order data extraction."""

from jlcpcb_cli.core.orders import _extract_order, _order_status


def test_order_status():
    assert _order_status(1) == "unpaid"
    assert _order_status(5) == "completed"
    assert _order_status(None) == "unknown"
    assert _order_status(99) == "unknown(99)"


def test_extract_order():
    data = {
        "orderAddress": {
            "companyName": "Hat Labs Oy",
            "linkAddress": "Street 1",
            "city": "Helsinki",
            "province": "Helsinki",
            "postalCode": "00840",
            "country": "FI",
        },
        "shippingMethod": "FEDEX EXPRESS",
        "paymentMethod": "ADYEN_CARD",
        "totalDummyMoney": 421.86,
        "totalCarriageMoney": 59.25,
        "totalMoney": 118.5,
        "orderItem": [
            {
                "orderType": 1,
                "pcbItem": {
                    "fileName": "gerbers_Y41",
                    "buildTime": 70,
                    "count": 10,
                    "orderDate": "2025-12-28 21:36:39",
                    "produceCode": "Y41",
                    "orderStatus": 5,
                    "price": 86.7,
                    "layer": 4,
                    "width": 194.3,
                    "length": 255.3,
                    "thickness": 1.6,
                    "pcbColor": "Green",
                    "surfaceFinish": "ENIG",
                    "copperWeight": 1.0,
                    "materialDetails": "FR4-Standard Tg 140C",
                    "orderFileUrl": "/file/download?uuid=abc",
                },
                "smtItem": {},
            }
        ],
    }

    result = _extract_order("W123", data)

    assert result["batchNum"] == "W123"
    assert result["shippingMethod"] == "FEDEX EXPRESS"
    assert result["totalProduct"] == 421.86
    assert len(result["orders"]) == 1

    pcb = result["orders"][0]
    assert pcb["orderType"] == "pcb"
    assert pcb["produceCode"] == "Y41"
    assert pcb["status"] == "completed"
    assert pcb["specs"]["layers"] == 4
    assert pcb["specs"]["surfaceFinish"] == "ENIG"
