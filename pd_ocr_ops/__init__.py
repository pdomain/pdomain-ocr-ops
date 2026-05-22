"""pd-ocr-ops: Suite plumbing and GPU dispatch adapters for the pd-* OCR suite."""

from importlib.metadata import version

__version__ = version("pd-ocr-ops")

from pd_ocr_ops.suite.routes import mount_routes
from pd_ocr_ops.suite.types import SuiteAdapters

__all__ = [
    "SuiteAdapters",
    "__version__",
    "mount_routes",
]
