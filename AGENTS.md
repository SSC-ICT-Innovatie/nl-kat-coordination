# AGENTS.md

Rules for AI coding agents working on this repository, and for the people who
run them. This covers any tool or bot that writes code, commits, or comments.

Every agent action has a human owner. That person reads the diff before it is
pushed and answers for it in the PR thread.

## 1. Architecture and design decisions go through the maintainer

An agent does not make design decisions. It investigates, lays out the options
with their trade-offs, and recommends one. The decision is taken by the project
maintainer (currently @underdarknl) in an issue or PR thread, and the agent
implements only what was decided.

The following always need that decision before any code is written:

- Changes to the data model: adding, renaming or removing an OOI type, changing
  its primary-key fields or field types. Stored data and its history must keep
  loading.
- Adding or removing bits, boefjes, normalizers, finding types or report types.
- Database migrations.
- Changes to the API between services, to a public API, or to the message
  queues.
- New dependencies, and changes to `docker-compose*.yml`, `.env-dist` or
  packaging.
- Anything that changes how existing installations behave after an upgrade.

When in doubt, treat it as a design decision. Write the proposal in an issue,
link it from the PR, and wait.

## 2. New features need an approved issue

Do not introduce a new feature unless an issue for it exists, has been refined,
and has been approved for implementation by the maintainer. An idea, a review
remark or a request in chat is not an approval.

- No approved issue yet? Write the proposal as an issue and stop there.
- Link the approved issue in the PR description.
- Build what the issue describes. Extra functionality you thought of along the
  way goes into a new issue, not into the PR.

Fixing a defect in existing behaviour is not a new feature. A fix that changes
the design still falls under section 1.

## 3. Other people's branches: hands off

A pull request belongs to its author until it is merged.

- Do not push to a branch you did not create, unless the PR author asks for it
  in the PR thread and names the change. A review finding, a red CI check, or a
  request from someone other than the author does not count.
- Do not touch draft pull requests at all.
- Offer changes instead of making them: a review comment with a `suggestion`
  block or a diff, or a stacked PR against the author's branch if the author
  asks for one. The author merges it.
- Never revert, rewrite, squash or force-push someone else's commits. If you
  think a commit is wrong, say so in the thread.

## 4. Open review threads are questions, not tasks

- If the reviewer and the author have not agreed, implement neither side. Wait
  for a decision, and link to it when you implement it.
- Do not resolve review threads you did not open.
- Do not approve, dismiss reviews, merge, or close other people's issues and
  pull requests.

## 5. One pull request, one concern

- No unrelated fixes, no reformatting of code you did not change, no renames
  outside the scope of the PR. Open a separate issue or PR for those.
- Follow the existing patterns of the component you touch, except the
  deprecated ones listed in section 6.

## 6. Deprecated patterns: do not copy them

Some patterns are still all over the code but are not wanted in new code. An
agent copies what it sees, so these are spelled out. Do not rewrite existing
code to match unless that is the purpose of the PR (section 5).

Findings:

- Every finding type you yield has its own entry in
  `boefjes/boefjes/plugins/kat_kat_finding_types/kat_finding_types.json`. Do
  not yield a `KATFindingType` id that is not in that catalog: it ends up with
  unknown severity and no description. Finding types imported from an external
  database (CVE and the like) are the exception.
- Do not set `description` on a `Finding` in code. The text comes from the
  finding type. Put what is specific to this occurrence in `proof`.
- If the finding type is too generic to describe the problem, add a more
  specific finding type instead of a custom description. Reports group and
  explain findings per type.

## 7. Before every push

Tests run in Docker. There is no supported local virtualenv.

| Changed       | Run                                      |
| ------------- | ---------------------------------------- |
| `rocky/**`    | `make -C rocky utest itest`              |
| `octopoes/**` | `make -C octopoes itest rtest`           |
| `boefjes/**`  | `make -C boefjes itest`                  |
| `bytes/**`    | `make -C bytes utest itest`              |
| `mula/**`     | `make -C mula utest itest`               |
| always        | `pre-commit run --files <changed files>` |

- If you added or changed translatable strings, run `make -C rocky lang` and
  commit the updated `django.pot`.
- After the push, check CI on that exact commit. A red check you caused is
  yours to fix before you ask for review.

## 8. Report truthfully

- Do not write "fixed" or "verified" unless you ran the check. Name the test or
  command and the commit you ran it on.
- State in the PR description that an agent wrote the change, and name the
  responsible person.
