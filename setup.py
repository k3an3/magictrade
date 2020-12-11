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
        'pylint',
        'pytest',
        'redis',
        'requests',
        'retry',
        'fast_arrow @ git+https://github.com/k3an3/fast_arrow@dev#egg=fast_arrow',
        'tdameritrade @ git+https://github.com/k3an3/tdameritrade@add-option-trades#egg=tdameritrade',
        'pytz',
        'scipy'
    ],
    entry_points={
        'console_scripts': [
            'magictrade-daemon=magictrade.runner:main',
            'magictrade-cli=magictrade.cli:cli',
            'robinhood-authenticator=magictrade.scripts.robinhood_authenticator:main',
            'optionalpha-toolbox=magictrade.scripts.optionalpha_toolbox:cli',
            'run-bollinger=magictrade.scripts.run_bollinger:init',
            'run-lin-slope=magictrade.scripts.run_lin_slope:init',
            'run-simplest-options=magictrade.scripts.run_simplest_options:init',
        ]
    }
)
