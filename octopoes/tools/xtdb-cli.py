#!/usr/bin/env python

import datetime
import json
import logging
import re

import click
from xtdb_client import XTDBClient

logger = logging.getLogger(__name__)


@click.group(context_settings={"help_option_names": ["-h", "--help"], "max_content_width": 120, "show_default": True})
@click.option("-n", "--node", default="0", help="XTDB node, or Organization code")
@click.option("-u", "--url", default="http://localhost:3000", help="XTDB server base url")
@click.option("-t", "--timeout", type=int, default=5000, help="XTDB request timeout (in ms)")
@click.option("-v", "--verbosity", count=True, help="Increase the verbosity level")
@click.pass_context
def cli(ctx: click.Context, url: str, node: str, timeout: int, verbosity: int):
    """This help functionality explains how to query XTDB using the xtdb-cli tool.
    The help functionality for all default XTDB commands was copied from the official
    XTDB docs for the HTTP implementation. Not all optional parameters as available
    on the HTTP docs may be implemented."""
    verbosities = [logging.WARN, logging.INFO, logging.DEBUG]
    try:
        if verbosity:
            logging.basicConfig(level=verbosities[verbosity - 1])
    except IndexError:
        raise click.UsageError("Invalid verbosity level (use -v, -vv, or -vvv)")

    client = XTDBClient(url, node, timeout)
    logger.info("Instantiated XTDB client with endpoint %s for node %s", url, node)

    ctx.ensure_object(dict)
    ctx.obj["client"] = client


@cli.command(help="Returns the current status information of the node")
@click.pass_context
def status(ctx: click.Context):
    client: XTDBClient = ctx.obj["client"]

    click.echo(json.dumps(client.status()))


@cli.command(help='EDN Query (default: "{:query {:find [ ?var ] :where [[?var :xt/id ]]}}")')
@click.option("--tx-id", type=int, help="Defaulting to latest transaction id (integer)")
@click.option("--tx-time", type=click.DateTime(), help="In UTC, defaulting to latest transaction time (date)")
@click.option("--valid-time", type=click.DateTime(), help="In UTC, defaulting to now (date)")
@click.argument("edn", required=False)
@click.pass_context
def query(
    ctx: click.Context,
    edn: str,
    valid_time: datetime.datetime | None = None,
    tx_time: datetime.datetime | None = None,
    tx_id: int | None = None,
):
    client: XTDBClient = ctx.obj["client"]

    if edn:
        click.echo(json.dumps(client.query(edn, valid_time, tx_time, tx_id)))
    else:
        click.echo(json.dumps(client.query(valid_time=valid_time, tx_time=tx_time, tx_id=tx_id)))


@cli.command(help="List all keys in node")
@click.pass_context
def list_keys(ctx: click.Context):
    client: XTDBClient = ctx.obj["client"]

    click.echo(json.dumps(client.query()))


@cli.command(help="List all values in node")
@click.pass_context
def list_values(ctx: click.Context):
    client: XTDBClient = ctx.obj["client"]

    click.echo(json.dumps(client.query("{:query {:find [(pull ?var [*])] :where [[?var :xt/id]]}}")))


@cli.command(help="Returns the document map for a particular entity.")
@click.option("--tx-id", type=int, help="Defaulting to latest transaction id (integer)")
@click.option("--tx-time", type=click.DateTime(), help="In UTC, defaulting to latest transaction time (date)")
@click.option("--valid-time", type=click.DateTime(), help="In UTC, defaulting to now (date)")
@click.argument("key")
@click.pass_context
def entity(
    ctx: click.Context,
    key: str,
    valid_time: datetime.datetime | None = None,
    tx_time: datetime.datetime | None = None,
    tx_id: int | None = None,
):
    client: XTDBClient = ctx.obj["client"]

    click.echo(json.dumps(client.entity(key, valid_time, tx_time, tx_id)))


@cli.command(help="Returns the history of a particular entity.")
@click.option(
    "--with-docs",
    is_flag=True,
    help="Includes the documents in the response sequence, under the doc key (boolean, default: false)",
)
@click.option(
    "--with-corrections",
    is_flag=True,
    help="""Includes bitemporal corrections in the response, inline,
    sorted by valid-time (in UTC) then tx-id (boolean, default: false)""",
)
@click.argument("key")
@click.pass_context
def history(ctx: click.Context, key: str, with_corrections: bool, with_docs: bool):
    client: XTDBClient = ctx.obj["client"]

    click.echo(json.dumps(client.history(key, with_corrections, with_docs)))


@cli.command(help="Returns the transaction details for an entity - returns a map containing the tx-id and tx-time.")
@click.option("--tx-id", type=int, help="Defaulting to the latest transaction id (integer)")
@click.option("--tx-time", type=click.DateTime(), help="In UTC, defaulting to the latest transaction time (date)")
@click.option("--valid-time", type=click.DateTime(), help="In UTC, defaulting to now (date)")
@click.argument("key")
@click.pass_context
def entity_tx(
    ctx: click.Context,
    key: str,
    valid_time: datetime.datetime | None = None,
    tx_time: datetime.datetime | None = None,
    tx_id: int | None = None,
):
    client: XTDBClient = ctx.obj["client"]

    click.echo(json.dumps(client.entity_tx(key, valid_time, tx_time, tx_id)))


@cli.command(help="Returns frequencies of indexed attributes")
@click.pass_context
def attribute_stats(ctx: click.Context):
    client: XTDBClient = ctx.obj["client"]

    click.echo(json.dumps(client.attribute_stats()))


@cli.command(
    help="""Wait until the Kafka consumer’s lag is back to 0 (i.e. when it no longer has
    pending transactions to write). Returns the transaction time of the most recent transaction."""
)
@click.option("--timeout", type=int, help="Specified in milliseconds (integer)")
@click.pass_context
def sync(ctx: click.Context, timeout: int | None):
    client: XTDBClient = ctx.obj["client"]

    click.echo(json.dumps(client.sync(timeout)))


@cli.command(
    help="""Waits until the node has indexed a transaction that is at or past the
    supplied tx-id. Returns the most recent tx indexed by the node."""
)
@click.option("--timeout", type=int, help="Specified in milliseconds, defaulting to 10 seconds (integer)")
@click.argument("tx-id", type=int)
@click.pass_context
def await_tx(ctx: click.Context, tx_id: int, timeout: int | None):
    client: XTDBClient = ctx.obj["client"]

    click.echo(json.dumps(client.await_tx(tx_id, timeout)))


@cli.command(
    help="""Blocks until the node has indexed a transaction that is past the supplied tx-time.
    The returned date is the latest index time when this node has caught up as of this call."""
)
@click.option("--timeout", type=int, help="Specified in milliseconds, defaulting to 10 seconds (integer)")
@click.argument("tx-time", type=click.DateTime())
@click.pass_context
def await_tx_time(ctx: click.Context, tx_time: datetime.datetime, timeout: int | None):
    client: XTDBClient = ctx.obj["client"]

    click.echo(json.dumps(client.await_tx_time(tx_time, timeout)))


@cli.command(
    help="Returns a list of all transactions, from oldest to newest transaction time - optionally including documents."
)
@click.option(
    "--with-ops", is_flag=True, help="Should the operations with documents be included? (boolean, default: false)"
)
@click.option("--after-tx-id", type=int, help="Transaction id to start after (integer, default: unbounded)")
@click.pass_context
def tx_log(ctx: click.Context, after_tx_id: int | None, with_ops: bool):
    client: XTDBClient = ctx.obj["client"]

    click.echo(json.dumps(client.tx_log(after_tx_id, with_ops)))


@cli.command(help="Show all document transactions")
@click.pass_context
def txs(ctx: click.Context):
    client: XTDBClient = ctx.obj["client"]

    click.echo(json.dumps(client.tx_log(None, True)))


@cli.command(
    help="""Takes a space separated list of transactions (any combination of put, delete, match, evict and fn)
    and executes them in order. This is the only 'write' endpoint."""
)
@click.argument("txs", nargs=-1)
@click.pass_context
def submit_tx(ctx: click.Context, txs):
    client: XTDBClient = ctx.obj["client"]

    click.echo(json.dumps(client.submit_tx([json.loads(tx) for tx in txs])))


@cli.command(
    help="""Checks if a submitted tx was successfully committed, returning a map with tx-committed and
    either true or false (or a NodeOutOfSyncException exception response if the node has not yet indexed
    the transaction)."""
)
@click.argument("tx-id", type=int)
@click.pass_context
def tx_committed(ctx: click.Context, tx_id: int) -> None:
    client: XTDBClient = ctx.obj["client"]

    click.echo(json.dumps(client.tx_committed(tx_id)))


@cli.command(help="Returns the latest transaction to have been indexed by this node.")
@click.pass_context
def latest_completed_tx(ctx: click.Context):
    client: XTDBClient = ctx.obj["client"]

    click.echo(json.dumps(client.latest_completed_tx()))


@cli.command(help="Returns the latest transaction to have been submitted to this cluster.")
@click.pass_context
def latest_submitted_tx(ctx: click.Context):
    client: XTDBClient = ctx.obj["client"]

    click.echo(json.dumps(client.latest_submitted_tx()))


@cli.command(help="Returns a list of currently running queries.")
@click.pass_context
def active_queries(ctx: click.Context):
    client: XTDBClient = ctx.obj["client"]

    click.echo(json.dumps(client.active_queries()))


@cli.command(help="Returns a list of recently completed/failed queries.")
@click.pass_context
def recent_queries(ctx: click.Context):
    client: XTDBClient = ctx.obj["client"]

    click.echo(json.dumps(client.recent_queries()))


@cli.command(help="Returns a list of slowest completed/failed queries ran on the node.")
@click.pass_context
def slowest_queries(ctx: click.Context):
    client: XTDBClient = ctx.obj["client"]

    click.echo(json.dumps(client.slowest_queries()))


@cli.command(
    help="""Deletes all OOI's of the given type with an evict. (OOITypes are Case sensitive).
    This does not remove the associated Origins or References and might leave your database in an unknown state for
    some related objects."""
)
@click.option("--ooitype", help="The type of OOI to evict")
@click.pass_context
def evict_all_of_type(ctx: click.Context, ooitype: str):
    client: XTDBClient = ctx.obj["client"]
    ooitype = re.sub(r"[^a-zA-Z0-9]", "", ooitype)  # sanitize the object type.
    if not ooitype:
        return
    oois = client.query(f'{{:query {{:find [ ?var ] :where [[?var :object_type "{ooitype}" ]]}}}}')
    # the query has double brackets due to fstring parsing
    transactions = []

    for ooi in oois:
        transactions.append(("evict", ooi[0], datetime.datetime.now(tz=datetime.timezone.utc).isoformat()))

    client.submit_tx(transactions)
    click.echo(f"Evicted all OOIs of type {ooitype}")


@cli.command(help="Deletes all reports with an evict.")
@click.pass_context
def evict_all_reports(ctx: click.Context):
    ctx.invoke(evict_all_of_type, ooitype="Report")


if __name__ == "__main__":
    cli()
