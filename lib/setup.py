from setuptools import setup, find_packages

setup(
    name='perfectstorm-lib',
    version='0.1',
    packages=find_packages(),
    install_requires=[
        'requests >= 2.13, < 3',
    ],
)
