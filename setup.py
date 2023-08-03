import setuptools
import os
import json


# Load the dependencies from Pipfile.lock
pipfile_lock_path = os.path.join(os.path.dirname(__file__), 'Pipfile.lock')
with open(pipfile_lock_path, 'r') as lockfile:
    pipfile_lock_data = json.load(lockfile)

# Extract the dependencies from 'default' section
install_requires = []
if 'default' in pipfile_lock_data.get('dependencies', {}):
    install_requires = list(pipfile_lock_data['dependencies']['default'])


setuptools.setup(
    name="pyBela",
    version="0.1.0",  # Update with your package version
    author="Teresa Pelinski",
    author_email="teresapelinski@gmail.com",
    description="pyBela",
    long_description="pyBela",
    long_description_content_type="text/markdown",
    url="https://github.com/BelaPlatform/pyBela",
    packages=setuptools.find_packages(),
    install_requires=install_requires,
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.10",
)
