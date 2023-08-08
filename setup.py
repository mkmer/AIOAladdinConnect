from setuptools import setup

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="AIOAladdinConnect",
    version="0.1.57",
    author="Mike Kasper",
    author_email="m_kasper@sbcglobal.net",
    url="http://github.com/mkmer/AIOAladdinConnect",
    download_url="https://github.com/mkmer/AIOAladdinConnect/archive/refs/tags/0.1.57.tar.gz",
    packages=["AIOAladdinConnect"],
    scripts=[],
    description="Python Async API for controlling Genie garage doors connected to Aladdin Connect devices",
    license="MIT",
    long_description=long_description,
    long_description_content_type="text/markdown",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
    ],
    install_requires=["aiohttp"],
    include_package_data=True,
)
