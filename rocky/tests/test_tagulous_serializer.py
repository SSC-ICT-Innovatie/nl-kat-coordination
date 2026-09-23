from unittest.mock import patch

from django.core import serializers


def test_tagulous_python_serializer_roundtrip(organization):
    """Regression guard for the Django/tagulous serializer coupling (#5319).

    settings.SERIALIZATION_MODULES routes the "python" serializer through
    tagulous, which monkeypatches a private Django deserializer hook at import
    time (_get_model on Django <= 5.1, Deserializer._get_model_from_node on
    5.2+). Nothing else in the test suite loads this serializer, so an
    incompatible Django/tagulous combination (e.g. Django 5.2 with tagulous
    2.1.1) only surfaced during the native build. This roundtrip fails loudly
    on such a combination.
    """
    with patch("katalogus.client.KATalogusClient"), patch("rocky.signals.OctopoesAPIConnector"):
        organization.tags = ["roundtrip"]
        organization.save()

    data = serializers.serialize("python", [organization])
    assert data[0]["fields"]["tags"] == ["roundtrip"]

    restored = list(serializers.deserialize("python", data))
    assert restored[0].object.code == organization.code
