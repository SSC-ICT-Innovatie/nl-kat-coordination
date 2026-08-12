Contributions
#############

All contributions, bug reports, bug fixes, documentation improvements, enhancements and ideas are welcome.
You can directly join and be involved in the development of OpenKAT:

- Install and use OpenKAT and provide feedback
- Development of boefje, normalizer and bit plugins
- Propose new features
- Report bugs
- Solve tickets with a ``good first issue`` label
- Port OpenKAT to other systems

Note that it is required to sign a `Contributor License Agreement <https://cla-assistant.io/minvws/nl-kat-coordination>`_ when submitting.
The ``CLAassitant`` bot will request this automatically on your first Pull Request.

Contribute to Codebase
======================


See :ref:`about-openkat-development` for our code style, coding conventions, and overall workflow.

- Fork the right repository in GitHub
- Create a new branch from either ``main`` or a release tag. Note that ``main`` changes rapidly, and as such may not be a suitable basis for your work.
    - This branch should be in the following format:
    - ``[feature|enhancement|bug|hotfix]/random-cat-popup-on-screen``
- Commit and push the code
    - Make sure the code is linted, formatted and has correct typing. Use ``pre-commit`` locally for this, see :ref:`about-openkat-precommit`.
    - All commits must be signed, see :ref:`about-openkat-signed-commits`.
- Submit Pull Request
    - Make sure your code is tested and the PR has a good title and description
    - Use the PR template
    - Let your code be reviewed
    - You might have to update your PR after remarks and submit rework for approval


Contribute Documentation
========================

Contributing to the documentation benefits everyone who uses OpenKAT.
We encourage you to help us improve the documentation, and you don't have to be an expert using OpenKAT to do so.
There are many sections that are better off written by non-experts.
If something in the docs doesn't make sense to you, updating the relevant section might be a great way to ensure it will help the next person.
You're welcome to propose edits to almost every text, including comments and docstrings in the code, this documentation, and other files.

You could help us out with the following sections:

- Code documentation
- Tutorials
- Translations
- This document

All documentation should be placed in a repository's ``docs`` folder.

Contribute Translations
=======================

.. image:: https://hosted.weblate.org/widget/openkat/287x66-white.png
   :target: https://hosted.weblate.org/engage/openkat/
   :alt: Translation status (summary)

.. image:: https://hosted.weblate.org/widget/openkat/multi-auto.svg
   :target: https://hosted.weblate.org/engage/openkat/
   :alt: Translation status (bar chart)

============ ==============================
 Language     Support
============ ==============================
 English      Default; used in source code
 Dutch        Official
 Papiamentu   Community
 Italian      Community
============ ==============================

We gratefully use `Weblate <https://hosted.weblate.org/engage/openkat/>`_ to manage the translations.
Community contributions are very welcome and can be made via Weblate's interface.
This is a great way to help the project forward and doesn't require any technical expertise.
If you would like to see OpenKAT in another language, let us know!

Any authenticated Weblate user can edit translation strings directly or make suggestions.
Any translation updates in Weblate will be automatically submitted as a GitHub PR after 24 hours, which will be reviewed by the development team.
If you contribute to the translation effort, you will receive a mention in the source code.

Note that editing the English localization requires changing the source string in Django, which must be done through a GitHub PR manually.
In addition, take care not to edit the ``.po`` files through GitHub directly, as this may cause merge conflicts when Weblate has pending translations.

Adding a new language
---------------------
You can add a new language to OpenKAT by following these steps:

1. Add a new language through Weblate's interface
    Alternatively: create a new ``rocky/rocky/locale/$LANGUAGE_CODE/LC_MESSAGES/django.po`` file directly in the repository.
    You can use ``rocky/rocky/locale/django.pot`` as a template.
2. Add the language code to the ``LANGUAGES`` list in ``rocky/rocky/settings.py``
    Note that languages not supported by Django require that you also add a custom dictionary entry in ``EXTRA_LANG_INFO``.

The new language should be automatically picked up by both Weblate and Django.

Contributor Social Contract
===========================
All contributors (including, but not limited to, developers and issue reporters) promise to do their best to adhere to the guidelines in :ref:`guidelines-index`.
Everyone is encouraged to politely and constructively point out guidelines violations to others.
Actively enforcing these guidelines makes that the entire project benefits in quality control.

Code of Conduct
===============
See the `Code of Conduct of the Ministry of Health, Welfare, and Sport <https://github.com/minvws/.github/blob/main/CODE_OF_CONDUCT.md>`_.

Security
========
See the `Responsible Disclosure Statement of the Ministry of Health, Welfare, and Sport <https://github.com/minvws/.github/blob/main/SECURITY.md>`_.
