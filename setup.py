from setuptools import setup, find_packages
from curses_components  import __version__

with open("requirements.md", "r") as f:
    long_description = f.read()

setup(
    name='curses_components',
    version=str(__version__),
    author='Cobus Nel',
    author_email='cobus@nel.org.za',
    description='A reusable curses component for displaying tabular data in a TUI.',
    long_description=long_description,
    long_description_content_type='text/markdown',
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
    install_requires=['pyperclip'],
)
