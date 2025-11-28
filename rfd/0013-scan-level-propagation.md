---
authors: Donny Peeters <@donnype>
state: implemented
discussion:
labels: Data Models, Objects, Scan Levels
---

# RFD 0013: Scan Level Propagation

## Introduction

In OpenKAT, **scan levels** (also called clearance levels) control which plugins can run on which objects.
The scan level is an integer from 0 to 4 (L0-L4) where:

- **L0**: No scanning allowed
- **L1**: Minimal scanning (passive information gathering)
- **L2**: Light active scanning
- **L3**: Normal active scanning
- **L4**: Intensive active scanning

Plugins are assigned scan levels, and they can only run on objects that have a scan level greater than or equal to the
plugin's level. For example:

- A plugin with `scan_level=2` can run on objects with scan_level ≥ 2
- An object with `scan_level=1` will only have L0 and L1 plugins run on it

When users or plugins set scan levels on objects, these propagate should propagate to related objects.
For example, the ipaddresses tied to a hostname through its DNS records should get the same scan level as the hostname.
In the current version of OpenKAT, **all** models can have scan levels, and they propagate through events.
This is quite an involved script running on the whole database, that does in-memory checks.
In practice however, we only really scan hostnames and ipaddresses (and later: urls).

A few questions to answer for a revision of this feature are:

1. **Which relationships should propagate scan levels?**
2. **What should the propagation rules be?**
3. **When should propagation happen?**

## Scan Level model/field

In earlier versions we had defined the ScanLevel as a model representing a many-to-many between objects and
organizations. This meant that levels were managed per organization. However, this became quite cumbersome because:

- It is hard to show some sort of level when no organization filters are applied in the interface
- If we wanted to start a scan, we had to take the max level over all ScanLevel models per object

The result being that even if org A lowers the scan level, an object is scanned if it has a higher scan level in org B.
We decided that the ScanLevel is a property that is not organization specific, because it determines how openkat
operationally works. And it is hard to hide scanning information of an object for org A even it has been scanned for
org B, and perhaps that doesn't even make sense. Hence, we decided that the organization-specific requirements are
to be fleshed out later, but just applying proper filtering on the resulting object suffices. Users with no admin
rights perhaps should be kept away from scanning and scan level logic altogether.

Having a global scan level also opens up the option to put the information on the object itself, which improves
performance and simplifies the setup. Of course, we still also need the `declared` field to convey whether the scan
level should inherit from related objects or not, and to override inherited scan levels to manually set levels.

## Proposal

The core of this proposal is to:

1. **Only set scan levels on hostnames, ipaddresses and urls**: it only makes sense to set scan levels on objects we
   scan.
2. **Propagate scan levels through DNS relationships**: if we limit ourselves to hostnames and ipaddresses, the old
   openkat scan level propagation logic will boil down to three operations:
   - Sync hostname scan level with IP address scan level (bidirectional) through DNSArecords.
   - Set a name server's scan level to the hostname's scan level, with a max of 1, through DNSNSrecords.
   - Sync hostname scan levels that are connected, updating the target's scan level, through DNSCNAMERecords.
   - Note that the MX records actually have no net effect in this new system since only the DNSMXrecord's scan level
     was updated, but there was no impact on other **hostnames**
3. **Run propagation periodically in the background** (with a configurable interval) and:
   - Avoids running several of these tasks simultaneously
   - Stop when revisiting an object in the same propagation chain
4. **Try to make propagation efficient by leveraging the new SQL capabilities of XTDB V2**
5. **Implement the information on the object models themselves**

### Functional Requirements (FR)

1. As a user, I want OpenKAT to work mostly autonomously
2. As a user, I don't want to manage all scan levels of my assets manually
3. As a user, I want to be able to manually override propagated scan levels

### Extensibility (Potential Future Requirements)

1. Allow custom propagation rules per organization
2. Propagation decay (inherited levels decrease/drop as relationships become more distant)

## Implementation

The scan level propagation system has been implemented using a periodic background task,
see `tasks/tasks.py`. The realisation that we only had to propagate to hostnames and ipaddresses has
simplified the setup considerably.

### Scan Level model

### SQL

The propagation rules are now pure SQL, see e.g. the following code from `tasks/tasks.py`:

```python
def sync_cname_scan_levels() -> None:
    """The target hostname scan level is set to the source hostname scan level."""
    try:
        with connections["xtdb"].cursor() as cursor:
            cursor.execute(
                f"""
                INSERT INTO {Hostname._meta.db_table} (_id, name, network_id, root, scan_level, declared)
                select target._id, target.name, target.network_id, target.root, source.scan_level, false
                FROM {Hostname._meta.db_table} source
                JOIN {DNSCNAMERecord._meta.db_table} dns on source._id = dns.target_id
                JOIN {Hostname._meta.db_table} target ON target._id = dns.hostname_id
                WHERE source.scan_level IS NOT NULL AND target.declared IS FALSE
                AND target.scan_level is null or  target.scan_level != source.scan_level;
                """  # noqa: S608
            )
    except OperationalError:
        logger.exception("Failed to perform CNAME scan level query")
```

Because of our natural keys, doing an `INSERT` suffices to guarantee we actually do an update in XTDB.
We join the hostname table on itself through the `DNSCNAMERecord` model, filter out the source scan levels that are
`NULL` and the target levels that are declared (as described above), and set the source level to the target level if
they are not equal yet. This is efficient as it targets exactly the data we need, without leaving the database at all.

**Redis Locking:**

To prevents multiple workers from running propagation simultaneously a lock was added on the task with a timeout to
ensures the lock doesn't get stuck if a worker crashes. Django's cache framework with the Redis backend was used for
this as Redis was already available:

```python
@app.task(queue=settings.QUEUE_NAME_RECALCULATIONS)
def schedule_scan_profile_recalculations():
    try:
        # Lock to:
        #   1. Avoid running several recalculation scripts at the same time and burn down the database
        #   2. Still take into account that there might be anomalies when a large set of objects has been changed
        with caches["default"].lock(
            "recalculate_scan_levels", blocking=False, timeout=10 * settings.SCAN_LEVEL_RECALCULATION_INTERVAL
        ):
            recalculate_scan_levels()
    except LockError:
        logger.warning("Scan level calculation is running, consider increasing SCAN_LEVEL_RECALCULATION_INTERVAL")

```

**Workflow overview from the users perspective:**

1. User sets `example.com` to L4
2. Propagation runs
3. Related IPs, hostnames get updated to L4
4. Plugin scheduler sees higher scan levels
5. More plugins become eligible to run
6. Additional scanning occurs automatically

### Functional Requirements Coverage

- **FR 1 & 2**: Scan levels propagate as described, allowing the app to crawl from declared assets to many layers of
  other assets.
- **FR 3**: Users can manually set scan levels to `declared` and back to `inherited` as well.
