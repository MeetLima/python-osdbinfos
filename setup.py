import os
from setuptools import setup, find_packages

__version__="0.0.5"

setup(
    name='osdbinfos',
    version=__version__,
    author='Jc Saad-Dupuy 2015',
    description='Identify videos files from opensubtitle webservice',
    long_description=open('README.md').read(),
    license="WTFPL",
    keywords="videos files opensubtitle",
    install_requires=open('requirements.txt').read(),

    package_dir={'': 'src'},
    packages=find_packages('src', exclude='docs'),
    entry_points={
        'console_scripts': [
                'osdbinfos-example = osdbinfos:main',
        ]
    },
)
