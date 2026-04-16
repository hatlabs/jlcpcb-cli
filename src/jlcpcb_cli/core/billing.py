"""Billing data retrieval via JLCPCB web API.

Provides access to the billing page data: batch payment history,
individual transaction receipts/credit notes, and invoices.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from jlcpcb_cli.core.web_client import WebClient

_BILLING_LIST_PATH = (
    "/overseas-pcb-order/v1/billing/queryBillingBatchNumList"
)
_BILLING_DETAIL_PATH = "/overseas-pcb-order/v1/billing/queryBillingDetail"
_MFG_INVOICE_PATH = "/overseas-core-platform/orderCenter/invoiceOrder"
_PARTS_INVOICE_PATH = (
    "/overseas-smt-component-order-platform/v1"
    "/overseasSmtComponentOrder/presaleOrder/getInvoiceInfo"
)


def list_billing(
    client: WebClient,
    *,
    search: str | None = None,
    page: int = 1,
    limit: int = 10,
) -> dict:
    """List billing batch orders with payment transaction summaries."""
    data = {
        "pageNum": page,
        "pageSize": limit,
        "queryTimeType": None,
        "batchNum": search or None,
        "startTime": None,
        "endTime": None,
    }

    result = client.api_post(_BILLING_LIST_PATH, data)
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
        "batches": [_extract_batch(b) for b in batches],
    }


def get_billing_detail(
    client: WebClient,
    batch_num: str,
    *,
    download_dir: str | None = None,
) -> dict:
    """Get full billing detail for a batch: summary + receipt for each transaction."""
    # Fetch the batch from the list endpoint filtered by batch number
    list_data = {
        "pageNum": 1,
        "pageSize": 10,
        "queryTimeType": None,
        "batchNum": batch_num,
        "startTime": None,
        "endTime": None,
    }
    result = client.api_post(_BILLING_LIST_PATH, list_data)
    page_data = result.get("data") or {}
    batches = page_data.get("list") or []

    if not batches:
        raise ValueError(f"Batch {batch_num} not found in billing history")

    batch = batches[0]
    batch_info = _extract_batch(batch)

    # Fetch detail for each transaction
    transactions = batch.get("billingPaymentInfoList") or []
    details = []
    for txn in transactions:
        detail_data = {
            "bizId": txn.get("bizId"),
            "tradeId": txn.get("tradeId"),
            "useSelected": batch.get("useSelected", 0),
            "paymentType": txn.get("paymentType"),
            "batchNum": txn.get("batchNum") or batch_num,
        }
        detail_result = client.api_post(_BILLING_DETAIL_PATH, detail_data)
        detail = detail_result.get("data") or {}
        details.append(_extract_detail(detail, txn))

    batch_info["details"] = details

    if download_dir is not None:
        _save_details(details, batch_num, download_dir)

    return batch_info


def get_billing_invoice(
    client: WebClient,
    batch_num: str,
    *,
    download_dir: str | None = None,
) -> dict:
    """Get invoice data for a billing batch.

    Dispatches to the correct endpoint based on batch prefix:
    W-prefix → manufacturing invoice, POB-prefix → parts invoice.
    """
    if batch_num.startswith("POB"):
        result = client.api_post(
            _PARTS_INVOICE_PATH,
            {
                "addressType": "billing",
                "orderBatchAccessId": "null",
                "orderBatchNo": batch_num,
            },
        )
        invoice = _extract_parts_invoice(result.get("data") or {})
    else:
        result = client.api_post(
            _MFG_INVOICE_PATH,
            {"batchNum": batch_num, "orderPay": "yes"},
        )
        invoice = _extract_mfg_invoice(result.get("data") or {})

    if download_dir is not None:
        _save_invoice(invoice, batch_num, download_dir)

    return invoice


# --- Extraction helpers ---


def _decrypt_or_none(value: str | None) -> str | None:
    """Return None for {secret}-encrypted fields, pass through plain text."""
    if value and str(value).startswith("{secret}"):
        return None
    return value


def _ms_to_iso(ms: int | float | None) -> str | None:
    if ms is None:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()


def _extract_batch(batch: dict) -> dict:
    transactions = batch.get("billingPaymentInfoList") or []
    return {
        "batchNum": batch.get("batchNum"),
        "amount": batch.get("amount"),
        "status": batch.get("status"),
        "date": _ms_to_iso(batch.get("updateDate")),
        "useSelected": batch.get("useSelected"),
        "queryType": batch.get("queryType"),
        "transactions": [_extract_transaction(t) for t in transactions],
    }


def _extract_transaction(txn: dict) -> dict:
    return {
        "bizId": txn.get("bizId"),
        "tradeId": txn.get("tradeId"),
        "paymentType": txn.get("paymentType"),
        "orderType": txn.get("orderType"),
        "amount": txn.get("amount"),
        "payMethod": txn.get("payMethod"),
        "settleCurrency": txn.get("settleCurrency"),
        "orderNumber": txn.get("orderNumber"),
        "date": _ms_to_iso(txn.get("updateTime")),
    }


def _extract_detail(detail: dict, txn: dict) -> dict:
    """Extract receipt/credit note detail from queryBillingDetail response."""
    addr = detail.get("billingAddressInfo") or {}
    base = detail.get("baseInfo") or {}
    fee_summary = detail.get("feeSummaryInfo") or {}
    order_fees = detail.get("orderFeeInfo") or []

    line_items = []
    for item in order_fees:
        line_items.append({
            "description": item.get("description"),
            "orderNumber": item.get("orderNumber"),
            "part": item.get("part"),
            "componentCode": item.get("componentCode"),
            "quantity": item.get("quantity"),
            "unitPrice": item.get("unitPrice"),
            "totalPrice": item.get("totalPrice"),
        })

    return {
        "paymentType": base.get("paymentType") or txn.get("paymentType"),
        "orderType": txn.get("orderType"),
        "amount": txn.get("amount"),
        "date": _ms_to_iso(txn.get("updateTime")),
        "payMethod": base.get("paymentMethod") or txn.get("payMethod"),
        "payChannelDetail": base.get("payChannelDetail"),
        "currency": base.get("settleCurrency") or txn.get("settleCurrency"),
        "billingAddress": {
            "company": addr.get("companyName"),
            "billingName": addr.get("billingName"),
            "vatNo": addr.get("vatNumber"),
            "country": addr.get("country"),
            "state": addr.get("state"),
            "city": addr.get("city"),
            "postalCode": addr.get("postCode"),
        },
        "feeSummary": {
            "subtotal": fee_summary.get("subTotal"),
            "shipping": fee_summary.get("shipping"),
            "discount": fee_summary.get("disCount"),
            "taxes": fee_summary.get("taxes"),
            "saleTaxes": fee_summary.get("saleTaxes"),
            "handlingPrice": fee_summary.get("handlingPrice"),
            "grandTotal": fee_summary.get("grandTotal"),
        },
        "lineItems": line_items,
    }


def _extract_mfg_invoice(data: dict) -> dict:
    """Extract manufacturing invoice from invoiceOrder response."""
    currency_vo = data.get("settleCurrencyInfoVO") or {}
    items = data.get("invoiceListResponseList") or []
    presale_items = data.get("presaleDetailResultVOList") or []

    line_items = []
    for item in items:
        line_items.append({
            "orderCode": item.get("orderCode"),
            "orderType": item.get("orderType"),
            "specifications": item.get("specifications"),
            "orderFileName": item.get("orderFileName"),
            "quantity": item.get("number"),
            "unitPrice": item.get("unitMoney"),
            "totalPrice": item.get("totalMoney"),
            "shippingFee": item.get("carriageMoney"),
            "tariffFee": item.get("tariffChargesMoney"),
            "presaleMoney": item.get("presaleMoney"),
            "totalWithFees": item.get("paiclMoney"),
        })

    presale_details = []
    for p in presale_items:
        presale_details.append({
            "componentCode": p.get("componentCode"),
            "smtOrderCode": p.get("smtOrderCode"),
            "orderBatchNo": p.get("orderBatchNo"),
            "quantity": p.get("componentNum"),
            "unitPrice": p.get("settleGoodsPrice"),
            "totalPrice": p.get("componentMoney"),
        })

    return {
        "type": "manufacturing",
        "invoiceNo": data.get("invoiceNo"),
        "invoiceDate": data.get("invoiceDate"),
        "batchNum": data.get("batchNum"),
        "typeOfTrade": data.get("typeOfTrade"),
        "trackingNumber": data.get("expressNo"),
        "shippingMethod": data.get("freightModeName"),
        "billingTo": {
            "name": _decrypt_or_none(data.get("manBilling")),
            "company": _decrypt_or_none(data.get("companyNameBilling")),
            "country": data.get("countryBilling"),
            "state": data.get("provinceBilling"),
            "city": data.get("cityBilling"),
            "postalCode": data.get("postCodeBilling"),
            "vatNo": data.get("taxVatBilling"),
            "eoriNo": data.get("eoriNoBilling"),
        },
        "shipTo": {
            "name": _decrypt_or_none(data.get("man")),
            "country": data.get("country"),
            "state": _decrypt_or_none(data.get("province")),
            "city": data.get("city"),
            "postalCode": data.get("postCode"),
        },
        "costs": {
            "productMoney": data.get("productMoney"),
            "carriageMoney": data.get("carriageMoney"),
            "tariffChargesMoney": data.get("tariffChargesMoney"),
            "presaleMoney": data.get("presaleMoney"),
            "discount": data.get("discount"),
            "subTotalMoney": data.get("subTotalMoney"),
            "totalMoney": data.get("totalMoney"),
        },
        "currency": currency_vo.get("settleCurrency"),
        "exchangeRate": currency_vo.get("settleExchangeRate"),
        "lineItems": line_items,
        "presaleDetails": presale_details,
    }


def _extract_parts_invoice(data: dict) -> dict:
    """Extract parts invoice from getInvoiceInfo response."""
    components = data.get("componentGoodsVOList") or []

    line_items = []
    for c in components:
        line_items.append({
            "componentCode": c.get("componentCode"),
            "componentName": c.get("componentName"),
            "model": c.get("componentModel"),
            "brand": c.get("componentBrand"),
            "specification": c.get("componentSpecification"),
            "quantity": c.get("presaleNumber"),
            "settledQuantity": c.get("settlePresaleNumber"),
            "unitPrice": c.get("goodsPrice"),
            "totalPrice": c.get("goodsMoney"),
            "paidAmount": c.get("goodsPaidMoney"),
            "status": c.get("goodsStatus"),
            "supplementStatus": c.get("supplementStatus"),
            "refundStatus": c.get("refundStatus"),
        })

    return {
        "type": "parts",
        "invoiceNo": data.get("invoiceNo"),
        "invoiceDate": data.get("invoiceDate"),
        "batchNum": data.get("orderBatchNo"),
        "customerCode": data.get("customerCode"),
        "billingTo": {
            "company": data.get("companyName"),
            "name": f"{data.get('firstName', '')} {data.get('lastName', '')}".strip(),
            "country": data.get("countryName"),
            "state": data.get("stateName"),
            "city": data.get("cityName"),
            "street": data.get("streetAddress"),
            "postalCode": data.get("postalCode"),
            "eoriNumber": data.get("eoriNumber"),
        },
        "costs": {
            "advanceChargeMoney": data.get("advanceChargeMoney"),
            "totalPayment": data.get("totalPayment"),
            "totalOperateFee": data.get("totalOperateFee"),
            "totalTariffFee": data.get("totalTariffFee"),
            "totalCarriageFee": data.get("totalCarriageFee"),
            "paidMoney": data.get("paidMoney"),
        },
        "lineItems": line_items,
    }


def _save_details(details: list[dict], batch_num: str, directory: str) -> None:
    """Save each transaction receipt/credit note as PDF + JSON."""
    from jlcpcb_cli.core.pdf import save_receipt_pdf

    path = Path(directory)
    path.mkdir(parents=True, exist_ok=True)
    for i, detail in enumerate(details, 1):
        ptype = (detail.get("paymentType") or "unknown").lower().replace(" ", "-")
        base = f"{batch_num}-{i:02d}-{ptype}"

        # Save PDF
        save_receipt_pdf(detail, batch_num, path / f"{base}.pdf")

        # Save JSON alongside
        with open(path / f"{base}.json", "w") as f:
            json.dump(detail, f, indent=2, default=str)


def _save_invoice(invoice: dict, batch_num: str, directory: str) -> None:
    """Save invoice as PDF + JSON."""
    from jlcpcb_cli.core.pdf import save_invoice_pdf

    path = Path(directory)
    path.mkdir(parents=True, exist_ok=True)

    # Save PDF
    save_invoice_pdf(invoice, path / f"{batch_num}-invoice.pdf")

    # Save JSON alongside
    with open(path / f"{batch_num}-invoice.json", "w") as f:
        json.dump(invoice, f, indent=2, default=str)
