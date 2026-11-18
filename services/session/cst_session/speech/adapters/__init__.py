"""Vendor adapters for the speech interface.

This is the only package that may import a vendor speech SDK
(``tests/test_speech_import_boundary.py`` enforces it). Each adapter must pass
the contract suite in ``tests/speech_contract.py``. The vendor is chosen in #20.
"""
