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
    ],
    dependency_links=[
        'https://github.com/KloudTrader/paperbroker#egg=paperbroker',
        'https://github.com/westonplatter/fast_arrow#egg=fast_arrow'
    ],
)
