"""CLI entry point for jlcpcb-cli."""

import json
import sys

import click

from jlcpcb_cli.core.web_client import get_web_client
from jlcpcb_cli.core.orders import get_order
from jlcpcb_cli.core.parts import list_inventory
from jlcpcb_cli.core.web_orders import list_orders
from jlcpcb_cli.core.web_parts import list_parts_orders, get_parts_order
from jlcpcb_cli.core import auth


def _output(data) -> None:
    click.echo(json.dumps(data, indent=2, default=str))


@click.group()
@click.option("--json", "json_output", is_flag=True, hidden=True)
def cli(json_output):
    """JLCPCB order data CLI."""
    pass


@cli.command()
def login():
    """Login to JLCPCB via browser."""
    auth.login()


@cli.group()
def orders():
    """PCB/SMT order operations."""
    pass


@orders.command("list")
@click.option(
    "--status",
    type=click.Choice(["all", "shipped", "production", "cancelled", "unpaid", "review"]),
    default="all",
    help="Filter by order status.",
)
@click.option("--search", default=None, help="Search by keyword.")
@click.option("--limit", default=15, type=int, help="Results per page.")
@click.option("--page", default=1, type=int, help="Page number.")
def orders_list(status, search, limit, page):
    """List order batches."""
    try:
        result = list_orders(
            get_web_client(), status=status, search=search, limit=limit, page=page
        )
        _output(result)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@orders.command("get")
@click.argument("batch_num")
def orders_get(batch_num):
    """Get full details for an order batch."""
    try:
        result = get_order(get_web_client(), batch_num)
        _output(result)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.group()
def parts():
    """Parts Manager: inventory and order history."""
    pass


@parts.command("inventory")
@click.option("--search", default="", help="Search by keyword.")
@click.option("--limit", default=30, type=int, help="Results per page.")
@click.option("--page", default=1, type=int, help="Page number.")
def parts_inventory(search, limit, page):
    """List components stored at JLCPCB."""
    try:
        result = list_inventory(
            get_web_client(), search=search, page=page, limit=limit
        )
        _output(result)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@parts.command("list-orders")
@click.option(
    "--status",
    type=click.Choice(["all", "paid", "unpaid", "cancelled", "completed"]),
    default="all",
    help="Filter by order status.",
)
@click.option("--search", default=None, help="Search by keyword.")
@click.option("--limit", default=25, type=int, help="Results per page.")
@click.option("--page", default=1, type=int, help="Page number.")
def parts_list_orders(status, search, limit, page):
    """List parts purchase order batches."""
    try:
        result = list_parts_orders(
            get_web_client(), status=status, search=search, limit=limit, page=page
        )
        _output(result)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@parts.command("get-order")
@click.argument("batch_no")
def parts_get_order(batch_no):
    """Get full details for a parts order batch."""
    try:
        result = get_parts_order(get_web_client(), batch_no)
        _output(result)
    except Exception as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


def main():
    cli()
