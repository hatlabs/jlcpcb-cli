"""CLI entry point for jlcpcb-cli."""

import json
import sys
from dataclasses import dataclass, field

import click

from jlcpcb_cli.core import auth
from jlcpcb_cli.core.client import JlcpcbClient, JlcpcbAPIError
from jlcpcb_cli.core.orders import get_order, list_orders


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
@click.pass_obj
def orders_get(ctx: CliContext, batch_num):
    """Get full details for an order batch."""
    try:
        result = get_order(ctx.client, batch_num)
        _output(result)
    except JlcpcbAPIError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


def main():
    cli(obj=CliContext())
