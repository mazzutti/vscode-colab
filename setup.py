from setuptools import setup, find_packages

setup(
    name='vscode-colab',
    version='0.1.0',
    author='Your Name',
    author_email='your.email@example.com',
    description='A library to set up a VS Code server in Google Colab.',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    url='https://github.com/yourusername/vscode-colab',
    packages=find_packages(where='src'),
    package_dir={'': 'src'},
    install_requires=[
        'requests',  # Add any other dependencies your project requires
    ],
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.6',
)