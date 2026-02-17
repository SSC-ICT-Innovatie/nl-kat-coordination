# Copyright: 2022, ECP, NLnet Labs and the Internet.nl contributors
# SPDX-License-Identifier: Apache-2.0
import ipaddress

from pyparsing import (
    CaselessLiteral,
    Combine,
    Group,
    OneOrMore,
    Optional,
    ParseException,
    ParserElement,
    Regex,
    StringEnd,
    White,
    Word,
    ZeroOrMore,
    alphanums,
    alphas,
    nums,
    printables,
)

ParserElement.set_default_whitespace_chars("")  # Whitespace is in the grammar

# Parser for SPF records.
#
# The record is parsed based on section 12 (Collected ABNF) of RFC-7208.
# [ https://tools.ietf.org/html/rfc7208#section-12 ]
#
# Most of the tokens have been combined together for easier access to the
# records parts.
# The terms can be found under <parsed_result>['terms'] if any.


def _parse_ipv6(tokens):
    """
    Helper function to parse IPv6 addresses.

    """
    match = str(tokens[0])
    try:
        return str(ipaddress.IPv6Address(match))
    except ipaddress.AddressValueError:
        try:
            return str(ipaddress.IPv6Network(match, strict=False))
        except (ipaddress.AddressValueError, ipaddress.NetmaskValueError) as e:
            raise ParseException("Non valid IPv6 address/network.") from e


SP = White(ws=" ", exact=1).suppress()

name = Word(alphas, exact=1) + Optional(Word(alphanums + "-_."))

delimiter = Word(".-+,/_=", exact=1)
transformers = Optional(Word(nums)) + Optional(CaselessLiteral("r"))
macro_letter = Word("sSlLoOdDiIpPhHcCrRtTvV", exact=1)
macro_literal = Word(printables, exact=1, exclude_chars="%")
macro_expand = (
    (CaselessLiteral("%{") + macro_letter + Optional(transformers) + ZeroOrMore(delimiter) + CaselessLiteral("}"))
    | CaselessLiteral("%%")
    | CaselessLiteral("%_")
    | CaselessLiteral("%-")
)


def _check_toplabel(tokens):
    if tokens[0][-1] == "-":
        raise ParseException("Top level ending in '-'")
    return None


toplabel = (
    (Optional(Word(nums)) + Word(alphas, exact=1) + Optional(Word(alphanums)))
    | (Word(alphanums) + CaselessLiteral("-") + Optional(Word(alphanums + "-")))
).set_parse_action(_check_toplabel)


def _check_domain_end(tokens):
    """
    domain_end = (
        (CaselessLiteral('.') + toplabel + Optional(CaselessLiteral('.')))
        | macro_expand)

    """
    domain_name = tokens[0]
    domain_end = domain_name.split(".")[-2] if domain_name[-1] == "." else domain_name.split(".")[-1]
    try:
        toplabel.parse_string(domain_end)
    except ParseException:
        macro_expand.parse_string(domain_end)
    return None


macro_string = Combine(ZeroOrMore(macro_expand | macro_literal))

domain_spec = macro_string.set_parse_action(_check_domain_end)

ip4_network = Regex(r"((25[0-5]|2[0-4]\d|1\d\d|[1-9]\d|\d)\.){3}(25[0-5]|2[0-4]\d|1\d\d|[1-9]\d|\d)")

ip6_cidr_length = CaselessLiteral("/") + Regex(r"(12[0-8]|1[01]\d|[1-9]\d|\d)")
ip4_cidr_length = CaselessLiteral("/") + Regex(r"(3[0-2]|[12]\d|\d)")
dual_cidr_length = Optional(ip4_cidr_length) + Optional(CaselessLiteral("/") + ip6_cidr_length)

unknown_modifier = Combine(name + CaselessLiteral("=") + macro_string)
explanation = Combine(CaselessLiteral("exp=") + domain_spec)
redirect = Combine(CaselessLiteral("redirect=") + domain_spec)
modifier = redirect | explanation | unknown_modifier

qualifier = Word("+-?~", exact=1)
exists = Combine(Optional(qualifier) + CaselessLiteral("exists:") + domain_spec)
ip6 = Combine(Optional(qualifier) + CaselessLiteral("ip6:") + Regex("[^ ]*").set_parse_action(_parse_ipv6))
ip4 = Combine(Optional(qualifier) + CaselessLiteral("ip4:") + ip4_network + Optional(ip4_cidr_length))
ptr = Combine(Optional(qualifier) + CaselessLiteral("ptr") + Optional(CaselessLiteral(":") + domain_spec))
mx = Combine(
    Optional(qualifier)
    + CaselessLiteral("mx")
    + Optional(CaselessLiteral(":") + domain_spec)
    + Optional(dual_cidr_length)
)
a = Combine(
    Optional(qualifier)
    + CaselessLiteral("a")
    + Optional(CaselessLiteral(":") + domain_spec)
    + Optional(dual_cidr_length)
)
include = Combine(Optional(qualifier) + CaselessLiteral("include:") + domain_spec)
all_ = Combine(Optional(qualifier) + CaselessLiteral("all"))

mechanism = all_ | include | a | mx | ptr | ip4 | ip6 | exists
directive = mechanism
terms = ZeroOrMore(OneOrMore(SP) + (directive | modifier))

version = CaselessLiteral("v=spf1").set_results_name("spf_version")
record = version + Group(terms).set_results_name("terms") + ZeroOrMore(SP) + StringEnd()


def parse(spf_record):
    try:
        return record.parse_string(spf_record)
    except Exception:
        return None
