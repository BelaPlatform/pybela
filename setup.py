import setuptools
from pathlib import Path

long_description = open(f"{Path(__file__).parent}/readme.md").read()

setuptools.setup(
    name="pybela",
    version="0.0.1",
    author="Teresa Pelinski",
    author_email="teresapelinski@gmail.com",
    description="pybela allows interfacing with Bela, the embedded audio platform, using Python. pybela provides a convenient way to stream, log, and monitor sensor data from Bela to the host machine.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/BelaPlatform/pybela",
    packages=setuptools.find_packages(),
    install_requires=[
        "jupyter",
        "panel",
        "jupyter-bokeh",
        "bitarray",
        "notebook",
        "websockets",
        "bokeh",
        "ipykernel",
        "nest-asyncio",
        "aiofiles",
        "paramiko"],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.9",
)
