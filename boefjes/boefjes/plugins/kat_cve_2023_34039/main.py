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

import logging
import subprocess
import tempfile
from os import getenv
from pathlib import Path

logger = logging.getLogger(__name__)

# Resolve the keys relative to this module. os.walk("keys") used the process
# CWD (/app/boefje in the OCI image) instead, so it walked a non-existent
# directory, silently found no keys and always reported "not vulnerable".
KEYS_DIR = Path(__file__).parent / "keys"
SSH_TIMEOUT = 30


# ssh exit code 255 covers everything from "connection timed out" to "permission
# denied". Match against lowercase stderr:
# - "timed out" wording is a TIMEOUT (rerunnable task state);
# - other network-failure wording (refused, unreachable, ...) is INCONCLUSIVE:
#   the key was never tested, so it is error/boefje — not a rejection, not a
#   timeout (per review M2: only genuine timeouts get the TIMEOUT state);
# - anything else on exit 255 ("Permission denied") is a definitive rejection.
CONNECTION_TIMEOUT_MARKERS = ("connection timed out", "timed out")
CONNECTION_FAILURE_MARKERS = (
    "connection refused",
    "network is unreachable",
    "network unreachable",
    "no route to host",
    "name or service not known",
    "connection reset by peer",
    "broken pipe",
    "connection closed",
    "connection lost",
)


def _connection_timed_out(stderr: str) -> bool:
    lowered = stderr.lower()
    return any(marker in lowered for marker in CONNECTION_TIMEOUT_MARKERS)


def _connection_failed(stderr: str) -> bool:
    """True if ssh's stderr reports a network failure other than a timeout.
    Such a failure says nothing about the key, but it is not a timeout
    either: the connection was answered (or decisively not routable)."""
    lowered = stderr.lower()
    return any(marker in lowered for marker in CONNECTION_FAILURE_MARKERS)


def run(boefje_meta: dict) -> list[tuple[set, str | bytes]]:
    input_ = boefje_meta["arguments"]["input"]  # input is IPService
    ip_port = input_["ip_port"]
    if input_["service"]["name"] != "ssh":
        return [({"openkat/deschedule"}, "Skipping because service is not an ssh service")]

    ip = ip_port["address"]["address"]
    port = ip_port["port"]

    inconclusive_attempts = 0
    timed_out_attempts = 0
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
                # Can be overridden through the plugin settings, see schema.json. A hung
                # SSH connection should not block the boefje forever.
                result = subprocess.run(
                    ssh_command,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    timeout=int(getenv("TIMEOUT", str(SSH_TIMEOUT))),
                )
            except subprocess.TimeoutExpired:
                # Inconclusive, and a genuine timeout: rerunnable state.
                inconclusive_attempts += 1
                timed_out_attempts += 1
                continue
            except FileNotFoundError:
                # The ssh executable itself is missing: a boefje/config problem,
                # not a scan result and not a timeout. One report suffices.
                return [({"error/boefje"}, "ssh executable not found; cannot test CVE-2023-34039 keys")]
            except Exception as exc:  # noqa: S112
                # No result at all: cannot count as evidence either way.
                logger.warning("Unexpected failure testing key %s: %r", key_file, exc)
                inconclusive_attempts += 1
                continue

            coutput = result.returncode
            if coutput in (0, 127):  # 0 = it worked, 127 = `exit` does not exist but we did connect
                key_id = key_file.relative_to(KEYS_DIR)
                return [
                    (
                        set(),
                        "\n".join(
                            (str(coutput), f"{key_id} is allowed access to vRealize Network Insight on {ip}:{port}")
                        ),
                    ),
                    ({"openkat/finding"}, "CVE-2023-34039"),
                ]

            stderr_text = result.stderr.decode(errors="replace") if isinstance(result.stderr, bytes) else ""
            if coutput == 255 and _connection_timed_out(stderr_text):
                # ssh itself reports the connection timed out: a genuine
                # timeout, rerunnable state.
                inconclusive_attempts += 1
                timed_out_attempts += 1
            elif coutput == 255 and _connection_failed(stderr_text):
                # ssh reports a network failure (refused, unreachable,
                # closed): the key was not tested, so this is not evidence
                # of either kind — but it is not a timeout either.
                inconclusive_attempts += 1
            else:
                # e.g. "Permission denied": ssh reached the host and
                # definitively rejected this key. Any other unrecognized
                # outcome is treated as rejection evidence — conservative, but
                # it does not invent a timeout where there was none. Rejections
                # need no counter: they are conclusive, so the loop continues
                # and the final message depends only on inconclusive attempts.
                pass

    if inconclusive_attempts:
        if timed_out_attempts:
            # At least one attempt genuinely timed out: rerunnable state.
            return [
                (
                    {"error/timeout"},
                    (
                        f"Unable to complete testing of all SSH keys: {timed_out_attempts} of {inconclusive_attempts} "
                        f"attempt(s) to {ip}:{port} timed out, so no definitive result is possible"
                    ),
                )
            ]
        # Every inconclusive attempt was a decisive network failure
        # (refused/unreachable/closed): a task failure, not a timeout.
        return [
            (
                {"error/boefje"},
                (
                    f"Unable to complete testing of all SSH keys: {inconclusive_attempts} attempt(s) to {ip}:{port} "
                    "failed to connect (refused, unreachable or closed), so no definitive result is possible"
                ),
            )
        ]
    return [(set(), "No known keys allowed")]
