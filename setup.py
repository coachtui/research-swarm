from setuptools import setup, find_packages

setup(
    name="research-swarm",
    version="0.1.0",
    author="Tui",
    description="Multi-agent AI system for researching supply chain bottlenecks",
    packages=find_packages(),
    install_requires=[
        line.strip()
        for line in open("requirements.txt")
        if line.strip() and not line.startswith("#")
    ],
    python_requires=">=3.9",
    entry_points={
        "console_scripts": [
            "research-swarm=research_swarm.__main__:main",
        ],
    },
)
