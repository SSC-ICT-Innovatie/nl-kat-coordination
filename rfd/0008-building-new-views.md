---
authors: Donny Peeters <@donnype>
state: implemented
discussion:
labels: Frontend, Organizations, Scalability
---

# RFD 0008: Creating New Views

## Introduction

Many parts of OpenKAT are focussed on one organization only.
With our current scalability goals, i.e. scaling to thousands of organizations,
we need to make the interface multi-organization-friendly.
This means seeing and editing data over multiple organizations at the same time.

## Proposal

This proposal suggests a strategic approach for creating the new views for OpenKAT 2.0.
To make sure we build multi-organization-friendly views, we should first build the global views for all organizations.
Because filtering the information down for a selection of organizations,
or even just one organization, will likely boil down to changing the querysets on most views,
creating organization-specific views would require more work.
If we immediately build both views,
we would be spending twice the amount of time creating new pages with little-added benefit for an MVP.
Moreover, as filtering down on organizations is something we are going to do for many pages,
there is likely a useful abstraction we could introduce.
And we've all learned over time that abstractions should only be introduced once it covers a lot of instances.
In short, we should build our main views globally and then come up with a smart way to scope the information.

### Functional Requirements (FR)

1. As a User, I want to be able to see and modify information globally for my OpenKAT install
2. As a User, I want to be able to manage information for one organization or a selection of organizations

### Extensibility (Potential Future Requirements)

1. As a User, I want to be able to manage organizations filtered on a specific organization tag

## Implementation

The multi-organization view strategy from this RFD has been successfully implemented.
Following the proposal's recommendation, global views were built first and then made filterable through a reusable abstraction.

### Core Implementation Framework

The implementation is based on two key components:

#### 1. OrganizationFilterMixin (Backend)

**Location:** `openkat/mixins.py` (lines 241-279)

This mixin provides the core filtering mechanism for all views:

```python
class OrganizationFilterMixin:
    def get_queryset(self):
        return filter_queryset_orgs_for_user(
            super().get_queryset(),
            self.request.user,
            set(self.request.GET.getlist("organization")),
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["filtered_organizations"] = get_filtered_organizations(...)
        return context
```

**Features:**

- Query parameter support: `?organization=<code>` or `?organization=<code1>&organization=<code2>`
- Automatic permission-based filtering
- Works with any Django ListView/DetailView/FilterView
- Provides filtered organization context to templates

#### 2. filter_queryset_orgs_for_user() Function

**Location:** `openkat/mixins.py` (lines 196-238)

Smart organization filtering that handles:

- Global views (all organizations) for users with `can_access_all_organizations` permission
- User-scoped organization lists (filtered by user's accessible organizations)
- Multiple organization field patterns: `organization` (FK), `organizations` (M2M), `organization_id`
- Unassigned objects (null organization) when user has global access

**25+ views across 7 major modules** now support multi-organization filtering.

### Functional Requirements Coverage

- **FR 1**: Users can see and modify information globally for the entire OpenKAT install
- **FR 2**: Users can manage information for one organization or a selection of organizations

### Key Implementation Files

| File                                                           | Purpose                                     |
| -------------------------------------------------------------- | ------------------------------------------- |
| `openkat/mixins.py`                                            | OrganizationFilterMixin and filtering logic |
| `openkat/context_processors.py`                                | Organization context for all templates      |
| `openkat/templates/partials/organizations_menu_dropdown.html`  | Organization selector UI                    |
| `openkat/templates/header.html`                                | Navigation with filter preservation         |
| `objects/views.py`, `tasks/views.py`, `plugins/views.py`, etc. | Multi-org views across all modules          |
