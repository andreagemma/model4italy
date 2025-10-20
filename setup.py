from setuptools import setup, find_packages

setup(
    name="m4i",
    version="0.1.0",
    author="Andrea Gemma",
    author_email="andrea.gemma@uniroma3.it.com",
    description="Modello di simulazione mesoscopico per l'analisi di sistemi di trasporto - Model4Italy",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    #url="https://github.com/tuo_username/pyrobot",  # Se pubblico su GitHub
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "numpy>=2.2.5",
        "shapely>=2.1.0",
        "scipy>=1.15.3",
        "dask>=2025.4.1",
        "pandas>=2.2.3",
        "openpyxl>=3.1.5",
        "frozenlist>=1.6.0",
        "jsonpickle>=4.0.1",
        "distributed>=2025.04.1",
        "geopandas>=1.0.1",
        "geoalchemy2>=0.17.1",
        "ray>=2.46.0",
        "dill>=0.4.0",
        "sqlalchemy>=2.0.40",
        "flask>=3.1.0",
        "gunicorn>=23.0.0",
        "psycopg2>=2.9.10",
        "psycopg2-binary>=2.9.10",
        "pyarrow>=20.0.0",
        "psycopg>=3.2.3",
        "psycopg-binary>=3.2.3",
        "fiona>=1.10.1",
        "blosc>=1.11.2",
        "pyproj>=3.7.1",
        "polars>=1.30.0",
        "websockets>=15.0.1",
        "redis>=6.1.0",
        "duckdb>=1.4.0"
    ],
    python_requires=">=3.10",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    entry_points={
        "console_scripts": [  ]
    },
)
