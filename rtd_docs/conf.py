# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# imports
import os, platform
from pathlib import Path

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

if list(map(int, platform.python_version_tuple()[:2])) < [3, 11]:
    import tomli as tomllib
else:
    import tomllib

pyproject_path = Path(__file__).parent.parent / "pyproject.toml"
print(f"pyproject_path = {pyproject_path}")
with pyproject_path.open("rb") as f:
    pyproject = tomllib.load(f)

release = pyproject["tool"]["poetry"]["version"]
project = f'shef-parser {release}'
copyright = 'No copyright. Developed by U.S. Government'
author = 'U.S. Army Corps of Engineers'
highlight_language = 'none' # prevents :: blocks from being highlighted

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx_design",
    "sphinx_copybutton",
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']



# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

on_rtd = os.environ.get("READTHEDOCS") == "True"
if not on_rtd:
    html_theme = "alabaster"  # fallback theme for local preview
else:
    html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]


