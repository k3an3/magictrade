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
        'requests',
        'tdameritrade'
    ],
    dependency_links=[
        'https://github.com/k3an3/fast_arrow@dev#egg=fast_arrow'
        'https://github.com/k3an3/tdameritrade@add-option-trades#egg=tdameritrade'
    ],
    entry_points={
        'console_scripts': [
            'magictrade-daemon=magictrade.runner:main',
            'magictrade-cli=magictrade.cli:cli'
        ]
    }
)
