import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QApplication

from igris_os.ui.galaxia import GalaxiaWidget


def test_hologram_is_dense_and_animates_at_idle():
    app = QApplication.instance() or QApplication([])
    widget = GalaxiaWidget()
    try:
        assert len(widget._rings) >= 15
        assert len(widget._core) >= 150
        assert len(widget._data_pts) >= 100
        assert widget._timer.isActive()
        assert any(ring.get("dashed") for ring in widget._rings)
    finally:
        widget.detach()
