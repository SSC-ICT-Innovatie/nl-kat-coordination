---
authors: Edward Hasekamp (@hasecon)
state: draft
discussion: https://github.com/SSC-ICT-Innovatie/nl-kat-coordination/pull/5466
implementation:
labels: octopoes, rocky, reporting
---

# RFD 0005: Finding lifecycle and timeline reporting

## Introduction

OpenKAT answers "what is open right now" well. It cannot currently answer "what
happened over this period" — when a finding first appeared, when it was resolved,
and how long it stayed open.

That question is asked from two directions. Auditors want period evidence rather
than a snapshot: a report they can rely on as proof that something was found on a
date and closed on a later one. Organisations reporting under NIS2 need the same
shape for the same reason. And internally, two existing reports already try to
answer part of it and pay a high price for doing so.

The data is already in the graph. XTDB is bitemporal, so every OOI carries the
valid time at which it appeared and the valid time at which it was retracted.
What is missing is a way to retrieve that efficiently, and a report that presents
it. This RFD proposes adding the first as OOI metadata and the second as a new
report type.

The design below follows a steer from @underdarknl on issue #5099[^1]: rather than
building a parallel timeline endpoint, surface XTDB's temporal capabilities as
parameters on the existing API and let the data live as metadata on the OOI
models themselves.

## Proposal

### Objective and goals

1. Make "first seen" and "last seen" available as first-class metadata on any
   OOI, retrieved in the same call that retrieves the OOI.
2. Allow querying over a period rather than at a single point in time.
3. Deliver this as a **new, separate report type**, not as an extension of an
   existing report — see the section below on why.
4. Remove the N+1 call pattern that the existing reports use to approximate this.

### Scope

In scope: an optional metadata field on the OOI base model, parameters on the
existing object and finding endpoints, the Datalog predicates needed to populate
them, and one new Rocky report type.

Out of scope for this RFD: attribution of _why_ a finding disappeared beyond
recording that it did; a queryable audit trail of who muted what (today that is
structured logging only); and cross-organisation or supply-chain period
reporting. Each of those is a separate problem and at least one of them needs its
own RFD.

### Current situation

Two reports already reach for this data, one call at a time:

- `rocky/reports/report_types/findings_report/report.py:69` calls
  `get_history()` once per distinct finding to derive a first-seen date.
- `rocky/reports/report_types/vulnerability_report/report.py:65` does the same,
  and adds a second per-finding call to `list_origins()` on the line below.

So a report over a thousand findings makes a thousand history calls, and the
vulnerability report makes two thousand. Both cache per finding reference within
a single run, which bounds the damage but does not change the shape.

"Last seen" was never implemented at all. In the vulnerability report it is a
literal placeholder:

```python
# rocky/reports/report_types/vulnerability_report/report.py:87
str(_("Last seen")): "-",
```

Nothing resembling `Lifecycle`, `with_lifecycle` or `first_seen` exists in
octopoes today, so this is greenfield rather than a refactor.

### Options considered

**A. Multiple snapshots via Datalog.** Query `list_findings(valid_time=T)` at a
series of points and diff the results. Works today with no backend change at all,
which makes it the obvious fallback. Two drawbacks: the resolution is only as
good as the number of snapshots, and a finding that appears and disappears
between two of them is invisible.

**B. A dedicated timeline endpoint backed by a transaction-log scan.** Read
`/_xtdb/tx-log` and reconstruct per-finding history. Most precise, but it adds a
second way of asking the same question and the endpoint may not be passed through
by the wrapper we run (see Risks).

**C. Lifecycle metadata plus parameters on the existing endpoints.** Mount an
optional `Lifecycle` model on the OOI base class, the way `scan_profile` is
already mounted, and populate it with new Datalog predicates. Extend the existing
endpoints with parameters instead of adding new ones.

**C is proposed.** It keeps one way of asking for objects, benefits every
consumer rather than only the new report, and means the existing reports can drop
their per-finding calls instead of gaining a parallel code path. A is kept as the
documented fallback for phase 2 if the transaction log turns out to be
unavailable.

### Proposed design

#### Phase 1 — snapshot mode

A new model mirroring how optional metadata already attaches to every OOI:

```python
class Lifecycle(BaseModel):
    first_seen: datetime | None = None
    last_seen: datetime | None = None
```

mounted on the base `OOI` as `lifecycle: Lifecycle | None = None`.

A `with_lifecycle=true` parameter on the existing `GET /{client}/findings`,
`/objects` and `/object` endpoints populates it. Two Datalog predicates,
`get-start-valid-time` and `get-end-valid-time`, provide the values.

With that in place, `FindingsReport` and `VulnerabilityReport` can migrate off
`get_history()`, and `last_seen` gets a real value for the first time. That is a
repair of two existing reports that rides along, not the deliverable this RFD
asks for.

#### Phase 2 — range mode

`valid_time_start` and `valid_time_end` parameters on the same endpoints, so a
caller can ask what existed, appeared or was retracted within a window. This is
what drives a new `FindingTimelineReport` in Rocky, with columns for first seen,
resolved, duration and status, plus a summary block.

A period report has to add up. Baseline plus added minus resolved should equal
the closing count, and the report should say so rather than leave the reader to
check.

### Why a separate report type

The deliverable is a new report type rather than a period mode bolted onto
`FindingsReport`, for four reasons.

**It answers a different question for a different reader.** A snapshot report
answers "what is open"; a period report answers "what happened, and can I prove
it". Supporting both in one report makes it bimodal, and bimodal reports tend to
serve neither case well.

**It carries no regression risk.** The existing reports are relied upon. A new
type can be built, reviewed and shipped without changing their output at all,
which matters given the non-functional requirement in RFD 0004 that changes to
existing behaviour must not degrade existing quality.

**An audit deliverable needs its own identity.** It has to state its own scope and
limitations — scan coverage for the period, an explicit "cause not established"
category — and that belongs in a document about the period, not as extra columns
in a report about now.

**It is the cheap and conventional option.** Rocky has fourteen report types;
registering one is a directory under `reports/report_types/`, a class, one import
and one entry in the `REPORTS` list in `reports/report_types/helpers.py`.

A useful consequence: because option A works today without any backend change, the
report can be built on two-snapshot diffing first and switched onto lifecycle
metadata once phase 1 lands. The report is therefore not blocked on the three
decisions below — only its efficiency is.

### Open questions

Three decisions are needed before implementation starts. They are the reason this
is a draft rather than a plan.

1. **Field name.** `lifecycle` reads well next to `scan_profile`, but
   `temporal_meta` or `xt_meta` are more honest about where the values come from.
2. **Endpoint shape.** Parameters on `/findings`, or a separate
   `/findings/timeline` sub-endpoint? Parameters keep one entry point; a
   sub-endpoint keeps the bimodal behaviour out of a widely used response.
3. **Which wrapper version to pin.** Phase 1 depends on temporal predicates that
   shipped in a specific XTDB version. A precursor PR should pin it, and we need
   to agree on which.

### Risks and limitations

These belong in the RFD rather than in a later surprise, because a period report
that overstates what it can prove is worse than no report.

- **The transaction log may not be reachable.** If the wrapper does not pass
  `/_xtdb/tx-log` through, phase 2 falls back to option A, which is slower and
  coarser.
- **Short-lived findings stay invisible under the fallback.** Something that
  appears and is resolved between two snapshots leaves no trace. Under option B
  it does.
- **Disappeared is not the same as resolved.** A finding also vanishes when a
  boefje is disabled, when clearance drops, or when a scan simply did not run.
  OpenKAT does not record boefje enablement history, so the cause often cannot be
  established. The report should carry an explicit "cause not established"
  category rather than silently counting these as fixed.
- **No scan is not a clean bill of health.** A period with no scan coverage
  produces an empty delta that looks like "nothing happened". Scan coverage data
  does exist — task history in the scheduler, append-only metadata in Bytes — so
  the report can state its own coverage, and it should.
- **Semantics of recreation.** An OOI that is deleted and created again needs a
  documented answer for what `first_seen` then means. An integration test for
  `get-start-valid-time` across a create-delete-recreate sequence should settle
  that before phase 1 ships.

### Future considerations

Reports are already stored immutably in Bytes with a secure hash and a
corresponding Report OOI, so the reproducibility a period report needs is largely
covered by the existing artefact regime rather than by new work.

Issue #4014[^2] asks for a report over a reference date in the past. It needs the
same parameterisation and should probably land on top of phase 2 rather than
beside it.

The detailed acceptance criteria for an audit-grade period report are being
worked out separately with the stakeholders who asked for it; this RFD covers the
mechanism they need, not those criteria.

## Footnotes

[^1]: [Issue #5099 — Finding timeline report, including the design steer and the refined plan](https://github.com/SSC-ICT-Innovatie/nl-kat-coordination/issues/5099)
[^2]: [Issue #4014 — Run a report over a valid time in the past](https://github.com/SSC-ICT-Innovatie/nl-kat-coordination/issues/4014)
