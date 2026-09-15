# jlcpcb-cli

Command-line interface to JLCPCB order data. Retrieves order history, PCB/SMT/3DP order details, cost breakdowns, and personal parts inventory via JLCPCB's web API.

No official API keys needed — this tool uses browser-based login for authentication and direct HTTP requests for data access.

## Installation

```bash
pip install git+https://github.com/hatlabs/jlcpcb-cli.git
```

Or for development:

```bash
git clone https://github.com/hatlabs/jlcpcb-cli.git
cd jlcpcb-cli
pip install -e ".[dev]"
```

## Authentication

Login via Google/Apple/password in a real Chrome window:

```bash
jlcpcb-cli login
```

Session cookies are persisted to `~/.jlcpcb-cli/browser-cookies.json`. Re-run `login` when the session expires.

Playwright is only needed for `login`: `pip install jlcpcb-cli[login]`

## Usage

### List order batches

```bash
jlcpcb-cli --json orders list
jlcpcb-cli --json orders list --limit 5 --page 2
jlcpcb-cli --json orders list --status shipped
jlcpcb-cli --json orders list --search "Y41"
```

Status filters: `all`, `shipped`, `production`, `cancelled`, `unpaid`, `review`

### Get order details

```bash
jlcpcb-cli --json orders get W2025122821367552
```

Returns detailed information for all orders in a batch, including:
- **PCB orders**: Layer count, dimensions, surface finish, copper weight, impedance control, cost breakdown
- **SMT orders**: BOM/coordinate files, assembly costs, patch side
- **3DP orders**: Status, dates, costs

### Assembly BOM

```bash
jlcpcb-cli --json orders bom W2026082015506207
```

Returns `{"batchNum", "smtOrders": [...]}`, one entry per SMT order in the batch. Each entry carries `orderCode`, `quantity` (boards assembled), `assemblySide`, `suppliedByJlcpcbTotal`, and `components`.

Each component row gives the LCSC part number, manufacturer part, designators, `placements` (placements over the whole order, not per board), `unitsUsed` (including the `lossUnits` allowance), and the unit price JLCPCB charged.

The units are split across `unitsFromPreorder` (your Parts Manager stock), `unitsFromJlcpcb` (sourced by JLCPCB for this order), `unitsFree`, and `unitsUnattributed` for whatever the other three do not account for. On a real 172-row order, five rows carried unattributed units. `unitPrice` and `totalMoney` cover the `unitsFromJlcpcb` units only, so a row supplied entirely from pre-ordered stock costs 0 here. `suppliedByJlcpcbTotal` is the sum of `totalMoney` over the rows.

The endpoint also reports a `totalPrice` per SMT order. It is not exposed: on one order it equalled `suppliedByJlcpcbTotal` and on another it exceeded it by 277 EUR, and nothing in the response accounts for the difference.

### Inventory usage

```bash
jlcpcb-cli --json orders usage W2026082015506207
```

Shows the Parts Manager stock each SMT order consumed: per component, the quantity drawn, the settled unit price, and the `POB` pre-order batch and presale order it came from. `totalFromInventory` is the component cost that sits in those pre-order batches rather than in this order's invoice.

All money in both commands is in USD, reported as `currency` on each SMT order. Neither endpoint returns a currency field; the web UI labels these same figures "Unit Price(USD)" on an account whose every other page renders EUR. Multiply by the batch's `exchangeRate` from `billing invoice` to get the invoiced amount in your settlement currency: on W2026082015506207 a `totalFromInventory` of 4654.66 times a rate of 0.8555 gives 3982.06, the `presaleMoney` on that invoice, to the cent.

`consigned` lists stock you shipped to JLCPCB yourself. No observed order has returned a row, so those rows pass through with JLCPCB's own field names and are not counted in `totalFromInventory`.

### Parts inventory

```bash
jlcpcb-cli --json parts inventory
jlcpcb-cli --json parts inventory --search "resistor" --limit 10
```

Lists components stored at JLCPCB (your personal inventory).

### Parts order history

```bash
jlcpcb-cli --json parts list-orders
jlcpcb-cli --json parts get-order POB0202603031859897
```

### Billing history

```bash
jlcpcb-cli billing list
jlcpcb-cli billing list --search W2026031901374275
jlcpcb-cli billing get W2026031901374275
jlcpcb-cli billing invoice W2026031901374275
jlcpcb-cli billing invoice W2026031901374275 --download .
jlcpcb-cli billing invoice POB0202603031859897
```

- `billing list` — Paginated payment history with Pay/Supplement/Refund transactions per batch
- `billing get` — Full receipt/credit note detail for each transaction in a batch
- `billing invoice` — Commercial invoice data (dispatches to correct endpoint by batch prefix)
- `--download DIR` — Save PDF + JSON files to the given directory (requires `pip install jlcpcb-cli[pdf]`)

## Order Structure

JLCPCB groups orders into **batches** (prefixed `W`). A batch may contain multiple orders (e.g., PCB + SMT assembly for the same board). Each order has a type:

| Type | Description |
|------|-------------|
| `pcb` | PCB manufacturing |
| `smt` | SMT assembly |
| `3dp` | 3D printing (JLC3DP) |

## Requirements

- Python 3.10+
- Playwright (only for `jlcpcb-cli login`): `pip install jlcpcb-cli[login]`
- WeasyPrint (only for `--download` PDF generation): `pip install jlcpcb-cli[pdf]`
  - Requires system libraries: `brew install pango` (macOS) or `apt install libpango-1.0-0` (Debian/Ubuntu)
