"""CLI entry point for jlcpcb-cli."""

import json
import sys

import click

from jlcpcb_cli.core.client import JlcpcbClient, JlcpcbAPIError
from jlcpcb_cli.core.orders import get_order
from jlcpcb_cli.core.parts import list_components


def _client() -> JlcpcbClient:
    return JlcpcbClient()


def _output(data) -> None:
    """Output data as JSON."""
    click.echo(json.dumps(data, indent=2, default=str))


@click.group()
@click.option("--json", "json_output", is_flag=True, hidden=True)
def cli(json_output):
    """JLCPCB order data CLI."""
    pass


@cli.group()
def orders():
    """PCB/SMT order operations."""
    pass


@orders.command("get")
@click.argument("batch_num")
def orders_get(batch_num):
    """Get full details for an order batch."""
    try:
        result = get_order(_client(), batch_num)
        _output(result)
    except JlcpcbAPIError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


@cli.group()
def parts():
    """Components library."""
    pass


@parts.command("list")
@click.option("--limit", default=30, type=int, help="Results per page.")
@click.option("--page", default=1, type=int, help="Page number.")
def parts_list(limit, page):
    """List components from the JLCPCB library."""
    try:
        result = list_components(_client(), page=page, limit=limit)
        _output(result)
    except JlcpcbAPIError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)


def main():
    cli()
