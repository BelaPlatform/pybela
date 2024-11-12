import setuptools
from pathlib import Path

long_description = open(f"{Path(__file__).parent}/readme.md").read()


def load_requirements(filename):
    with open(filename, 'r') as file:
        return file.read().splitlines()


requirements = load_requirements('requirements.txt')

setuptools.setup(
    name="pybela",
    version="1.0.1",
    author="Teresa Pelinski",
    author_email="teresapelinski@gmail.com",
    description="pybela allows interfacing with Bela, the embedded audio platform, using python. It offers a convenient way to stream data between Bela and python, in both directions. In addition to data streaming, pybela supports data logging, as well as variable monitoring and control functionalities.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/BelaPlatform/pybela",
    packages=setuptools.find_packages(),
    install_requires=requirements,
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.9",
)
