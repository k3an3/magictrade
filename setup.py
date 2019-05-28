from setuptools import setup, find_packages

setup(
    name='magictrade',
    version='0.1',
    packages=find_packages(),
    url='',
    license='',
    author="Keane O'Kelley",
    author_email='keane.m.okelley@gmail.com',
    description='',
    install_requires=[
        'matplotlib',
        'pytest',
        'redis',
        'scipy',
        'fast_arrow',
        'requests'
    ],
    dependency_links=[
        'https://github.com/k3an3/fast_arrow@dev#egg=fast_arrow'
    ],
    entry_points={
        'console_scripts': [
            'magictrade-daemon=magictrade.runner:main',
            'magictrade-cli=magictrade.cli:cli'
        ]
    }
)
