---
authors: Donny Peeters <@donnype>
state: implemented
discussion:
labels: Data Models, Objects, Organizations
---

# RFD 0014: Organization Attribution

## Introduction

OpenKAT V2 is a multi-tenant system where **organizations** are the primary unit of access control and segmentation.
In RFD 0005 and 0008, we established that:

- Files can belong to multiple organizations (many-to-many)
- Views filter data by organization
- Users have access to specific organizations

However, for objects (OOIs) like hostnames, IP addresses, and DNS records, we face a challenge:
**Which organization(s) should own each discovered object?**

When users add objects to OpenKAT, they do so within an organization context:

- User at Organization A adds `example.com` → belongs to Org A
- User at Organization B adds `192.0.2.0/24` → belongs to Org B

But scanning discovers many related objects:

- `example.com` resolves to `192.0.2.1` (via A record)
- `192.0.2.1` reverse-resolves to `mail.example.com` (via PTR record)
- `example.com` has MX record pointing to `mail.example.com`

**Should these discovered objects belong to:**

1. The organization that initiated the scan?
2. All organizations that have related objects?
3. A single "primary" organization?
4. No organization (shared pool)?

And: 5. How can we implement attribution of objects to organizations?

## Proposal

The core of this proposal is to:

1. **Add a many-to-many relationships** between objects and organizations
2. **Propagate organization membership like we propagate scan levels**

### Functional Requirements (FR)

1. As a user, I want OpenKAT to run largely independently and not to manage which orgs objects belong to manually.
2. Objects can belong to multiple organizations simultaneously
3. Users should only see objects belonging to their accessible organizations

### Extensibility (Potential Future Requirements)

1. Support organization-specific settings
2. Provide UI visibility into organization attribution paths
3. Support manual organization assignment overrides that persist
4. Add a confidence score to the attribution

## Implementation

The organization attribution system has been implemented as designed, largely like the scan level propagation.
All major object types have many-to-many relationships with Organization:

```python
class Hostname(XTDBNaturalKeyModel):
    ...
    organizations = models.ManyToManyField("openkat.Organization", related_name="hostnames")

class IPAddress(XTDBNaturalKeyModel):
    ...
    organizations = models.ManyToManyField("openkat.Organization", related_name="ip_addresses")

class Network(XTDBNaturalKeyModel):
    ...
    organizations = models.ManyToManyField("openkat.Organization", related_name="networks")
```

### Propagation Relationships

Similar to scan level propagation (RFD 0012), organization attribution propagates through DNS relationships,
see `tasks/tasks.py`.

```python
def attribute_through_cnames() -> None:
    try:
        with connections["xtdb"].cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO {HostnameOrganization._meta.db_table} (_id, hostname_id, organization_id)
                SELECT target._id ||'|'|| cast(osource.organization_id as varchar), target._id, osource.organization_id
                FROM {Hostname._meta.db_table} source
                RIGHT JOIN {DNSCNAMERecord._meta.db_table} dns on source._id = dns.target_id
                RIGHT JOIN {Hostname._meta.db_table} target ON target._id = dns.hostname_id
                RIGHT JOIN {HostnameOrganization._meta.db_table} osource ON source._id = osource.hostname_id
                LEFT JOIN {HostnameOrganization._meta.db_table} otarget ON target._id = otarget.hostname_id
                AND osource.organization_id = otarget.organization_id
                WHERE otarget._id is null and osource._id is not null and target._id is not null;
                """  # noqa: S608
            )
    except OperationalError:
        logger.exception("Failed to perform CNAME scan level query")
```

This is just like `sync_cname_scan_levels` from RFD 0013, but with the added join of the m2m tables to determine the
target and source. Note that we do have to create the natural key explicitly with:
`target._id ||'|'|| cast(osource.organization_id as varchar`.

### Functional Requirements Coverage

- **FR 1**: Objects are attributed to organizations through relationships in a background task
- **FR 2**: Objects can belong to multiple organizations (many-to-many)
- **FR 3**: View filtering ensures users only see their organizations' objects
