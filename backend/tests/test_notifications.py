"""Unit tests for app.notifications."""

from __future__ import annotations

import json
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

from app.notifications import notify_scan_complete, send_webhook


# ── send_webhook ─────────────────────────────────────────────────────────────


def _make_response(status: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status = status
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


def test_send_webhook_success():
    """send_webhook posts JSON and does not raise on success."""
    with patch("urllib.request.urlopen", return_value=_make_response(200)) as mock_open:
        send_webhook("https://example.com/hook", {"event": "test"})
    mock_open.assert_called_once()
    req = mock_open.call_args[0][0]
    assert req.full_url == "https://example.com/hook"
    assert req.get_header("Content-type") == "application/json"
    assert json.loads(req.data) == {"event": "test"}


def test_send_webhook_url_error_does_not_raise():
    """send_webhook swallows URLError and does not propagate."""
    import urllib.error

    with patch(
        "urllib.request.urlopen",
        side_effect=urllib.error.URLError("timeout"),
    ):
        send_webhook("https://example.com/hook", {"event": "test"})  # must not raise


def test_send_webhook_unexpected_error_does_not_raise():
    """send_webhook swallows unexpected exceptions."""
    with patch("urllib.request.urlopen", side_effect=RuntimeError("boom")):
        send_webhook("https://example.com/hook", {"event": "test"})  # must not raise


# ── notify_scan_complete ──────────────────────────────────────────────────────


def _make_db(webhook_url: str | None = "https://example.com/hook") -> MagicMock:
    """Return a mock DB session that satisfies get_webhook_url()."""
    db = MagicMock()
    setting_row = MagicMock()
    setting_row.value = webhook_url
    result = MagicMock()
    result.scalar_one_or_none.return_value = setting_row if webhook_url else None
    db.execute.return_value = result
    return db


def test_notify_scan_complete_no_url_skips():
    """Skips notification when no webhook URL is configured."""
    db = _make_db(webhook_url=None)
    with patch("app.notifications.send_webhook") as mock_send:
        notify_scan_complete(db, scan_id=1, new_device_ids=[], risk_counts={"critical": 1})
    mock_send.assert_not_called()


def test_notify_scan_complete_nothing_to_report_skips():
    """Skips notification when no new devices and no critical risks."""
    db = _make_db()
    with patch("app.notifications.send_webhook") as mock_send:
        notify_scan_complete(
            db, scan_id=1, new_device_ids=[], risk_counts={"high": 2, "critical": 0}
        )
    mock_send.assert_not_called()


def test_notify_scan_complete_fires_for_new_devices():
    """Fires when new devices are present."""
    db = _make_db()
    # Mock Device query
    dev = MagicMock()
    dev.ip_address = "192.168.1.50"
    dev.hostname = "newbox"
    dev.mac_address = "aa:bb:cc:dd:ee:ff"
    dev.vendor = "Acme"
    scalars_result = MagicMock()
    scalars_result.all.return_value = [dev]
    execute_result_for_devices = MagicMock()
    execute_result_for_devices.scalars.return_value = scalars_result

    setting_row = MagicMock()
    setting_row.value = "https://example.com/hook"
    setting_result = MagicMock()
    setting_result.scalar_one_or_none.return_value = setting_row

    db.execute.side_effect = [setting_result, execute_result_for_devices]

    with patch("app.notifications.send_webhook") as mock_send:
        notify_scan_complete(db, scan_id=5, new_device_ids=[42], risk_counts={"critical": 0})

    mock_send.assert_called_once()
    payload = mock_send.call_args[0][1]
    assert payload["event"] == "scan_complete"
    assert len(payload["new_devices"]) == 1
    assert payload["new_devices"][0]["ip"] == "192.168.1.50"


def test_notify_scan_complete_fires_for_critical_risks():
    """Fires when critical risks are present (no new devices needed)."""
    db = _make_db()
    setting_row = MagicMock()
    setting_row.value = "https://example.com/hook"
    setting_result = MagicMock()
    setting_result.scalar_one_or_none.return_value = setting_row
    db.execute.return_value = setting_result

    with patch("app.notifications.send_webhook") as mock_send:
        notify_scan_complete(
            db, scan_id=7, new_device_ids=[], risk_counts={"critical": 3, "high": 1}
        )

    mock_send.assert_called_once()
    payload = mock_send.call_args[0][1]
    assert payload["risk_counts"]["critical"] == 3
    assert "critical risk" in payload["summary"]
