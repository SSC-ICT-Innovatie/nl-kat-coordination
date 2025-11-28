---
authors: Donny Peeters <@donnype>
state: implemented
discussion:
labels: Reporting, Metrics, Database Queries
---

# RFD 0018: Basic Reporting Architecture

## Introduction

OpenKAT users need reports to:

- Communicate security posture to stakeholders
- Track findings and vulnerabilities over time
- Demonstrate compliance with security standards

In OpenKAT V1, reporting tightly coupled to the octopoes backend. With the migration to XTDB V2 and SQL capabilities
(RFD 0008), we can now leverage database aggregations to efficiently generate reports.
This RFD documents the **initial reporting architecture** we've built and acknowledges that specific reporting
requirements need further development together with current users.

## Proposal

The core of this proposal is to:

1. **Establish basic report generation infrastructure** with PDF output
2. **Leverage SQL aggregation capabilities** for efficient metric collection
3. **Define an extensible metrics collection framework** that can grow with user needs
4. **Acknowledge that detailed reporting requirements are still evolving**

This foundational reporting system should:

1. Collects metrics from the database using SQL aggregations
2. Generate PDF reports from HTML templates
3. Support filtering by organizations, finding types, and object sets
4. Support being triggered manually or scheduled

This provides a MVP for reporting while leaving room for future enhancement by not building many report types and
aggregations and keeping the infrastructure simple.

At its core, the PDF generation can still be done by weasyprint by using HTML as the base structure.

### Functional Requirements (FR)

1. Generate PDF reports with security metrics and findings
2. Store the data separately so we can regenerate the HTML version dynamically, but also simply download the JSON data.
3. Store generated PDF reports as files
4. Filter reports by organization, finding type, or object set
5. Support both manual and scheduled report generation
6. Collect metrics efficiently using database aggregations

### Extensibility (Potential Future Requirements)

1. Custom report templates
2. Historical trending and time-series analysis
3. Reports with findings that organizations act upon
4. Automated report distribution (email, webhooks)
5. Interactive dashboards and visualizations

## Implementation

The reporting system is implemented in `reports/generator.py` and `reports/models.py`.

### Report Model

```python
class Report(models.Model):
    file = models.OneToOneField(File, on_delete=models.CASCADE, related_name="report")
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    organizations = models.ManyToManyField("openkat.organization", blank=True, related_name="filtered_reports")
    finding_types = ArrayField(models.CharField(max_length=255), default=list, blank=True)
    object_set = models.ForeignKey(
        "tasks.ObjectSet", on_delete=models.SET_NULL, related_name="reports", null=True, blank=True
    )

    data = models.JSONField(default=dict, blank=True)  # Stores metrics for historical reference
    created_at = models.DateTimeField(auto_now_add=True)
```

Pipeline: collect metrics → render HTML → convert to PDF → store report.

### Metrics Collection with Database Aggregations

Key innovation: using **Django ORM aggregations** to efficiently collect metrics in the database:

```python
def collect_findings_metrics(organizations, finding_types):
    findings = Finding.objects.select_related("finding_type").all()

    if finding_types:
        findings = findings.filter(finding_type__code__in=finding_types)
    if organizations:
        findings = findings.filter(organizations__pk__in=[org.pk for org in organizations])

    findings_by_type = (
        findings.values("finding_type__code", "finding_type__name", "finding_type__score")
        .annotate(count=Count("id"))
        .order_by("-finding_type__score", "-count")
    )

    hostname_offenders = (
        findings.filter(hostname__isnull=False)
        .values("hostname_id", "hostname__name")
        .annotate(finding_count=Count("id"))
        .order_by("-finding_count")[:10]
    )

    return {"total_findings": findings.count(), "by_type": list(findings_by_type), ...}
```

### Task Integration

Reports integrate with the Task system (`tasks/tasks.py`). It supports manual (user-triggered) and scheduled (automated)
report generation with progress tracking.

## Roadmap: Developing with Users

The reporting requirements will evolve through **collaboration with current OpenKAT users**. The process:

1. **Deploy V2** to production environments
2. **Gather object data** in production
3. **Gather user feedback** on what metrics they want out of their production data
4. **Identify common use cases** (compliance, executive briefings, technical deep-dives)
5. **Iterate on report content** and presentation

This iterative approach ensures we build **reports users actually need** rather than guessing requirements upfront.

## Functional Requirements Coverage

- **FR 1 (PDF generation)**: Implemented via `ReportPDFGenerator` and weasyprint
- **FR 2 & 3 (Storage)**: The Report model together with the File reference store the data as described
- **FR 4 (Filtering)**: Organizations and finding types filtering implemented, object sets partially
- **FR 5 (Manual and scheduled)**: Integrated with Task system and Schedule model
- **FR 6 (Efficient collection)**: Uses Django ORM aggregations (Count, F, Value)

## Conclusion

The basic reporting architecture provides a **solid foundation** for generating security metrics reports in OpenKAT.
By leveraging XTDB V2's SQL capabilities, we can efficiently aggregate data and produce PDF reports.

The decision to ship a basic report system allows us to **gather real user feedback iteratively**, rather than building
elaborate features that may not match actual needs. The architecture is extensible enough to support future enhancements
as requirements become clearer through collaboration. This has meant that we could focus on optimizing the scanning
infrastructure even more.
