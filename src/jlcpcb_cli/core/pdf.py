"""PDF generation for JLCPCB billing documents using WeasyPrint."""

import html as html_mod
from pathlib import Path

from weasyprint import HTML


def _esc(value) -> str:
    """HTML-escape a value, returning empty string for None."""
    if value is None:
        return ""
    return html_mod.escape(str(value))


def render_receipt_pdf(detail: dict, batch_num: str) -> bytes:
    """Render a transaction receipt or credit note to PDF bytes.

    Handles Pay, Supplement, and Refund transaction types.
    Refund → "CREDIT NOTE", others → "Receipt from JLCPCB".
    """
    payment_type = detail.get("paymentType", "")
    is_refund = payment_type == "Refund"
    title = "CREDIT NOTE" if is_refund else "Receipt from JLCPCB"
    currency = detail.get("currency", "EUR")
    symbol = "€" if currency == "EUR" else "$"

    addr = detail.get("billingAddress") or {}
    fee = detail.get("feeSummary") or {}
    items = detail.get("lineItems") or []

    # Build line items rows
    if is_refund:
        # Credit note: Description | Part # | Amount
        header_row = "<th>Description</th><th>Part #</th><th class='num'>Amount</th>"
        item_rows = ""
        for item in items:
            desc = _esc(item.get("description"))
            part = _esc(item.get("componentCode") or item.get("part"))
            price = item.get("totalPrice")
            amount_str = f"- {symbol}{price}" if price else ""
            item_rows += f"<tr><td>{desc}</td><td>{part}</td><td class='num'>{amount_str}</td></tr>"
        grand_total = fee.get("grandTotal")
        grand_str = f"- {symbol}{grand_total}" if grand_total else ""
    elif any(item.get("quantity") for item in items):
        # Pay receipt with quantities: Product | Order Number | Qty | Total
        header_row = (
            "<th>Product</th><th>Order Number</th>"
            "<th class='num'>Qty</th><th class='num'>Total</th>"
        )
        item_rows = ""
        for item in items:
            product = _esc(item.get("description") or item.get("product"))
            order_num = _esc(item.get("orderNumber"))
            qty = _esc(item.get("quantity"))
            price = item.get("totalPrice")
            total_str = f"{currency} {symbol}{price}" if price else ""
            item_rows += (
                f"<tr><td>{product}</td><td>{order_num}</td>"
                f"<td class='num'>{qty}</td><td class='num'>{total_str}</td></tr>"
            )
        grand_total = fee.get("grandTotal")
        grand_str = f"{currency} {symbol}{grand_total}" if grand_total else ""
    else:
        # Supplement: Description | Order Number | Amount
        header_row = (
            "<th>Description</th><th>Order Number</th><th class='num'>Amount</th>"
        )
        item_rows = ""
        for item in items:
            desc = _esc(item.get("description"))
            order_num = _esc(item.get("orderNumber"))
            price = item.get("totalPrice")
            amount_str = f"{currency} {symbol}{price}" if price else ""
            item_rows += (
                f"<tr><td>{desc}</td><td>{order_num}</td>"
                f"<td class='num'>{amount_str}</td></tr>"
            )
        grand_total = fee.get("grandTotal")
        grand_str = f"{currency} {symbol}{grand_total}" if grand_total else ""

    date = detail.get("date", "")
    # Format ISO date to readable
    if "T" in date:
        date = date.split("T")[0] + " " + date.split("T")[1][:5]
    pay_method = _esc(detail.get("payMethod"))
    pay_channel = _esc(detail.get("payChannelDetail"))
    if pay_channel:
        pay_method = f"{pay_method} ({pay_channel})"

    billing_name = _esc(addr.get("billingName") or addr.get("company"))

    if is_refund:
        # Credit note layout: JLCPCB header + billing address
        meta_html = f"""
        <div class="two-col">
            <div class="left">
                <div class="jlcpcb-header">
                    <div class="logo-text">JLCPCB</div>
                    <div class="sub">JiaLiChuang (HongKong) Co., Limited</div>
                </div>
                <p>Unit 21, 28/F, Metropole Square<br>
                No.2 On Yiu Street, Shatin, New Territories<br>
                HONG KONG, China<br>
                support@jlcpcb.com<br>
                +86 755 23919769<br>
                JLCPCB.COM</p>
                <p>Date: {date}<br>
                Batch Order #: {_esc(batch_num)}<br>
                Payment Type: {_esc(payment_type)}<br>
                Payment Method: {pay_method}</p>
            </div>
            <div class="right">
                <div class="doc-title">{title}</div>
                <p class="billing-to"><strong>Billing To:</strong><br>
                {billing_name}<br>
                {_esc(addr.get('country'))}</p>
            </div>
        </div>
        """
    else:
        # Receipt layout: simple metadata
        meta_html = f"""
        <div class="receipt-header">
            <h2>{title}</h2>
            <p>To: {billing_name}<br>
            Batch Order #: {_esc(batch_num)}<br>
            Date: {_esc(date)}<br>
            Payment Method: {pay_method}<br>
            Payment Type: {_esc(payment_type)}</p>
        </div>
        """

    html = f"""<!DOCTYPE html>
<html><head><style>
{_receipt_css()}
</style></head><body>
{meta_html}
<table>
    <thead><tr>{header_row}</tr></thead>
    <tbody>{item_rows}</tbody>
</table>
<div class="grand-total">
    <span class="label">Grand Total:</span>
    <span class="value">{grand_str}</span>
</div>
</body></html>"""

    return HTML(string=html).write_pdf()


def render_mfg_invoice_pdf(invoice: dict) -> bytes:
    """Render a manufacturing invoice to PDF bytes."""
    currency = invoice.get("currency", "EUR")
    symbol = "€" if currency == "EUR" else "$"
    bill_to = invoice.get("billingTo") or {}
    ship_to = invoice.get("shipTo") or {}
    costs = invoice.get("costs") or {}
    items = invoice.get("lineItems") or []
    presale = invoice.get("presaleDetails") or []

    # Invoice metadata table
    meta_rows = [
        ("Invoice No.:", _esc(invoice.get("invoiceNo"))),
        ("Invoice Date:", _esc(invoice.get("invoiceDate"))),
        ("Reference:", _esc(invoice.get("trackingNumber"))),
        ("Batch No.:", _esc(invoice.get("batchNum"))),
        ("Ship Via:", _esc(invoice.get("shippingMethod"))),
        ("Type of Trade:", _esc(invoice.get("typeOfTrade"))),
    ]
    meta_html = "".join(
        f"<tr><td class='label'>{k}</td><td>{v}</td></tr>" for k, v in meta_rows
    )

    # Line items
    item_rows = ""
    for i, item in enumerate(items, 1):
        specs = _esc(item.get("specifications"))
        fname = _esc(item.get("orderFileName"))
        ocode = _esc(item.get("orderCode"))
        qty = _esc(item.get("quantity"))
        up = item.get("unitPrice")
        tp = item.get("totalPrice")
        unit_str = f"{currency} {symbol}{up:.2f}" if up is not None else ""
        total_str = f"{currency} {symbol}{tp:.2f}" if tp is not None else ""
        item_rows += (
            f"<tr><td>{i}</td><td>{specs}</td><td>{fname}</td>"
            f"<td>{ocode}</td><td class='num'>{qty}</td>"
            f"<td class='num'>{unit_str}</td><td class='num'>{total_str}</td></tr>"
        )

    # Totals
    product = costs.get("productMoney")
    shipping = costs.get("carriageMoney")
    total = costs.get("totalMoney")
    presale_money = costs.get("presaleMoney")

    def fmt(v):
        if v is None:
            return ""
        return f"{currency} {symbol}{float(v):.2f}"

    # Ship-to address
    ship_lines = "<br>".join(
        filter(None, [
            _esc(ship_to.get("name")), _esc(ship_to.get("company")),
            _esc(ship_to.get("state")), _esc(ship_to.get("city")),
            _esc(ship_to.get("postalCode")), _esc(ship_to.get("country")),
        ])
    )

    # Bill-to address
    bill_lines = "<br>".join(
        filter(None, [
            _esc(bill_to.get("company")), _esc(bill_to.get("name")),
            _esc(bill_to.get("state")), _esc(bill_to.get("city")),
            _esc(bill_to.get("postalCode")), _esc(bill_to.get("country")),
        ])
    )
    if bill_to.get("vatNo"):
        bill_lines += f"<br>VAT No: {_esc(bill_to['vatNo'])}"
    if bill_to.get("eoriNo"):
        bill_lines += f"<br>EORI No: {_esc(bill_to['eoriNo'])}"

    # Prepaid footnote
    prepaid_html = ""
    if presale_money and float(presale_money) > 0:
        prepaid_html = f"""
        <div class="prepaid">
            <span class="label">PrePaid Amount:</span>
            <span class="value">{fmt(presale_money)}</span>
        </div>
        <p class="prepaid-note">The prepaid amount refers to the amount that the customer
        paid when pre-ordered the components, which are used for
        rigid populated printed circuit board.</p>
        """

    html = f"""<!DOCTYPE html>
<html><head><style>
{_invoice_css()}
</style></head><body>
<div class="header">
    <div class="jlcpcb-info">
        <div class="logo-text">JLCPCB</div>
        <div class="sub">JiaLiChuang (HongKong) Co., Limited</div>
        <p>Unit 21, 28/F, Metropole Square<br>
        No.2 On Yiu Street, Shatin, New Territories<br>
        HONG KONG, China<br><br>
        support@jlcpcb.com<br>
        +86 755 23919769<br>
        JLCPCB.COM</p>
    </div>
    <table class="meta-table">
        {meta_html}
    </table>
</div>

<div class="addresses">
    <div class="ship-to">
        <h3>Ship To:</h3>
        <p>{ship_lines}</p>
    </div>
    <div class="bill-to">
        <h3>Billing To:</h3>
        <p>{bill_lines}</p>
    </div>
</div>

<table class="items">
    <thead>
        <tr>
            <th>#</th><th>Product</th><th>File Name</th>
            <th>Order Number</th><th class='num'>QTY</th>
            <th class='num'>Unit Price</th><th class='num'>Ext Price</th>
        </tr>
    </thead>
    <tbody>{item_rows}</tbody>
</table>

<div class="totals">
    <div class="total-row">
        <span class="label">Merchandise Total:</span>
        <span class="value">{fmt(product)}</span>
    </div>
    <div class="total-row">
        <span class="label">Shipping:</span>
        <span class="value">{fmt(shipping)}</span>
    </div>
    <div class="total-row grand">
        <span class="label">Grand Total:</span>
        <span class="value">{fmt(total)}</span>
    </div>
</div>

{prepaid_html}
</body></html>"""

    return HTML(string=html).write_pdf()


def render_parts_invoice_pdf(invoice: dict) -> bytes:
    """Render a parts invoice to PDF bytes."""
    currency = "EUR"  # Parts invoices are always in settlement currency
    symbol = "€"
    bill_to = invoice.get("billingTo") or {}
    costs = invoice.get("costs") or {}
    items = invoice.get("lineItems") or []

    # Billing address
    bill_lines = "<br>".join(
        filter(None, [
            _esc(bill_to.get("company")), _esc(bill_to.get("name")),
            ", ".join(filter(None, [
                _esc(bill_to.get("street")),
                _esc(bill_to.get("city")),
                _esc(bill_to.get("state")),
                _esc(bill_to.get("postalCode")),
            ])),
            _esc(bill_to.get("country")),
        ])
    )
    if bill_to.get("eoriNumber"):
        bill_lines += f"<br>EORI No: {_esc(bill_to['eoriNumber'])}"

    # Line items
    item_rows = ""
    for item in items:
        part = _esc(item.get("componentCode"))
        model = _esc(item.get("model"))
        desc_parts = []
        spec = item.get("specification")
        brand = item.get("brand")
        name = _esc(item.get("componentName"))
        if spec:
            desc_parts.append(_esc(spec))
        if brand:
            desc_parts.append(_esc(brand))
        description = f"{name}<br><small>{' | '.join(desc_parts)}</small>" if desc_parts else name

        qty = _esc(item.get("quantity"))
        up = item.get("unitPrice")
        tp = item.get("totalPrice")
        unit_str = f"{currency} {symbol}{up:.4f}" if up is not None else ""
        total_str = f"{currency} {symbol}{tp:.2f}" if tp is not None else ""
        item_rows += (
            f"<tr><td>{model or part}</td><td class='desc'>{description}</td>"
            f"<td class='num'>{qty}</td>"
            f"<td class='num'>{unit_str}</td><td class='num'>{total_str}</td></tr>"
        )

    subtotal = costs.get("advanceChargeMoney") or costs.get("totalPayment")
    grand_total = costs.get("paidMoney") or costs.get("totalPayment")

    def fmt(v):
        if v is None:
            return ""
        return f"{currency} {symbol}{float(v):.2f}"

    html = f"""<!DOCTYPE html>
<html><head><style>
{_invoice_css()}
</style></head><body>
<div class="header">
    <div class="jlcpcb-info">
        <div class="logo-text">JLCPCB</div>
        <div class="sub">JiaLiChuang (HongKong) Co., Limited</div>
        <p>Unit 21, 28/F, Metropole Square<br>
        No.2 On Yiu Street, Shatin, New Territories<br>
        HONG KONG<br><br>
        support@jlcpcb.com<br>
        +86 755 23919769<br>
        JLCPCB.COM</p>
    </div>
    <div class="invoice-title-block">
        <div class="invoice-title">INVOICE</div>
        <table class="meta-table">
            <tr><td class='label'>Invoice No.:</td><td>{_esc(invoice.get('invoiceNo'))}</td></tr>
            <tr><td class='label'>Invoice Date:</td><td>{_esc(invoice.get('invoiceDate'))}</td></tr>
            <tr><td class='label'>Batch No.:</td><td>{_esc(invoice.get('batchNum'))}</td></tr>
        </table>
        <p>{bill_lines}</p>
    </div>
</div>

<table class="items">
    <thead>
        <tr>
            <th>Mfr. Part #</th><th>Description</th>
            <th class='num'>QTY</th>
            <th class='num'>Unit Price</th><th class='num'>Ext. Price</th>
        </tr>
    </thead>
    <tbody>{item_rows}</tbody>
</table>

<div class="totals">
    <div class="total-row">
        <span class="label">Subtotal:</span>
        <span class="value">{fmt(subtotal)}</span>
    </div>
    <div class="total-row grand">
        <span class="label">Grand Total:</span>
        <span class="value">{fmt(grand_total)}</span>
    </div>
</div>
</body></html>"""

    return HTML(string=html).write_pdf()


def save_receipt_pdf(
    detail: dict, batch_num: str, filepath: Path
) -> None:
    """Render and save a receipt/credit note PDF."""
    pdf_bytes = render_receipt_pdf(detail, batch_num)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_bytes(pdf_bytes)
    print(f"Saved {filepath}")


def save_invoice_pdf(invoice: dict, filepath: Path) -> None:
    """Render and save an invoice PDF."""
    if invoice.get("type") == "parts":
        pdf_bytes = render_parts_invoice_pdf(invoice)
    else:
        pdf_bytes = render_mfg_invoice_pdf(invoice)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_bytes(pdf_bytes)
    print(f"Saved {filepath}")


# --- CSS ---


def _receipt_css() -> str:
    return """
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: Arial, Helvetica, sans-serif; font-size: 11pt;
           padding: 40px; color: #333; max-width: 700px; }
    h2 { font-size: 16pt; margin-bottom: 12px; }
    p { margin-bottom: 8px; line-height: 1.5; }
    .two-col { display: flex; gap: 40px; margin-bottom: 20px; }
    .two-col .left { flex: 1; }
    .two-col .right { flex: 1; text-align: right; }
    .doc-title { font-size: 22pt; font-weight: bold; color: #333;
                 margin-bottom: 12px; }
    .billing-to { text-align: left; }
    .logo-text { font-size: 22pt; font-weight: bold; color: #1a5ab8; }
    .sub { font-size: 9pt; color: #1a5ab8; margin-bottom: 10px; }
    .receipt-header { margin-bottom: 20px; }
    table { width: 100%; border-collapse: collapse; margin: 16px 0; }
    thead tr { background: #4a7cc9; color: white; }
    th { padding: 8px 12px; text-align: left; font-weight: 600; font-size: 10pt; }
    td { padding: 8px 12px; border-bottom: 1px solid #e0e0e0; font-size: 10pt; }
    .num { text-align: right; }
    .grand-total { text-align: right; margin-top: 8px; font-size: 12pt; }
    .grand-total .label { font-weight: bold; margin-right: 20px; }
    .grand-total .value { font-weight: bold; }
    """


def _invoice_css() -> str:
    return """
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: Arial, Helvetica, sans-serif; font-size: 10pt;
           padding: 30px 40px; color: #333; }
    h3 { font-size: 11pt; margin-bottom: 6px; }
    p { margin-bottom: 6px; line-height: 1.4; }
    small { font-size: 8pt; color: #666; }
    .header { display: flex; justify-content: space-between;
              margin-bottom: 24px; }
    .jlcpcb-info { flex: 1; }
    .logo-text { font-size: 22pt; font-weight: bold; color: #1a5ab8; }
    .sub { font-size: 9pt; color: #1a5ab8; margin-bottom: 8px; }
    .invoice-title { font-size: 28pt; font-weight: bold; color: #333;
                     text-align: right; margin-bottom: 8px; }
    .invoice-title-block { text-align: right; }
    .meta-table { margin-left: auto; border-collapse: collapse;
                  margin-bottom: 12px; }
    .meta-table td { padding: 3px 8px; font-size: 10pt;
                     border: 1px solid #ccc; }
    .meta-table td.label { font-weight: 600; text-align: right;
                           background: #f5f5f5; }
    .addresses { display: flex; gap: 40px; margin-bottom: 24px; }
    .ship-to, .bill-to { flex: 1; }
    table.items { width: 100%; border-collapse: collapse; margin: 16px 0; }
    .items thead tr { background: #4a7cc9; color: white; }
    .items th { padding: 8px 10px; text-align: left; font-weight: 600;
                font-size: 9pt; }
    .items td { padding: 6px 10px; border-bottom: 1px solid #e0e0e0;
                font-size: 9pt; vertical-align: top; }
    .items td.desc { max-width: 250px; }
    .num { text-align: right; }
    .totals { text-align: right; margin-top: 12px; }
    .total-row { margin: 4px 0; }
    .total-row .label { display: inline-block; width: 150px;
                        text-align: right; margin-right: 12px; }
    .total-row .value { display: inline-block; width: 120px;
                        text-align: right; }
    .total-row.grand { font-weight: bold; font-size: 11pt;
                       border-top: 1px solid #333; padding-top: 6px;
                       margin-top: 8px; }
    .prepaid { text-align: right; margin-top: 16px;
               padding-top: 8px; border-top: 1px solid #ccc; }
    .prepaid .label { display: inline-block; width: 150px;
                      text-align: right; margin-right: 12px;
                      font-weight: 600; }
    .prepaid .value { display: inline-block; width: 120px;
                      text-align: right; font-weight: 600; }
    .prepaid-note { font-size: 8pt; color: #666; margin-top: 6px;
                    text-align: left; max-width: 400px; }
    """
