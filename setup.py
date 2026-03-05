from setuptools import setup, find_packages

setup(
    name="debconf-translation-manager",
    version="0.4.0",
    packages=find_packages(),
    package_data={
        "debconf_translation_manager": [
            "data/*.desktop",
            "data/icons/hicolor/scalable/apps/*.svg",
            "locale/*/LC_MESSAGES/*.mo",
        ],
    },
    entry_points={
        "console_scripts": [
            "debconf-translation-manager=debconf_translation_manager.__main__:main",
        ],
    },
)
