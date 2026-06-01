def test_top_level_exports_present():
    from pdomain_ops import SuiteAdapters, mount_routes
    from pdomain_ops.gpu import LongJobRunner, StageDispatcher, pick_device
    from pdomain_ops.suite import InstalledApp, SuiteApp, UIPrefs

    assert mount_routes is not None
    assert SuiteAdapters is not None
    assert SuiteApp is not None
    assert InstalledApp is not None
    assert UIPrefs is not None
    assert StageDispatcher is not None
    assert LongJobRunner is not None
    assert pick_device is not None


def test_universal_pages_surface_is_top_level_importable() -> None:
    from pdomain_ops import (
        PageChangeEntry,
        PagePayload,
        PageRecord,
        ProjectRecord,
        ProvenanceGraph,
        ProvenanceNode,
        RotationSource,
        build_provenance_summary,
    )

    assert PageRecord.__name__ == "PageRecord"
    assert RotationSource.AUTO == "auto"
    assert callable(build_provenance_summary)
    _ = (PageChangeEntry, PagePayload, ProjectRecord, ProvenanceGraph, ProvenanceNode)


def test_lifecycle_modules_are_not_top_level_exports() -> None:
    import pdomain_ops

    assert "BlobStore" not in pdomain_ops.__all__
    assert "PageAggregate" not in pdomain_ops.__all__
