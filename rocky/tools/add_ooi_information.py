import datetime
from dataclasses import dataclass
from itertools import product

import httpx
import structlog
from bs4 import BeautifulSoup

SEPARATOR = "|"
SOURCE_TIMEOUT = 10

logger = structlog.get_logger(__name__)


@dataclass
class _Service:
    name: str
    port: int | None = None
    transport_protocol: str | None = None
    description: str | None = None


@dataclass
class _PortInfo:
    port: int
    protocols: list
    description: str


class InformationUpdateError(Exception):
    """Could not update information due to various reasons"""


def iana_service_table(source: str, search_query: str) -> list[_Service]:
    services = []

    response = httpx.get(source, params={"search": search_query}, timeout=SOURCE_TIMEOUT)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    table = soup.select_one("table#table-service-names-port-numbers")

    if not table:
        return []

    for item in table.select("tbody tr"):
        columns = [col.text for col in item.find_all("td")[:4]]
        name, port, transport_protocol, description = columns

        try:
            if name == search_query:
                service = _Service(
                    name, int(port) if port else None, transport_protocol if transport_protocol else None, description
                )
                services.append(service)
        except Exception:  # noqa: S110
            # just ignore on parse errors
            pass
    return services


def service_info(value: str) -> tuple[str, str]:
    """Provides information about IP Services such as common assigned ports for certain protocols and descriptions"""
    source = "https://www.iana.org/assignments/service-names-port-numbers/service-names-port-numbers.xhtml"
    services = iana_service_table(source, value)
    if not services:
        return f"No description found for {value}", "No source found"

    descriptions = []
    for service in services:
        descriptions.append(
            f"Service is usually on port {service.port}, "
            f"with protocol {service.transport_protocol}: {service.description}"
        )

    return ". ".join(descriptions), source


# from: https://newbedev.com/how-to-parse-table-with-rowspan-and-colspan
def table_to_2d(table_tag):
    rowspans_list: list = []  # track pending rowspans
    rows = table_tag.find_all("tr")

    # first scan, see how many column_names we need
    colcount = 0
    for r, row in enumerate(rows):
        cells = row.find_all(["td", "th"], recursive=False)
        # count column_names (including spanned).
        # add active rowspans from preceding rows
        # we *ignore* the colspan value on the last cell, to prevent
        # creating 'phantom' column_names with no actual cells, only extended
        # colspans. This is achieved by hardcoding the last cell width as 1.
        # a colspan of 0 means “fill until the end” but can really only apply
        # to the last cell; ignore it elsewhere.
        colcount = max(
            colcount, sum(int(c.get("colspan", 1)) or 1 for c in cells[:-1]) + len(cells[-1:]) + len(rowspans_list)
        )
        # update rowspan bookkeeping; 0 is a span to the bottom.
        rowspans_list += [int(c.get("rowspan", 1)) or len(rows) - r for c in cells]
        rowspans_list = [s - 1 for s in rowspans_list if s > 1]

    # it doesn't matter if there are still rowspan numbers 'active'; no extra
    # rows to show in the table means the larger than 1 rowspan numbers in the
    # last table row are ignored.

    # build an empty matrix for all possible cells
    table = [[None] * colcount for row in rows]

    # fill matrix from row data
    rowspans: dict = {}  # track pending rowspans, column number mapping to count
    for row, row_elem in enumerate(rows):
        span_offset = 0  # how many column_names are skipped due to row and colspans
        for col, cell in enumerate(row_elem.find_all(["td", "th"], recursive=False)):
            # adjust for preceding row and colspans
            col += span_offset
            while rowspans.get(col, 0):
                span_offset += 1
                col += 1

            # fill table data
            rowspan = rowspans[col] = int(cell.get("rowspan", 1)) or len(rows) - row
            colspan = int(cell.get("colspan", 1)) or colcount - col
            # next column is offset by the colspan
            span_offset += colspan - 1
            value = cell.get_text()
            for drow, dcol in product(range(rowspan), range(colspan)):
                try:
                    table[row + drow][col + dcol] = value
                    rowspans[col + dcol] = rowspan
                except IndexError:
                    # rowspan or colspan outside the confines of the table
                    pass

        # update rowspan bookkeeping
        rowspans = {c: s - 1 for c, s in rowspans.items() if s > 1}

    return table


def _map_usage_value(value: str) -> bool:
    value = value.lower().strip()
    return bool(value and value != "no")


def wiki_port_tables(source: str) -> list[_PortInfo]:
    response = httpx.get(source, timeout=SOURCE_TIMEOUT)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    rows = []
    for table in soup.select("table.wikitable.sortable"):
        rows.extend(table_to_2d(table))

    del rows[:2]

    items = []
    for row in rows:
        try:
            port, tcp, udp, _, _, description = row
            port = int(port)
            protocols = []
            if _map_usage_value(tcp):
                protocols.append("tcp")
            if _map_usage_value(tcp):
                protocols.append("udp")
            description = description.strip()
        except Exception:  # noqa: S112
            continue

        items.append(_PortInfo(port, protocols, description))

    return items


def port_info(number: str, protocol: str) -> tuple[str, str]:
    """Provides possible or common protocols for operation of network applications behind TCP and UDP ports"""
    source = "https://en.wikipedia.org/wiki/List_of_TCP_and_UDP_port_numbers"
    items = wiki_port_tables(source)
    descriptions = []
    if not items:
        return (f"No description found in wiki table for port {number} with protocol {protocol}", source)

    for item in items:
        if item.port == int(number) and protocol.lower() in item.protocols:
            descriptions.append(item.description)

    return ". ".join(descriptions), source


def get_info(ooi_type: str, natural_key: str) -> dict:
    """Adds OOI information to the OOI Information table"""
    logger.info("Getting OOI information for %s %s", ooi_type, natural_key)
    try:
        if ooi_type == "IPPort":
            protocol, port = natural_key.split(SEPARATOR)
            description, source = port_info(port, protocol)
            return {
                "description": description,
                "source": source,
                "information updated": datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
            }
        if ooi_type == "Service":
            description, source = service_info(natural_key)
            return {
                "description": description,
                "source": source,
                "information updated": datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
            }
    except httpx.HTTPError as error:
        logger.error("Getting OOI information for %s %s failed due to http error: %s", ooi_type, natural_key, error)
        raise InformationUpdateError()
    return {"description": "No source available."}
