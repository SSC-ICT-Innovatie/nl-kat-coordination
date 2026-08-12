#!/usr/bin/env python

import json
import logging
from typing import Any

import click
from xtdb_client import XTDBClient

logger = logging.getLogger(__name__)


@click.group(context_settings={"help_option_names": ["-h", "--help"], "max_content_width": 120, "show_default": True})
@click.option("-c", "--code", default="0", help="The organisation code")
@click.option("-u", "--url", default="http://localhost:3000", envvar="XTDB_URI", help="XTDB server base url")
@click.option("-t", "--timeout", type=int, default=5000, help="XTDB request timeout (in ms)")
@click.option("-v", "--verbosity", count=True, help="Increase the verbosity level")
@click.pass_context
def cli(ctx: click.Context, url: str, code: str, timeout: int, verbosity: int):
    verbosities = [logging.WARN, logging.INFO, logging.DEBUG]
    try:
        if verbosity:
            logging.basicConfig(level=verbosities[verbosity - 1])
    except IndexError:
        raise click.UsageError("Invalid verbosity level (use -v, -vv, or -vvv)")

    client = XTDBClient(url, code, timeout)
    logger.info("Instantiated XTDB client with endpoint %s for node %s", url, code)

    ctx.ensure_object(dict)
    ctx.obj["client"] = client


def method_query(method: str):
    method = f'"{method}"' if method else ""
    return f"""{{
:query {{
    :find [(pull ?var [*])] :where [
            [?var :type "Origin"]
            [?var :origin_type "observation"]
            [?var :method {method}]
        ]
    }}
}}
"""


@cli.command("list", help="List observation origins based on method")
@click.argument("method", required=False)
@click.pass_context
def list_(ctx: click.Context, method: str):
    origins = ctx.obj["client"].query(method_query(method))
    if not origins:
        raise click.UsageError("No targets found")
    if "error" in origins:
        raise click.UsageError(origins["error"])
    click.echo(json.dumps(origins))


def search_replace_method(data_list: list[dict[str, Any]], search_string: str, replace_string: str) -> None:
    for data_dict in data_list:
        for key in ["method", "xt/id"]:
            if key in data_dict and search_string in data_dict[key]:
                data_dict[key] = data_dict[key].replace(search_string, replace_string)


@cli.command(help="Rename an observation origin method")
@click.option("--armed", is_flag=True, help="Arm the tool to overwrite the method name (confirmation)")
@click.argument("method")
@click.argument("renamed")
@click.pass_context
def rename(ctx: click.Context, armed: bool, method: str, renamed: str):
    origins = ctx.obj["client"].query(method_query(method))
    if not origins:
        raise click.UsageError("No targets found")
    if "error" in origins:
        raise click.UsageError(origins["error"])
    if armed:
        delete_txs = [["delete", o[0]["xt/id"]] for o in origins]
        search_replace_method([o[0] for o in origins], method, renamed)
        put_txs = [["put", o[0]] for o in origins]
        click.echo(json.dumps(ctx.obj["client"].submit_tx(delete_txs + put_txs)))
    else:
        search_replace_method([o[0] for o in origins], method, renamed)
        click.echo(json.dumps(origins))


if __name__ == "__main__":
    cli()
