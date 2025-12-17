from typing import Any

from rest_framework import serializers
from rest_framework.fields import CharField, SerializerMethodField
from rest_framework.relations import PrimaryKeyRelatedField, SlugRelatedField

from objects.models import (
    DNSAAAARecord,
    DNSARecord,
    DNSCAARecord,
    DNSCNAMERecord,
    DNSMXRecord,
    DNSNSRecord,
    DNSPTRRecord,
    DNSSRVRecord,
    DNSTXTRecord,
    Finding,
    FindingType,
    Hostname,
    IPAddress,
    IPPort,
    Network,
    Software,
)


class GetOrCreateSerializer(serializers.ModelSerializer):
    def create(self, validated_data):
        obj, created = self.Meta.model.objects.get_or_create(**validated_data)

        return obj


class FindingTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = FindingType
        exclude = ["_valid_from"]
        read_only_fields = ["id"]


class FindingSerializer(serializers.ModelSerializer):
    finding_type = SlugRelatedField(slug_field="code", read_only=True)
    finding_type_code = CharField(write_only=True)

    hostname = CharField(write_only=True, required=False, allow_null=True)
    ipaddress = CharField(write_only=True, required=False, allow_null=True)

    hostname_id = PrimaryKeyRelatedField(source="hostname", read_only=True)
    ip_address_id = PrimaryKeyRelatedField(source="ip_address", read_only=True)

    def create(self, validated_data):
        hostname_name = validated_data.pop("hostname", None)
        ipaddress_str = validated_data.pop("ipaddress", None)

        hostname_obj = None
        ip_address_obj = None

        if hostname_name:
            hostname_obj = Hostname.objects.get(name=hostname_name)
        elif ipaddress_str:
            ip_address_obj = IPAddress.objects.get(ip_address=ipaddress_str)

        ft, created = FindingType.objects.get_or_create(code=validated_data.pop("finding_type_code"))
        f, created = Finding.objects.get_or_create(
            finding_type=ft, hostname=hostname_obj, ip_address=ip_address_obj, **validated_data
        )
        return f

    class Meta:
        model = Finding
        exclude = ["_valid_from"]
        read_only_fields = ["id"]


class NetworkSerializer(serializers.ModelSerializer):
    class Meta:
        model = Network
        exclude = ["_valid_from"]
        read_only_fields = ["id"]


class HostnameSerializer(GetOrCreateSerializer):
    dns_records = SerializerMethodField(read_only=True)

    def get_dns_records(self, obj: Hostname) -> list[dict[str, Any]]:
        dns = []

        for field, serializer_class in [
            (obj.dnsarecord_set, DNSARecordSerializer),
            (obj.dnsaaaarecord_set, DNSAAAARecordSerializer),
            (obj.dnscnamerecord_set, DNSCNAMERecordSerializer),
            (obj.dnsmxrecord_set, DNSMXRecordSerializer),
            (obj.dnstxtrecord_set, DNSTXTRecordSerializer),
            (obj.dnsnsrecord_set, DNSNSRecordSerializer),
            (obj.dnsptrrecord_set, DNSPTRRecordSerializer),
            (obj.dnscaarecord_set, DNSCAARecordSerializer),
            (obj.dnssrvrecord_set, DNSSRVRecordSerializer),
        ]:
            serializer = serializer_class(data=list(field.all()), many=True)
            serializer.is_valid()
            dns.extend([dns | {"object_type": serializer_class.Meta.model.__name__.lower()} for dns in serializer.data])

        return dns

    class Meta:
        model = Hostname
        exclude = ["_valid_from"]
        read_only_fields = ["id"]


class SoftwareSerializer(GetOrCreateSerializer):
    class Meta:
        model = Software
        exclude = ["_valid_from"]
        read_only_fields = ["id"]


class IPAddressSerializer(GetOrCreateSerializer):
    class Meta:
        model = IPAddress
        exclude = ["_valid_from"]
        read_only_fields = ["id"]


class IPPortSerializer(GetOrCreateSerializer):
    ip_address = CharField(write_only=True)
    ip_address_id = PrimaryKeyRelatedField(source="ip_address", read_only=True)
    software = SoftwareSerializer(many=True, default=[])

    def create(self, validated_data):
        ip_address = validated_data.pop("ip_address")
        ip, created = IPAddress.objects.get_or_create(ip_address=ip_address)

        port = validated_data.pop("port")
        software = validated_data.pop("software")
        ipport, created = IPPort.objects.get_or_create(ip_address=ip, port=port, defaults=validated_data)

        for s in software:
            name = s.pop("name")
            obj, created = Software.objects.get_or_create(name=name, defaults=s)
            ipport.software.add(obj)

        return ipport

    class Meta:
        model = IPPort
        exclude = ["_valid_from"]
        read_only_fields = ["id"]


class DNSARecordSerializer(GetOrCreateSerializer):
    class Meta:
        model = DNSARecord
        exclude = ["_valid_from"]
        read_only_fields = ["id"]


class DNSAAAARecordSerializer(GetOrCreateSerializer):
    class Meta:
        model = DNSAAAARecord
        exclude = ["_valid_from"]
        read_only_fields = ["id"]


class DNSPTRRecordSerializer(GetOrCreateSerializer):
    class Meta:
        model = DNSPTRRecord
        exclude = ["_valid_from"]
        read_only_fields = ["id"]


class DNSCNAMERecordSerializer(GetOrCreateSerializer):
    class Meta:
        model = DNSCNAMERecord
        exclude = ["_valid_from"]
        read_only_fields = ["id"]


class DNSMXRecordSerializer(GetOrCreateSerializer):
    class Meta:
        model = DNSMXRecord
        exclude = ["_valid_from"]
        read_only_fields = ["id"]


class DNSNSRecordSerializer(GetOrCreateSerializer):
    class Meta:
        model = DNSNSRecord
        exclude = ["_valid_from"]
        read_only_fields = ["id"]


class DNSCAARecordSerializer(GetOrCreateSerializer):
    class Meta:
        model = DNSCAARecord
        exclude = ["_valid_from"]
        read_only_fields = ["id"]


class DNSTXTRecordSerializer(GetOrCreateSerializer):
    class Meta:
        model = DNSTXTRecord
        exclude = ["_valid_from"]
        read_only_fields = ["id"]


class DNSSRVRecordSerializer(GetOrCreateSerializer):
    class Meta:
        model = DNSSRVRecord
        exclude = ["_valid_from"]
        read_only_fields = ["id"]
