# Feature flow

## Getting features in the main branch

Most features should follow the path laid out on our project board. This document describes the requirements for features to move between columns of the board.
Listing these requirements should reduce the _bystander effect_ for doing code or QA reviews and make it easier for other developers to pick up these tasks.
This would enable us to move features quickly from in progress to merged and avoid bottlenecks at either the review or QA stage.
The required procedure to merge a feature into main are as follows.

### 1. Approved Features / Need Refinement &rarr; Refined Tasks

- We are not reinventing the wheel: there is no high-quality library that already has this feature.
- This issue is "bite-sized" and (only) leaves non-critical implementation details to the developer.

### 2. In Progress &rarr; Review

- The authors of the ticket have created a pull request.
- The `Checklists for authors` in our pull_request_template has been filled in by the authors.

### 3. Review &rarr; QA review

- The `Checklist for code reviewers` in our _pull_request_template_ has been filled in by a code reviewer.

### 4. QA Review &rarr; Ready for Merge

- The `Checklist for QA` in our _pull_request_template_ has been filled in by a QA reviewer.

### 5. Ready for merge &rarr; Done

The procedures above should guarantee that members of the _kat-managers_ group can merge these features directly.
We should actively aim to resolve any discussions about the implementation at stages 1 and 2.
It is the responsibility of the authors to bring possible issues to the attention of anyone that might have an opinion about the issue.

---

## Releasing features

Once a release branch has been created with a new set of functionality, it is important that we do a QA review again.
This time, the QA has an extended checklist to also guarantee that there is no regression in the more advanced functionality of OpenKAT.
Also, we need to assure that there is no regression between the different supported deployments options of OpenKAT.

### Environments for the extended QA

- [ ] Clone the source repository and run `make reset` [Linux and Darwin, perhaps different docker versions and installs]
- [ ] Install the debian packages [On different distro's: ubuntu 20.04 + 22.04, debian 11 + 12]
- [ ] Install the container images

Ideally we would follow the following QA procedure on each of these environments:

### Checklist for QA

- [ ] I confirmed that there are no unintended functional regressions in this branch:
  - [ ] I have managed to pass the onboarding flow
  - [ ] Objects and Findings are created properly
  - [ ] Tasks are created and completed properly

### Extended checklist for QA

#### Checking the UI/UX

- [ ] Turning Boefjes on and off in the KATalogus
- [ ] Create, turn off, and delete Boefjes-settings
- [ ] Perform scans
- [ ] Analyse results
- [ ] Reports (Findings), per object, per report
- [ ] Generating PDF-reports
- [ ] Pagination of several tables
- [ ] Translations
- [ ] Manually starting Boefjes and normalizers
- [ ] Manually adding and deleting objects and Findings
- [ ] Automatic scheduling and starting of Boefjes and normalizers
- [ ] Exporting the object list as JSON and CSV
- [ ] Inspection of task details
- [ ] Inspection of all pages interfaces, including de tree- and graph view of objects
- [ ] UI/UX in general

#### Checking User/Organization management functionality

- [ ] I can create and delete an organization
- [ ] I can create and delete users
- [ ] I can assign and revoke rights to these users
- [ ] I can reset 2FA

#### Checking Performance

- [ ] Verify that there is no significant performance regression

---

## Tips and tricks for pull request QA testing

### Think outside the box

- Feel free to deviate from the checklist: testing things that are not obviously related to the PR is a good way to find bugs.
- Thoroughness is key: embrace the "hacker mindset" and try to break (new) functionality by providing unexpected input, and attempt to perform unauthorized actions.
- Try to break the UI: try resizing the window, using zoom functionality, and test multiple browsers.
- Always remember that you are taking on the role of a user that is probably not as familiar with the application as you are: everything you encounter should feel intuitive and easy to use. Lack of intuitiveness deserves a QA comment.

### Be pragmatic but versatile

- Features updating the data model should usually be backward compatible, so we should not run `make reset` upon every review. Switch tactics with respect to updating your local environment regularly.
- Small documentation changes do not require rebuilding and restarting all services to performa a QA review.
- Properly gauge the impact of a feature: API changes in the KATalogus, for example, can affect Rocky, Mula and Octopoes, but never Bytes (in the current setup).
- Changes that hit the core of every service (package updates) require performing the extended QA checklist.
