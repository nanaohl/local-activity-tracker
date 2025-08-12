
from setuptools import setup

setup(
    name="activity-tracker",
    version="0.1.0",
    packages=['src'],
    package_dir={'src': 'src'},
    include_package_data=True,
    install_requires=[
        "pyobjc-core",
        "tabulate",
    ],
    entry_points={
        "console_scripts": [
            "activity=src.main:main",
        ],
    },
    author="Your Name",  # Replace with your name
    author_email="your.email@example.com",  # Replace with your email
    description="A CLI application to track application usage and display summaries.",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/activity-tracker",  # Replace with your repo URL
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: MacOS :: MacOS X",
    ],
    python_requires=">=3.7",
)
