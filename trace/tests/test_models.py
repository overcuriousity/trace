import unittest
import shutil
import tempfile
from pathlib import Path
from trace.models import Note, Case, Evidence
from trace.storage import Storage, StateManager

class TestModels(unittest.TestCase):
    def test_note_hash(self):
        note = Note(content="Test content")
        note.calculate_hash()
        self.assertTrue(note.content_hash)

    def test_case_dict(self):
        c = Case(case_number="123", name="Test")
        d = c.to_dict()
        self.assertEqual(d["case_number"], "123")
        c2 = Case.from_dict(d)
        self.assertEqual(c2.name, "Test")

class TestStorage(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.storage = Storage(app_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_save_and_load_case(self):
        case = Case(case_number="T-001", name="Test Case")
        self.storage.add_case(case)

        # Reload storage from same dir
        new_storage = Storage(app_dir=self.test_dir)
        loaded_case = new_storage.get_case(case.case_id)

        self.assertIsNotNone(loaded_case)
        self.assertEqual(loaded_case.name, "Test Case")

    def test_find_evidence(self):
        case = Case(case_number="T-002")
        ev = Evidence(name="Gun")
        case.evidence.append(ev)
        self.storage.add_case(case)

        c, e = self.storage.find_evidence(ev.evidence_id)
        self.assertEqual(c.case_id, case.case_id)
        self.assertEqual(e.name, "Gun")

class TestStateManager(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.mgr = StateManager(app_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_set_get_active(self):
        self.mgr.set_active(case_id="123", evidence_id="456")
        state = self.mgr.get_active()
        self.assertEqual(state["case_id"], "123")
        self.assertEqual(state["evidence_id"], "456")

if __name__ == '__main__':
    unittest.main()
