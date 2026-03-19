QA Test plan
############

This document describes the QA process within OpenKAT. The QA process consists of the following phases:

- Read the PR
- Manual testing
- Check the Docker logs
- Document QA notes


Read the PR
===========

The first step is to read the ticket and the PR (including comments) to get an idea of what the PR is about and what it should fix. The QA notes on what could possibly break are useful to put a focus, however, experience shows that other parts sometimes break as a side effect. Therefore it is useful to generally perform more manual testing than described in the QA notes of the PR.

Check which files have changed in the PR and skim the code to get a general idea of what/where things have changed. Based on the file changes try to focus and reproduce also the things observed in the code.

- If changes to Rocky are made you know that this affects the user experience, thus weird/unexpected user behaviour scenarios should be tested.

- If there are changes to Octopoes, verify that the 'inner workings' of OpenKAT still work, such as propagation of clearance levels, objects are created, etc.

- If there are changes to the Mula (Scheduler), verify that Tasks are created (boefjes and normalizers), reschedule tasks, schedule reports, etc.

Manual testing
=================

Each PR is manually tested to check if any bugs are identified before the PR is merged onto the main branch.

The manual testing phase consists of 2 stages:
- General user testing to check if everything still works as expected and there are no unexpected side effects.
- Specific testing for the PR to check if the PR works as described and test what happens if the user performs unexpected actions (e.g. goes back into the flow, editing data, unexpected values, etc.). This is specific for each PR.

The following things are always checked:

- Does the onboarding flow work?
- Does the onboarding result in the expected number of findings? This means that the corresponding tasks from boefjes and normalizers have also succeeded.
- Manually enabling/disabling boefjes in the Katalogus.
- Check if all navigation tabs can be loaded.
- Findings: check if findings are created and if they resolve from Pending into a severity. Check that the Finding specific pages can be loaded.
- Reports: Generate a normal and aggregate report with the following variables:
	- 1 host with 1 report
	- 1 host with multiple reports
	- multiple hosts with 1 report
	- multiple hosts with multiple reports
	- schedule a report and check for single scheduled reports.
	- Check if reports can be exported to PDF and json.
	- Check if the Scheduled and History tabs show data.
- Objects: Open the object details page of a hostname and check if the following data is present:
	- Multiple results under 'Last observed by'
	- Multiple results under 'Last Inferred by'
	- List of related objects
	- Tasks that ran on the Hostname object
	- Findings tab
- Tasks: On the Tasks page check the following:
	- Check for any failed tasks on the boefjes and normalizer Task statistics.
	- On the Boefjes tab:
		- download raw data file to check if this works.
		- Reschedule a task to check if this works and completes.
	- On the Normalizer tab:
		- Check if the normalizer creates Yielded tasks (not every normalizer creates yielded tasks, requires manual verification to verify that this is correct).
		- Click the link of the yielded objects to see that the redirect works.
- Generally click around, and see if you observe any unexpected behaviour.
- Add a second organization and verify that no data from organization 1 shows up in organization 2.

If a potential bug is identified, usually the first step is to verify if this also happens on the main branch. If it is a PR specific bug the bug is discussed with the author of the PR to discuss if this is (currently) expected behaviour. The next step is to write the QA notes.

Check the Docker logs
=====================

Check the Docker logs for any errors to check if any unexpected things crashed or broke that were not visible in the web interface.

Document QA notes
====================
The QA notes template is pasted in the PR and filled in with a description of the bugs, including any screenshots and reproducing steps. This is a mandatory step, as the next time the PR is QAed it might not be as clear on what/where the bug occurred and it is useful for future reference.

The template for QA notes can be found in ```docs/source/templates/pull_request_template_review_qa.md```

On occasion
===========

On occasion the following things are checked, as they don't tend to break often.

- Check if a multi report can be generated.
- Answer Question object and change Configs
- Add various objects manually to check if the objects can be created.
- Upload files (e.g. list of hostnames and raw files)
