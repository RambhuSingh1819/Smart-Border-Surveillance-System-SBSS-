import unittest

from src.db_manager import DatabaseManager
from src.threat_scanner import ThreatScanner


class TestThreatScannerLogic(unittest.TestCase):
    def test_weapon_label_normalization(self):
        self.assertTrue(ThreatScanner.is_weapon_label("gun"))
        self.assertTrue(ThreatScanner.is_weapon_label("pistol"))
        self.assertTrue(ThreatScanner.is_weapon_label("knife"))
        self.assertTrue(ThreatScanner.is_weapon_label("firearm"))
        self.assertFalse(ThreatScanner.is_weapon_label("person"))
        self.assertFalse(ThreatScanner.is_weapon_label("bottle"))

    def test_weapon_label_aliases(self):
        self.assertTrue(ThreatScanner.is_weapon_label("handgun"))
        self.assertTrue(ThreatScanner.is_weapon_label("rifle"))
        self.assertTrue(ThreatScanner.is_weapon_label("dagger"))

    def test_normalized_label_uses_lowercase(self):
        self.assertEqual(ThreatScanner.normalize_label("  Pistol  "), "pistol")
        self.assertEqual(ThreatScanner.normalize_label("GUN!!!"), "gun")

    def test_invalid_labels_are_rejected(self):
        self.assertFalse(ThreatScanner.is_weapon_label("cell phone"))
        self.assertFalse(ThreatScanner.is_weapon_label("backpack"))

    def test_deduplicate_items_retains_distinct_weapons(self):
        items = [
            {"box": [10, 10, 50, 50], "label": "knife"},
            {"box": [200, 200, 250, 250], "label": "knife"},
        ]
        result = ThreatScanner.deduplicate_items(items)
        self.assertEqual(len(result), 2)

    def test_deduplicate_items_removes_overlapping_weapons(self):
        items = [
            {"box": [10, 10, 50, 50], "label": "knife"},
            {"box": [12, 12, 52, 52], "label": "knife"},
        ]
        result = ThreatScanner.deduplicate_items(items)
        self.assertEqual(len(result), 1)


class TestDatabaseValidation(unittest.TestCase):
    def test_zone_normalization(self):
        self.assertEqual(
            DatabaseManager.normalize_zone_value("Perimeter-A, Zone-B , , Main-Gate"),
            "Perimeter-A,Zone-B,Main-Gate"
        )
        self.assertEqual(DatabaseManager.normalize_zone_list("Perimeter-A, Zone-B"), ["perimeter-a", "zone-b"])

    def test_plate_validation(self):
        self.assertEqual(DatabaseManager.normalize_plate(" up16-ab-1234 "), "UP16-AB-1234")
        self.assertTrue(bool(DatabaseManager.normalize_plate("UP16AB1234")))
        self.assertEqual(DatabaseManager.normalize_plate("!!!"), "")


class TestEngineEdgeCases(unittest.TestCase):
    def test_face_verifier_invalid_crop(self):
        from src.face_engine import FaceVerifier
        verifier = FaceVerifier()
        is_auth, name, score = verifier.verify_crop(None)
        self.assertFalse(is_auth)
        self.assertEqual(score, 0.0)

    def test_anpr_processor_invalid_crop(self):
        from src.anpr_processor import ANPRProcessor
        class DummyDetector:
            pass
        anpr = ANPRProcessor(DummyDetector())
        plate, crop = anpr.extract_plate(None)
        self.assertEqual(plate, "UNREADABLE")
        self.assertIsNone(crop)


if __name__ == "__main__":
    unittest.main()
