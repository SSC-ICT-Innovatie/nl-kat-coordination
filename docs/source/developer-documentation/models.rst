Django Models
=============

OpenKAT v2 uses Django ORM models stored across two databases: PostgreSQL for operational data and XTDB for object data.

Database Backend: XTDB vs PostgreSQL
-------------------------------------

XTDB Models
***********

Objects scanned and discovered by OpenKAT are stored in XTDB, a bitemporal database. These models inherit from ``XTDBModel`` or ``XTDBNaturalKeyModel``.

**Benefits:**

- Bitemporal tracking (valid-time and transaction-time)
- Complete audit history
- Temporal queries
- Per-organization tables (isolation)

**XTDB Models:**

- ``Network``
- ``Hostname``
- ``IPAddress``
- ``IPPort``
- ``DNSARecord``, ``DNSCNAMERecord``, etc.
- ``Finding``
- ``ObjectTask``

PostgreSQL Models
*****************

Operational data uses standard Django models with PostgreSQL:

**PostgreSQL Models:**

- ``User`` (Django auth)
- ``Organization``
- ``OrganizationMember``
- ``Task``
- ``Schedule``
- ``Plugin``
- ``File``
- ``ObjectSet``
- ``BusinessRule``

Core Object Models
------------------

Network
*******

The root container for all network objects.

.. code-block:: python

   class Network(XTDBNaturalKeyModel):
       name = models.CharField(max_length=255, unique=True)

       _natural_key_attrs = ["name"]

**Natural Key**: ``name``

Hostname
********

Represents a DNS hostname within a network.

.. code-block:: python

   class Hostname(XTDBNaturalKeyModel):
       network = models.ForeignKey(Network, on_delete=models.CASCADE)
       name = models.CharField(max_length=255)

       _natural_key_attrs = ["network", "name"]

**Natural Key**: ``network|name``

**Primary Key Example**: ``internet|example.com``

IPAddress
*********

IP address within a network (supports both IPv4 and IPv6).

.. code-block:: python

   class IPAddress(XTDBNaturalKeyModel):
       network = models.ForeignKey(Network, on_delete=models.CASCADE)
       address = models.GenericIPAddressField()

       _natural_key_attrs = ["network", "address"]

**Natural Key**: ``network|address``

**Primary Key Example**: ``internet|192.0.2.1``

DNSARecord
**********

Links a hostname to an IP address via DNS A record.

.. code-block:: python

   class DNSARecord(XTDBNaturalKeyModel):
       hostname = models.ForeignKey(Hostname, on_delete=models.CASCADE)
       ip_address = models.ForeignKey(IPAddress, on_delete=models.CASCADE)
       ttl = models.IntegerField(null=True, blank=True)

       _natural_key_attrs = ["hostname", "ip_address"]

**Natural Key**: ``hostname|ip_address``

Finding
*******

Represents a security finding created by business rules.

.. code-block:: python

   class Finding(XTDBNaturalKeyModel):
       finding_type = models.CharField(max_length=255)
       object = models.CharField(max_length=500)  # Reference to any object
       description = models.TextField(blank=True)

       _natural_key_attrs = ["finding_type", "object"]

**Natural Key**: ``finding_type|object``

Organization Models
-------------------

Organization
************

Represents a tenant in the multi-tenant system.

.. code-block:: python

   class Organization(models.Model):
       code = models.CharField(max_length=32, unique=True)
       name = models.CharField(max_length=255)

OrganizationMember
******************

Links users to organizations with permissions.

.. code-block:: python

   class OrganizationMember(models.Model):
       organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
       user = models.ForeignKey(User, on_delete=models.CASCADE)
       is_admin = models.BooleanField(default=False)
       permissions = models.JSONField(default=list)

XTDBOrganization
****************

XTDB uses a separate organization model for isolation.

.. code-block:: python

   class XTDBOrganization(XTDBModel):
       code = models.CharField(max_length=32, primary_key=True)
       name = models.CharField(max_length=255)

Objects in XTDB have a many-to-many relationship with ``XTDBOrganization`` for multi-org support.

Task Models
-----------

Task
****

Represents a unit of work to be executed by Celery.

.. code-block:: python

   class Task(models.Model):
       id = models.UUIDField(primary_key=True, default=uuid.uuid4)
       organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
       type = models.CharField(max_length=32)  # e.g., "plugin"
       data = models.JSONField(default=dict)
       status = models.CharField(max_length=16)
       created_at = models.DateTimeField(auto_now_add=True)

**Task Types:**

- ``plugin``: Run a plugin on an object
- ``business_rule``: Execute business rules
- ``report``: Generate a report

Schedule
********

Defines recurring task schedules for plugins.

.. code-block:: python

   class Schedule(models.Model):
       organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
       plugin = models.ForeignKey(Plugin, on_delete=models.CASCADE)
       object_set = models.ForeignKey(ObjectSet, on_delete=models.CASCADE)
       enabled = models.BooleanField(default=True)
       interval = models.DurationField()  # e.g., timedelta(hours=24)

ObjectTask
**********

Links tasks to the objects they created (provenance tracking).

.. code-block:: python

   class ObjectTask(XTDBNaturalKeyModel):
       task_id = models.CharField(max_length=36)  # UUID as string
       type = models.CharField(max_length=32)
       plugin_id = models.CharField(max_length=64)
       input_object = models.CharField(max_length=500)
       output_object = models.CharField(max_length=500)

       _natural_key_attrs = ["task_id", "output_object"]

This model enables tracing which task created which objects.

Plugin Models
-------------

Plugin
******

Defines an executable plugin.

.. code-block:: python

   class Plugin(models.Model):
       plugin_id = models.CharField(max_length=64, unique=True)
       name = models.CharField(max_length=255)
       description = models.TextField(blank=True)
       type = models.CharField(max_length=32)  # e.g., "boefje"
       scan_level = models.IntegerField(default=0)

File
****

Stores uploaded files or plugin outputs.

.. code-block:: python

   class File(models.Model):
       organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
       name = models.CharField(max_length=255)
       content = models.BinaryField()
       content_type = models.CharField(max_length=100)
       created_at = models.DateTimeField(auto_now_add=True)

Object Set Models
-----------------

ObjectSet
*********

Groups objects of the same type for filtering and scheduling.

.. code-block:: python

   class ObjectSet(models.Model):
       organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
       name = models.CharField(max_length=255)
       object_type = models.CharField(max_length=64)  # e.g., "hostname", "ipaddress"
       query = models.JSONField(default=dict)  # Filter parameters

**Example query:**

.. code-block:: json

   {
     "name__contains": "example",
     "scan_level__gte": 2
   }

Business Rule Models
--------------------

BusinessRule
************

SQL-based finding detection.

.. code-block:: python

   class BusinessRule(models.Model):
       name = models.CharField(max_length=255)
       description = models.TextField(blank=True)
       query = models.TextField()  # SQL query
       inverse_query = models.TextField(blank=True)  # Cleanup query
       enabled = models.BooleanField(default=True)

Natural Keys in XTDB
--------------------

XTDB models use natural keys instead of auto-incrementing IDs. The natural key is derived from the model's attributes.

**Example:**

.. code-block:: python

   network = Network.objects.create(name="internet")
   # Primary key: "internet"

   hostname = Hostname.objects.create(network=network, name="example.com")
   # Primary key: "internet|example.com"

   ip = IPAddress.objects.create(network=network, address="192.0.2.1")
   # Primary key: "internet|192.0.2.1"

This ensures deterministic IDs across different systems.

Querying Objects
----------------

Standard Django Queries
***********************

.. code-block:: python

   # Filter hostnames
   hostnames = Hostname.objects.filter(network__name="internet")

   # Get specific object by natural key
   hostname = Hostname.objects.get(pk="internet|example.com")

   # Create with foreign keys
   dns_record = DNSARecord.objects.create(
       hostname=hostname,
       ip_address=ip,
       ttl=3600
   )

Organization Filtering
**********************

Objects in XTDB belong to organizations via many-to-many relationships:

.. code-block:: python

   # Add organization to object
   hostname.organizations.add(xtdb_org)

   # Filter by organization
   org_hostnames = Hostname.objects.filter(organizations__code="myorg")

API Object Creation with Task Tracking
---------------------------------------

When creating objects via the API with a ``task_id`` parameter:

.. code-block:: http

   # POST /api/v1/objects/hostname/?task_id=UUID
   # Creates Hostname and ObjectTask

   POST /api/v1/objects/hostname/?task_id=550e8400-e29b-41d4-a716-446655440000
   {
     "network": "internet",
     "name": "test.example.com"
   }

This automatically creates:

1. The ``Hostname`` object
2. An ``ObjectTask`` linking the task to the hostname

Best Practices
--------------

1. **Use natural keys**: Design models with meaningful natural key attributes
2. **Organization aware**: Always filter by organization for multi-tenancy
3. **Task tracking**: Use ``task_id`` when creating objects programmatically
4. **Temporal queries**: Leverage XTDB's temporal features for audit trails
5. **Bulk operations**: Use ``bulk_create()`` for performance when creating many objects
