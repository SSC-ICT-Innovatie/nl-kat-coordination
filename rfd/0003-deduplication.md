---
authors: Jeroen Dekkers (@dekkers), Donny Peeters (@donnype)
state: implemented
discussion: https://github.com/minvws/nl-kat-coordination/pull/4051
implementation: https://github.com/minvws/nl-kat-coordination/pull/4482, https://github.com/minvws/nl-kat-coordination/pull/4554
labels: boefjes
---

# RFD 0003: Deduplication of boefjes tasks between organization

The goal of deduplicating boefje tasks is to avoid doing multiple scans in similar organizations for the same
assets. When a large number of organizations have the same asset, this would prevent scanning the asset too many
times, saving resources and avoiding hammering external APIs too much.

## Functional requirements

Deduplication can only be done when all the inputs of the boefje are exactly the same. This includes the input OOI
and all the boefje settings.

1. A few boefjes use the organization itself as a parameter, so those boefjes can't be duplicated. Hence, we should
   be able to turn deduplication off per boefje.
2. When doing deduplication between organizations, in general a user should not know for which other organizations
   the task has been deduplicated in the same KAT install. If the user belongs to those organizations this is perhaps not
   a problem, but insights into which tasks have been deduplicated for which organization is considered out of scope.
3. In the end, deduplication is a feature that prevents doing double work in the background. Nevertheless,
   organizations might not want to deduplication to happen as this does affect when jobs are processed, so
   deduplication should be a setting that can be turned off for the whole install and per organization.

## Nonfunctional requirements

1. For our data lineage and the ability to debug deduplicated jobs, we should know which jobs have been deduplicated.
2. We should also strive to minimize the impact on our data models, as we see deduplication as an optimization that
   should not make future work significantly harder.

## Technical design

### Current situation

The current input of a boefje is defined as the BoefjeMeta. This currently defined as:

```python
class Job(BaseModel):
    id: UUID
    started_at: AwareDatetime | None = Field(default=None)
    ended_at: AwareDatetime | None = Field(default=None)

    @property
    def runtime(self) -> timedelta | None:
        if self.started_at is not None and self.ended_at is not None:
            return self.ended_at - self.started_at
        else:
            return None


class Boefje(BaseModel):
    """Identifier for Boefje in a BoefjeMeta"""

    id: Annotated[str, StringConstraints(min_length=1)]
    version: str | None = Field(default=None)


class BoefjeMeta(Job):
    boefje: Boefje
    input_ooi: str | None = None
    arguments: dict = {}
    organization: str
    runnable_hash: str | None = None
    environment: dict[str, str] | None = None
```

The local job handler gets the `BoefjeMeta` object from the scheduler and additionally sets `arguments["input"]`,
`runnable_hash`, `environment`, `started_at` fields (see `BoefjeHandler` in boefjes/job_handler.py). The local
boefje `run` function gets the full `BoefjeMeta` pydantic object:

```python
from boefjes.job_models import BoefjeMeta


def run(boefje_meta: BoefjeMeta) -> list[tuple[set, bytes | str]]:
```

The docker runner creates the boefje_meta object itself and currently only sets the `id`, `boefje`, `input_ooi`,
`arguments`, `organization` and `environment` fields (see `create_boefje_meta` in boefjes/api.py). The docker boefje
`run` function gets a dictionary with those values:

```python
def run(boefje_meta: dict) -> list[tuple[set, bytes | str]]:
```

### Arguments that are passed to boefjes that need to be considered for deduplication

To make sure we only do deduplication on boefje tasks that really are the same, we should be more strict in what we
pass to the boefje as input. We've been providing more information than is necessary to the boefjes by giving the whole
BoefjeMeta as input to each boefje.

#### Usage of arguments field

This is used by almost every boefje and the main way to specify on what the boefje should run. This is the
serialized OOI, the result of calling `serialize` on an OOI.

It might be better to provide the serialized OOI as `input_ooi` argument to the boefje `run` to make the contents of
the field clear. See below for the proposed signature.

#### Usage of organization field

The external DB boefje currently needs the organization to fetch the data from the external database. Obviously,
this means the boefje can't be deduplicated.

To support this we should add a flag to boefjes that require the organization. If the flag is set, we provide
organization to the boefje and can't do deduplication. If the flag isn't set, we don't provide the organization and can
duplicate. This way we make sure the organization is never used when it is not supposed to be. We could reuse the flag
we already need to mark boefjes that can be deduplicated, and hence pass the organization to all boefjes where this
is `False`.

#### Usage of boefje task id field

There is no boefje that uses the task id at this point and can be removed safely.

#### Usage of input_ooi field

Only the leakix boefje used the input_ooi field. For the sake of simplicy we should probably not provide this to the
boefje. It should be easy to refactor this so it used the serialized input OOI.

#### Usage of environment field

This is not used directly from the BoefjeMeta argument in `run`, but the provided variables are set environment
variables are set and the boefje

#### Usage of started_at, ended_at, boefje and runnable_hash fields

This isn't used by any boefje and can be safely removed from the boefje arguments.

#### Boefje signature / arguments

Boefje that does not require organization can have the following signature:

```python
def run(input_ooi: dict[str, Any]) -> list[tuple[set, bytes | str]]:
```

And boefje that requires organization:

```python
def run(input_ooi: dict[str, Any], organization: str) -> list[tuple[set, bytes | str]]:
```

The `input_ooi` is the serialized input OOI that is stored in the BoefjeMeta `arguments`. The environment field does
need to be passed as argument, because it is already passed to the boefje using environment variables.

### Deduplication implementation

The scheduler schedules boefjes and the boefje worker executes them and saves the raw files to bytes. Hence, these
are probably the services that need modification to support deduplication. (Changes to other services could suggest
this feature has a bigger impact than intended.)

#### Deduplication algorithm: Option 1 (not implemented)

A possible algorithm for deduplication could be:

- The scheduler wants to scheduler a boefje for a specific organization and input OOI.
- The scheduler checks if the boefje needs the organization. If so, it can continue with scheduling the boefje task.
- The scheduler queries the stored tasks to see if a different organization has already run on this input OOI.
- If there is a match, the scheduler fetches the environment of the previous boefje task and the environment of the
  new boefje task. If they are the same, they can be deduplicated. If they differ, the new boefje needs to be scheduled.

This could be further optimized by storing information about the configured boefje settings. If we store which
organizations have the same settings and which have different settings, we don't have to fetch this information for
every boefje task.

#### Deduplication algorithm: Option 2 (implemented)

The goal of OpenKAT is to do continuous monitoring. This means that most of the time we are scanning an already
existing OOI. For deduplication, this means that the common scenario is that a certain OOI might be in a large number of
organizations. The scenario that a new OOI is added that already exists in another organization is probably less common.

We can take advantage of this by checking all other organizations for the same OOIs either before or after a boefje
has run. The big advantage of doing deduplication this way is that we don't need to insert data from the past or
with a different valid_time, because we proactively schedule tasks for other organizations at the same moment.

The algorithm would be:

- The scheduler wants to schedule a boefje task with id "123" for a specific input ooi
- If the boefje can be deduplicated, the scheduler asks the katalogus for its config
- The scheduler queries the katalogus for organizations that have the same config for this boefje
- The scheduler queries octopoes to check which of these organizations have the input ooi as well
- The scheduler schedules tasks for the remaining organizations for the same boefje and input ooi. Also see "A Task
  per organization or one Task spanning multiple organizations" below.
- Set a new `deduplication_key` field of both task "123" and the other task equal to the original task id: "123"
- For task that are not deduplicated, set this field to `null`
- The scheduler updates its task pop API to return all duplicates of a task as well.
- The boefje runner only runs the first task, but saves the raw file for all other tasks as well.

To know which tasks have been deduplicated, we can query the Task table for tasks where `id == deduplication_key`,
or `id != deduplication_key` for tasks that are duplicates.

An easy optimization would be to combine the first two katalogus calls by providing an API that can return both the
config of the requested boefje and all its duplicates (perhaps through a "?with_duplicates=true" url parameter). This
would allow us to perform this check in the database directly.

Another way to optimize this might be to mark whether an OOI also exists in a different organization. This can be done
when OOIs are created, updated and deleted instead of doing that check on every boefje run. We might also do
something similar when environment settings are updated.

#### Returning environment settings and all its duplicates in the KATalogus

The katalogus stores the current settings of a boefje as a boefje_config. Finding other configs for the same
boefje with the same settings is complicated for two reasons. Firstly, the settings are stored as JSON and hence
need not be ordered by its fields consistently. This could be tackled with a migration, of course. But, secondly, an
install might have encryption enabled. Our encryption uses a nonce that makes sure two settings that are equal are
no longer equal when encrypted. So, our hands are tied. We should therefore perform the check at the application level.
This does solve the first issue as Python considers two dictionaries equal irrespective of the order of their keys.

Note that this restriction also makes storing a hash of the settings to easily query duplicate settings hard: plain
hashes (without a nonce) would make the nonce in our encryption redundant and requires us to keep track of
create/update/delete operations for the settings field at the application level. We deemed this a risky change that
would require even more database changes.

#### If boefje needs organization and should not be deduplicated (Functional requirement 1)

The katalogus should add a `deduplicate` boolean field to both the Boefje and Organization model. The scheduler already
fetches all available boefjes for an organization, but this information is not present currently in the right place
within the boefje scheduler logic, so would require some refactoring. Hence, an even simpler implementation of this
would be never to provide duplicated environment settings in the API by filtering boefjes where `deduplicate=True`
in database time.

#### Deduplication can be turned off per organization or install (Functional requirement 3)

In line with the previous section, we can add a `deduplicate` field on the organization model as well and add a
`deduplicate=True` for the organization model as well in the boefje config query. We should also add an environment
setting to turn deduplication off globally, and check this setting both in the config API and the runner. The runner
should take measures to make sure it handles deduplicated tasks as regular tasks, by putting them as separate tasks
in its local queue, for example.

#### Users should not know deduplication happened (Functional requirement 2)

Since we have the same number of Tasks and RawFiles per organization when deduplication is turned on and the data
looks the same, this requirement has been met.

#### A Task per organization or one Task spanning multiple organizations

In the scheduler, we could either create one Task entry per organization or one Task for all organizations. If we
create one Task entry that spans multiple organizations, we would have to fan these out in rocky and make sure
organizations cannot modify this task, or else this information could "leak" to other users. Therefore, creating an
entry per organization has less impact on both security and our core data model, but puts more responsibility in
the API/Query layer. But code is easier to change than a database, so we decided that this is the safer route.

#### What if the task fails

For now, an easy way to handle task failure is to push the other tasks back on the scheduler queue.

#### Future improvements

The current implementation reuses the raw file of the first boefje task. It is not clear if we can easily prevent
storing save the raw file again for the other organization by sharing the data in bytes. Not saving multiple files is a
nice-to-have optimization we could do later.
