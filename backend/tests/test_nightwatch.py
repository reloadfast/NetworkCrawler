"""Tests for nightwatch module (daily digest system)."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_db import in_memory_engine

import pytest
from test_db import session as test_db_session


class TestDecryptUtils:
    """Tests for decrypt_utils.py."""

    @pytest.fixture(autouse=True)
    def _setup(self, monkeypatch):
        monkeypatch.setenv("APP_SECRET_KEY", "test-secret-key-nightwatch")

    def test_encrypt_decrypt_roundtrip(self):
        from app.nightwatch.decrypt_utils import decrypt_api_key, encrypt_api_key

        plaintext = "sk-test-api-key-12345"
        encrypted = encrypt_api_key(plaintext)
        decrypted = decrypt_api_key(encrypted)
        assert decrypted == plaintext

    def test_encrypt_returns_string(self):
        from app.nightwatch.decrypt_utils import encrypt_api_key

        result = encrypt_api_key("test")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_decrypt_returns_string(self):
        from app.nightwatch.decrypt_utils import decrypt_api_key, encrypt_api_key

        encrypted = encrypt_api_key("test")
        result = decrypt_api_key(encrypted)
        assert isinstance(result, str)

    def test_different_inputs_produce_different_outputs(self):
        from app.nightwatch.decrypt_utils import encrypt_api_key

        enc1 = encrypt_api_key("key-1")
        enc2 = encrypt_api_key("key-2")
        assert enc1 != enc2


class TestDecryptionEdgeCases:
    """Edge cases for decrypt_utils."""

    @pytest.fixture(autouse=True)
    def _setup(self, monkeypatch):
        monkeypatch.setenv("APP_SECRET_KEY", "edge-case-secret")

    def test_empty_string(self):
        from app.nightwatch.decrypt_utils import decrypt_api_key, encrypt_api_key

        enc = encrypt_api_key("")
        dec = decrypt_api_key(enc)
        assert dec == ""

    def test_unicode_key(self):
        from app.nightwatch.decrypt_utils import decrypt_api_key, encrypt_api_key

        plaintext = "key-with-unicode-🔑"
        enc = encrypt_api_key(plaintext)
        dec = decrypt_api_key(enc)
        assert dec == plaintext

    def test_long_key(self):
        from app.nightwatch.decrypt_utils import decrypt_api_key, encrypt_api_key

        plaintext = "x" * 1000
        enc = encrypt_api_key(plaintext)
        dec = decrypt_api_key(enc)
        assert dec == plaintext


@pytest.fixture
def seg_session(in_memory_engine):
    """Session with segmentation test data."""
    from app.db import Base
    from app.models.device import Device as DeviceModel
    from app.models.device import Port
    from app.models.risk import Risk
    from app.models.scan_event import ScanEvent
    from app.models.settings import AppSetting
    from app.models.scan import Scan
    from app.models.recommendation import Recommendation
    from app.nightwatch import decrypt_utils
    from app.nightwatch import digest_builder
    from app.nightwatch import digest_orchestrator
    from app.nightwatch import llm_client
    from app.nightwatch import ntopng_fetcher
    from app.nightwatch import crowdsec_fetcher
    from app.nightwatch import telegram_sender
    from app.nightwatch import preview
    from app.analysis.segmentation import analyse_segmentation

    from sqlalchemy.orm import sessionmaker
    Base.metadata.create_all(bind=in_memory_engine)

    factory = sessionmaker(bind=in_memory_engine)
    with factory() as s:
        # Seed iot and server devices
        iot = DeviceModel(ip_address="192.168.1.100", mac_address="aa:bb:cc:dd:ee:01",
                     hostname="smart-plug", device_type="iot")
        iot.ports.append(Port(port_number=80, protocol="tcp", service_name="http", version_banner="Nginx"))
        srv = DeviceModel(ip_address="192.168.1.10", mac_address="aa:bb:cc:dd:ee:02",
                     hostname="nas", device_type="server")
        srv.ports.append(Port(port_number=22, protocol="tcp", service_name="ssh", version_banner="OpenSSH"))
        s.add(iot)
        s.add(srv)
        s.flush()
        yield s, analyse_segmentation

@pytest.mark.integration
class TestSegmentation:
    """Tests for analysis/segmentation.py."""

    def test_same_24_no_match(self):
        from app.analysis.segmentation import _same_24
        assert _same_24("192.168.1.1", "192.168.2.1") is None

    def test_same_24_match(self):
        from app.analysis.segmentation import _same_24
        assert _same_24("192.168.1.1", "192.168.1.254") == "192.168.1.0/24"

    def test_same_24_invalid_ip(self):
        from app.analysis.segmentation import _same_24
        assert _same_24("invalid", "valid") is None

    def test_analyse_no_iot_or_servers(self, seg_session):
        from sqlalchemy.orm import sessionmaker
        from app.analysis.segmentation import analyse_segmentation

    def test_analyse_flat_network_detected(self, seg_session):
        from app.analysis.segmentation import analyse_segmentation
        session, func = seg_session
        result = func(session)
        assert result.flat_network
        assert result.iot_count == 1
        assert result.server_count == 1
        assert len(result.recommendations) == 3
        assert "IoT VLAN" in result.recommendations[0]

    def test_mixed_risk_pairs_on_same_subnet(self, seg_session):
        from app.analysis.segmentation import analyse_segmentation
        session, func = seg_session
        result = func(session)
        assert len(result.mixed_risk_pairs) >= 1
        pair = result.mixed_risk_pairs[0]
        assert pair.iot_device_id is not None
        assert pair.iot_ip == "192.168.1.100"
        assert pair.server_ip == "192.168.1.10"
        assert pair.shared_subnet == "192.168.1.0/24"
