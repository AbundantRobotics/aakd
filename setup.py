import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="aakd",
    version="1.0",
    author="Leonard Gerard",
    author_email="leonard@abundantrobotics.com",
    description="Python tools and library to communicate with Kollmorgen akd drives",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/AbundantRobotics/aakd",
    packages=setuptools.find_packages(),
    install_requires=[
        "argcomplete",
        "pyyaml",
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
    ],
    entry_points={
        'console_scripts': [
            'aakd = aakd.aakd_command:main',
        ],
    }
)
