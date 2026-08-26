# Configuration file for the Sphinx documentation builder.
# BLEECAM — https://github.com/NatLabRockies/bleecam
#
# Full reference: https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import sys
from datetime import date

# Make the package importable for autodoc without requiring an install
# (works both locally and on Read the Docs, which also pip-installs the package).
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

# -- Project information -----------------------------------------------------

project = "BLEECAM"
author = "Sherif Khalifa and the BLEECAM contributors"
copyright = f"{date.today().year}, Alliance for Energy Innovation, LLC / National Laboratory of the Rockies (NLR)"

# The short X.Y version and the full version, including beta tag.
version = "0.1.0"
release = "0.1.0-beta.1"

# -- General configuration ---------------------------------------------------

extensions = [
    "myst_parser",              # Markdown (MyST) source
    "sphinx.ext.autodoc",       # pull API docs from docstrings
    "sphinx.ext.autosummary",   # summary tables for modules
    "sphinx.ext.napoleon",      # Google/NumPy-style docstrings
    "sphinx.ext.viewcode",      # [source] links
    "sphinx.ext.intersphinx",   # cross-links to Python/pandas/etc.
    "sphinx.ext.mathjax",       # render LaTeX math
    "sphinx_copybutton",        # copy button on code blocks
    "sphinx_design",            # cards, grids, tabs
]

# Accept both .md (MyST) and .rst sources.
source_suffix = {
    ".md": "markdown",
    ".rst": "restructuredtext",
}

# MyST extensions we rely on in the pages.
myst_enable_extensions = [
    "colon_fence",   # ::: fenced directives
    "dollarmath",    # $...$ and $$...$$ math
    "deflist",       # definition lists
    "linkify",       # bare URLs become links
    "tasklist",      # - [ ] checkboxes
    "attrs_inline",
    "substitution",
]
myst_heading_anchors = 3  # auto-generate anchors for h1-h3

templates_path = ["_templates"]
exclude_patterns = [
    "_build",
    "Thumbs.db",
    ".DS_Store",
    "report",
    "*.docx",
    # Internal-only working notes, not part of the published documentation.
    "positioning.md",
    "core_refactor_scoping.md",
]

# -- Autodoc / autosummary ---------------------------------------------------

autosummary_generate = True
autodoc_typehints = "description"
autodoc_member_order = "bysource"
autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "show-inheritance": True,
}
# Optional/heavy third-party libraries that the API modules may reference.
# Mocking them keeps the docs build from needing a solver or plotting stack.
autodoc_mock_imports = [
    "pyaugmecon",
    "highspy",
    "matplotlib",
    "pycirclize",
    "PIL",
    "SALib",
]
napoleon_google_docstring = True
napoleon_numpy_docstring = True

# -- Intersphinx -------------------------------------------------------------

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "pandas": ("https://pandas.pydata.org/docs/", None),
    "numpy": ("https://numpy.org/doc/stable/", None),
}

# -- HTML output -------------------------------------------------------------

html_theme = "furo"
html_title = "BLEECAM Documentation"
html_static_path = ["_static"]

# Use the project logo if present in docs/img.
_logo = os.path.join(os.path.dirname(__file__), "img", "bleecam_logo.svg")
if os.path.exists(_logo):
    html_logo = "img/bleecam_logo.svg"

html_theme_options = {
    "source_repository": "https://github.com/NatLabRockies/bleecam/",
    "source_branch": "main",
    "source_directory": "docs/",
    "footer_icons": [
        {
            "name": "GitHub",
            "url": "https://github.com/NatLabRockies/bleecam",
            "html": "",
            "class": "fa-brands fa-github",
        },
    ],
}

# A short banner marking the docs as beta.
html_theme_options["announcement"] = (
    "BLEECAM is a public <strong>beta</strong> (v0.1.0-beta.1). "
    "APIs, data, and results may change between releases."
)
