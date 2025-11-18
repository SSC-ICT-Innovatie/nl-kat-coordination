.. _about-openkat-development:

Development
###########

Code
====

We strive to keep the code compatible with the Python versions used in Debian Stable and the last two Ubuntu LTS releases.
As of writing, these are Python 3.8, 3.9, and 3.10.

To improve readability and consistency we use the `PEP 8 <https://peps.python.org/pep-0008/>`_ guidelines.
Developers are encouraged to write their code as strictly compliant as possible.

Tools
=====

To make development and validation easier, we adopted :ref:`about-openkat-precommit` hooks to automate most of this.
This will help identify broken/bad code, improve consistency and save time during code reviews.
Some tools and hooks have been adopted for both local development as well as in our CI/CD pipeline as GitHub actions.

Some of the tools are:

- ``black`` for formatting, it also takes care of imports order
- ``ruff`` for checking code style, programming errors, and more
- ``vulture`` for checking dead code

With some tools exceptions are made that differ a bit from the standard configuration such as line lengths, error codes, etc.
See the different configuration files. A few more will be implemented later on including:

- ``mypy`` for type checking

For the frontend there are a few more tasks in the CI/CD pipeline:

- Compiling messages/language files
- ``robotidy`` for tidying up Robot tests


.. _about-openkat-precommit:

Pre-commit
----------

Continuous Integration will run several checks as mentioned above, like ``black``, ``ruff`` and more using pre-commit hooks.
Any warnings from these checks will cause the Continuous Integration to fail; therefore, it is helpful to run the check yourself before submitting code.
This can be done automatically by `installing pre-commit <https://pre-commit.com/#install>`_. We recommend that you first
`install pipx <https://pipx.pypa.io/stable/installation/>`_ and then use pipx to install pre-commit:

    pipx install pre-commit

If you already use homebrew you can also use it to install pre-commit:

    brew install pre-commit

Note that using apt to install pre-commit is not recommended because that will give you an old pre-commit version that might
not work. After pre-commit is installed, run::

    pre-commit install

from the root directory of a repository. Now all of the checks will be run each time you commit changes without your needing to run each one manually.
In addition, using pre-commit will also allow you to more easily remain up-to-date with our code checks as they change.

.. _about-openkat-signed-commits:

Signed commits
==============

The OpenKAT github project is configured to require all commits of a PR to be
signed. The easiest way to do this is to configure git to automatically sign all
commits by default. See the `GitHub documentation
<https://docs.github.com/en/authentication/managing-commit-signature-verification/signing-commits>`_
how to do this.

Type Hinting
============

In this project we use strict type hinting where possible.
This should make code easier to read and reason about and easier to use (external) libraries.
Also, many modern frameworks today use type hints for e.g. runtime data validation and documentation.
Static code analysis tools (including those in an IDE) and type linters can be used to validate typing and improve code quality.

Although we try to provide as much type hinting as possible, it may be harder to use type hints in some contexts because of mismatches between different type linters or external libraries that don't have type hints or typing stubs.
Therefore we try to be less strict in e.g. (parts of) Django based applications, but enforce stricter type hinting in more isolated code such as clients and utility functions.

In principle, all independent code (e.g. which does not depend on, or inherit from, external libraries) should be strictly typed.

In practice, this means ``mypy --strict --ignore-missing-imports``; we do not check stubs.

Testing
=======

To prevent bugs and regressions, and to evaluate and verify that the products work, we test the codebase.
We do this both manually and automated (preferred).
Developers are encouraged to follow the `Test Driven Development <https://en.wikipedia.org/wiki/Test-driven_development>`_ paradigm (although this is not strictly required).
It is obligatory to write unit tests for each bug fix and implemented feature.

Code should be written in such a way that it is inherently testable.

Unit Tests
----------

Most repositories must have at least unit tests for quick white box testing. For Python we use two testing packages:

- ``pytest`` as the preferred package and type of tests
- The builtin ``unittest`` package is still used for some of the older tests; those tests are also run using the ``pytest`` runner

Unit tests should be:

- Reproducible; meaning independent from environment or running order
- Fast; external and I/O calls should preferably be mocked
- Maintable; meaning easy to read and update
- Truly unit tests; testing units of code and not accessing external resources

Integration Tests
-----------------

For integration testing the frontend we adopted `Robot Framework <https://robotframework.org>`_.
It has a simple syntax and many plugins available that should improve our test coverage.

Development Environment
=======================

See :doc:`/installation-and-deployment/index` for the overall installation instructions.
In a development context, we strongly recommend to use the Docker setup to test and make changes in the codebase (and not production packages).

When it comes to development there is no specific IDE that must be used, although many of us would choose PyCharm as the preferred IDE.

``make`` is used for automating several tasks such as building, cloning, pulling changes and more.
Developers are encouraged to implement any helper or convenience shell functionality through a ``Makefile``.

Furthermore the different services are containerised using Docker and set up to run with ``docker-compose``.

Merge Strategy
==============
**Commits should preferably be squashed** when merging a PR back into the primary branch.
This helps to keep the git history clean and easier to digest.
Multiple rework commits *may* be submitted (or also squashed together) to highlight the rework and give more transparency.

Branching
---------

In principle, all work-in-progress by the core team is based off the ``main`` branch. Releases are tags on the ``main`` branch.
If you are a community contributor, it may be wise to use a release tag as the basis for your work instead of the ``main`` branch.
This is because that branch generally changes rapidly, and may require you to continuously pull and merge all changes into your PR.

Reviews
-------

Code and functional reviewers are encouraged to be reasonably strict. **An approval should only be given after serious consideration**.
Reviewers should not be tempted to accept "it works" contributions, and should consider whether the changes by the PR will lead to extra refactoring and maintenance down the road.
We believe that writing good, well thought-out code is more important than adding features as quickly as possible.
Remember that writing tests and documentation (where necessary) are obligatory.
That said, everyone should remember to be polite and constructive in their feedback and comments.

``# noqa:``  may be used sparingly on a per-line basis if the CI encounters a false positive, or if it concerns a code style issue that is non-trivial to fix.
Code reviewers are strongly encouraged to be sceptical of this.

Code commenting and documentation
---------------------------------
Everyone is encouraged to write meaningful comments in their code where necessary, especially in complicated or abstract parts.

`PEP 257 <https://peps.python.org/pep-0257/>`_ (as checked by ``pydocstyle``) is our preferred way of writing docstrings.
Ideally, each public method, class, function, and module has one.

Using docstrings and type hints everywhere improves the quality of the automatically generated API documentation.

(Note: we may decide to prefer reStructuredText docstrings later.)

Line ends
=========

We accept contributions from all sorts of development environments. Please set ``git config --global core.autocrlf true`` if you use a Windows environment. Check out `the documentation on issues related to line ends and white spaces <https://git-scm.com/book/en/v2/Customizing-Git-Git-Configuration#_formatting_and_whitespace>`_ if you need more information or run into issues.

Technical diagrams
==================

We prefer the use of `Mermaid <https://mermaid-js.github.io>`_ to create (technical) diagrams of things.
These are automatically rendered by GitHub and the online Sphinx docs.

Mermaid has support for things like PlantUML and ERD's.

Dependency management
=====================

Our module dependencies are managed using `Poetry <https://python-poetry.org>`_, through ``pyproject.toml`` and the ``make poetry-dependencies`` command.
Poetry can create and manage per-module virtual environments for you automatically.
The CI checks whether the ``pyproject.toml`` file is up-to-date with the ``poetry.lock`` and ``requirements.txt`` files.
The automatically generated ``requirements.txt`` files are used by the Docker images, Debian packages, and the CI environment.
