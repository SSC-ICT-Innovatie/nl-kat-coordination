# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import subprocess

branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"]).decode("utf-8")
commit_date = subprocess.check_output(["git", "log", "--format=#%h %cs", "-n 1"]).decode("utf-8")

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = "OpenKAT"
copyright = "Ministerie van Volksgezondheid, Welzijn en Sport (European Union Public License 1.2)"
author = "The OpenKAT team"
version = branch + commit_date
release = version

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.githubpages",
    "sphinx.ext.autosectionlabel",
    "sphinx.ext.todo",
    "sphinx.ext.autodoc",
    "sphinx_rtd_theme",
    "myst_parser",
    "sphinxcontrib.mermaid",
    "sphinxcontrib.autodoc_pydantic",
]

myst_enable_extensions = ["tasklist"]

templates_path = ["_templates"]
exclude_patterns = []

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = "sphinx_rtd_theme"

html_logo = "_static/keiko-hero.jpg"
html_favicon = "_static/favicon.svg"

html_theme_options = {"collapse_navigation": False, "style_nav_header_background": "#ca005d"}

html_context = {
    "display_github": True,
    "github_user": "minvws",
    "github_repo": "nl-kat-coordination",
    "github_version": "main",
    "conf_py_path": "/docs/source/",
}

html_static_path = ["_static"]
html_css_files = ["openkat.css"]

mermaid_use_local = "mermaid.min.js"
mermaid_include_elk = ""
d3_use_local = "d3.min.js"

autosectionlabel_prefix_document = True

suppress_warnings = [
    f"autosectionlabel.installation-and-deployment/environment-settings/{document}"
    for document in ("boefjes", "bytes", "mula", "octopoes")
] + ["autosectionlabel.developer-documentation/octopoes-models"]
