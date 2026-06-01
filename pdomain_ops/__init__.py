"""pdomain-ops: Suite plumbing and GPU dispatch adapters for the pdomain-* suite."""

from importlib.metadata import version

__version__ = version("pdomain-ops")

from pdomain_ops.pages import (
    DeadBranch,
    PageChangeEntry,
    PagePayload,
    PageRecord,
    ProjectRecord,
    ProvenanceGraph,
    ProvenanceNode,
    RotationSource,
    build_provenance_summary,
    get_extension,
    set_extension,
)
from pdomain_ops.suite.routes import mount_routes
from pdomain_ops.suite.types import SuiteAdapters

__all__ = [
    "DeadBranch",
    "PageChangeEntry",
    "PagePayload",
    "PageRecord",
    "ProjectRecord",
    "ProvenanceGraph",
    "ProvenanceNode",
    "RotationSource",
    "SuiteAdapters",
    "__version__",
    "build_provenance_summary",
    "get_extension",
    "mount_routes",
    "set_extension",
]
