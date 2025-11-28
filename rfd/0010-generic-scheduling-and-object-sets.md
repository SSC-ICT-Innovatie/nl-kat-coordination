---
authors: Donny Peeters <@donnype>
state: implemented
discussion:
labels: Data Models, Scheduling
---

# RFD 0010: Generic Scheduling

## Introduction

In RFD 0005, an improved model for schedules and tasks was introduced,
with a focus on the relation between tasks and files.
Here, the only field that defines when a schedule should run is `schedule` that supports only cron expressions,
and the only field defining the input of a task is `data` that is modeled after a `BoefjeMeta` or `NormalizerMeta`.
In light of RFD 0006, 0007 and 0009, the schedule model in RFD 0005 does not suffice anymore:

- We want to make the arbitrary JSON data more explicit. Plugins can be run on a variety of input sets,
  so e.g. a BoefjeMeta is too limited as well as redundant: fields such as `started_at` and `ended_at` should be defined
  on the Task, while fields as `input_ooi` should be replaced by a more generic input data field on the Schedule.
- Schedules on an interval should be configured with a recurrence field, as discussed multiple times, this is a more
  flexible and powerful approach.
- We could want to trigger a plugin to parse a file when it is created, e.g. because it contains `nmap` output. This is
  also a schedule in the sense that it signals a plugin to start on a specific input set. In V1 of OpenKAT,
  the trigger always equaled the input set: when we create a Hostname, we only get this hostname as input, nothing more.
  In OpenKAT V2, we can support arbitrary triggers and inputs, like triggering a plugin that checks for a newly created
  hostname if there was ever an IP address that had an open database port in the past that now points to this hostname.
  In one step, without bits.

## Proposal

The core of this proposal is to:

1. Replace the `schedule` field with a `recurrences` field
2. Have a `plugin` field on a schedule.
3. Add a nullable `input` field containing django_ql, that generates the input data the plugin should run on.
   Perhaps we need a query per OOI type here, as djangoql assumes we know the model being queried.
4. Add a `run_on` field that will hold a type such as "file" or "hostname"
5. Add some `operation` field that specifies the operation such as "create", "update" or "delete", that only has effect
   if `run_on` is set.

This means that our current default daily scheduling boils down to about one database entry per plugin (pseudocode:

```json
[
  {
    "recurrences": "daily",
    "plugin": "dns",
    "input": {
      "hostname": "dnsmxrecord__is_null = false"
    },
    "run_on": null,
    "operation": null
  }
]
```

The first takes all plugins that have not defined their own `recurrences` and applies them to all IPV4Address and
Hostname objects. We first check if the plugins are enabled, match scan levels and input, type and do as much as
possible in parallel, of course.

The power here is that users can decide to have complete control where needed:

```json
[
  {
    "recurrences": "daily",
    "plugin": "rpki-download",
    "input": {}
  },
  {
    "recurrences": "hourly",
    "plugin": "bgp-download",
    "input": {}
  },
  {
    "recurrences": "hourly",
    "plugin": "rpki",
    "input": ["rpki-download", "bgp-download"],
    "run_on": "file"
  }
]
```

Or spreading certain plugins over the day, where batches or hostnames are processed instead of all-or-nothing based
on their scan level.

### Functional Requirements (FR)

1. As a user I want to know when my plugins start scanning objects
2. As a user I want to be able to turn schedules off
3. As a developer, I want to be able to schedule a specific plugin on a subset of objects (scan level doesn't suffice)

### Extensibility (Potential Future Requirements)

1. Scheduled Workflows

### Why the proposal covers the functional requirements

This is straightforward from the fields on the schedule as detailed above and in the implementation section below.

## Implementation

The generic scheduling system from this RFD has been implemented as follows.

### Schedule Model Structure

**Location:** `tasks/models.py` (lines 86-110)

The Schedule model has the following structure:

```python
class ObjectSet(models.Model):
    """Composite-like model representing a set of objects that can be used as an input for tasks"""

    name = models.CharField(max_length=100, blank=True, null=True, unique=True)
    description = models.TextField(blank=True)
    object_type: models.ForeignKey = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_query = models.TextField(null=True, blank=True)

    # concrete objects
    static_objects = ArrayField(models.CharField(), default=list, blank=True)


class Schedule(models.Model):
    enabled = models.BooleanField(default=True)
    recurrences = recurrence.fields.RecurrenceField(null=True, blank=True)
    task_type = models.CharField(max_length=32, default="plugin")

    organization = models.ForeignKey("openkat.organization", ...)
    plugin = models.ForeignKey("plugins.plugin", ...)
    object_set = models.ForeignKey(ObjectSet, ...)

    # Report-specific fields
    report_name = models.CharField(max_length=255, null=True, blank=True)
    report_description = models.TextField(blank=True)
    report_finding_types = ArrayField(models.CharField(max_length=255), default=list)
```

### Notable deviations from initial proposal

Points 1 and 2 of the proposal have been implemented as suggested. An `enabled` was added to convey if a schedule
should run or not. An optional `organization` field was added as well, since some schedules could only apply to
specific organizations. The `task_type` was added because schedules now exist for reporting tasks as well, hence the
last three fields.

One thing that has changed significantly is the input of a schedule, which is now an `ObjectSet`. ObjectSets where
introduced because the requirements of schedules shifted a bit after talking to users: one of their main concern was
that running everything at once would result in rate limits being hit or organizations blocking their IP. They said
that the ideal scenario was to be able to scan disjoint organizations in parallel. But the only way to do have this
level of control without introducing a boat load of declarative configuration (which is now always still possible
since we have full control), is to introduce a model that represents a collection/set of input objects.

The ObjectSets define an object type, a (DjangoQL) query that should be applied to that object type, and perhaps a
collection of manually added object that are hard to capture in a query, see the `static_objects` field. The
default value is a dynamically created object set that contains all objects of the type called e.g. `all hostnames`
or `all ipaddresses`.

Note that the model can also function as a stored query. To leverage this property, we added a filter field on the
hostname and ipaddress list pages where you can filter on the object set query. Together with a few default object
sets we create during the installation, such as `mail servers`, `name servers` and `root domains` (all checked
through a simple DjangoQL query), this has enabled V2 to have functionality that hasn't been possible yet such as
listing all name servers and mail servers (performantly).

### Implemented Features

#### 1. Recurrences Field

**Replaces the old `schedule` cron field** with Python's `recurrence` library:

```python
from recurrence.fields import RecurrenceField

schedule.recurrences = RecurrenceField(null=True, blank=True)
```

**Usage in scheduling logic** (`tasks/tasks.py`, lines 382-424):

```python
def run_schedule_for_organization(schedule: Schedule):
    last_run = schedule.tasks.order_by("-created_at").first()
    if schedule.recurrences:
        occurrences = schedule.recurrences.between(last_run.created_at, now)
        if not occurrences:
            return  # Not time to run yet
```

Recurrence supports Daily, weekly, monthly scheduling and custom recurrence patterns.

Logic:

- Uses `schedule.recurrences.between(last_run.created_at, now)`
- Checks if schedule should run by comparing with last execution timestamp
- Falls back to daily scheduling if recurrences not specified

#### 2. ObjectSet for Input Specification ✅

**Location:** `tasks/models.py` (lines 46-83)

ObjectSet replaces the old `data` and `type` fields:

```python
class ObjectSet(models.Model):
    ...

    def get_query_objects(self):
        queryset = self.object_type_class.objects.all()
        if self.object_query:
            return apply_search(queryset, self.object_query, NoOrgQLSchema)
        return queryset.none()
```

**DjangoQL Integration:**

- Uses `apply_search()` with `NoOrgQLSchema` for object filtering without exposing organization information
- Supports complex queries like `scan_level > 0` or `name__contains='test'`
- Allows static object lists via `static_objects` ArrayField
