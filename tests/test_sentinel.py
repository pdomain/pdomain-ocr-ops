import pdomain_ocr_ops


def test_pdomain_ocr_ops_imports():
    # Version is read from importlib.metadata; just assert it's a non-empty string
    assert isinstance(pdomain_ocr_ops.__version__, str)
    assert pdomain_ocr_ops.__version__
