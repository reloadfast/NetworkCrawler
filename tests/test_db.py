import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db import Base, upsert_device, get_db
from app.models.device import Device

DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)

class TestUpsertDevice(unittest.TestCase):
    def setUp(self):
        self.session = TestingSessionLocal()

    def tearDown(self):
        self.session.close()

    def test_insert_new_device(self):
        device = upsert_device(self.session, ip_address="192.168.1.1", mac_address="00:1A:2B:3C:4D:5E", vendor="Vendor1", hostname="Host1", os_guess="OS1")
        self.session.commit()
        self.assertIsNotNone(device)
        self.assertEqual(device.ip_address, "192.168.1.1")
        self.assertEqual(device.mac_address, "00:1A:2B:3C:4D:5E")
        self.assertEqual(device.vendor, "Vendor1")
        self.assertEqual(device.hostname, "Host1")
        self.assertEqual(device.os_guess, "OS1")

    def test_update_existing_device(self):
        device = upsert_device(self.session, ip_address="192.168.1.1", mac_address="00:1A:2B:3C:4D:5E", vendor="Vendor1", hostname="Host1", os_guess="OS1")
        self.session.commit()
        updated_device = upsert_device(self.session, ip_address="192.168.1.2", mac_address="00:1A:2B:3C:4D:5E", vendor="Vendor2", hostname="Host2", os_guess="OS2")
        self.session.commit()
        self.assertIsNotNone(updated_device)
        self.assertEqual(updated_device.ip_address, "192.168.1.2")
        self.assertEqual(updated_device.mac_address, "00:1A:2B:3C:4D:5E")
        self.assertEqual(updated_device.vendor, "Vendor2")
        self.assertEqual(updated_device.hostname, "Host2")
        self.assertEqual(updated_device.os_guess, "OS2")

    def test_attempt_update_with_existing_ip(self):
        device1 = upsert_device(self.session, ip_address="192.168.1.1", mac_address="00:1A:2B:3C:4D:5E", vendor="Vendor1", hostname="Host1", os_guess="OS1")
        self.session.commit()
        device2 = upsert_device(self.session, ip_address="192.168.1.1", mac_address="00:1A:2B:3C:4D:5F", vendor="Vendor2", hostname="Host2", os_guess="OS2")
        self.session.commit()
        self.assertIsNotNone(device1)
        self.assertIsNone(device2)

    def test_insert_with_existing_mac_different_ip(self):
        device1 = upsert_device(self.session, ip_address="192.168.1.1", mac_address="00:1A:2B:3C:4D:5E", vendor="Vendor1", hostname="Host1", os_guess="OS1")
        self.session.commit()
        device2 = upsert_device(self.session, ip_address="192.168.1.2", mac_address="00:1A:2B:3C:4D:5E", vendor="Vendor2", hostname="Host2", os_guess="OS2")
        self.session.commit()
        self.assertIsNotNone(device1)
        self.assertIsNotNone(device2)
        self.assertEqual(device2.ip_address, "192.168.1.2")
        self.assertEqual(device2.mac_address, "00:1A:2B:3C:4D:5E")
        self.assertEqual(device2.vendor, "Vendor2")
        self.assertEqual(device2.hostname, "Host2")
        self.assertEqual(device2.os_guess, "OS2")

    def test_insert_with_existing_mac_same_ip(self):
        device1 = upsert_device(self.session, ip_address="192.168.1.1", mac_address="00:1A:2B:3C:4D:5E", vendor="Vendor1", hostname="Host1", os_guess="OS1")
        self.session.commit()
        device2 = upsert_device(self.session, ip_address="192.168.1.1", mac_address="00:1A:2B:3C:4D:5E", vendor="Vendor2", hostname="Host2", os_guess="OS2")
        self.session.commit()
        self.assertIsNotNone(device1)
        self.assertIsNotNone(device2)
        self.assertEqual(device2.ip_address, "192.168.1.1")
        self.assertEqual(device2.mac_address, "00:1A:2B:3C:4D:5E")
        self.assertEqual(device2.vendor, "Vendor2")
        self.assertEqual(device2.hostname, "Host2")
        self.assertEqual(device2.os_guess, "OS2")

if __name__ == "__main__":
    unittest.main()