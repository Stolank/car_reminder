import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import reminder_storage as storage


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = os.path.join(self.directory.name, "reminders.json")

    def test_packaged_data_uses_user_directory(self):
        with patch.object(sys, "frozen", True, create=True), patch.dict(
            os.environ, {"LOCALAPPDATA": self.directory.name}
        ):
            target = Path(storage.reminder_data_path())
        self.assertEqual(target, Path(self.directory.name) / "CarReminder" / "reminders.json")
        storage.save_reminders(target, [])
        self.assertEqual(storage.load_reminders(target), [])

    def test_round_trip_russian_and_missing_file(self):
        self.assertEqual(storage.load_reminders(self.path), [])
        items = [{"kind": "Техосмотр", "due_date": "22.10.2026", "note": "Документы"}]
        storage.save_reminders(self.path, items)
        self.assertEqual(storage.load_reminders(self.path), items)
        self.assertIn("Техосмотр", Path(self.path).read_text(encoding="utf-8"))

    def test_failed_replace_preserves_original_and_cleans_temp(self):
        storage.save_reminders(self.path, [])
        before = Path(self.path).read_bytes()
        with patch.object(storage.os, "replace", side_effect=PermissionError):
            with self.assertRaises(OSError):
                storage.save_reminders(self.path, [{"kind": "Changed"}])
        self.assertEqual(Path(self.path).read_bytes(), before)
        self.assertEqual(os.listdir(self.directory.name), ["reminders.json"])

    def test_invalid_file_is_not_silently_treated_as_empty(self):
        for value in (None, {}, [None], [{"kind": "Missing date"}]):
            Path(self.path).write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaises(ValueError):
                storage.load_reminders(self.path)

    def test_backup_format_round_trip(self):
        path = Path(self.directory.name) / "backup.json"
        items = [{"kind": "Техосмотр", "due_date": "22.10.2026", "note": "Документы"}]
        storage.write_backup(path, items)
        self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {
            "format": "car-reminder-desktop", "version": 1, "reminders": items,
        })
        self.assertEqual(storage.read_backup(path), items)
