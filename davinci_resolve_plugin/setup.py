"""Setup script for DaVinci Resolve Media Lake Plugin."""

from setuptools import setup, find_packages
import os

# Read version from version.py
version = {}
with open(os.path.join("medialake_resolve", "core", "version.py")) as f:
    exec(f.read(), version)

# Read requirements
with open("requirements.txt") as f:
    requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]

# Read README
with open("README.md", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="medialake-resolve-plugin",
    version=version["__version__"],
    author="Media Lake Team",
    author_email="medialake@example.com",
    description="DaVinci Resolve plugin for Media Lake asset management",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/aws-solutions-library-samples/guidance-for-medialake-on-aws",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Multimedia :: Video :: Non-Linear Editor",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.10",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "medialake-resolve=medialake_resolve.__main__:main",
        ],
    },
    include_package_data=True,
    package_data={
        "medialake_resolve": [
            "resources/icons/*.png",
            "resources/icons/*.svg",
            "resources/styles/*.qss",
            "ffmpeg/bin/*",
        ],
    },
)
