import setuptools

setuptools.setup(
    name="pyBela",
    version="0.0.0",  # Update with your package version
    author="Teresa Pelinski",
    author_email="teresapelinski@gmail.com",
    description="pyBela",
    long_description="pyBela",
    long_description_content_type="text/markdown",
    url="https://github.com/BelaPlatform/pyBela",
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
    python_requires=">=3.10",
)
