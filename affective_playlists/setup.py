"""
Setup script for affective_playlists.

Installs the package and creates a CLI command that can be run from anywhere.
Usage: pip install -e .
Then: affective-playlists or affective_playlists from any directory
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="affective-playlists",
    version="1.0.0",
    author="Joel Debeljak",
    description="Unified music analysis and organization tool",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/jodcodes/affective_playlists",
    packages=find_packages(include=["src", "src.*"]),
    package_dir={"": "."},
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License",
        "Operating System :: MacOS",
    ],
    python_requires=">=3.10",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "affective-playlists=main:main",
            "affective_playlists=main:main",
        ],
    },
    include_package_data=True,
)
