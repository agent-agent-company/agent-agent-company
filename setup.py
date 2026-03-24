"""
AAC Protocol - Agent-Agent Company Protocol
"""
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="aac-protocol",
    version="0.1.0",
    author="AAC Protocol Team",
    author_email="",
    description="Agent-Agent Company Protocol - A decentralized agent marketplace protocol",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/AAC-Protocol/aac-protocol",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.10",
    install_requires=[
        "fastapi>=0.110.0",
        "uvicorn[standard]>=0.27.0",
        "pydantic>=2.6.0",
        "pydantic-settings>=2.1.0",
        "sqlalchemy>=2.0.25",
        "aiosqlite>=0.19.0",
        "anyio>=4.2.0",
        "click>=8.1.0",
        "rich>=13.7.0",
        "python-dateutil>=2.8.0",
    ],
    extras_require={
        "dev": [
            "pytest>=8.0.0",
            "pytest-asyncio>=0.23.0",
            "httpx>=0.26.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "aac-creator=aac_protocol.creator.cli.main:main",
            "aac-user=aac_protocol.user.cli.main:main",
        ],
    },
)
