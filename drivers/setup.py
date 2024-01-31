import setuptools

with open("README.md", "r") as f:
    long_description = f.read()

setuptools.setup(
    name="geolake-drivers",
    version="0.1.0b0",
    author="geolake Contributors",
    author_email="geolake@googlegroups.com",
    description="intake-based drivers for geolake",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/CMCC-Foundation/geolake/drivers",
    packages=setuptools.find_packages(),
    install_requires=["intake", "pytest", "pydantic<2.0.0"],
    entry_points={
        "intake.drivers": [
            "netcdf = geolake_drivers.netcdf:NetCDFSource",
            "wrf = geolake_drivers.wrf:WRFSource",
            "sentinel = geolake_drivers.sentinel:SentinelSource"
        ]
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Environment :: Web Environment",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: Apache Software License",
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Topic :: Scientific/Engineering",
    ],
    python_requires=">=3.8",
    license="Apache License, Version 2.0",
)
