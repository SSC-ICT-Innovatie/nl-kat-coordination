---
authors: Donny Peeters <@donnype>
state: implemented
discussion:
labels: Octopoes, Origins
---

# RFD 0007: Deletion Propagation

## Introduction

Origins in OpenKAT have two functions. The first is to control deletion propagation:

- **Declarations** are "circular" origins with one Object in the result set that equals the `object` (input) field, and
  are hence not subject to deletion propagation.
- **Observations** are regular origins because old items from their `result` (array) field will be deleted upon an
  update operation.
- **Affirmations** are Declarations that should actually be deleted, because they don't "prove" the Object. An example
  of this is a job that only adds extra information to an Object, and hence is circular without proving existence.
- **Inference Origins** are origins found by bits, and hence updates on Objects with an Inference Origin or
  InferenceOrigins themselves trigger the run of the bit the origins references.

The second function is to provide attribution: an origin has a `method` (a.k.a. `normalizer_id` or `bit_id`),
`source_method` (a.k.a. `boefje_id`) and a `task_id` (a.k.a. `normalizer_meta_id`) field.
This means that origins can be used to:

1. Find the tasks that produced an Object
2. Find all Objects that were found in a certain Task
3. Find Objects that were the result of a specific boefje, normalizer or bit.
4. Trigger bits on changes in an event-driven manner

## Proposal

The core of this proposal is to remove Origins: Declarations, Observations and Affirmations.
To still have deletion propagation, we should delete old Objects in plugins explicitly when needed and define `CASCADE`s,
on our models. This would solve all deletion propagation requirements.

### New Bit Trigger System

With XTDB 2.0, bits might be powerful enough to run them all every minute, especially if we would keep track of what
was already updated through an `updated_at` like field/feature. But this would make everything less responsive.
Hence, we could re-implement the trigger system using Django Signals and trigger bits on an UPDATE, CREATE or DELETE.

### New attribution path towards Objects

To still relate Objects to Tasks, Objects should get a new `attribution_id` field that is either:

- A `task_id` pointing to a Task
- A `user_id` pointing to a User that manually created the Object
- Any future attribution identifiers

Or a separate model that keeps track of this.

### Functional Requirements (FR)

1. As a User, I don't want duplicate Objects in OpenKAT because it makes it hard to find the currently active
   Objects and thereby act quickly.
2. As a User, I want data that is not valid anymore because a scan did not find it again to be removed.

### Extensibility (Potential Future Requirements)

1. As a User, I want to be able to trace the full lineage of how an Object was created (through which tasks and
   plugins).
2. As a User, I want to know which user manually created an Object for audit purposes.

## Implementation

The deletion propagation system has been implemented according to the proposal with the following design choices:

### Origins Removed

**Status: Fully Removed** - All Origin types (Declarations, Observations, Affirmations, InferenceOrigins) have been
completely removed from the codebase. No Origin-related models, tables, or logic remain.

### Explicit Plugin Deletion

With the Plugins now talking to a REST API, plugins can perform the logic for data cleanup themselves.
Note that before, we ended up having four origin types to trigger different behaviors.
The API model means that plugins have full control and can perform advanced analyses using object-data in the future,
but it also means that we lose control of what plugins are allowed to remove from the database.
There are a few considerations and mitigations to mention here:

- Currently, we have full control over the API access of each plugin through the permissions field.
- Only trusted plugins should get delete-access, and for the MVP all plugins using the API stem from this repository.
- If this is not sufficient, a default deletion mode where we remove previous task results can always be built on
  top of this model given the ObjectTask model that maps objects to the task that found them.
- A hybrid approach would be to only allow plugins to delete objects for which there exists only one ObjectTask (see
  below) and the plugin id and input object match.

### Deletion Propagation via CASCADE

Other deletions are handled through Django model `CASCADE` relationships instead of the old Origin system:

**CASCADE Relationships** (`objects/models.py`):

```python
# Parent -> Child cascading deletes
IPAddress.network -> Network(CASCADE)
Hostname.network -> Network(CASCADE)
IPPort.address -> IPAddress(CASCADE)
Finding.hostname -> Hostname(CASCADE)
Finding.address -> IPAddress(CASCADE)

# DNS Records (all CASCADE to hostname)
DNSARecord.hostname -> Hostname(CASCADE)
DNSAAAARecord.hostname -> Hostname(CASCADE)
DNSPTRRecord.hostname -> Hostname(CASCADE)
DNSCNAMERecord.hostname -> Hostname(CASCADE)
DNSMXRecord.hostname -> Hostname(CASCADE)
DNSNSRecord.hostname -> Hostname(CASCADE)
DNSCAARecord.hostname -> Hostname(CASCADE)
DNSTXTRecord.hostname -> Hostname(CASCADE)
DNSSRVRecord.hostname -> Hostname(CASCADE)
```

**PROTECT Relationships** (prevent accidental deletion):

- Cross-references like DNS targets, mail servers, and name servers use `PROTECT`
- Organization relationships use `PROTECT` to avoid accidental organization deletion

### New Attribution System: ObjectTask Model

**Location:** `objects/models.py` (lines 177-184)

```python
class ObjectTask(XTDBNaturalKeyModel):
    task_id = models.CharField(max_length=36)  # UUID as string
    type = models.CharField(max_length=32, default="plugin")
    plugin_id = models.CharField(max_length=64)
    output_object = models.CharField()

    _natural_key_attrs = ["task_id", "output_object"]
```

How attribution for objects and tasks works:

1. When plugins create objects via the API, the `ObjectTaskResultMixin` captures the task context from the JWT token
2. `ObjectTask` records are created linking each output object to its originating task
3. Attribution queries can traverse from objects to tasks to objects

**Implementation in viewsets** (`objects/viewsets.py`, lines 55-79):

```python
class ObjectTaskResultMixin:
    def perform_create(self, serializer):
        if self.request.auth.get("task_id") is not None:
            task = Task.objects.get(pk=self.request.auth.get("task_id"))
            ObjectTask(
                task_id=str(task.pk),
                type=task.type,
                plugin_id=task.data.get("plugin_id"),
                output_object=result.pk,
            ).save()
```

### Functional Requirements Coverage

- **FR 1**: Duplicate Objects are prevented through natural key constraints in XTDB
- **FR 2**: Stale data is removed via explicit plugin deletion logic and CASCADE relationships.

### Limitations

1. **User Attribution**: Task-based attribution (`task_id`) is fully implemented, but user-based
   attribution (`user_id`) for manually created objects is not tracked at the individual Object level (only in task data).

2. **Manual Deletion Required**: Unlike the old Origin system where non-observed Objects were automatically deleted,
   plugins must now explicitly delete stale objects or rely on CASCADE relationships.

This implementation successfully removes the Origin system complexity while maintaining deletion propagation through
standard Django ORM patterns. The new approach is more explicit and follows Django conventions, making it easier to
understand and maintain.
