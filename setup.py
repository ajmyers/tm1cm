import pathlib

from setuptools import find_namespace_packages
from setuptools import setup

here = pathlib.Path(__file__).parent.resolve()

long_description = (here / "README.md").read_text(encoding="utf-8")

setup(
    name="tm1cm",
    description="A model migration library for TM1 Planning Analytics",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://skipcheck.io/tm1cm/",
    author="Andrew Myers",
    author_email="me@ajmyers.net",
    license="GPL-3.0-or-later",
    license_files=["LICENSE"],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Build Tools",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: 3.14",
        "Programming Language :: Python :: 3 :: Only",
    ],
    keywords="tm1, planning analytics, ibm, pa, olap, cube",
    package_dir={"": "src"},
    # Namespace packages too: tm1cm/include (the scaffold's files) has no __init__.py
    packages=find_namespace_packages(where="src"),
    python_requires=">=3.11, <4",
    install_requires=[
        "skipcheck-tm1>=0.1.1,<1",
        # The login probes of TM1 and Cognos (tm1cm.discovery); skipcheck-tm1's own HTTP client
        "httpx2>=2.16,<3",
        "GitPython>=3.1.41,<4",
        "termcolor>=2,<4",
        "pyyaml>=6.0.1,<7",
        "filetype>=1.2,<2",
    ],
    extras_require={
        "test": [
            "pytest>=8,<10",
            "pytest-cov>=6,<8",
            "flake8>=7,<9",
            # Runs TM1 in Docker for the integration tests; skips them without a TM1 source
            "skipcheck-tm1-testcontainers>=0.1.1,<1",
        ],
    },
    entry_points={
        'console_scripts': ['tm1cm=tm1cm.__main__:start'],
    },
    project_urls={
        "Homepage": "https://skipcheck.io/tm1cm/",
        "Documentation": "https://skipcheck.io/tm1cm/docs/",
        "Bug Reports": "https://github.com/ajmyers/tm1cm/issues",
        "Source": "https://github.com/ajmyers/tm1cm",
    },
    include_package_data=True,
)
