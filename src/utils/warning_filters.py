import warnings
import logging
from functools import wraps


def setup_warning_filters():
    """Configure global warning filters and logging levels that just pollute the output"""
    # Completely disable all warnings
    warnings.simplefilter("ignore")

    # Set all loggers to ERROR level
    logging.getLogger().setLevel(logging.ERROR)
    for logger_name in logging.root.manager.loggerDict:
        logging.getLogger(logger_name).setLevel(logging.ERROR)

    # Specific filters for extra safety
    warnings.filterwarnings("ignore", category=DeprecationWarning)
    warnings.filterwarnings("ignore", category=UserWarning)
    warnings.filterwarnings("ignore", category=FutureWarning)

    # Module-specific filters
    modules = [
        "defusedxml",
        "h5py",
        "ctranslate2",
        "pkg_resources",
        "docling_core",
        "websockets",
        "uvicorn",
        "google",
    ]

    for module in modules:
        warnings.filterwarnings("ignore", module=module)


def suppress_warnings(func):
    """Decorator to suppress warnings in specific functions"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            return func(*args, **kwargs)

    return wrapper
