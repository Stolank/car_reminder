"""File storage and backup format for the desktop reminder."""

import json
import os
import shutil
import sys
import tempfile
from datetime import date


BACKUP_FORMAT = "car-reminder-desktop"


def reminder_data_path():
    if getattr(sys, "frozen", False):
        local_dir = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~/AppData/Local")
        return os.path.join(local_dir, "CarReminder", "reminders.json")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "reminders.json")


def load_reminders(data_file):
    if not os.path.exists(data_file):
        return []

    with open(data_file, "r", encoding="utf-8") as file:
        data = json.load(file)
    if not isinstance(data, list):
        raise ValueError("Ожидался список напоминаний")

    reminders = []
    for item in data:
        if not isinstance(item, dict) or not {"kind", "due_date"} <= item.keys():
            raise ValueError("Неверный формат напоминания")
        if "kind" in item and "due_date" in item:
            reminders.append(
                {
                    "kind": str(item.get("kind", "")).strip(),
                    "due_date": str(item.get("due_date", "")).strip(),
                    "note": str(item.get("note", "")).strip(),
                }
            )
    return reminders


def save_reminders(data_file, reminders):
    write_json(data_file, reminders)


def write_backup(path, reminders):
    write_json(path, {"format": BACKUP_FORMAT, "version": 1, "reminders": reminders})


def read_backup(path):
    with open(path, "r", encoding="utf-8-sig") as file:
        data = json.load(file)
    if isinstance(data, dict):
        if data.get("format") != BACKUP_FORMAT or type(data.get("version")) is not int or data["version"] != 1:
            raise ValueError("Это не поддерживаемая копия настольной версии.")
        data = data.get("reminders")
    if not isinstance(data, list):
        raise ValueError("Ожидался список напоминаний.")
    for item in data:
        if (not isinstance(item, dict)
                or not all(isinstance(item.get(key), str) for key in ("kind", "due_date"))
                or not item["kind"].strip()
                or not isinstance(item.get("note", ""), str)):
            raise ValueError("В копии есть запись с неверной структурой.")
    reminders = [{key: item.get(key, "") for key in ("kind", "due_date", "note")} for item in data]
    try:
        for item in reminders:
            for value in item.values():
                value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValueError("В копии есть повреждённые символы.") from error
    return reminders


def is_active_data_file(path, data_file):
    if os.path.normcase(os.path.realpath(path)) == os.path.normcase(os.path.realpath(data_file)):
        return True
    try:
        return os.path.samefile(path, data_file)
    except FileNotFoundError:
        return False


def preserve_data_file(data_file):
    try:
        source = open(data_file, "rb")
    except FileNotFoundError:
        return None
    path = None
    try:
        with source, tempfile.NamedTemporaryFile(
            mode="wb", dir=os.path.dirname(data_file), delete=False,
            prefix=f"car-reminders-backup-before-restore-{date.today().isoformat()}-", suffix=".json",
        ) as safety:
            path = safety.name
            shutil.copyfileobj(source, safety)
            safety.flush()
            os.fsync(safety.fileno())
        return path
    except OSError:
        if path is not None:
            os.unlink(path)
        raise


def write_json(path, data):
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    temporary_path = None
    try:
        # Replace the original only after the complete new file is on disk.
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=directory,
            prefix=".reminders-", suffix=".tmp", delete=False,
        ) as file:
            temporary_path = file.name
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None and os.path.exists(temporary_path):
            os.unlink(temporary_path)
