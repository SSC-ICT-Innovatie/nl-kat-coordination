import re
import tempfile
from collections.abc import Collection, Sequence
from enum import Enum
from functools import total_ordering
from typing import Any, ClassVar, Self, cast

import structlog
import tagulous.models
from django.apps import apps
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import connections, models
from django.db.models import ForeignKey, Model
from django.db.models.expressions import RawSQL
from django.db.models.fields.related import RelatedField
from django.forms.models import model_to_dict
from django.utils.datastructures import CaseInsensitiveMapping
from django.utils.translation import gettext_lazy as _
from djangoql.schema import DjangoQLSchema, IntField
from psycopg import sql
from tldextract import tldextract
from transit.writer import Writer

from openkat.models import ORGANIZATION_CODE_LENGTH, LowerCaseCharField, LowerCaseSlugField

logger = structlog.get_logger(__name__)


def object_type_by_name() -> CaseInsensitiveMapping[type[models.Model]]:
    return CaseInsensitiveMapping({model.__name__: model for model in apps.get_app_config("objects").get_models()})


def to_xtdb_dict(model: "XTDBModel") -> dict:
    model.clean()
    mod = model_to_dict(model, exclude=["id"] + [field.name for field in model._meta.many_to_many])

    if hasattr(model, "natural_key"):
        mod["_id"] = model.natural_key
    else:
        mod["_id"] = model.pk

    if "_valid_from" in mod:
        del mod["_valid_from"]

    for field in model._meta.fields:
        if isinstance(field, ForeignKey):
            if not mod[field.name] and issubclass(field.model, XTDBNaturalKeyModel) and getattr(model, field.name):
                mod[field.name] = getattr(model, field.name).natural_key
            mod[field.name + "_id"] = mod[field.name]
            del mod[field.name]
            continue

    return mod


class ScanLevelEnum(models.IntegerChoices):
    L0 = 0, "L0"
    L1 = 1, "L1"
    L2 = 2, "L2"
    L3 = 3, "L3"
    L4 = 4, "L4"


MAX_SCAN_LEVEL = max(scan_level.value for scan_level in cast("type[Enum]", ScanLevelEnum))


class XTDBQuerySet(models.QuerySet):
    def bulk_create(
        self,
        objs: Sequence[models.Model],
        batch_size: int | None = None,
        ignore_conflicts: bool = False,
        update_conflicts: bool = False,
        update_fields: Collection[str] | None = None,
        unique_fields: Collection[str] | None = None,
    ) -> list[models.Model]:
        o = []
        for obj in objs:
            o.append(obj.save())  # Because the pks are set, django would resolve to updates

        return o


class XTDBModel(models.Model):
    # This seems to be the only way to avoid Django trying to set the field in any instance, while still being able to
    # query the field.
    _valid_from: models.DateTimeField = models.GeneratedField(
        expression=RawSQL("_valid_from", ()), output_field=models.DateTimeField(), db_persist=False
    )

    class Meta:
        managed = False
        abstract = True

    objects = XTDBQuerySet.as_manager()

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        super().save(force_insert=True, force_update=False, using=using, update_fields=None)

    @property
    def last_seen(self):
        return self._valid_from


class XTDBOrganizationTag(tagulous.models.TagTreeModel):
    COLOR_CHOICES = settings.TAG_COLORS
    BORDER_TYPE_CHOICES = settings.TAG_BORDER_TYPES

    color = models.CharField(choices=COLOR_CHOICES, max_length=20, default=COLOR_CHOICES[0][0])
    border_type = models.CharField(choices=BORDER_TYPE_CHOICES, max_length=20, default=BORDER_TYPE_CHOICES[0][0])

    class TagMeta:
        force_lowercase = True
        protect_all = True


class XTDBOrganization(XTDBModel):
    name = models.CharField(max_length=126, unique=True, help_text=_("The name of the organisation"))
    code = LowerCaseSlugField(
        max_length=ORGANIZATION_CODE_LENGTH,
        unique=True,
        allow_unicode=True,
        help_text=_(
            "A slug containing only lower-case unicode letters, numbers, hyphens or underscores "
            "that will be used in URLs and paths"
        ),
    )
    tags = tagulous.models.TagField(to=XTDBOrganizationTag, blank=True)

    def __str__(self) -> str:
        return str(self.name)


class XTDBNaturalKeyModel(XTDBModel):
    id: models.CharField = models.CharField(primary_key=True, db_column="_id")

    _natural_key_attrs: ClassVar[list[str]]
    _optional_key_attrs: ClassVar[list[str]] = []

    @property
    def natural_key(self) -> str:
        parts = []

        for attr in self._natural_key_attrs:
            part = getattr(self, attr)
            if (part is None or part == "") and attr not in self._optional_key_attrs:
                raise ValueError("All natural key attributes must be set when saving object")

            if part is None:
                part = ""

            if isinstance(part, XTDBNaturalKeyModel):
                part = part.natural_key
            elif isinstance(part, Model):
                part = part.pk

            parts.append(str(part))

        return "|".join(parts).strip("|")

    @classmethod
    def from_natural_key(cls, key: str) -> Self:
        """
        Build the model op using only its natural key.

        IMPORTANT: this will not be consistent for fields not in the natural key. Make sure the code using this helper
        does not rely on those fields.

        :param eager: If true, allow the key to have additional parts at the end (useful building nested natural keys).
        """

        cnt, fields, parts = cls.natural_key_fields(key)

        if len(fields) < len(cls._natural_key_attrs):
            raise ValueError("Not enough attributes in natural key")

        if cnt < len(parts):
            raise ValueError("Too many attributes in natural key")

        return cls(**fields)

    @classmethod
    def natural_key_fields(cls, key: str) -> tuple[int, dict[Any, Any], list[str]]:
        parts = key.split("|")
        fields = {}
        cnt = 0

        # Iterate through the parts, and join parts if the field is a related model with a nested natural key.
        # For example, a DNSARecord with ["hostname", "ip_address"] and the natural key
        # "internet|test.com|internet|127.0.0.1" will need to build a fields dict of the form
        # {"hostname_id": "internet|test.com", "ip_address_id": "internet|127.0.0.1"}. The only way to know how to
        # partition the `parts` is to inspect the fields through cls._meta.fields and let them try to create their
        # natural key from the "left-over parts".
        fields_by_name = {field.name: field for field in cls._meta.fields}

        for attr in cls._natural_key_attrs:
            if not hasattr(cls, attr):
                raise ValueError(f"Invalid attribute in natural key: {attr}")
            if cnt >= len(parts):
                raise ValueError("Not enough attributes in natural key")

            field = fields_by_name[attr]

            if isinstance(field, RelatedField):
                if issubclass(field.related_model, XTDBNaturalKeyModel):
                    sub_cnt, nk_fields, _ = field.related_model.natural_key_fields("|".join(parts[cnt:]))
                    related = field.related_model(**nk_fields)
                    fields[field.name] = related
                    cnt += sub_cnt
                else:
                    field_name = field.name + "_id"
                    fields[field_name] = field.to_python(parts[cnt])
                    cnt += 1
            else:
                fields[attr] = field.to_python(parts[cnt])
                cnt += 1
        return cnt, fields, parts

    def save(self, *args: Any, **kwargs: Any) -> None:
        # TODO: Make sure this also is implemented in all the necessary model methods and manager methods
        if not self.id:
            self.id = self.natural_key
        elif self.id != self.natural_key:
            # We can't change the id field, so the natural key attributes should also not be changed
            raise Exception("Can't change natural key attributes, create new object and delete the old one")

        super().save(*args, **kwargs)

    class Meta(XTDBModel.Meta):
        managed = False
        abstract = True


class ObjectTask(XTDBNaturalKeyModel):
    task_id = models.CharField(max_length=36)  # UUID as string (36 chars with hyphens)
    type = models.CharField(max_length=32, default="plugin")
    plugin_id = models.CharField(max_length=64)
    output_object = models.CharField()
    output_object_type = models.CharField()

    _natural_key_attrs = ["task_id", "output_object"]


class Asset(XTDBModel):
    class Meta:
        managed = False
        abstract = True


class Network(Asset):
    name: LowerCaseCharField = LowerCaseCharField(primary_key=True, db_column="_id")
    scan_level: models.IntegerField = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(MAX_SCAN_LEVEL)], null=True, blank=True
    )
    declared: models.BooleanField = models.BooleanField(default=False)
    organizations = models.ManyToManyField(XTDBOrganization, related_name="networks", through="NetworkOrganization")

    def __str__(self) -> str:
        return self.name


class NetworkOrganization(XTDBNaturalKeyModel):
    network: models.ForeignKey = models.ForeignKey(Network, on_delete=models.PROTECT)
    organization: models.ForeignKey = models.ForeignKey(XTDBOrganization, on_delete=models.PROTECT)

    _natural_key_attrs = ["network", "organization"]


class IPAddress(XTDBNaturalKeyModel, Asset):  # type: ignore[misc]
    network: models.ForeignKey = models.ForeignKey(Network, on_delete=models.CASCADE)
    address: models.GenericIPAddressField = models.GenericIPAddressField(unpack_ipv4=True)
    scan_level: models.IntegerField = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(MAX_SCAN_LEVEL)], null=True, blank=True
    )
    declared: models.BooleanField = models.BooleanField(default=False)
    organizations = models.ManyToManyField(
        XTDBOrganization, related_name="ipaddresses", through="IPAddressOrganization"
    )

    _natural_key_attrs = ["network", "address"]

    def __str__(self) -> str:
        return self.address


class IPAddressOrganization(XTDBNaturalKeyModel):
    ipaddress: models.ForeignKey = models.ForeignKey(IPAddress, on_delete=models.PROTECT)
    organization: models.ForeignKey = models.ForeignKey(XTDBOrganization, on_delete=models.PROTECT)

    _natural_key_attrs = ["ipaddress", "organization"]


class Protocol(models.TextChoices):
    TCP = "TCP", "TCP"
    UDP = "UDP", "UDP"


class IPPort(XTDBNaturalKeyModel):
    address: models.ForeignKey = models.ForeignKey(IPAddress, on_delete=models.CASCADE)
    protocol: models.CharField = models.CharField(choices=Protocol)
    port: models.IntegerField = models.IntegerField(validators=[MinValueValidator(1), MaxValueValidator(65535)])
    tls: models.BooleanField = models.BooleanField(null=True)
    service: models.CharField = models.CharField()

    _natural_key_attrs = ["address", "protocol", "port"]

    def __str__(self) -> str:
        return f"[{self.address}]:{self.port}"


def validate_hostname(hostname: str) -> None:
    """
    Validate hostname according to RFC 1123.

    Rules:
    - Labels separated by dots
    - Each label must be 1-63 characters long
    - Total hostname length must not exceed 253 characters
    - Labels can contain letters (a-z, case-insensitive), digits (0-9), and hyphens (-)
    - Labels cannot start or end with a hyphen
    - At least one label is required

    Args:
        hostname: The hostname string to validate

    Raises:
        ValidationError: If the hostname does not comply with RFC 1123
    """
    if not hostname:
        raise ValidationError(_("Hostname cannot be empty."))

    # Check total length (RFC 1123: max 253 characters)
    if len(hostname) > 253:
        raise ValidationError(
            _("Hostname is too long. Maximum length is 253 characters, got %(length)d.") % {"length": len(hostname)}
        )

    # Split into labels
    labels = hostname.split(".")

    # Check for empty labels (e.g., "example..com" or ".example.com")
    if any(not label for label in labels):
        raise ValidationError(_("Hostname cannot contain empty labels (consecutive dots or leading/trailing dots)."))

    # Validate each label
    # RFC 1123 allows labels to contain: letters, digits, hyphens
    # Labels cannot start or end with hyphens
    label_pattern = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$", re.IGNORECASE)

    for label in labels:
        # Check label length (RFC 1123: max 63 characters per label)
        if len(label) > 63:
            raise ValidationError(
                _("Label '%(label)s' is too long. Maximum length per label is 63 characters, got %(length)d.")
                % {"label": label, "length": len(label)}
            )

        # Check label format
        if not label_pattern.match(label):
            if label.startswith("-") or label.endswith("-"):
                raise ValidationError(_("Label '%(label)s' cannot start or end with a hyphen.") % {"label": label})
            else:
                raise ValidationError(
                    _("Label '%(label)s' contains invalid characters. Only letters, digits, and hyphens are allowed.")
                    % {"label": label}
                )


class Hostname(XTDBNaturalKeyModel, Asset):  # type: ignore[misc]
    dnsarecord_set: models.Manager["DNSARecord"]
    dnsaaaarecord_set: models.Manager["DNSAAAARecord"]
    dnscnamerecord_set: models.Manager["DNSCNAMERecord"]
    dnsmxrecord_set: models.Manager["DNSMXRecord"]
    dnsnsrecord_set: models.Manager["DNSNSRecord"]
    dnsptrrecord_set: models.Manager["DNSPTRRecord"]
    dnscaarecord_set: models.Manager["DNSCAARecord"]
    dnstxtrecord_set: models.Manager["DNSTXTRecord"]
    dnssrvrecord_set: models.Manager["DNSSRVRecord"]
    dnscnamerecord_target_set: models.Manager["DNSCNAMERecord"]
    dnsmxrecord_mailserver: models.Manager["DNSMXRecord"]
    dnsnsrecord_nameserver: models.Manager["DNSNSRecord"]

    class Q:
        """A set of useful DjangoQL queries for Hostname"""

        mail_server = "dnsmxrecord_mailserver != None"
        name_server = "dnsnsrecord_nameserver != None"
        root_domain = "root = True"

    network: models.ForeignKey = models.ForeignKey(Network, on_delete=models.CASCADE)
    name: LowerCaseCharField = LowerCaseCharField()
    root: models.BooleanField = models.BooleanField(default=False)
    scan_level: models.IntegerField = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(MAX_SCAN_LEVEL)], null=True, blank=True
    )
    declared: models.BooleanField = models.BooleanField(default=False)
    organizations = models.ManyToManyField(XTDBOrganization, related_name="hostnames", through="HostnameOrganization")

    _natural_key_attrs = ["network", "name"]

    def __str__(self) -> str:
        return self.name

    def clean(self) -> None:
        """Validate and normalize the hostname."""
        super().clean()

        # Normalize: remove single trailing dot (FQDN notation)
        # Multiple trailing dots are invalid and will be caught by validation
        if self.name and self.name.endswith(".") and not self.name.endswith(".."):
            self.name = self.name.rstrip(".")

        # Validate hostname according to RFC 1123
        if self.name:
            validate_hostname(self.name)

    def save(self, *args, **kwargs):
        # Normalize single trailing dot before any processing (FQDN notation)
        # Multiple trailing dots are invalid and will be caught by validation
        if self.name and self.name.endswith(".") and not self.name.endswith(".."):
            self.name = self.name.rstrip(".")

        # Validate hostname (but don't run full_clean which validates the entire model including id)
        if self.name:
            validate_hostname(self.name)

        if self.name:
            extracted = tldextract.extract(self.name)
            registered_domain = extracted.top_domain_under_public_suffix.rstrip(".")
            self.root = self.name == registered_domain

            # If this is a subdomain, ensure the root domain exists
            if not self.root and registered_domain:
                root_hostname, created = Hostname.objects.get_or_create(
                    network=self.network, name=registered_domain, defaults={"root": True}
                )
                # Ensure root flag is set correctly if it already existed
                if not created and not root_hostname.root:
                    root_hostname.root = True
                    root_hostname.save(update_fields=["root"])

        super().save(*args, **kwargs)


class HostnameOrganization(XTDBNaturalKeyModel):
    hostname: models.ForeignKey = models.ForeignKey(Hostname, on_delete=models.PROTECT)
    organization: models.ForeignKey = models.ForeignKey(XTDBOrganization, on_delete=models.PROTECT)

    _natural_key_attrs = ["hostname", "organization"]


class NoOrgQLSchema(DjangoQLSchema):
    exclude = (XTDBOrganization, XTDBOrganizationTag)


class HostnameQLSchema(NoOrgQLSchema):
    """Custom schema to support nameservers_with_ipv6_count field for Hostname queries"""

    def get_fields(self, model):
        fields = super().get_fields(model)
        if model == Hostname:
            fields += [IntField(name="nameservers_with_ipv6_count")]
        return fields


class FindingType(XTDBModel):
    code = models.CharField(primary_key=True, db_column="_id")
    name = models.CharField(null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    source = models.CharField(null=True, blank=True)
    risk = models.CharField(null=True, blank=True)
    impact = models.TextField(null=True, blank=True)
    recommendation = models.TextField(null=True, blank=True)
    score = models.FloatField(validators=[MinValueValidator(0.0), MaxValueValidator(10.0)], null=True)


class Finding(XTDBNaturalKeyModel):
    finding_type: models.ForeignKey = models.ForeignKey(FindingType, on_delete=models.PROTECT)
    hostname: models.ForeignKey = models.ForeignKey(Hostname, null=True, on_delete=models.CASCADE)
    address: models.ForeignKey = models.ForeignKey(IPAddress, null=True, on_delete=models.CASCADE)

    organizations = models.ManyToManyField(
        XTDBOrganization, blank=True, related_name="findings", through="FindingOrganization"
    )

    _natural_key_attrs = ["finding_type", "hostname", "address"]
    # FIXME: Check if at least one is set
    _optional_key_attrs = ["hostname", "address"]


class FindingOrganization(XTDBNaturalKeyModel):
    finding: models.ForeignKey = models.ForeignKey(Finding, on_delete=models.PROTECT)
    organization: models.ForeignKey = models.ForeignKey(XTDBOrganization, on_delete=models.PROTECT)

    _natural_key_attrs = ["finding", "organization"]


class DNSRecordBase(XTDBNaturalKeyModel):
    ttl: models.IntegerField = models.IntegerField()

    class Meta:
        managed = False
        abstract = True


class DNSARecord(DNSRecordBase):
    hostname: models.ForeignKey = models.ForeignKey(Hostname, on_delete=models.CASCADE)
    ip_address: models.ForeignKey = models.ForeignKey(IPAddress, on_delete=models.PROTECT)

    hostname_id: str

    _natural_key_attrs = ["hostname", "ip_address"]

    def __str__(self) -> str:
        return f"{self.hostname} A {self.ip_address}"


class DNSAAAARecord(DNSRecordBase):
    hostname: models.ForeignKey = models.ForeignKey(Hostname, on_delete=models.CASCADE)
    ip_address: models.ForeignKey = models.ForeignKey(IPAddress, on_delete=models.PROTECT)

    _natural_key_attrs = ["hostname", "ip_address"]

    def __str__(self) -> str:
        return f"{self.hostname} AAAA {self.ip_address}"


class DNSPTRRecord(DNSRecordBase):
    hostname: models.ForeignKey = models.ForeignKey(Hostname, on_delete=models.CASCADE)
    ip_address: models.ForeignKey = models.ForeignKey(IPAddress, on_delete=models.PROTECT)

    _natural_key_attrs = ["hostname", "ip_address"]

    def __str__(self) -> str:
        return f"{self.ip_address} PTR {self.hostname}"


class DNSCNAMERecord(DNSRecordBase):
    hostname: models.ForeignKey = models.ForeignKey(Hostname, on_delete=models.CASCADE)
    target: models.ForeignKey = models.ForeignKey(
        Hostname, on_delete=models.PROTECT, related_name="dnscnamerecord_target_set"
    )

    _natural_key_attrs = ["hostname", "target"]

    def __str__(self) -> str:
        return f"{self.hostname} CNAME {self.target}"


class DNSMXRecord(DNSRecordBase):
    hostname: models.ForeignKey = models.ForeignKey(Hostname, on_delete=models.CASCADE)
    mail_server: models.ForeignKey = models.ForeignKey(
        Hostname, on_delete=models.PROTECT, related_name="dnsmxrecord_mailserver"
    )
    preference: models.IntegerField = models.IntegerField()

    _natural_key_attrs = ["hostname", "preference", "mail_server"]

    def __str__(self) -> str:
        return f"{self.hostname} MX {self.preference} {self.mail_server}"


class DNSNSRecord(DNSRecordBase):
    hostname: models.ForeignKey = models.ForeignKey(Hostname, on_delete=models.CASCADE)
    name_server: models.ForeignKey = models.ForeignKey(
        Hostname, on_delete=models.PROTECT, related_name="dnsnsrecord_nameserver"
    )

    _natural_key_attrs = ["hostname", "name_server"]

    def __str__(self) -> str:
        return f"{self.hostname} NS {self.name_server}"


class CAATag(models.TextChoices):
    CONTACTEMAIL = "contactemail", "contactemail"
    CONTACTPHONE = "contactphone", "contactphone"
    IODEF = "iodef", "iodef"
    ISSUE = "issue", "issue"
    ISSUEMAIL = "issuemail", "issuemail"
    ISSUEVMC = "issuevmc", "issuevmc"
    ISSUEWILD = "issuewild", "issuewild"


class DNSCAARecord(DNSRecordBase):
    hostname: models.ForeignKey = models.ForeignKey(Hostname, on_delete=models.CASCADE)
    flags: models.IntegerField = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(255)])
    tag: models.CharField = models.CharField(choices=CAATag)
    value: models.CharField = models.CharField()

    _natural_key_attrs = ["hostname", "flags", "tag", "value"]

    def __str__(self) -> str:
        return f"{self.hostname} CAA {self.flags} {self.tag} {self.value}"


class DNSTXTRecord(DNSRecordBase):
    hostname: models.ForeignKey = models.ForeignKey(Hostname, on_delete=models.CASCADE)
    prefix: models.CharField = models.CharField(blank=True)
    value: models.CharField = models.CharField()

    _natural_key_attrs = ["hostname", "prefix", "value"]
    _optional_key_attrs = ["prefix"]

    def __str__(self) -> str:
        prefix_part = f"{self.prefix}." if self.prefix else ""
        return f"{prefix_part}{self.hostname} TXT {self.value}"


class DNSSRVRecord(DNSRecordBase):
    hostname: models.ForeignKey = models.ForeignKey(Hostname, on_delete=models.CASCADE)
    proto: LowerCaseCharField = LowerCaseCharField()
    service: LowerCaseCharField = LowerCaseCharField()
    priority: models.IntegerField = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(65535)])
    weight: models.IntegerField = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(65535)])
    port: models.IntegerField = models.IntegerField(validators=[MinValueValidator(0), MaxValueValidator(65535)])

    _natural_key_attrs = ["hostname", "proto", "service", "priority", "weight", "port"]

    def __str__(self) -> str:
        return f"_{self.service}._{self.proto}.{self.hostname} SRV {self.priority} {self.weight} {self.port}"


class Software(XTDBNaturalKeyModel):
    name: models.CharField = models.CharField()
    version: models.CharField = models.CharField(null=True, blank=True)
    cpe: models.CharField = models.CharField(null=True, blank=True)
    ports: models.ManyToManyField = models.ManyToManyField(IPPort, blank=True, related_name="software")

    _natural_key_attrs = ["name", "version"]
    _optional_key_attrs = ["version"]


def bulk_insert(objects: Sequence[models.Model]) -> None:
    """Use COPY to efficiently bulk-insert objects into XTDB. Assumes objects have the same type, skips other types."""

    if not objects:
        return

    table_name = objects[0]._meta.db_table

    with tempfile.NamedTemporaryFile() as fp:
        # The transit-json format is not working because the writer uses a comma as a delimiter between objects. It
        # would work if we override Writer.marshaler.write_sep() to skip the comma (or use a newline) between objects.
        # But apparently msgpack works out of the box, which makes life even easier.

        writer = Writer(fp, "msgpack")
        for obj in objects:
            if obj._meta.db_table != table_name:
                continue
            writer.write(to_xtdb_dict(obj))

        fp.seek(0)

        with (
            connections["xtdb"].cursor() as cursor,
            cursor.copy(
                sql.SQL("COPY {} FROM STDIN WITH (FORMAT 'transit-msgpack')").format(sql.Identifier(table_name))
            ) as copy,
        ):
            while data := fp.read():
                copy.write(data)


severity_order = ["recommendation", "low", "medium", "high", "critical"]


@total_ordering
class RiskLevelSeverity(Enum):
    """Represents the risk level severity of findings"""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    RECOMMENDATION = "recommendation"

    def __gt__(self, other: "RiskLevelSeverity") -> bool:
        return severity_order.index(self.value) > severity_order.index(other.value)

    def __str__(self) -> str:
        return self.value


SEVERITY_SCORE_LOOKUP = {
    RiskLevelSeverity.CRITICAL.value: 10.0,
    RiskLevelSeverity.HIGH.value: 8.9,
    RiskLevelSeverity.MEDIUM.value: 6.9,
    RiskLevelSeverity.LOW.value: 3.9,
    RiskLevelSeverity.RECOMMENDATION.value: 0.0,
}
