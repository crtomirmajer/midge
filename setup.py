from setuptools import find_packages, setup

setup(
    name='midge',
    author='crtomirmajer',
    version='0.1.0',
    long_description='',
    python_requires='>3.5.2',
    packages=find_packages(exclude=[]),
    py_modules=['midge'],
    entry_points={
        'console_scripts': [
            'midge = midge.cli:midgectl',
        ]
    },
    install_requires=[
        'asyncio',
        'click',
        'numpy',
        'dataclass-marshal==0.1.0'
    ],
    extras_require={
        'unit-tests': [
            'pytest==3.6.4',
            'pytest-asyncio==0.9.0',
        ]
    },
    include_package_data=True,
    dependency_links=[
        'git+ssh://git@github.com/crtomirmajer/dataclass-marshal.git@0.1.0#egg=dataclass-marshal-0.1.0',
    ],
)
