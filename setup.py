#!/usr/bin/env python3

import setuptools

setuptools.setup(
    name='pymorandum',
    package='pymorandum',
    license='MIT',
    entry_points={
        'console_scripts': [
            'pymorandum=pymorandum:main',
        ],
    },
)

