"""CLI entry point for jlcpcb-cli."""

import json
import sys
from dataclasses import dataclass, field

import click

from jlcpcb_cli.core import auth
from jlcpcb_cli.core.client import JlcpcbClient, JlcpcbAPIError
from jlcpcb_cli.core.orders import get_order, list_orders
from jlcpcb_cli.core.parts import get_parts_order, list_parts_orders


@dataclass
class CliContext:
    _client: JlcpcbClient | None = field(default=None, init=False, repr=False)

    @property
    def client(self) -> JlcpcbClient:
        if self._client is None:
            self._client = JlcpcbClient()
        return self._client


def _output(data) -> None:
    """Output data as JSON."""
    click.echo(json.dumps(data, indent=2, default=str))


@click.group()
@click.option("--json", "json_output", is_flag=True, hidden=True, help="Output as JSON (always enabled).")
@click.pass_context
def cli(ctx, json_output):
    """JLCPCB order data CLI."""
    ctx.ensure_object(CliContext)


@cli.command()
@click.pass_obj
def login(ctx: CliContext):
    """Force re-login via browser."""
    auth.login()


@cli.group()
@click.pass_obj
def orders(ctx: CliContext):
    """PCB/SMT/3DP order operations."""
    pass


@orders.command("list")
@click.option(
    "--status",
    type=click.Choice(["all", "shipped", "production", "cancelled", "unpaid", "review"]),
    default="all",
    help="Filter by order status.",
)
@click.option("--search", default=None, help="Search by keyword.")
@click.option("--limit", default=15, type=int, help="Results per page (max 50).")
@click.option("--page", default=1, type=int, help="Page number.")
@click.pass_obj
def orders_list(ctx: CliContext, status, search, limit, page):
    """List order batches."""
    try:
        result = list_orders(ctx.client, status=status, search=search, limit=limit, page=page)
        _output(result)
    except JlcpcbAPIError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@orders.command("get")
@click.argument("batch_num")
@click.option("--output-dir", type=click.Path(exists=True), help="Download files to this directory.")
@click.pass_obj
def orders_get(ctx: CliContext, batch_num, output_dir):
    """Get full details for an order batch."""
    try:
        result = get_order(ctx.client, batch_num)
        if output_dir:
            from pathlib import Path

            out = Path(output_dir).resolve()
            for order in result.get("orders", []):
                code = order.get("orderCode", "unknown")
                files = order.get("files") or {}
                for label, url_path in files.items():
                    ext = _file_extension(label)
                    filename = f"{code}-{label}{ext}"
                    path = (out / filename).resolve()
                    if not str(path).startswith(str(out)):
                        click.echo(f"Skipping unsafe path: {filename}", err=True)
                        continue
                    if path.exists():
                        click.echo(f"Skipping (exists): {path}", err=True)
                        continue
                    ctx.client.download_file(url_path, path)
                    click.echo(f"Downloaded: {path}", err=True)
        _output(result)
    except JlcpcbAPIError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.group()
@click.pass_obj
def parts(ctx: CliContext):
    """Parts Manager order operations."""
    pass


@parts.command("list")
@click.option(
    "--status",
    type=click.Choice(["all", "paid", "unpaid", "cancelled", "completed"]),
    default="all",
    help="Filter by order status.",
)
@click.option("--search", default=None, help="Search by keyword.")
@click.option("--limit", default=25, type=int, help="Results per page.")
@click.option("--page", default=1, type=int, help="Page number.")
@click.pass_obj
def parts_list(ctx: CliContext, status, search, limit, page):
    """List parts order batches."""
    try:
        result = list_parts_orders(ctx.client, status=status, search=search, limit=limit, page=page)
        _output(result)
    except JlcpcbAPIError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@parts.command("get")
@click.argument("batch_no")
@click.pass_obj
def parts_get(ctx: CliContext, batch_no):
    """Get full details for a parts order batch."""
    try:
        result = get_parts_order(ctx.client, batch_no)
        _output(result)
    except JlcpcbAPIError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


def _file_extension(label: str) -> str:
    """Map file label to a suitable extension."""
    return {
        "boardImage": ".png",
        "gerbers": ".zip",
        "bom": ".csv",
        "coordinates": ".csv",
    }.get(label, "")


def main():
    cli(obj=CliContext())
