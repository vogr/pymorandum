#!/usr/bin/env python3

import setuptools

setuptools.setup(
    name='pymorandum',
    package='pymorandum',
    license='MIT',
    install_requires=[
        'jinja2',
        'ninja_syntax',
    ],
    entry_points={
        'console_scripts': [
            'pymorandum=pymorandum:main',
        ],
    },
)

