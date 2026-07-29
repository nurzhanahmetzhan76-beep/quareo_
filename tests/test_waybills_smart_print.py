"""Focused unit tests for Smart Print's archive identity and filtering rules."""

import sys
import types

# This unit suite does not open PDFs.  PyMuPDF is optional in the lightweight
# test virtualenv, so provide its import name while testing the pure helpers.
sys.modules.setdefault("fitz", types.SimpleNamespace())

from retailpool.routers.waybills import _split_new_waybills, extract_waybill_identifier


def _waybill(identifier: str) -> dict:
    return {"waybill_id": identifier}


def test_uses_order_number_from_filename_as_stable_identifier():
    assert extract_waybill_identifier("Kaspi/order_1001.pdf", b"not a pdf") == "order:1001"
    assert extract_waybill_identifier("waybill-1002-copy.pdf", b"not a pdf") == "order:1002"


def test_unlabelled_filename_falls_back_to_a_content_identifier():
    identifier = extract_waybill_identifier("label.pdf", b"same-label-bytes")
    assert identifier.startswith("content:")
    assert identifier == extract_waybill_identifier("renamed.pdf", b"same-label-bytes")


def test_filters_previously_processed_and_duplicate_waybills_before_merging():
    files = [_waybill("order:1001"), _waybill("order:1002"), _waybill("order:1002"), _waybill("order:1003")]

    new_files, already_processed = _split_new_waybills(files, {"order:1001"})

    assert [item["waybill_id"] for item in new_files] == ["order:1002", "order:1003"]
    assert already_processed == 2
