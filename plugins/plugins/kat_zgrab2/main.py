import argparse
import json
import os
import subprocess

import httpx

# banner, jarm, tls -> no single port mapped
PORT_SERVICE_MAP = {
    21: "ftp",
    22: "ssh",
    23: "telnet",
    25: "smtp",
    80: "http",
    110: "pop3",
    123: "ntp",
    143: "imap",
    1911: "fox",
    443: "http",
    502: "modbus",
    631: "ipp",
    993: "imap",
    11211: "memcached",
    1521: "oracle",
    1723: "pptp",
    1883: "mqtt",
    20000: "dnp3",
    27017: "mongodb",
    3306: "mysql",
    5432: "postgres",
    5672: "amqp091",
    6379: "redis",
    1433: "mssql",
    4190: "managesieve",
    47808: "bacnet",
    102: "siemens",
    445: "smb",
    1080: "socks5",
}


def main():
    token = os.getenv("OPENKAT_TOKEN")
    base_url = os.getenv("OPENKAT_API")

    if not token:
        raise Exception("No OPENKAT_TOKEN env variable")
    if not base_url:
        raise Exception("No OPENKAT_API env variable")

    client = httpx.Client(base_url=base_url, headers={"Authorization": "Token " + token})

    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("ip_ports", nargs="*")
    args = parser.parse_args()

    results = []

    for ip_port in args.ip_ports:
        ip, port = ip_port.split(":")
        ip = ip.removeprefix("[").removesuffix("]")
        port = int(port)

        service = PORT_SERVICE_MAP.get(port)
        if service is None:
            continue

        result = subprocess.run(["zgrab2", service], capture_output=True, text=True, input=f"{ip},,,{port}")
        data = json.loads(result.stdout)

        if "data" not in data:
            continue

        results.append(
            {"address": ip, "port": port, "service": service, "protocol": "TCP" if service != "ntp" else "UDP"}
        )

    client.post("/objects/ipport/", json=results).raise_for_status()


if __name__ == "__main__":
    main()
