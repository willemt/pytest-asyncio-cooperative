#!/usr/bin/env python
# -*- coding: utf-8 -*-

import codecs
import os

from setuptools import find_packages, setup


def read(fname):
    file_path = os.path.join(os.path.dirname(__file__), fname)
    return codecs.open(file_path, encoding="utf-8").read()


setup(
    name="pytest-asyncio-cooperative",
    version="0.1.2",
    author="Willem Thiart",
    author_email="himself@willemthiart.com",
    maintainer="Willem Thiart",
    maintainer_email="himself@willemthiart.com",
    license="MIT",
    url="https://github.com/willemt/pytest-asyncio-cooperative",
    description="Run all your asynchronous tests cooperatively.",
    long_description=read("README.rst"),
    packages=find_packages(exclude=["tests", "docs"]),
    python_requires=">=3.7",
    install_requires=["pytest>=3.5.0"],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Framework :: Pytest",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Testing",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: Implementation :: CPython",
        "Programming Language :: Python :: Implementation :: PyPy",
        "Operating System :: OS Independent",
        "License :: OSI Approved :: MIT License",
    ],
    entry_points={"pytest11": ["asyncio-cooperative = pytest_asyncio_cooperative.plugin"]},
)
