"""Suite plumbing: registry, prefs, launcher, auth, storage, routes."""

from pdomain_ocr_ops.suite.register_self import register_self
from pdomain_ocr_ops.suite.types import (
    CommonUIPrefs,
    InstalledApp,
    LayerColors,
    SuiteAdapters,
    SuiteApp,
    UIPrefs,
)

__all__ = [
    "CommonUIPrefs",
    "InstalledApp",
    "LayerColors",
    "SuiteAdapters",
    "SuiteApp",
    "UIPrefs",
    "register_self",
]
