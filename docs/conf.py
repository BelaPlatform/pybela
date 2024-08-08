# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

import os
import sys
import re
sys.path.insert(0, os.path.abspath('../pybela'))

author = 'Teresa Pelinski'
copyright = '2024'
def get_version_from_setup_py():
    version_pattern = re.compile(r"version=['\"]([^'\"]+)['\"]")
    with open('../setup.py', 'r') as f:
        setup_py_content = f.read()
    match = version_pattern.search(setup_py_content)
    if match:
        return match.group(1)
    raise RuntimeError("Unable to find version string in setup.py")

release = get_version_from_setup_py()
project = f'pybela {release}'

# -- General configuration ---------------------------------------------------
extensions = [
    'sphinx.ext.napoleon', 'sphinx.ext.viewcode', 'sphinx_rtd_theme']
templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store', '../pybela/utils.py']


# -- Options for HTML output -------------------------------------------------
html_theme = 'sphinx_rtd_theme'
html_css_files = [
    'custom.css',
]
html_static_path = ['_static']
html_css_files = ['custom.css']
html_show_sphinx = False
html_show_sourcelink = False
html_sidebars = {
    '**': ['globaltoc.html', 'searchbox.html']
}
html_theme_options = {
    'collapse_navigation': False,
    'sticky_navigation': True,
    'navigation_depth': 4,
    'titles_only': False,
    'display_version': True,
    'prev_next_buttons_location': 'None',
}

# remove title from readme file to avoid duplication
file_path = 'readme.rst'

with open(file_path, 'r+') as file:
    lines = file.readlines()[2:]  # Read lines and skip the first two
    file.seek(0)  # Move the cursor to the beginning of the file
    file.writelines(lines)  # Write the modified lines
    file.truncate()  # Truncate the file to the new size
