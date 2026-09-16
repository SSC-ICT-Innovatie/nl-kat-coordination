# Rocky

Rocky is part of the openKAT project, made with Django.
To comply to government standards, [Manon](https://github.com/minvws/nl-rdo-manon) is used for style and accessibility.
Yarn is used as package manager and ParcelJS is used as bundler to compile the frontend (CSS and Javascript).
You can find the Manon repository [here](https://github.com/minvws/nl-rdo-manon).

## Installation

### Containerized

To run rocky from using Docker, run this from the parent directory `nl-kat-coordination`:

```bash
$ make kat
```

and continue reading this document at "First run".

### Local

For a local set up, you need to start the Django app and compile the frontend.

#### Django App

This requires a working Python (>3.10) environment.
One example of how to create, activate and initialize a development environment is:

```bash
$ python3 -m venv $PWD/.venv
$ source .venv/bin/activate
$ python3 -m pip install -r requirements-dev.txt
```

Copy the `.env-dist` to a `.env` and configure the hosts and credentials to PostgreSQL, RabbitMQ and the other services.

```bash
$ cp .env-dist .env
```

For instance, to configure the PostgreSQL database set the following variables:

```
ROCKY_DB_HOST=
ROCKY_DB_PORT=
ROCKY_DB=
ROCKY_DB_USER=
ROCKY_DB_PASSWORD=
ROCKY_DB_DSN=
```

Here, `ROCKY_DB_DSN` is optional (e.g. `postgresql://username:password@hostname:port/database_name`)
and if not set, the other DB variables will be used.

Once your environment variables are set up (see `.env-dist`, you can initialize Rocky using:

```bash
$ make build-rocky-native
```

To start the Django server, run:

```bash
$ make run
```

#### Frontend

Yarn is used to bundle CSS and Javascript.

To compile the frontend using yarn locally, run:

```bash
$ yarn --ignore-engine
$ yarn build
```

To compile the frontend using Docker, run:

```bash
$ make build-rocky-frontend
```

The app should be running at [localhost:8000](http://localhost:8000).

#### TL;DR

Given a proper `.env` file, run:

```bash
$ python3 -m venv $PWD/.venv
$ source .venv/bin/activate
$ python3 -m pip install -r requirements-dev.txt
$ make build-rocky-native
$ & make run
$ make build-rocky-frontend
```

## Development

(rocky-testing)=

### Testing

To run all unit tests, run:

```bash
$ make utest
```

#### Tip

A local Python environment is useful for unit testing even when using Docker.
Follow the first instructions in the local setup to create a Python environment.
Then create a `rocky/.env` from the template `rocky/.env-dist` and set `ROCKY_DB_HOST=localhost`.
Now for the unit tests you should be able to just run

```bash
$ pytest
```

to run them locally.

You can easily parallelize the tests can be parallelized using pytest-xdist:

```bash
$ python -m pip install pytest-xdist
$ time pytest  # 1:08,92 on 13-02-2024
$ time pytest -n 8  # 21,749 on 13-02-2024
```

## Design

### Fonts license

All fonts used within Rocky remain under their own license. For example: Fredoka, Open Sans & Tabler icons.

For more information check their respective folders for extra/ more specific license (if available) or visit:

#### Fredoka

https://fonts.google.com/specimen/Fredoka/about

#### Open Sans

https://fonts.google.com/specimen/Open+Sans/about

#### Tabler icons

https://tabler-icons.io/

## Technical Design

### Running a boefje

The following diagram shows the triggered flows when running a Boefje from Rocky.

```{mermaid}
sequenceDiagram
    participant Rocky
    participant Scheduler
    participant Boefje
    participant Bytes
    participant Normalizer
    participant Octopoes
    Rocky->>+Scheduler: Push Boefje Task
    Boefje->>Scheduler: Pull Boefje Task
    Scheduler-->>Rocky: boefje_task.status = dispatched
    Boefje->>Bytes: Save Raw
    Boefje->>Scheduler: boefje_task.status = completed
    Scheduler->>-Rocky: boefje_task.status = completed
    Bytes-->>Scheduler: Raw File Received
    Scheduler->>+Scheduler: Push Normalizer Task
    Normalizer->>Scheduler: Pull Normalizer Task
    Normalizer->>Bytes: Get Raw
    Scheduler-->>Rocky: normalizer_task.status = dispatched
    Normalizer->>Octopoes: Add object(s)
    Normalizer->>Scheduler: normalizer_task.status = completed
    Scheduler->>-Rocky: normalizer_task.status = completed
```

### Rocky View Structure

Rocky has a hierarchical set of views that are not easy to capture in a single diagram.
We therefore made several diagrams to show the most coherent components.

#### Overview of child Views of the OrganizationViews

```{mermaid}
classDiagram
direction RL
    class OrganizationView
    OrganizationView : organization
    OrganizationView : octopoes_api_connector
    OrganizationView : organization_member
    OrganizationView : indemnification_present

    OrganizationView <|-- View
    SinglePluginView <|-- OrganizationView
    BytesRawView <|-- OrganizationView
    Health <|-- OrganizationView
    HealthChecks <|-- OrganizationView
    IndemnificationAddView <|-- OrganizationView
    OctopoesView <|-- OrganizationView
    OOIAddTypeSelectView <|-- OrganizationView
    Report <|-- OrganizationView
    OrganizationDetailView <|-- OrganizationView
    OrganizationMemberEditView <|-- OrganizationView
    DownloadTaskDetail <|-- OrganizationView
    TaskListView <|-- OrganizationView
    UploadCSV <|-- OrganizationView
    UploadRaw <|-- OrganizationView
    ObjectsBreadcrumbsMixin <|-- OrganizationView
    OrganizationMemberBreadcrumbsMixin <|-- OrganizationView
    FindingTypeAddView <|-- OrganizationView
```

#### Exhaustive overview of OctopoesViews

```{mermaid}
classDiagram
direction RL
    class OrganizationView
    class OctopoesView
    class SchedulerView
    class TaskListView

    OctopoesView <|-- OrganizationView

    SchedulerView <|-- OctopoesView
    TaskListView <|-- SchedulerView
    BoefjeDetailView <|-- TaskListView
    OOIDetailView <|-- TaskListView
    OOIDetailView <|-- OOIRelatedObjectAddView
    OOIDetailView <|-- OOIFindingManager
    ChangeClearanceLevel <|-- SchedulerView

    SingleOOIMixin <|-- OctopoesView
    SingleOOITreeMixin <|-- SingleOOIMixin

    BaseOOIDetailView <|-- SingleOOITreeMixin
    BaseOOIDetailView <|-- ConnectorFormMixin
    OOIDetailView <|-- BaseOOIDetailView
    OOIFindingListView <|-- OOIFindingManager
    OOIFindingListView <|-- BaseOOIDetailView
    MuteFindingView <|-- BaseOOIDetailView
    BaseReportView <|-- BaseOOIDetailView

    OOIReportView <|-- BaseOOIDetailView
    OOITreeView <|-- BaseOOIDetailView
    OOISummaryView <|-- OOITreeView
    OOIGraphView <|-- OOITreeView

    OOIRelatedObjectManager <|-- SingleOOITreeMixin
    OOIFindingManager <|-- SingleOOITreeMixin
    OOIRelatedObjectAddView <|-- OOIRelatedObjectManager

    OOIReportPDFView <|-- SingleOOITreeMixin
    OnboardingSetupScanOOIDetailView <|-- SingleOOITreeMixin

    BaseOOIFormView <|-- SingleOOIMixin
    OOIDeleteView <|-- SingleOOIMixin

    OnboardingSetupScanOOIAddView <|-- BaseOOIFormView
    OOIEditView <|-- BaseOOIFormView
    OOIAddView <|-- BaseOOIFormView
    FindingAddView <|-- BaseOOIFormView

    BaseOOIListView <|-- ConnectorFormMixin
    OOIListView <|-- BaseOOIListView
    FindingListView <|-- BaseOOIListView
    OOIListExportView <|-- BaseOOIListView

    ScanProfileDetailView <|-- OOIDetailView
    ScanProfileResetView <|-- OOIDetailView
```

#### KATalogus Views

This diagram shows the current view structure and what properties are set in each class for the KATalogus.

```{mermaid}
classDiagram
direction RL
    class FormView
    class OrganizationView
    class SinglePluginView
    class KATalogusView
    class PluginSettingsAddView
    class PluginEnableDisableView
    class SingleSettingView
    class PluginSettingsListView

    OrganizationView : organization
    OrganizationView : octopoes_api_connector
    OrganizationView : organization_member
    OrganizationView : indemnification_present

    SinglePluginView : katalogus_client
    SinglePluginView : plugin
    SinglePluginView : plugin_schema

    SingleSettingView : setting_name

    class PluginSettingsDeleteView
    class BoefjeDetailView
    class TaskListView

    KATalogusView  <|--  OrganizationView
    KATalogusView  <|--  FormView
    SinglePluginView  <|--  OrganizationView
    SingleSettingView  <|--  SinglePluginView
    BoefjeDetailView  <|--  PluginSettingsListView
    BoefjeDetailView  <|--  TaskListView
    PluginEnableDisableView  <|--  SinglePluginView
    PluginSettingsAddView  <|--  FormView
    PluginSettingsAddView  <|--  SinglePluginView
    PluginSettingsDeleteView  <|--  SingleSettingView
    PluginSettingsListView  <|--  SinglePluginView
```
