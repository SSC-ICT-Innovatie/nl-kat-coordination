import io
import json
import zipfile

from boefjes.plugins.kat_external_links_in_capture.normalize import run as run_external
from boefjes.plugins.kat_links_in_capture.links import registrable_domain
from boefjes.plugins.kat_links_in_capture.normalize import run as run_in_zone

INPUT_URL = "HostnameHTTPURL|https|internet|demo.dvwa.cloud|443|/"


def har_zip(
    body: str,
    url: str = "https://demo.dvwa.cloud/",
    mime: str = "text/html",
    redirect_first: bool = False,
    extra_entries: list | None = None,
):
    """A Playwright HAR archive: the HAR document plus its bodies as separate members."""
    entries = list(extra_entries or [])

    if redirect_first:
        entries.append(
            {
                "request": {"url": "http://demo.dvwa.cloud/"},
                "response": {"status": 301, "content": {"mimeType": "text/html", "text": ""}},
            }
        )

    entries.append({"request": {"url": url}, "response": {"content": {"mimeType": mime, "_file": "body.html"}}})

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("har.har", json.dumps({"log": {"entries": entries}}))
        archive.writestr("body.html", body)

    return buffer.getvalue()


def links(*hrefs: str) -> str:
    return "<html><body>" + "".join(f'<a href="{href}">x</a>' for href in hrefs) + "</body></html>"


def names(results) -> list[str]:
    return sorted(ooi.name for ooi in results)


def test_finds_subdomains_linked_from_the_page():
    """The hub page of dvwa.cloud links to subdomains that no other source reports."""
    raw = har_zip(
        links(
            "https://api.dvwa.cloud/",
            "https://log4shell.dvwa.cloud/",
            "/relative/path",  # the page's own host: not a discovery
            "https://www.linkedin.com/company/x",
        )
    )

    result = list(run_in_zone({"primary_key": INPUT_URL}, raw))

    assert names(result) == ["api.dvwa.cloud", "dvwa.cloud", "log4shell.dvwa.cloud"]
    assert "www.linkedin.com" not in names(result)


def test_subdomains_carry_their_apex_so_clearance_can_be_inherited():
    """registered_domain is what lets a cleared apex promote a discovered subdomain."""
    result = list(run_in_zone({"primary_key": INPUT_URL}, har_zip(links("https://api.dvwa.cloud/"))))

    subdomain = next(ooi for ooi in result if ooi.name == "api.dvwa.cloud")
    apex = next(ooi for ooi in result if ooi.name == "dvwa.cloud")

    assert subdomain.registered_domain == apex.reference
    # The apex itself must not point at itself.
    assert apex.registered_domain is None


def test_external_normalizer_yields_only_the_other_side():
    raw = har_zip(links("https://api.dvwa.cloud/", "https://www.linkedin.com/company/x"))

    assert names(run_external({"primary_key": INPUT_URL}, raw)) == ["linkedin.com", "www.linkedin.com"]
    assert names(run_in_zone({"primary_key": INPUT_URL}, raw)) == ["api.dvwa.cloud", "dvwa.cloud"]


def test_tenants_of_a_shared_platform_are_not_each_others_zone():
    """Without the private suffix list every tenant of a platform looks like one domain.

    `a.azurewebsites.net` linking to `b.azurewebsites.net` would then mint another
    customer's site as an in-zone asset, and Microsoft's apex as the organisation's
    registrable domain.
    """
    tenant = "HostnameHTTPURL|https|internet|klant-a.azurewebsites.net|443|/"
    raw = har_zip(links("https://klant-b.azurewebsites.net/"), url="https://klant-a.azurewebsites.net/")

    assert names(run_in_zone({"primary_key": tenant}, raw)) == []
    assert names(run_external({"primary_key": tenant}, raw)) == ["klant-b.azurewebsites.net"]

    assert registrable_domain("klant-a.azurewebsites.net") == "klant-a.azurewebsites.net"
    assert registrable_domain("demo.dvwa.cloud") == "dvwa.cloud"


def test_non_http_links_are_ignored():
    raw = har_zip(links("mailto:info@dvwa.cloud", "tel:+31123", "javascript:void(0)", "#anchor"))

    assert names(run_in_zone({"primary_key": INPUT_URL}, raw)) == []


def test_redirect_entry_without_a_body_is_skipped():
    raw = har_zip(links("https://api.dvwa.cloud/"), redirect_first=True)

    assert "api.dvwa.cloud" in names(run_in_zone({"primary_key": INPUT_URL}, raw))


def test_ip_input_has_no_zone_to_compare_against():
    """webpage-capture also runs on IPAddressHTTPURL, where there is no hostname."""
    raw = har_zip(links("https://api.dvwa.cloud/"))

    assert list(run_in_zone({"primary_key": "IPAddressHTTPURL|https|internet|1.2.3.4|443|/"}, raw)) == []
    assert list(run_external({"primary_key": "IPAddressHTTPURL|https|internet|1.2.3.4|443|/"}, raw)) == []


def test_capture_without_an_html_document_yields_nothing():
    raw = har_zip("{}", mime="application/json")

    assert list(run_in_zone({"primary_key": INPUT_URL}, raw)) == []


def test_redirect_with_its_own_html_body_is_not_mistaken_for_the_page():
    """A 301 often carries the server's default "Moved Permanently" page.

    Picking the first HTML-bodied entry would parse that and find no links at all.
    """
    redirect = {
        "request": {"url": "http://demo.dvwa.cloud/"},
        "response": {"status": 301, "content": {"mimeType": "text/html", "text": "<html><h1>Moved</h1></html>"}},
    }
    raw = har_zip(links("https://api.dvwa.cloud/"), extra_entries=[redirect])

    assert "api.dvwa.cloud" in names(run_in_zone({"primary_key": INPUT_URL}, raw))


def test_one_malformed_href_does_not_cost_the_whole_page():
    """urlparse raises on some hrefs; the task must not die on a single bad link."""
    raw = har_zip(links("https://api.dvwa.cloud]/", "https://app.dvwa.cloud/"))

    assert names(run_in_zone({"primary_key": INPUT_URL}, raw)) == ["app.dvwa.cloud", "dvwa.cloud"]


def test_a_hostname_the_model_rejects_does_not_cost_the_whole_page():
    """Underscores are common in the wild and the Hostname validator refuses them."""
    raw = har_zip(links("https://my_site.dvwa.cloud/", "https://app.dvwa.cloud/"))

    assert names(run_in_zone({"primary_key": INPUT_URL}, raw)) == ["app.dvwa.cloud", "dvwa.cloud"]


def test_internationalised_domains_are_compared_in_the_same_form():
    """Hostname punycodes its name, so the primary key and the href disagree.

    Without normalising, the in-zone normalizer finds nothing and the external one
    mints the organisation's own domain as a third-party host.
    """
    idn = "HostnameHTTPURL|https|internet|xn--mller-kva.de|443|/"
    raw = har_zip(links("https://shop.müller.de/"), url="https://xn--mller-kva.de/")

    # The apex is the input OOI here, so only the subdomain is new.
    found = list(run_in_zone({"primary_key": idn}, raw))
    assert names(found) == ["shop.xn--mller-kva.de"]
    assert found[0].registered_domain.tokenized.name == "xn--mller-kva.de"
    assert names(run_external({"primary_key": idn}, raw)) == []


def test_a_trailing_dot_is_the_same_host():
    """api.dvwa.cloud. would otherwise be a second Hostname inheriting the same L2."""
    raw = har_zip(links("https://api.dvwa.cloud./"))

    assert names(run_in_zone({"primary_key": INPUT_URL}, raw)) == ["api.dvwa.cloud", "dvwa.cloud"]


def test_base_href_changes_what_relative_links_point_at():
    body = '<html><head><base href="https://app.dvwa.cloud/"></head><body><a href="/x">x</a></body></html>'

    assert names(run_in_zone({"primary_key": INPUT_URL}, har_zip(body))) == ["app.dvwa.cloud", "dvwa.cloud"]


def test_a_page_that_is_its_own_apex_is_not_re_emitted():
    apex = "HostnameHTTPURL|https|internet|dvwa.cloud|443|/"
    raw = har_zip(links("https://dvwa.cloud/about", "https://api.dvwa.cloud/"), url="https://dvwa.cloud/")

    assert names(run_in_zone({"primary_key": apex}, raw)) == ["api.dvwa.cloud"]
