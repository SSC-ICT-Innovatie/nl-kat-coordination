import json
import logging
import os
import sys

import httpx
from httpx import HTTPError
from libnmap.objects import NmapHost, NmapReport, NmapService
from libnmap.parser import NmapParser


def get_ip_ports_and_service(host: NmapHost) -> list[dict[str, str | int]]:
    """Yields IPs, open ports and services if any ports are open on this host."""
    open_ports = host.get_open_ports()

    results = []
    if open_ports:
        for port, protocol in open_ports:
            service: NmapService = host.get_service(port, protocol)

            # If service is tcpwrapped we should consider the port closed
            if service.service == "tcpwrapped":
                continue
            service_name = service.service
            if service_name == "http" and service.tunnel == "ssl":
                service_name = "https"

            ip_port = {
                "address": host.address,
                "protocol": protocol.upper(),
                "port": port,
                "state": service.state,
                "service": service_name,
            }
            results.append(ip_port)

    return results


def run(file_id: str) -> list[dict[str, str | int]]:
    token = os.getenv("OPENKAT_TOKEN")
    if not token:
        raise Exception("No OPENKAT_TOKEN env variable")

    base_url = os.getenv("OPENKAT_API")
    if not base_url:
        raise Exception("No OPENKAT_API env variable")

    headers = {"Authorization": "Token " + token}
    client = httpx.Client(base_url=base_url, headers=headers)

    file = client.get(f"/file/{file_id}/download/").raise_for_status()
    # Multiple XMLs are concatenated through "\n\n". XMLs end with "\n"; we split on "\n\n\n".
    raw_splitted = file.content.decode().split("\n\n\n")

    # Relevant network object is received from the normalizer_meta.
    results = []
    logging.info("Parsing %d Nmap-xml(s).", len(raw_splitted))

    for nmap_output in raw_splitted:
        parsed = NmapParser.parse_fromstring(nmap_output)
        ports_scanned = get_ports_scanned(parsed)

        for host in parsed.hosts:
            new_ports = get_ip_ports_and_service(host)
            address = (
                client.post("/objects/ipaddress/", json={"address": str(host.address), "network": "internet"})
                .raise_for_status()
                .json()
            )

            not_closed = [obj["port"] for obj in new_ports if obj.pop("state") != "closed"]
            idx = 0
            batch_size = 250

            for idx_2 in range(batch_size, len(ports_scanned) + batch_size, batch_size):
                params = {"port": ports_scanned[idx:idx_2], "address": address["id"]}
                ports = [
                    x["id"] for x in client.get("/objects/ipport/", params=params).raise_for_status().json()["results"]
                ]

                if not ports:
                    idx = idx_2
                    continue
                try:
                    client.delete(
                        "/objects/ipport/", params={"pk": list(set(ports) - set(not_closed))}
                    ).raise_for_status()
                except HTTPError:
                    print(f"Failed to delete ports for {host}, continuing")  # noqa: T201
                idx = idx_2

            results.extend(new_ports)

    client.post("/objects/ipport/", json=results).raise_for_status()

    return results


def get_ports_scanned(parsed: NmapReport) -> list[int]:
    """Given an NmapReport, get the list of ports that were actually scanned"""

    ports_scanned = []

    for port_range in parsed.get_raw_data().get("_scaninfo", {}).get("services", "").split(","):
        if port_range == "":
            continue

        if "-" in port_range:
            begin, end = port_range.split("-", 1)
            ports_scanned.extend(list(range(int(begin), int(end))))
            continue

        ports_scanned.append(int(port_range))

    return ports_scanned


if __name__ == "__main__":
    results = run(sys.argv[1])

    print(json.dumps(results))  # noqa: T201
