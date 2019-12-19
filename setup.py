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
        'py-expression-eval',
        'pytest',
        'redis',
        'requests',
        'scipy',
        'fast_arrow @ git+https://github.com/k3an3/fast_arrow@dev#egg=fast_arrow',
        'tdameritrade @ git+https://github.com/k3an3/tdameritrade@add-option-trades#egg=tdameritrade', 'pytz'
    ],
    entry_points={
        'console_scripts': [
            'magictrade-daemon=magictrade.runner:main',
            'magictrade-cli=magictrade.cli:cli'
        ]
    }
)
