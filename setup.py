import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="aakd",
    version="1.0",
    author="Leonard Gerard",
    author_email="leonard@abundantrobotics.com",
    description="A python library and tool to communicate with kollmorgen akd drives",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/AbundantRobotics/aakd",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    entry_points={
        'console_scripts': [
            'aakd = aakd.aakd_command:main',
        ],
    }
)
