import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtWidgets import QApplication

from igris_os.domain import ActionRisk, CapabilitySpec
from igris_os.ui.galaxia import GalaxiaWidget


@pytest.fixture(scope="module")
def app():
    app = QApplication.instance() or QApplication([])
    yield app


def test_galaxy_tracks_real_capability_states(app):
    widget = GalaxiaWidget()
    try:
        specs = [
            CapabilitySpec("programming.python.develop",
                           "Genera y prueba Python",
                           ActionRisk.WRITE_WORKSPACE),
            CapabilitySpec("system.health", "Diagnóstico local",
                           ActionRisk.READ_ONLY),
        ]
        widget.set_capabilities(specs)
        assert widget.state_of("programming.python.develop") == "pending"
        assert widget.state_of("system.health") == "pending"

        widget.set_active("programming.python.develop")
        assert widget.state_of("programming.python.develop") == "working"

        widget.set_result("programming.python.develop", True)
        assert widget.state_of("programming.python.develop") == "ok"

        widget.set_result("system.health", False)
        assert widget.state_of("system.health") == "error"

        widget.reset_states()
        assert widget.state_of("programming.python.develop") == "pending"
        assert widget.state_of("system.health") == "pending"
    finally:
        widget.detach()


def test_galaxy_node_signal_carries_real_metadata(app):
    widget = GalaxiaWidget()
    try:
        received = []
        widget.nodeActivated.connect(
            lambda name, description, risk, state:
            received.append((name, description, risk, state)))
        specs = [CapabilitySpec("system.health", "Diagnóstico local",
                                ActionRisk.READ_ONLY)]
        widget.set_capabilities(specs)
        widget.nodeActivated.emit(
            "system.health", "Diagnóstico local", "read_only", "pending")
        assert received == [
            ("system.health", "Diagnóstico local", "read_only", "pending")]
    finally:
        widget.detach()


def test_capture_widget_detects_blank_frame(app):
    from PyQt6.QtGui import QColor, QPixmap
    from igris_os.multimedia import VisualVerifier

    class FakeWidget:
        def grab(self):
            pixmap = QPixmap(40, 30)
            pixmap.fill(QColor(0, 0, 0))
            return pixmap

    check = VisualVerifier().capture_widget(FakeWidget())
    assert not check.ok
    assert check.blank
