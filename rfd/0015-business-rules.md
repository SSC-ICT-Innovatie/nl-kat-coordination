---
authors: Donny Peeters <@donnype>
state: implemented
discussion:
labels: Business Rules, Task Processing, Performance
---

# RFD 0015: Business Rules on Task Results

## Introduction

OpenKAT needs to automatically detect security issues and generate findings based on discovered objects,
such as missing SPF records, open database ports, or exposed software services.

Before, we had SQL based business rules that performed transformations on the whole database. Although this make the
database very consistent, this approach offers flexibility but has drawbacks:

**Performance:** Running rules on the entire database is expensive and most processing is redundant since objects
rarely change. This was the reason to delay the task and trigger it on object changes to have a more efficient stale
installation.
**Complexity:** Requires maintaining raw SQL queries that require intricate knowledge about the database structure.
This without any IDE support for debugging or refactoring, just SQL/database knowledge of XTDB.

We also had to build in checks if tasks had run, so we weren't creating false-positives for e.g. missing DNS records.

This got us thinking: when in our pipeline are we confident that hostnames are missing a DNS record? Right after a
DNS task. What data do we need for that? The task output.

Combine this with the fact that our system is not write-heavy in the sense that we do not expect to process hundreds
of tasks per minute, and we concluded that it would make a lot of sense to simply run the "business rules" on task
output, right after a task finishes. Instead of batch processing the entire database.

## Proposal

The core of this proposal is to:

1. **Process business rules immediately after each task completes**
2. **Only evaluate rules on the task's input and output objects**
3. **Implement rules as Python functions for now rather than dynamic definitions**

### Functional Requirements (FR)

1. Business rules should execute automatically without manual intervention
2. Business Rules should be efficient
3. Rules should be responsible for creating findings when conditions are met
4. Rules should delete findings when conditions are no longer met
5. Rules can be enabled/disabled without code deployment

### Extensibility (Potential Future Requirements)

1. Support organization-specific business rules
2. Output the results of a business rule in another business rule

## Implementation

The business rule system has been implemented using the `process_result` pattern in `tasks/tasks.py`.
Each processing function implements multiple related business rules.

### Key Design Patterns

**Natural key optimization:** Parse natural keys directly, avoiding database queries:

```python
rec_type.from_natural_key(obj["output_object"])
```

Although this does not capture optional fields, all checks currently use only required (natural_key) fields.

**Bidirectional finding management:** Both create and delete findings:

```python
Finding.objects.filter(...).delete()  # Remove when resolved
findings.extend([Finding(...)])        # Create when matched
```

**Bulk operations:** Minimize database round-trips with bulk inserts.

### BusinessRule Model

Rules can still be enabled/disabled through the database without code deployment:

```python
class BusinessRule(models.Model):
    name = models.CharField(max_length=200, unique=True)
    enabled = models.BooleanField(default=True)
    description = models.TextField(blank=True)
```

Each processing function checks which rules are enabled:

```python
enabled_rules = set(BusinessRule.objects.filter(enabled=True).values_list("name", flat=True))

if "missing_spf" in enabled_rules:
    # Execute rule logic
```

## Functional Requirements Coverage

- **FR 1 to 5** have been covered, as is apparent from the discussion above.

## Future Considerations

**Hybrid approach:** If needed, we could add an optional rule engine for organization-specific custom rules.
