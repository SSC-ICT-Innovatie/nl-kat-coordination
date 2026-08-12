from os import getenv

import dns
from dns.edns import EDEOption
from dns.resolver import Answer


def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
    """return results to normalizer."""
    ip = boefje_meta["arguments"]["input"]["address"]

    resolver = dns.resolver.Resolver()
    # https://dnspython.readthedocs.io/en/stable/_modules/dns/edns.html
    # enable EDE to get the ServFail return values if the server supports it # codespell-ignore
    resolver.use_edns(options=[EDEOption(15)])
    resolver.nameservers = [getenv("REMOTE_NS", "1.1.1.1")]
    reverse_ip = dns.reversename.from_address(ip)
    try:
        answer: Answer = resolver.resolve(reverse_ip, "PTR")
        result = f"RESOLVER: {answer.nameserver}\n{answer.response}"
        return [(set(), result)]
    except dns.resolver.NXDOMAIN:
        return [(set(), "NXDOMAIN")]
    except dns.resolver.NoNameservers as error:
        # no servers responded happily, we'll check the response from the first
        # https://dnspython.readthedocs.io/en/latest/_modules/dns/rcode.html
        # https://www.rfc-editor.org/rfc/rfc8914#name-extended-dns-error-code-6-d
        first_error = error.kwargs["errors"][0]
        if first_error[3] == "SERVFAIL":
            for ede_error in first_error[4].options:
                if int(ede_error.code) == 22:
                    # Auth nameserver for ip could not be reached, error codes defined in RFC 8914
                    return [(set(), "NoAuthServersReachable:" + ede_error.text)]
                    # returned when the resolver indicates a Lame delegation.
        return [(set(), "NoAnswer")]
    except (dns.resolver.Timeout, dns.resolver.NoAnswer):
        return [(set(), "NoAnswer")]
