Project management
##################

OpenKAT development is largely public except for the retrospective meetings of the development team at the Ministry of Health, Welfare and Sports. Do get in touch if you want to contribute. In principle, `all project management is handled in a central board <https://github.com/orgs/minvws/projects/7>`_.
Issues and PRs may be created in the repositories of the KAT modules, and will be linked to the central board.
All (linked) issues and PR's should be assigned to a status column, and have an assignee so we know who is chiefly responsible / who should take action.
Developers are encouraged to use the Review column(s) to get their PR's merged, and to regularly check if they can help review something.

Feature Milestones
==================

Although we have no fixed release schedules, we focus on a pre-defined list of tasks each iteration/cycle.

At the beginning of each release cycle, we take inventory of which (major) functionality we want to implement.
This will most likely be based on cards in the "incoming features and refinements" column on the project board.
We agree to prioritize our collective effort on implementing that functionality, although there is always time for bug fixing, testing, and quality control.
All tasks that belong to that cycle should have an appropriate milestone label in the project board, and should be moved to the To-Do column.

A cycle only ends if either:

* functionality is no longer required (i.e. changing requirements);
* the changes on ``main`` are complete, have been approved by QA, and have been released to a production tag.

When a cycle has been completed, we hold a quick retrospective to evaluate what we did and did not manage to complete, and any additional problems that we uncovered.

Bugs and Feature Requests
=========================

For effective bug reporting and feature requests there are :doc:`../templates/index`.
These should be used and submitted in the coordination repository's `issues board <https://github.com/minvws/nl-kat-coordination/issues>`_.
Please make sure to link them to the central project board as an incoming feature/refinement.


Pull Requests
=============

Each unit of work shall be submitted as a pull request using a :doc:`../templates/pull_request_template_author` and reviewed by at least one developer.
The checklist should be completed by a functional and a code reviewer.

In-depth content discussions
============================
All formal discussions about the direction of the project or about significant technical choices should be done through `GitHub Discussions <https://github.com/minvws/nl-kat-coordination/discussions>`_.
It is important that there is a paper trail about why certain decisions were made, and this is not guaranteed through e.g. Signal or Jitsi.
