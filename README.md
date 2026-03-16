# jlcpcb-cli

Command-line interface to JLCPCB order data. Retrieves order history, PCB/SMT/3DP order details, and cost breakdowns via JLCPCB's internal API.

No official API exists — this tool reverse-engineers the web interface using browser-based login for authentication and direct HTTP requests for data access.

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
- **SMT orders**: BOM/coordinate files, assembly costs
- **3DP orders**: Material, color, dimensions, technology

## Order Structure

JLCPCB groups orders into **batches** (prefixed `W`). A batch may contain multiple orders (e.g., PCB + SMT assembly for the same board). Each order has a type:

| Type | Description |
|------|-------------|
| `order_pcb` | PCB manufacturing |
| `order_smt` | SMT assembly |
| `order_tdp` | 3D printing (JLC3DP) |

## Requirements

- Python 3.10+
- Playwright (only for `jlcpcb-cli login`): `pip install jlcpcb-cli[login]`
