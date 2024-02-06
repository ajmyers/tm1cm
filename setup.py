from setuptools import setup, find_packages
import pathlib

here = pathlib.Path(__file__).parent.resolve()

long_description = (here / "README.md").read_text(encoding="utf-8")

VERSION = "0.9.5"

setup(
    name="tm1cm",
    version=VERSION,
    description="A model migration library for TM1 Planning Analytics",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/ajmyers/tm1cm",
    author="Andrew Myers",
    author_email="me@ajmyers.net",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Build Tools",
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3 :: Only",
    ],
    keywords="tm1, planning analytics, ibm, pa, olap, cube",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    python_requires=">=3.7, <4",
    install_requires=[
        "TM1py>=1.2.1,<=1.11.3",
        "gitdb2==2.0.5",
        "GitPython==2.1.11",
        "termcolor==1.1.0",
        "ntplib==0.3.4",
        "pyyaml==6.0",
    ],
    entry_points={
        'console_scripts': ['tm1cm=tm1cm.__main__:main'],
    },
    project_urls={
        "Bug Reports": "https://github.com/ajmyers/tm1cm/issues",
        "Source": "https://github.com/ajmyers/tm1cm",
    },
    include_package_data=True
)
