from setuptools import setup, find_packages

setup(
    name="s3-cleanup",
    version="1.0.0",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[
        "boto3>=1.26.0",
    ],
    entry_points={
        "console_scripts": [
            "s3-cleanup=s3_cleanup.main:main",
        ],
    },
)
