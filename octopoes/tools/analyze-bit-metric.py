#!/usr/bin/env python

import json
import logging
from datetime import datetime

import click
from xtdb_client import XTDBClient

logger = logging.getLogger(__name__)


class BitMetric:
    def __init__(self, data):
        date_format = "%Y-%m-%dT%H:%M:%SZ"
        self.tx_time: datetime = datetime.strptime(data["txTime"], date_format)
        self.tx_id: int = int(data["txId"])
        self.valid_time: datetime = datetime.strptime(data["validTime"], date_format)
        self.content_hash: str = data["contentHash"]
        self.yld: dict[str, str] = json.loads(data["doc"]["yield"])
        self.cfg: dict[str, str] = json.loads(data["doc"]["config"])
        self.src: dict[str, str] = json.loads(data["doc"]["source"])
        self.name: str = data["doc"]["bit"]
        self.pms: list[dict[str, str]] = json.loads(data["doc"]["parameters"])
        self.elapsed: list[dict[str, str]] = json.loads(data["doc"]["elapsed"])

    def empty(self):
        return len(self.yld) == 0

    def __eq__(self, val):
        return (
            self.src == val.src
            and self.cfg == val.cfg
            and self.yld == val.yld
            and self.name == val.name
            and self.pms == val.pms
        )

    def __hash__(self):
        return hash(str(hash(self.tx_time)) + self.content_hash)


@click.group(context_settings={"help_option_names": ["-h", "--help"], "max_content_width": 120, "show_default": True})
@click.option("-n", "--node", default="0", help="XTDB node")
@click.option("-u", "--url", default="http://localhost:3000", help="XTDB server base url")
@click.option("-t", "--timeout", type=int, default=5000, help="XTDB request timeout (in ms)")
@click.option("-v", "--verbosity", count=True, help="Increase the verbosity level")
@click.pass_context
def cli(ctx: click.Context, url: str, node: str, timeout: int, verbosity: int):
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
    ctx.obj["raw_bit_metrics"] = client.history("BIT_METRIC", False, True)
    if not ctx.obj["raw_bit_metrics"]:
        raise click.UsageError("No bit metrics found")
    if "error" in ctx.obj["raw_bit_metrics"] and ctx.obj["raw_bit_metrics"]["error"] == "Node not found":
        raise click.UsageError("Node node found")
    ctx.obj["bit_metrics"] = list(map(lambda x: BitMetric(x), ctx.obj["raw_bit_metrics"]))


@cli.command(help="Returns the raw bit metric")
@click.pass_context
def raw(ctx: click.Context):
    click.echo(json.dumps(ctx.obj["raw_bit_metrics"]))


@cli.command(help="Returns the parsed metric")
@click.pass_context
def parse(ctx: click.Context):
    bit_metrics = ctx.obj["bit_metrics"]
    metrics = {
        "total": len(bit_metrics),
        "total_elapsed": sum([bm.elapsed for bm in bit_metrics]),
        "empty": len([bm for bm in bit_metrics if bm.empty()]),
        "empty_elapsed": sum([bm.elapsed for bm in bit_metrics if bm.empty()]),
        "useful": len([bm for bm in bit_metrics if not bm.empty()]),
        "useful_elapsed": sum([bm.elapsed for bm in bit_metrics if not bm.empty()]),
        "futile_runs": {bm.name: bit_metrics.count(bm) - 1 for bm in bit_metrics if bit_metrics.count(bm) > 1},
    }
    click.echo(json.dumps(metrics))


if __name__ == "__main__":
    cli()
