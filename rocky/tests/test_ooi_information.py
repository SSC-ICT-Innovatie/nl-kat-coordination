from pathlib import Path

from tools.add_ooi_information import get_info, port_info, service_info


def test_port_info(mocker):
    requests_patch = mocker.patch("tools.add_ooi_information.httpx")
    requests_patch.get().text = (Path(__file__).parent / "stubs" / "wiki.html").read_text()

    descriptions, source = port_info("80", "TCP")

    assert descriptions == (
        "Hypertext Transfer Protocol (HTTP)[48][49] uses TCP in versions 1.x and 2. "
        "HTTP/3 uses QUIC,[50] a transport protocol on top of UDP."
    )
    assert source == "https://en.wikipedia.org/wiki/List_of_TCP_and_UDP_port_numbers"

    descriptions, source = port_info("443", "UDP")
    assert descriptions == (
        "Hypertext Transfer Protocol Secure (HTTPS)[48][49] uses TCP in versions 1.x "
        "and 2. HTTP/3 uses QUIC,[50] a transport protocol on top of UDP."
    )


def test_service_info(mocker):
    requests_patch = mocker.patch("tools.add_ooi_information.httpx")
    requests_patch.get().text = (Path(__file__).parent / "stubs" / "iana_service.html").read_text()

    description, source = service_info("ssh")

    assert (
        description == "Service is usually on port 22, with protocol tcp: The Secure Shell (SSH) Protocol. "
        "Service is usually on port 22, with protocol udp: The Secure Shell (SSH) Protocol. "
        "Service is usually on port 22, with protocol sctp: SSH. Service is usually on port None, "
        "with protocol tcp: SSH Remote Login Protocol"
    )

    assert source == "https://www.iana.org/assignments/service-names-port-numbers/service-names-port-numbers.xhtml"

    output = get_info("Service", "ssh")
    output.pop("information updated")  # Remove timestamp

    assert output == {"description": description, "source": source}
