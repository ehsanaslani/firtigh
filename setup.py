from setuptools import setup, find_packages

setup(
    name="firtigh-bot",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "python-telegram-bot==20.3",
        "openai==0.28.0",
        "python-dotenv==1.0.0",
    ],
) 