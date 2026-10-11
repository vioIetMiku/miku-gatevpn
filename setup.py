#!/usr/bin/env python3
from setuptools import setup, find_packages

setup(
    name='miku-gatevpn',
    version='1.0.0',
    description='VPN Gate proxy pool management system with network namespace isolation',
    author='VioletMiku',
    author_email='',
    url='https://github.com/vioIetMiku/miku-gatevpn',
    packages=find_packages(),
    install_requires=[
        'flask>=2.0.0',
        'requests>=2.28.0',
    ],
    entry_points={
        'console_scripts': [
            'miku=miku.cli:cli',
        ],
    },
    python_requires='>=3.8',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
    ],
)
