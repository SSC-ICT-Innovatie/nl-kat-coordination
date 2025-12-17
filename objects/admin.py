from django.contrib import admin

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
    Hostname,
    IPAddress,
    IPPort,
    Network,
)


@admin.register(Network)
class NetworkAdmin(admin.ModelAdmin):
    list_display = ("name", "scan_level", "declared")
    search_fields = ("name", "scan_level", "declared")
    ordering = ("name",)


@admin.register(IPAddress)
class IPAddressAdmin(admin.ModelAdmin):
    list_display = ("ip_address", "network", "scan_level", "declared")
    list_filter = ("network", "scan_level", "declared")
    search_fields = ("ip_address",)
    ordering = ("ip_address",)


@admin.register(IPPort)
class IPPortAdmin(admin.ModelAdmin):
    list_display = ("ip_address", "protocol", "port")
    list_filter = ("protocol",)
    search_fields = ("ip_address__ip_address", "port")
    ordering = ("ip_address__ip_address", "port")


@admin.register(Hostname)
class HostnameAdmin(admin.ModelAdmin):
    list_display = ("name", "network", "scan_level", "declared")
    list_filter = ("network", "scan_level", "declared")
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(DNSARecord)
class DNSARecordAdmin(admin.ModelAdmin):
    list_display = ("hostname", "ip_address", "ttl")
    list_filter = ("ttl",)
    search_fields = ("hostname__name", "ip_address__ip_address")
    ordering = ("hostname__name",)


@admin.register(DNSAAAARecord)
class DNSAAAARecordAdmin(admin.ModelAdmin):
    list_display = ("hostname", "ip_address", "ttl")
    list_filter = ("ttl",)
    search_fields = ("hostname__name", "ip_address__ip_address")
    ordering = ("hostname__name",)


@admin.register(DNSPTRRecord)
class DNSPTRRecordAdmin(admin.ModelAdmin):
    list_display = ("ip_address", "hostname", "ttl")
    list_filter = ("ttl",)
    search_fields = ("hostname__name", "ip_address__ip_address")
    ordering = ("ip_address__ip_address",)


@admin.register(DNSCNAMERecord)
class DNSCNAMERecordAdmin(admin.ModelAdmin):
    list_display = ("hostname", "target", "ttl")
    list_filter = ("ttl",)
    search_fields = ("hostname__name", "target__name")
    ordering = ("hostname__name",)


@admin.register(DNSMXRecord)
class DNSMXRecordAdmin(admin.ModelAdmin):
    list_display = ("hostname", "mail_server", "preference", "ttl")
    list_filter = ("preference", "ttl")
    search_fields = ("hostname__name", "mail_server__name")
    ordering = ("hostname__name", "preference")


@admin.register(DNSNSRecord)
class DNSNSRecordAdmin(admin.ModelAdmin):
    list_display = ("hostname", "name_server", "ttl")
    list_filter = ("ttl",)
    search_fields = ("hostname__name", "name_server__name")
    ordering = ("hostname__name",)


@admin.register(DNSCAARecord)
class DNSCAARecordAdmin(admin.ModelAdmin):
    list_display = ("hostname", "flags", "tag", "value", "ttl")
    list_filter = ("flags", "tag", "ttl")
    search_fields = ("hostname__name", "value")
    ordering = ("hostname__name",)


@admin.register(DNSTXTRecord)
class DNSTXTRecordAdmin(admin.ModelAdmin):
    list_display = ("hostname", "prefix", "value", "ttl")
    list_filter = ("prefix", "ttl")
    search_fields = ("hostname__name", "prefix", "value")
    ordering = ("hostname__name",)


@admin.register(DNSSRVRecord)
class DNSSRVRecordAdmin(admin.ModelAdmin):
    list_display = ("hostname", "service", "proto", "priority", "weight", "port", "ttl")
    list_filter = ("service", "proto", "priority", "ttl")
    search_fields = ("hostname__name", "service", "proto")
    ordering = ("hostname__name", "service", "proto")
