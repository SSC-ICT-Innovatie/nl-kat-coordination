---
authors: Jeroen Dekkers <@dekkers>, Donny Peeters <@donnype>
state: implemented
discussion:
labels: Planning, Architecture, Requirements
---

# RFD 0012: MVP Requirements

These are the minimum requirements we want to fulfill for a OpenKAT version 2.0 minimum viable product. This means the minimum needed to get back to a state where OpenKAT is working and useful again and can be used by our stakeholders.

We will probably implement more requirements when working on version 2.0 when it is easy to do so and time permits it. But there is also a lot of important functionality not listed here that we need to implement later. That something is not listed here does not mean we don't plan to do that, but we first focus on an MVP. It is important to get back to a working state as soon as possible and we will then implement the other requirements in further iterations.

## Scheduling and tasks

- Tasks can be run on a predefined interval.
- It must be possible to manually schedule tasks.
- The scanning tasks should be run containerized.
- Scanning should be done based on the clearance level of an asset. Only scans that have a level lower or equal to the level of the assets should be done.

## Adding assets, discovery and scan level propagation

- It should be possible to manually add assets via the web interface or import a file with assets.
- The system should have a way to automatically add assets from an external system.
- The system should automatically search for and add assets that are relevant to the system.
- The system should automatically propagate clearance levels when a clearance level of an object implies a clearance level for another object.

## Findings

- OpenKAT must create findings for vulnerabilities and compliance issues.
- Findings can either be directly sourced from scanning / normalizer tasks or created by business rules.
- It should be possible to mute findings.

## Business rules

- OpenKAT should have business rules that define when findings are created.
- Those business rules must support configuration parameters.
- Configuration should be done on the global level, per organization level, for groups of assets and individual assets.

## Organizations

- All assets should be assigned to one or more organizations.
- Users can be added to organizations and can only view data from those organizations.
- Users can also be global with permissions to see all organizations.
- It should be possible to view everything globally (e.g. for all organizations), for a selection of organizations or a single organization.

## Auditability and historical data

- All actions by users should be logged for audit purposes.
- Information about how and why assets are added should be saved. E.g. whether a user added it or it was discovered and if it was discovered how.
- Changes should be tracked.
- All historical versions of assets should be kept.

## Reporting and exporting

- Reports can be run on a predefined interval.
- Reports can be created on an ad-hoc basis.
- Reports can be viewed in the web interface and be downloaded as PDF.
- It should be possible to get an export of findings and assets.

EDIT:
Since the structure and capabilities have changed in V2, only one report type/flow has been implemented to show the
capabilities and have the infrastructure in place. We decided that more specialized and enhanced reports should be
created iteratively once V2 is live and has collected relevant data, so we can focus on our scanning and database
infrastructure.

## Dashboarding

- Users should be able to create flexible dashboards.
- Dashboards should preferably be real-time if this is possible to do without dashboards getting too slow.
- Dashboards should be able to show data both globally and for a subset of organizations.

EDIT:
Since Dashboarding will be built on top of reporting, this has gotten a lower priority as well.

# Planning

## Week 36 (1-5 sep)

- Scheduling and tasks
- Storing assets with scan levels in XTDB 2, create database models

## Week 37 (8-12 sep)

- Scheduling and tasks
- Storing assets with scan levels in XTDB 2, create database models

## Week 38 (15-19 sep)

- Scheduling and tasks - MVP requirements implemented
- Storing objects in XTDB 2 - MVP requirements implemented
- Create findings database model
- Business rule engine for creating findings

## Week 39 (22-26 sep)

- Business rule engine for creating findings
- Create findings database model - MVP requirements implemented
- Scan level propagation and discovery

## Week 40 (29 sep-6 oct)

- Business rule engine for creating findings - MVP requirements implemented
- Scan level propagation and discovery - MVP requirements implemented
- Organizations

## Week 41 (6-10 oct)

- Reporting
- Organizations - MVP requirements implemented
- Auditability and historical data - MVP requirements implemented

## Week 42 (13-17 oct)

- Reporting
- Dashboarding

## Week 43 (20-24 oct)

- Reporting - MVP requirements implemented
- Dashboarding - MVP requirements implemented
