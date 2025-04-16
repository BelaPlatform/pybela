# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

import os
import sys
import toml

sys.path.insert(0, os.path.abspath('../pybela'))

author = 'Teresa Pelinski'
copyright = '2025'

def get_version_from_pyproject_toml():
    with open('../pyproject.toml', 'r') as f:
        pyproject_data = toml.load(f)
        print(pyproject_data)
    return pyproject_data['project']['version']

release = get_version_from_pyproject_toml()
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
