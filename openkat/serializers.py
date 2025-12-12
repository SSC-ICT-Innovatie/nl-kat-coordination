from rest_framework.serializers import PrimaryKeyRelatedField, Serializer
from tagulous.contrib.drf import TagSerializer

from openkat.models import Organization


class OrganizationSerializer(TagSerializer):
    class Meta:
        model = Organization
        fields = ["id", "name", "tags"]


class ToOrganizationSerializer(Serializer):
    to_organization = PrimaryKeyRelatedField(queryset=Organization.objects.all())
