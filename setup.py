
from setuptools import setup, find_packages

setup(
    name="BlockedFrontend",
    version='2.0.0',
    description="A flask-based frontend for blocked.org.uk",
    url="https://www.blocked.org.uk",
    author="Daniel Ramsay",
    author_email="daniel@dretzq.org.uk",
    license="GPL",
    keywords="blocked censorship",
    packages=["BlockedFrontend"],
    install_requires=[
        'flask>=0.10',
        'requests>=2.9'
        ],
    zip_safe=False,
)
    
