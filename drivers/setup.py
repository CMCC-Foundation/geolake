import setuptools

with open("README.md", "r") as f:
    long_description = f.read()

setuptools.setup(
    name="intake-geokube",
    version="0.1a0",
    author="CMCC Foundation - PPOS Research Group",
    author_email="ppos-services@cmcc.it",
    description="Geokube driver for Intake.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/geokube/intake-geokube",
    packages=setuptools.find_packages(),
    install_requires=["intake", "pytest", "pydantic<2.0.0"],
    entry_points={
        "intake.drivers": [
            "geokube_netcdf = intake_geokube.netcdf:NetCDFSource",
            "cmcc_wrf_geokube = intake_geokube.wrf:CMCCWRFSource",
            "cmcc_sentinel_geokube = intake_geokube.sentinel:CMCCSentinelSource"
        ]
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Environment :: Web Environment",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: Apache Software License",
        "Natural Language :: English",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Topic :: Scientific/Engineering :: Atmospheric Science",
    ],
    python_requires=">=3.8",
    license="Apache License, Version 2.0",
)
