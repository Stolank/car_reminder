import json
import os
from datetime import date, datetime, timedelta
import tkinter as tk
from tkinter import messagebox, ttk


APP_TITLE = "Напоминалка для автомобиля"
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "reminders.json")
DATE_FORMAT = "%d.%m.%Y"
WARNING_DAYS = 30

DEFAULT_TYPES = [
    "Страховка на машину",
    "Техосмотр",
    "Замена масла в двигателе",
    "Замена масла в коробке",
    "Замена свечей в двигателе",
]


def parse_date(value):
    return datetime.strptime(value.strip(), DATE_FORMAT).date()


def format_date(value):
    return value.strftime(DATE_FORMAT)


def load_reminders():
    if not os.path.exists(DATA_FILE):
        return []

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, json.JSONDecodeError):
        messagebox.showwarning(
            APP_TITLE,
            "Не удалось прочитать reminders.json. Файл поврежден или недоступен.",
        )
        return []

    reminders = []
    for item in data:
        if not isinstance(item, dict):
            continue
        if "kind" in item and "due_date" in item:
            reminders.append(
                {
                    "kind": str(item.get("kind", "")).strip(),
                    "due_date": str(item.get("due_date", "")).strip(),
                    "note": str(item.get("note", "")).strip(),
                }
            )
    return reminders


def save_reminders(reminders):
    with open(DATA_FILE, "w", encoding="utf-8") as file:
        json.dump(reminders, file, ensure_ascii=False, indent=2)


def reminder_status(due_date):
    today = date.today()
    days_left = (due_date - today).days

    if days_left < 0:
        return f"Просрочено на {abs(days_left)} дн."
    if days_left == 0:
        return "Заканчивается сегодня"
    if days_left <= WARNING_DAYS:
        return f"Осталось {days_left} дн."
    return "Не скоро"


class CarReminderApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("900x520")
        self.root.minsize(760, 440)

        self.reminders = load_reminders()
        self.selected_index = None

        self.kind_var = tk.StringVar(value=DEFAULT_TYPES[0])
        self.day_var = tk.StringVar()
        self.month_var = tk.StringVar()
        self.year_var = tk.StringVar()
        self.note_var = tk.StringVar()

        self.build_ui()
        self.refresh_table()
        self.show_startup_alerts()

    def build_ui(self):
        container = ttk.Frame(self.root, padding=14)
        container.pack(fill=tk.BOTH, expand=True)

        form = ttk.LabelFrame(container, text="Добавить или изменить напоминание", padding=12)
        form.pack(fill=tk.X)

        ttk.Label(form, text="Что напомнить").grid(row=0, column=0, sticky=tk.W, padx=(0, 8))
        kind_box = ttk.Combobox(form, textvariable=self.kind_var, values=DEFAULT_TYPES, state="readonly")
        kind_box.grid(row=1, column=0, sticky=tk.EW, padx=(0, 12), pady=(4, 8))

        ttk.Label(form, text="День").grid(row=0, column=1, sticky=tk.W)
        day_spin = ttk.Spinbox(form, from_=1, to=31, width=6, textvariable=self.day_var)
        day_spin.grid(row=1, column=1, sticky=tk.W, pady=(4, 8))

        ttk.Label(form, text="Месяц").grid(row=0, column=2, sticky=tk.W)
        month_spin = ttk.Spinbox(form, from_=1, to=12, width=6, textvariable=self.month_var)
        month_spin.grid(row=1, column=2, sticky=tk.W, padx=(8, 0), pady=(4, 8))

        ttk.Label(form, text="Год").grid(row=0, column=3, sticky=tk.W)
        year_spin = ttk.Spinbox(form, from_=2020, to=2100, width=8, textvariable=self.year_var)
        year_spin.grid(row=1, column=3, sticky=tk.W, padx=(8, 0), pady=(4, 8))

        ttk.Label(form, text="Заметка").grid(row=0, column=4, sticky=tk.W, padx=(12, 0))
        note_entry = ttk.Entry(form, textvariable=self.note_var)
        note_entry.grid(row=1, column=4, sticky=tk.EW, padx=(12, 0), pady=(4, 8))

        form.columnconfigure(0, weight=2)
        form.columnconfigure(4, weight=3)

        button_bar = ttk.Frame(form)
        button_bar.grid(row=2, column=0, columnspan=5, sticky=tk.W, pady=(4, 0))

        ttk.Button(button_bar, text="Сохранить", command=self.save_current).pack(side=tk.LEFT)
        ttk.Button(button_bar, text="Очистить", command=self.clear_form).pack(side=tk.LEFT, padx=8)
        ttk.Button(button_bar, text="Удалить выбранное", command=self.delete_selected).pack(side=tk.LEFT)

        list_frame = ttk.LabelFrame(container, text="Ваши сроки", padding=12)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(12, 0))

        columns = ("kind", "due_date", "status", "note")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("kind", text="Напоминание")
        self.tree.heading("due_date", text="Дата")
        self.tree.heading("status", text="Статус")
        self.tree.heading("note", text="Заметка")

        self.tree.column("kind", width=240, minwidth=180)
        self.tree.column("due_date", width=110, minwidth=90, anchor=tk.CENTER)
        self.tree.column("status", width=170, minwidth=130, anchor=tk.CENTER)
        self.tree.column("note", width=260, minwidth=160)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.tag_configure("overdue", background="#ffd9d9")
        self.tree.tag_configure("soon", background="#fff3bf")
        self.tree.tag_configure("ok", background="#e8f5e9")
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        hint = ttk.Label(
            container,
            text="Формат даты: день, месяц, год. При запуске программа показывает просроченные и ближайшие напоминания.",
        )
        hint.pack(fill=tk.X, pady=(8, 0))

    def get_form_date(self):
        day = int(self.day_var.get())
        month = int(self.month_var.get())
        year = int(self.year_var.get())
        return date(year, month, day)

    def save_current(self):
        try:
            due_date = self.get_form_date()
        except ValueError:
            messagebox.showerror(APP_TITLE, "Введите правильную дату: день, месяц и год.")
            return

        reminder = {
            "kind": self.kind_var.get().strip(),
            "due_date": format_date(due_date),
            "note": self.note_var.get().strip(),
        }

        if not reminder["kind"]:
            messagebox.showerror(APP_TITLE, "Выберите, о чем напомнить.")
            return

        if self.selected_index is None:
            self.reminders.append(reminder)
        else:
            self.reminders[self.selected_index] = reminder

        self.sort_reminders()
        save_reminders(self.reminders)
        self.refresh_table()
        self.clear_form()

    def sort_reminders(self):
        def key(item):
            try:
                return parse_date(item["due_date"])
            except ValueError:
                return date.max

        self.reminders.sort(key=key)

    def refresh_table(self):
        self.tree.delete(*self.tree.get_children())
        self.sort_reminders()

        for index, item in enumerate(self.reminders):
            try:
                due_date = parse_date(item["due_date"])
            except ValueError:
                status = "Ошибка даты"
                tag = "overdue"
            else:
                days_left = (due_date - date.today()).days
                status = reminder_status(due_date)
                if days_left < 0:
                    tag = "overdue"
                elif days_left <= WARNING_DAYS:
                    tag = "soon"
                else:
                    tag = "ok"

            self.tree.insert(
                "",
                tk.END,
                iid=str(index),
                values=(item["kind"], item["due_date"], status, item.get("note", "")),
                tags=(tag,),
            )

    def on_select(self, _event=None):
        selected = self.tree.selection()
        if not selected:
            return

        self.selected_index = int(selected[0])
        item = self.reminders[self.selected_index]
        self.kind_var.set(item["kind"])
        self.note_var.set(item.get("note", ""))

        try:
            due_date = parse_date(item["due_date"])
        except ValueError:
            self.day_var.set("")
            self.month_var.set("")
            self.year_var.set("")
            return

        self.day_var.set(str(due_date.day))
        self.month_var.set(str(due_date.month))
        self.year_var.set(str(due_date.year))

    def clear_form(self):
        self.selected_index = None
        self.tree.selection_remove(self.tree.selection())
        self.kind_var.set(DEFAULT_TYPES[0])
        self.day_var.set("")
        self.month_var.set("")
        self.year_var.set("")
        self.note_var.set("")

    def delete_selected(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showinfo(APP_TITLE, "Сначала выберите строку для удаления.")
            return

        index = int(selected[0])
        item = self.reminders[index]
        if not messagebox.askyesno(APP_TITLE, f"Удалить напоминание \"{item['kind']}\"?"):
            return

        del self.reminders[index]
        save_reminders(self.reminders)
        self.refresh_table()
        self.clear_form()

    def show_startup_alerts(self):
        alerts = []
        for item in self.reminders:
            try:
                due_date = parse_date(item["due_date"])
            except ValueError:
                continue

            days_left = (due_date - date.today()).days
            if days_left <= WARNING_DAYS:
                alerts.append(f"{item['kind']} - {item['due_date']} ({reminder_status(due_date)})")

        if alerts:
            messagebox.showwarning(APP_TITLE, "Есть важные сроки:\n\n" + "\n".join(alerts))


if __name__ == "__main__":
    root = tk.Tk()
    app = CarReminderApp(root)
    root.mainloop()
