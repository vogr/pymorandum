#!/usr/bin/env python3

import setuptools

setuptools.setup(
    name='pymorandum',
    package='pymorandum',
    license='MIT',
    install_requires=[
        'jinja2',
        'natsort',
        'ninja_syntax',
        'python-slugify',
    ],
    entry_points={
        'console_scripts': [
            'pymorandum=pymorandum:main',
        ],
    },
)

