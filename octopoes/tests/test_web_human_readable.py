from octopoes.models import Reference
from octopoes.models.ooi.web import ImageMetadata


def test_imagemetadata_human_readable_with_hostname_http_url_resource():
    # check_images (webpage-capture / webpage-analysis screenshots) produces
    # ImageMetadata(resource=<HostnameHTTPURL>), whose primary key has fewer tokens
    # than an HTTPResource. format_reference_human_readable must fall back to
    # HostnameHTTPURL parsing rather than raising a pydantic ValidationError, which
    # would 500 the object list wherever such an ImageMetadata is rendered.
    reference = Reference.from_str("ImageMetadata|https|internet|example.com|443|/")

    assert ImageMetadata.format_reference_human_readable(reference) == "https://example.com:443/"
