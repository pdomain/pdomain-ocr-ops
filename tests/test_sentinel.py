import pd_ocr_ops


def test_pd_ocr_ops_imports():
    # Version is read from importlib.metadata; just assert it's a non-empty string
    assert isinstance(pd_ocr_ops.__version__, str)
    assert pd_ocr_ops.__version__
