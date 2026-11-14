import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import tkinter as tk
import unittest
from datetime import date, timedelta
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import car_reminder as reminder
import reminder_storage as storage
from windows_instance import WindowsInstance


@unittest.skipUnless(os.name == "nt", "Windows-only instance guard")
class InstanceTests(unittest.TestCase):
    def test_second_process_signals_first_and_lock_is_reusable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "reminders.json")
            first = WindowsInstance(path)
            try:
                self.assertTrue(first.primary)
                self.assertFalse(first.activation_requested())
                result = subprocess.run(
                    [sys.executable, "-B", "-c",
                     "import sys; from windows_instance import WindowsInstance; "
                     "i = WindowsInstance(sys.argv[1]); print(i.primary); i.close()", path],
                    cwd=Path(reminder.__file__).parent, capture_output=True, text=True,
                    check=True, timeout=10,
                )
                self.assertEqual(result.stdout.strip(), "False")
                self.assertTrue(first.activation_requested())
                self.assertFalse(first.activation_requested())
                other = WindowsInstance(str(Path(directory) / "other.json"))
                try:
                    self.assertTrue(other.primary)
                finally:
                    other.close()
            finally:
                first.close()
            reopened = WindowsInstance(path)
            try:
                self.assertTrue(reopened.primary)
            finally:
                reopened.close()


class DateTests(unittest.TestCase):
    def test_dates_and_status_boundaries(self):
        today = date(2026, 10, 22)
        for offset, expected in ((-1, "Просрочено на 1 дн."), (0, "Срок сегодня"),
                                 (30, "Осталось 30 дн."), (31, "Осталось 31 дн.")):
            self.assertEqual(reminder.reminder_status(today + timedelta(days=offset), today), expected)
        for value in (date(1, 1, 1), date(2028, 2, 29), date(9999, 12, 31)):
            self.assertEqual(reminder.parse_date(reminder.format_date(value)), value)
        with self.assertRaises(ValueError):
            reminder.parse_date("31.02.2026")


class InterfaceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.data_patch = patch.object(reminder, "DATA_FILE", os.path.join(self.directory.name, "reminders.json"))
        self.data_patch.start()
        self.addCleanup(self.data_patch.stop)
        self.error_patch = patch.object(reminder.messagebox, "showerror")
        self.error = self.error_patch.start()
        self.addCleanup(self.error_patch.stop)
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = reminder.CarReminderApp(self.root)
        self.addCleanup(lambda: self.app.close())

    def add_item(self, kind="Техосмотр", due="22.10.2026"):
        self.app.open_editor()
        dialog = self.app.editor
        dialog.withdraw()
        dialog.kind_var.set(kind)
        dialog.date_var.set(due)
        dialog.save()
        self.root.update_idletasks()

    def test_backup_round_trip_and_working_file_protection(self):
        self.add_item()
        working = Path(reminder.DATA_FILE)
        original = working.read_bytes()
        copy = working.with_name("copy.json")
        with patch.object(reminder.filedialog, "asksaveasfilename", return_value=str(copy)), patch.object(
            reminder.messagebox, "showinfo"
        ):
            self.app.export_backup()
        self.assertEqual(storage.read_backup(copy), self.app.reminders)
        with patch.object(reminder.filedialog, "asksaveasfilename", return_value=str(working)):
            self.app.export_backup()
        self.error.assert_called_once()
        self.assertEqual(working.read_bytes(), original)

    def test_unchanged_form_closes_without_confirmation(self):
        self.app.open_editor()
        dialog = self.app.editor
        original = dialog.note_var.get()
        dialog.note_var.set("Unsaved")
        dialog.note_var.set(original)
        with patch.object(reminder.messagebox, "askyesno") as confirm:
            dialog.request_close()
        confirm.assert_not_called()
        self.assertIsNone(self.app.editor)

    def test_dirty_form_preserves_input_until_discard_confirmed(self):
        self.add_item()
        self.app.edit_selected()
        dialog = self.app.editor
        dialog.note_var.set("Unsaved")
        with patch.object(reminder.messagebox, "askyesno", return_value=False) as confirm:
            self.app.request_close()
            dialog.request_close()
            self.assertEqual(confirm.call_count, 2)
            self.assertIs(self.app.editor, dialog)
            self.assertEqual(dialog.note_var.get(), "Unsaved")
            confirm.return_value = True
            dialog.request_close()
        self.assertIsNone(self.app.editor)
        self.assertEqual(storage.load_reminders(reminder.DATA_FILE)[0]["note"], "")

    def test_successful_save_does_not_ask_to_discard(self):
        with patch.object(reminder.messagebox, "askyesno") as confirm:
            self.add_item()
        confirm.assert_not_called()
        self.assertIsNone(self.app.editor)
        self.assertEqual(len(storage.load_reminders(reminder.DATA_FILE)), 1)

    def test_restore_validates_confirms_and_preserves_original(self):
        self.add_item()
        working = Path(reminder.DATA_FILE)
        original = working.read_bytes()
        copy = working.with_name("copy.json")
        copy.write_text('[{"kind": "Wrong", "date": "01.01.2027"}]', encoding="utf-8")
        with patch.object(reminder.filedialog, "askopenfilename", return_value=str(copy)), patch.object(
            reminder.messagebox, "askyesno", return_value=False
        ) as confirm, patch.object(reminder.messagebox, "showinfo"):
            self.app.restore_backup()
            confirm.assert_not_called()
            self.error.assert_called_once()
            copy.write_text("[]", encoding="utf-8")
            self.app.restore_backup()
            self.assertEqual(working.read_bytes(), original)
            self.assertFalse(list(working.parent.glob("car-reminders-backup-before-restore-*")))
            confirm.return_value = True
            self.app.restore_backup()
        self.assertEqual(storage.load_reminders(reminder.DATA_FILE), [])
        saved, = working.parent.glob("car-reminders-backup-before-restore-*")
        self.assertEqual(saved.read_bytes(), original)

    def test_restore_reopens_damaged_store_and_preserves_bytes(self):
        working = Path(reminder.DATA_FILE)
        damaged = b"\xff damaged"
        working.write_bytes(damaged)
        self.app.close()
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = reminder.CarReminderApp(self.root)
        self.assertTrue(self.app.load_error)
        copy = working.with_name("copy.json")
        copy.write_text("[]", encoding="utf-8")
        with patch.object(reminder.filedialog, "askopenfilename", return_value=str(copy)), patch.object(
            reminder.messagebox, "askyesno", return_value=True
        ), patch.object(reminder.messagebox, "showinfo"):
            with patch.object(storage, "preserve_data_file", side_effect=PermissionError):
                self.app.restore_backup()
            self.assertTrue(self.app.load_error)
            self.assertEqual(working.read_bytes(), damaged)
            self.app.restore_backup()
        self.assertFalse(self.app.load_error)
        self.assertNotIn("disabled", self.app.add_button.state())
        saved, = working.parent.glob("car-reminders-backup-before-restore-*")
        self.assertEqual(saved.read_bytes(), damaged)

    def test_restore_rejects_surrogate_before_confirmation(self):
        self.add_item()
        working = Path(reminder.DATA_FILE)
        original = working.read_bytes()
        copy = working.with_name("copy.json")
        copy.write_text(json.dumps([{"kind": "Valid", "due_date": "01.01.2027", "note": chr(0xD800)}]),
                        encoding="utf-8")
        with patch.object(reminder.filedialog, "askopenfilename", return_value=str(copy)), patch.object(
            reminder.messagebox, "askyesno"
        ) as confirm:
            self.app.restore_backup()
        confirm.assert_not_called()
        self.error.assert_called_once()
        self.assertEqual(working.read_bytes(), original)
        self.assertFalse(list(working.parent.glob("car-reminders-backup-before-restore-*")))

    def test_saving_hidden_reminder_explains_filter(self):
        self.app.urgent_only.set(True)
        future = reminder.format_date(date.today() + timedelta(days=31))
        with patch.object(reminder.messagebox, "showinfo") as info:
            self.add_item(due=future)
        self.assertIn("скрыта фильтром", info.call_args.args[1])
        self.assertEqual(storage.load_reminders(reminder.DATA_FILE)[0]["due_date"], future)
        self.assertFalse(self.app.tree.get_children())
        self.app.urgent_only.set(False)
        self.app.apply_filter()
        self.assertEqual(len(self.app.tree.get_children()), 1)

    def test_undo_delete_keeps_new_records_and_can_retry(self):
        self.add_item()
        with patch.object(reminder.messagebox, "askyesno", return_value=True):
            self.app.delete_selected()
        self.add_item("Страховка", "01.01.2027")
        with patch.object(storage, "save_reminders", side_effect=OSError):
            self.app.undo_delete()
        self.assertIsNotNone(self.app.last_deleted)
        self.app.undo_delete()
        self.app.undo_delete()
        self.assertCountEqual([item["kind"] for item in storage.load_reminders(reminder.DATA_FILE)], ["Техосмотр", "Страховка"])

    def test_calendar_enter_chooses_focused_day_without_saving(self):
        self.app.open_editor()
        dialog = self.app.editor
        dialog.date_var.set("22.10.2026")
        self.assertEqual(dialog.open_calendar(), "break")
        picker, = [child for child in dialog.winfo_children() if isinstance(child, reminder.DatePicker)]
        day = next(button for button in picker.days.winfo_children() if button.cget("text") == "23")
        self.assertEqual(picker.activate_focused_button(SimpleNamespace(widget=day)), "break")
        self.assertEqual(dialog.date_var.get(), "23.10.2026")
        self.assertFalse(os.path.exists(reminder.DATA_FILE))
        dialog.close()

    def test_urgent_filter_keeps_record_mapping_and_counts(self):
        today = date.today()
        self.app.reminders = [
            {"kind": kind, "due_date": reminder.format_date(today + timedelta(days=days))}
            for kind, days in (("Soon", 30), ("Later", 31), ("Overdue", -1), ("Today", 0))
        ]
        self.app.reminders.append({"kind": "Invalid", "due_date": "invalid"})
        self.app.urgent_only.set(True)
        self.app.apply_filter()
        visible = self.app.tree.get_children()
        self.assertEqual([self.app.reminders[int(row)]["kind"] for row in visible],
                         ["Overdue", "Today", "Soon", "Invalid"])
        self.assertIn("Всего: 5", self.app.summary.cget("text"))
        self.app.tree.selection_set(visible[-1])
        self.app.edit_selected()
        self.assertEqual(self.app.editor.kind_var.get(), "Invalid")
        self.app.editor.close()
        self.app.urgent_only.set(False)
        self.app.apply_filter()
        self.assertEqual(len(self.app.tree.get_children()), 5)

    def test_full_note_follows_selection_and_hides_when_filtered(self):
        today = date.today()
        long_note = "Проверить уровень масла и расходники. " * 30 + "\nПоследняя строка"
        self.app.reminders = [
            {"kind": "Now", "due_date": reminder.format_date(today), "note": ""},
            {"kind": "Later", "due_date": reminder.format_date(today + timedelta(days=31)), "note": long_note},
        ]
        self.root.geometry("720x380")
        self.root.deiconify()
        self.app.refresh_table()
        self.assertFalse(self.app.note_panel.winfo_manager())
        self.app.tree.selection_set("1")
        self.root.update()
        self.assertTrue(self.app.note_panel.winfo_ismapped())
        self.assertEqual(self.app.note_preview.get("1.0", "end-1c"), long_note)
        self.assertEqual(str(self.app.note_preview.cget("state")), "disabled")
        self.assertLess(self.app.note_preview.yview()[1], 1)
        self.assertGreater(self.app.tree.winfo_height(), 100)
        self.app.tree.selection_set("0")
        self.root.update()
        self.assertFalse(self.app.note_panel.winfo_manager())
        self.assertEqual(self.app.note_preview.get("1.0", "end-1c"), "")
        self.app.tree.selection_set("1")
        self.root.update()
        self.app.urgent_only.set(True)
        self.app.apply_filter()
        self.assertFalse(self.app.note_panel.winfo_manager())

    def test_add_edit_and_add_while_row_selected(self):
        self.add_item()
        self.assertEqual(len(self.app.reminders), 1)
        self.app.edit_selected()
        dialog = self.app.editor
        dialog.withdraw()
        dialog.note_var.set("Изменено")
        dialog.save()
        self.assertEqual(self.app.reminders[0]["note"], "Изменено")
        self.add_item("Замена масла", "23.10.2026")
        self.assertEqual(len(self.app.reminders), 2)
        self.assertEqual(len(storage.load_reminders(reminder.DATA_FILE)), 2)

    def test_invalid_date_and_cancel_leave_data_unchanged(self):
        self.add_item(due="31.02.2026")
        self.error.assert_called_once()
        self.assertEqual(self.app.reminders, [])
        self.assertIsNotNone(self.app.editor)
        self.app.editor.close()
        self.assertIsNone(self.app.editor)
        self.assertFalse(os.path.exists(reminder.DATA_FILE))

    def test_failed_save_keeps_form_and_original_data(self):
        self.add_item()
        original = storage.load_reminders(reminder.DATA_FILE)
        self.app.edit_selected()
        dialog = self.app.editor
        dialog.withdraw()
        dialog.note_var.set("Unsaved")
        with patch.object(storage, "save_reminders", side_effect=OSError):
            dialog.save()
        self.assertEqual(self.app.reminders, original)
        self.assertIs(self.app.editor, dialog)
        self.assertEqual(dialog.note_var.get(), "Unsaved")
        dialog.close()

    def test_delete_confirmation_and_failure(self):
        self.add_item()
        with patch.object(reminder.messagebox, "askyesno", return_value=False):
            self.app.delete_selected()
        self.assertEqual(len(self.app.reminders), 1)
        with patch.object(reminder.messagebox, "askyesno", return_value=True):
            with patch.object(storage, "save_reminders", side_effect=OSError):
                self.app.delete_selected()
            self.assertEqual(len(self.app.reminders), 1)
            self.app.delete_selected()
        self.assertEqual(self.app.reminders, [])
        self.assertEqual(storage.load_reminders(reminder.DATA_FILE), [])

    def test_calendar_leap_year_and_month_transitions(self):
        self.app.open_editor()
        dialog = self.app.editor
        dialog.withdraw()
        dialog.date_var.set("01.02.2028")
        picker = reminder.DatePicker(dialog, dialog.date_var)
        picker.withdraw()
        day_labels = [child.cget("text") for child in picker.days.winfo_children()]
        self.assertIn("29", day_labels)
        self.assertNotIn("30", day_labels)
        picker.year, picker.month = 2026, 12
        picker.move(1)
        self.assertEqual((picker.year, picker.month), (2027, 1))
        picker.move(-1)
        self.assertEqual((picker.year, picker.month), (2026, 12))
        picker.choose(date(2028, 2, 29))
        self.assertEqual(dialog.date_var.get(), "29.02.2028")
        dialog.close()

    def test_calendar_arrows_cross_month_without_selecting_date(self):
        self.app.open_editor()
        dialog = self.app.editor
        dialog.date_var.set("28.02.2028")
        dialog.open_calendar()
        picker, = [child for child in dialog.winfo_children() if isinstance(child, reminder.DatePicker)]
        picker.withdraw()

        self.assertEqual(picker.move_day_focus(date(2028, 2, 28), 1), "break")
        self.assertIn(date(2028, 2, 29), picker.day_buttons)
        self.assertEqual(picker.move_day_focus(date(2028, 2, 29), 1), "break")
        self.assertEqual((picker.year, picker.month), (2028, 3))
        self.assertEqual(dialog.date_var.get(), "28.02.2028")
        picker.move_day_focus(date(2028, 3, 1), -7)
        self.assertEqual((picker.year, picker.month), (2028, 2))
        picker.day_buttons[date(2028, 2, 23)].invoke()
        self.assertEqual(dialog.date_var.get(), "23.02.2028")
        dialog.close()

    def test_day_change_refreshes_status_preserves_selection(self):
        self.add_item(due=reminder.format_date(date.today() - timedelta(days=1)))
        self.app.current_day = date.today() - timedelta(days=1)
        self.root.after_cancel(self.app.timer)
        self.app.check_day()
        self.assertEqual(self.app.current_day, date.today())
        self.assertEqual(self.app.selected_index(), 0)
        self.assertIn("Просрочено: 1", self.app.summary.cget("text"))

    def test_corrupt_file_disables_writes(self):
        self.app.close()
        Path(reminder.DATA_FILE).write_text("broken", encoding="utf-8")
        self.root = tk.Tk()
        self.root.withdraw()
        self.app = reminder.CarReminderApp(self.root)
        self.assertTrue(self.app.load_error)
        self.assertIn("disabled", self.app.add_button.state())
        self.assertFalse(self.app.commit([]))
        self.assertEqual(Path(reminder.DATA_FILE).read_text(encoding="utf-8"), "broken")

    def test_layout_at_minimum_and_default_window_sizes(self):
        self.add_item()
        self.root.deiconify()
        for width, height in ((720, 380), (940, 540)):
            self.root.geometry(f"{width}x{height}")
            self.root.update()
            self.assertTrue(self.app.actions.winfo_ismapped())
            toolbar = self.app.toolbar_controls
            children = sorted(toolbar.winfo_children(), key=lambda child: child.winfo_x())
            for left, right in zip(children, children[1:]):
                self.assertLessEqual(left.winfo_x() + left.winfo_width(), right.winfo_x())
            self.assertGreater(self.app.tree.winfo_height(), 180)
            self.assertLessEqual(self.app.summary.winfo_reqwidth(), width)
        self.app.clear_selection()
        self.root.update_idletasks()
        self.assertFalse(self.app.actions.winfo_ismapped())

    def test_keyboard_workflow_and_layout_at_high_scaling(self):
        original_scaling = self.root.tk.call("tk", "scaling")
        self.addCleanup(lambda: self.root.tk.call("tk", "scaling", original_scaling))

        def press(widget, key):
            self.assertIs(self.root.focus_get(), widget)
            widget.event_generate("<KeyPress-" + key + ">")
            if widget.winfo_exists():
                widget.event_generate("<KeyRelease-" + key + ">")
            self.root.update()

        def assert_fits(parent):
            for child in parent.winfo_children():
                if not child.winfo_ismapped() or isinstance(child, tk.Toplevel):
                    continue
                self.assertLessEqual(child.winfo_x() + child.winfo_width(), parent.winfo_width())
                self.assertLessEqual(child.winfo_y() + child.winfo_height(), parent.winfo_height())
                if isinstance(child, (reminder.ttk.Button, reminder.ttk.Menubutton, reminder.ttk.Checkbutton)):
                    self.assertGreaterEqual(child.winfo_width(), child.winfo_reqwidth(), child.cget("text"))
                    self.assertGreaterEqual(child.winfo_height(), child.winfo_reqheight(), child.cget("text"))
                assert_fits(child)

        for percent in (150, 200):
            with self.subTest(scaling=percent):
                self.app.close()
                self.root = tk.Tk()
                self.root.tk.call("tk", "scaling", (96 / 72) * percent / 100)
                self.app = reminder.CarReminderApp(self.root)
                self.root.geometry("720x380")
                self.root.update()
                before = len(self.app.reminders)
                add = self.app.add_button
                add.focus_force()
                self.root.update()
                press(add, "space")
                dialog = self.app.editor
                self.assertIsNotNone(dialog)
                assert_fits(dialog)
                press(dialog.date_entry, "Tab")
                press(dialog.calendar_button, "Return")
                picker, = [child for child in dialog.winfo_children() if isinstance(child, reminder.DatePicker)]
                assert_fits(picker)
                first = picker.day_buttons[picker.selected]
                expected = reminder.format_date(picker.selected + timedelta(days=1))
                press(first, "Right")
                press(self.root.focus_get(), "Return")
                self.assertEqual(dialog.date_var.get(), expected)
                press(dialog.calendar_button, "Tab")
                press(self.root.focus_get(), "Return")
                self.assertEqual(len(storage.load_reminders(reminder.DATA_FILE)), before + 1)
                self.assertIsNone(self.app.editor)
                self.assertIs(self.root.focus_get(), self.app.tree)
                toolbar = self.app.toolbar
                assert_fits(toolbar)
                self.assertGreater(self.app.tree.winfo_height(), 130)
                self.root.geometry("1280x540")
                self.root.update()
                self.assertEqual(self.app.toolbar_controls.grid_info()["row"], 0)
                assert_fits(toolbar)

    def test_day_refresh_waits_for_open_editor(self):
        self.add_item()
        self.app.edit_selected()
        self.app.editor.withdraw()
        yesterday = date.today() - timedelta(days=1)
        self.app.current_day = yesterday
        self.root.after_cancel(self.app.timer)
        self.app.check_day()
        self.assertEqual(self.app.current_day, yesterday)
        self.assertEqual(self.app.editor.index, 0)
        self.app.editor.close()


if __name__ == "__main__":
    unittest.main()
