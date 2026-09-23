from boefjes.plugins.kat_webpage_analysis.find_email_in_html.normalize import run


def test_mailto_with_subject_parameter_does_not_crash():
    pk = "HTTPResource|internet|1.2.3.4|tcp|443|https|internet|example.com|https|internet|example.com|443|/"
    input_ooi = {"primary_key": pk, "website": {"hostname": {"network": {"name": "internet"}, "name": "example.com"}}}
    raw = b'<a href="mailto:info@example.com?subject=hi">mail</a>'
    results = list(run(input_ooi, raw))
    assert "EmailAddress|info|internet|example.com" in [r.primary_key for r in results]
