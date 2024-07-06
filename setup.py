"""Package setup"""
# Standard Library Imports
import os
import sys
from pathlib import Path

# Third Party Imports
import setuptools

VERSION_TAG = "CI_COMMIT_TAG"
if VERSION_TAG not in os.environ:
    sys.stderr.write(f"The environment variable {VERSION_TAG} is not set!\n")

setuptools.setup(
    name="s3-syncer",
    version=os.environ.get(VERSION_TAG, "0.0.1"),
    packages=setuptools.find_packages(exclude="tests"),
    description="A tool for uploading and downloading objects from a s3 endpoint.",
    long_description="A script for uploading and downloading objects from a s3 bucket. Support for unix-like glob patterns for local files and prefix search on s3 keys.",
    url="https://github.com/Justinodactylus/s3-syncer",
    author="Justinodactylus",
    author_email="83211042+Justinodactylus@users.noreply.github.com",
    install_requires=[
        line.strip()
        for line
        in Path(Path(__file__).parent, "requirements.txt").read_text().splitlines()
        if line
    ],
    entry_points = {
        'console_scripts': ['s3-syncer=s3_syncer._s3_syncer:s3_syncer_cli'],
    },
    python_requires=">=3.9",
)
