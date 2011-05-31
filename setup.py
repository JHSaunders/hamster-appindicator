from setuptools import setup, find_packages
setup(
    name= "hamster_appindicator",
    version = 0.1,
    packages=find_packages(),
    entry_points="""
        [console_scripts]
        hamster-indicator = hamster_appindicator.hamster_indicator:start_indicator
    """
)
