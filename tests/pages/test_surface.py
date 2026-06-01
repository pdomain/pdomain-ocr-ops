def test_pages_package_reexports_universal_surface() -> None:
    from pdomain_ops import pages

    expected = {
        "DeadBranch",
        "PageChangeEntry",
        "PagePayload",
        "PageRecord",
        "ProjectRecord",
        "ProvenanceGraph",
        "ProvenanceNode",
        "RotationSource",
        "build_provenance_summary",
    }
    assert expected <= set(pages.__all__)
    for name in pages.__all__:
        assert hasattr(pages, name), name
