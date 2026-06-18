"""Prevent pytest from treating couple-finance/ as a test collection target."""


def pytest_ignore_collect(collection_path, config, **kwargs):
    """Skip the hyphenated package directory itself during collection."""
    if collection_path.is_dir() and "-" in str(collection_path.name):
        return True
    return False
