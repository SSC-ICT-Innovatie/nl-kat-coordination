from boefjes.plugins.kat_finding_normalizer.normalize import run


def test_mailto_with_subject_parameter_does_not_crash():
    input_ooi = {"website": {"hostname": {"network": {"name": "internet"}, "name": "example.com"}}}
    raw = b'<a href="mailto:info@example.com?subject=hi">mail</a>'
    results = list(run(input_ooi, raw))
    assert "EmailAddress|info|internet|example.com" in [r.primary_key for r in results]
