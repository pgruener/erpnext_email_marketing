from setuptools import setup, find_packages

with open("requirements.txt") as f:
	install_requires = f.read().strip().split("\n")

# get version from __version__ variable in email_marketing/__init__.py
from email_marketing import __version__ as version

setup(
	name="email_marketing",
	version=version,
	description="Email Marketing",
	author="RS",
	author_email="beratung@royal-software.de",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)
