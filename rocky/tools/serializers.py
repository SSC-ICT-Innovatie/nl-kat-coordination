from rest_framework.serializers import PrimaryKeyRelatedField, Serializer
from tagulous.contrib.drf import TagSerializer

from tools.models import Organization


class OrganizationSerializer(TagSerializer):
    class Meta:
        model = Organization
        fields = ["id", "name", "code", "tags"]


class OrganizationSerializerReadOnlyCode(TagSerializer):
    class Meta:
        model = Organization
        fields = ["id", "name", "code", "tags"]
        read_only_fields = ["code"]


class ToOrganizationSerializer(Serializer):
    to_organization = PrimaryKeyRelatedField(queryset=Organization.objects.all())
