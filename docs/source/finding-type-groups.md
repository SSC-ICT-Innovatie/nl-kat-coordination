# Finding Type groups

The static OpenKAT Finding Type catalog defines `groups` as an array of stable group identifiers.
The canonical group registry is `boefjes/boefjes/plugins/kat_kat_finding_types/finding_type_groups.json`.
Each group has a display name, description, and optional parent identifier.
A Finding Type may belong to multiple groups. A parent relationship describes the taxonomy;
it does **not** imply descendant-aware filtering.

Run `python boefjes/boefjes/plugins/kat_kat_finding_types/validate_groups.py`
to validate group references and hierarchy.
Group propagation into Octopoes is provided by Phase 2.

## Finding Type tags

Finding Types may additionally define an optional `tags` array of strings. Tags
are cross-cutting labels rather than security-domain groups; no tag OOI or tag
registry is required. The initial tag, `misconfiguration`, marks configuration
weaknesses across groups such as DNS Security, HTTP Security Headers, and HTTP
Cookies. An absent `tags` field means no tags.

The catalog validator also checks that provided tags are non-empty strings with
no duplicates. `KATFindingType` stores both `groups` and `tags`, using empty
lists for older definitions without these fields. Tags do not change finding
identity or severity. Dashboard persistence is separate Rocky work.

## Preserving and refreshing classifications

`groups` and `tags` belong to `KATFindingType`, not to each `Finding`.
Many bits and normalizers submit only `KATFindingType(id=...)`. Such partial
OOIs leave group and tag fields **unset**. During serialization these fields
are omitted rather than sent as empty lists, so Octopoes merges do not erase
classification supplied by the KAT Finding Types catalog. The catalog
normalizer explicitly sets both fields, including empty lists, so an updated
catalog can intentionally remove obsolete assignments.

An application update does **not** automatically backfill Finding Types that
already exist in XTDB. After deploying updated Boefjes and Octopoes services,
refresh the `kat-finding-types` boefje for the existing `KATFindingType` OOIs
in each organization. Two ways to do that:

- **Automated (recommended):** run the Rocky management command. It schedules
  the boefje for every existing `KATFindingType` in every organization (or one
  organization with `--organization`); `--dry-run` only reports the counts.
  The boefjes worker and the `kat_kat_finding_types` normalizer must complete
  afterwards.

      python manage.py refresh_finding_type_metadata            # all organizations
      python manage.py refresh_finding_type_metadata --dry-run  # count only

- **Manual:** in Rocky, find **KAT Finding Types** in KAT-alogus,
  select the existing Finding Type OOIs and run the boefje. If the list is
  paginated, repeat for all relevant pages, and repeat for each organization.

In both cases the normalizer must also complete; only scheduling the boefje is
not sufficient. Check the resulting `KATFindingType` details to confirm that
`groups` and `tags` are populated.

This refresh reuses the existing OOI and its finding relationships; it does
not recreate findings or create new OOIs for the classification. Finding Types
not defined in the static catalog continue to have empty classification.
Run this refresh after later catalog classification changes as well. A new
installation hydrates catalog metadata through the usual boefje workflow.

## Filtering findings in Rocky

The findings page offers optional Group and Tag dropdowns. Each filters on
explicit `KATFindingType` membership (not hierarchy descendants); the group
dropdown's help text states this as well. Selecting both applies an AND
condition. Filtering happens in Octopoes before counting, sorting, or
pagination and combines with existing severity, search, muted, and
observation-time filters.

The dropdown labels come from the canonical JSON group registry and the
available tags from the Finding Type catalog. Group display names are shown
verbatim, like finding type names and severity values elsewhere in Rocky;
only the static labels are translated. The Rocky container copies these two
files from Boefjes at build time; after changing the registry or catalog,
rebuild Rocky so the displayed options match the deployed catalog, and
restart Rocky afterwards: the choices are cached for the lifetime of the
process. The findings-page controls do not yet persist in dashboard widgets.
