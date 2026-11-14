#Программа-напоминалка для автомобиля
import calendar
import json
import os
import shutil
import sys
import tempfile
from datetime import date, datetime
import tkinter as tk
from tkinter import font as tkfont
from tkinter import filedialog, messagebox, ttk


APP_TITLE = "Напоминалка для автомобиля"
def reminder_data_path():
    if getattr(sys, "frozen", False):
        local_dir = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~/AppData/Local")
        return os.path.join(local_dir, "CarReminder", "reminders.json")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "reminders.json")


DATA_FILE = reminder_data_path()
DATE_FORMAT = "%d.%m.%Y"
WARNING_DAYS = 30
BACKUP_FORMAT = "car-reminder-desktop"

COLORS = {
    "background": "#f4f6f5",
    "surface": "#ffffff",
    "text": "#202824",
    "muted": "#59665e",
    "border": "#d7dfda",
    "accent": "#18734c",
    "accent_hover": "#125b3c",
    "selected": "#dceee4",
    "danger": "#9d293b",
    "danger_background": "#fff0f2",
    "warning": "#74530b",
    "warning_background": "#fff7df",
}


def apply_theme(root):
    # The native Windows theme ignores some button colors; clam honors them.
    style = ttk.Style(root)
    style.theme_use("clam")
    root.configure(background=COLORS["background"])
    for name in ("TkDefaultFont", "TkTextFont", "TkMenuFont"):
        tkfont.nametofont(name, root=root).configure(family="Segoe UI", size=10)
    root.option_add("*TCombobox*Listbox.background", COLORS["surface"])
    root.option_add("*TCombobox*Listbox.foreground", COLORS["text"])
    root.option_add("*TCombobox*Listbox.selectBackground", COLORS["selected"])
    root.option_add("*TCombobox*Listbox.selectForeground", COLORS["text"])
    style.configure(".", font=("Segoe UI", 10), background=COLORS["surface"],
                    foreground=COLORS["text"], bordercolor=COLORS["border"],
                    lightcolor=COLORS["border"], darkcolor=COLORS["border"])
    style.configure("Page.TFrame", background=COLORS["background"])
    style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"))
    style.configure("DialogTitle.TLabel", font=("Segoe UI", 14, "bold"))
    style.configure("Field.TLabel", font=("Segoe UI", 10, "bold"))
    style.configure("Summary.TLabel", background=COLORS["background"], foreground=COLORS["muted"])
    style.configure("Empty.TLabel", font=("Segoe UI", 12), foreground=COLORS["muted"])
    style.configure("Car.TLabel", font=("Segoe MDL2 Assets", 23), foreground=COLORS["accent"])
    style.configure("TButton", padding=(12, 8), relief="flat", borderwidth=1,
                    background=COLORS["surface"], focuscolor=COLORS["accent"], focusthickness=1)
    style.map("TButton", background=[("disabled", "#edf0ee"), ("pressed", "#dce5df"),
                                    ("active", "#edf3ef")],
              foreground=[("disabled", "#7a867e")],
              bordercolor=[("focus", COLORS["accent"])])
    style.configure("Primary.TButton", background=COLORS["accent"], foreground="white",
                    font=("Segoe UI", 10, "bold"), bordercolor=COLORS["accent"],
                    lightcolor=COLORS["accent"], darkcolor=COLORS["accent"], focuscolor="white")
    style.map("Primary.TButton", background=[("disabled", "#e0e6e2"),
                                             ("pressed", "#0f4c32"),
                                             ("active", COLORS["accent_hover"])],
              foreground=[("disabled", "#66746b"), ("!disabled", "white")],
              bordercolor=[("!disabled", COLORS["accent"])],
              lightcolor=[("!disabled", COLORS["accent"])],
              darkcolor=[("!disabled", COLORS["accent"])])
    style.configure("Icon.TButton", font=("Segoe MDL2 Assets", 12), padding=(8, 8))
    style.configure("Danger.Icon.TButton", foreground=COLORS["danger"])
    style.map("Danger.Icon.TButton", background=[("active", "#fce3e7")],
              foreground=[("!disabled", COLORS["danger"])])
    for name in ("TEntry", "TCombobox"):
        style.configure(name, padding=9, fieldbackground=COLORS["surface"],
                        insertcolor=COLORS["text"], selectbackground=COLORS["selected"],
                        selectforeground=COLORS["text"])
        style.map(name, bordercolor=[("focus", COLORS["accent"])],
                  lightcolor=[("focus", COLORS["accent"])],
                  darkcolor=[("focus", COLORS["accent"])])
    style.configure("Treeview", rowheight=42, background=COLORS["surface"],
                    fieldbackground=COLORS["surface"], borderwidth=0)
    style.map("Treeview", background=[("selected", COLORS["selected"])],
              foreground=[("selected", COLORS["text"])])
    style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"),
                    padding=(12, 10), background="#eaf0ec", relief="flat")
    style.map("Treeview.Heading", background=[("active", "#eaf0ec")])
    style.configure("TScrollbar", background="#c5d1c9", troughcolor=COLORS["background"],
                    borderwidth=0, arrowsize=12, relief="flat")
    style.map("TScrollbar", background=[("active", "#a2b7aa")])
    style.configure("Day.TButton", padding=(4, 6), borderwidth=0)
    style.configure("Selected.Day.TButton", background=COLORS["accent"], foreground="white")
    style.map("Selected.Day.TButton", background=[("active", COLORS["accent_hover"])],
              foreground=[("!disabled", "white")])


def center_window(window, parent):
    window.update_idletasks()
    width, height = window.winfo_reqwidth(), window.winfo_reqheight()
    x = parent.winfo_rootx() + (parent.winfo_width() - width) // 2
    y = parent.winfo_rooty() + (parent.winfo_height() - height) // 2
    x = max(0, min(x, window.winfo_screenwidth() - width))
    y = max(0, min(y, window.winfo_screenheight() - height - 60))
    window.geometry(f"+{x}+{y}")

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
    return f"{value.day:02d}.{value.month:02d}.{value.year:04d}"


def load_reminders():
    if not os.path.exists(DATA_FILE):
        return []

    with open(DATA_FILE, "r", encoding="utf-8") as file:
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


def save_reminders(reminders):
    write_json(DATA_FILE, reminders)


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


def is_active_data_file(path):
    if os.path.normcase(os.path.realpath(path)) == os.path.normcase(os.path.realpath(DATA_FILE)):
        return True
    try:
        return os.path.samefile(path, DATA_FILE)
    except FileNotFoundError:
        return False


def preserve_data_file():
    try:
        source = open(DATA_FILE, "rb")
    except FileNotFoundError:
        return None
    path = None
    try:
        with source, tempfile.NamedTemporaryFile(
            mode="wb", dir=os.path.dirname(DATA_FILE), delete=False,
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


def reminder_status(due_date, today=None):
    today = today or date.today()
    days_left = (due_date - today).days

    if days_left < 0:
        return f"Просрочено на {abs(days_left)} дн."
    if days_left == 0:
        return "Срок сегодня"
    return f"Осталось {days_left} дн."


class Tooltip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.window = None
        widget.bind("<Enter>", self.show, add="+")
        widget.bind("<Leave>", self.hide, add="+")
        widget.bind("<ButtonPress>", self.hide, add="+")
        widget.bind("<Destroy>", self.hide, add="+")

    def show(self, _event=None):
        if self.window is not None:
            return
        self.window = tk.Toplevel(self.widget)
        self.window.overrideredirect(True)
        self.window.geometry(
            f"+{self.widget.winfo_rootx()}+{self.widget.winfo_rooty() + self.widget.winfo_height() + 4}"
        )
        ttk.Label(self.window, text=self.text, padding=6, relief="solid").pack()

    def hide(self, _event=None):
        if self.window is not None:
            self.window.destroy()
            self.window = None


class DatePicker(tk.Toplevel):
    MONTHS = (
        "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
        "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
    )

    def __init__(self, parent, variable):
        super().__init__(parent)
        self.title("Выбрать дату")
        self.transient(parent)
        self.resizable(False, False)
        self.variable = variable
        try:
            self.selected = parse_date(variable.get())
        except ValueError:
            self.selected = date.today()
        self.year = self.selected.year
        self.month = self.selected.month
        self.configure(background=COLORS["surface"])
        body = ttk.Frame(self, padding=16)
        body.pack()
        navigation = ttk.Frame(body)
        navigation.pack(fill=tk.X)
        self.previous = ttk.Button(navigation, text="‹", width=3, command=lambda: self.move(-1))
        self.previous.pack(side=tk.LEFT)
        Tooltip(self.previous, "Предыдущий месяц")
        self.heading = ttk.Label(navigation, anchor=tk.CENTER, width=22, style="Field.TLabel")
        self.heading.pack(side=tk.LEFT, expand=True, fill=tk.X)
        self.following = ttk.Button(navigation, text="›", width=3, command=lambda: self.move(1))
        self.following.pack(side=tk.RIGHT)
        Tooltip(self.following, "Следующий месяц")
        self.days = ttk.Frame(body, padding=(0, 10, 0, 0))
        self.days.pack()
        ttk.Button(body, text="Сегодня", command=lambda: self.choose(date.today())).pack(pady=(10, 0))
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.bind("<Escape>", lambda _event: self.close())
        self.bind("<Return>", self.activate_focused_button)
        self.render()
        center_window(self, parent)
        self.grab_set()

    def activate_focused_button(self, event):
        if isinstance(event.widget, ttk.Button):
            event.widget.invoke()
            return "break"

    def move(self, delta):
        month_index = (self.year - 1) * 12 + self.month - 1 + delta
        if not 0 <= month_index < 9999 * 12:
            return
        year_index, month_index = divmod(month_index, 12)
        self.year, self.month = year_index + 1, month_index + 1
        self.render()

    def render(self):
        self.heading.configure(text=f"{self.MONTHS[self.month - 1]} {self.year}")
        self.previous.configure(state="disabled" if (self.year, self.month) == (1, 1) else "normal")
        self.following.configure(state="disabled" if (self.year, self.month) == (9999, 12) else "normal")
        for child in self.days.winfo_children():
            child.destroy()
        for column, name in enumerate(("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")):
            ttk.Label(self.days, text=name, anchor=tk.CENTER).grid(row=0, column=column, sticky=tk.EW)
        weeks = calendar.Calendar(firstweekday=0).monthdayscalendar(self.year, self.month)
        for row in range(6):
            for column in range(7):
                day = weeks[row][column] if row < len(weeks) else 0
                button = ttk.Button(self.days, width=4, text=str(day) if day else "",
                                    takefocus=bool(day), style="Day.TButton")
                button.grid(row=row + 1, column=column, padx=1, pady=1)
                if day:
                    value = date(self.year, self.month, day)
                    button.configure(command=lambda value=value: self.choose(value))
                    if value == self.selected:
                        button.configure(style="Selected.Day.TButton")
                        button.focus_set()
                else:
                    button.state(["disabled"])

    def choose(self, value):
        self.variable.set(format_date(value))
        self.close()

    def close(self):
        parent = self.master
        self.grab_release()
        self.destroy()
        if parent.winfo_exists():
            parent.grab_set()
            parent.calendar_button.focus_set()


class ReminderDialog(tk.Toplevel):
    def __init__(self, app, index=None):
        super().__init__(app.root)
        self.app = app
        self.index = index
        self.title("Новое напоминание" if index is None else "Изменить напоминание")
        self.transient(app.root)
        self.resizable(False, False)
        self.configure(background=COLORS["surface"])
        item = app.reminders[index] if index is not None else {}
        self.kind_var = tk.StringVar(self, value=item.get("kind", DEFAULT_TYPES[0]))
        self.date_var = tk.StringVar(self, value=item.get("due_date", ""))
        self.note_var = tk.StringVar(self, value=item.get("note", ""))
        header = ttk.Frame(self, padding=(24, 20, 24, 0))
        header.pack(fill=tk.X)
        ttk.Label(header, text=self.title(), style="DialogTitle.TLabel").pack(anchor=tk.W)
        body = ttk.Frame(self, padding=24)
        body.pack(fill=tk.BOTH, expand=True)
        body.columnconfigure(0, weight=1)
        ttk.Label(body, text="Напоминание", style="Field.TLabel").grid(row=0, column=0, sticky=tk.W)
        self.kind_entry = ttk.Combobox(body, textvariable=self.kind_var, values=DEFAULT_TYPES, width=40)
        self.kind_entry.grid(row=1, column=0, sticky=tk.EW, pady=(4, 14))
        ttk.Label(body, text="Дата (ДД.ММ.ГГГГ)", style="Field.TLabel").grid(row=2, column=0, sticky=tk.W)
        date_row = ttk.Frame(body)
        date_row.grid(row=3, column=0, sticky=tk.EW, pady=(4, 14))
        self.date_entry = ttk.Entry(date_row, textvariable=self.date_var, width=16)
        self.date_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.calendar_button = ttk.Button(date_row, text="Календарь", command=self.open_calendar)
        self.calendar_button.pack(side=tk.LEFT, padx=(8, 0))
        self.calendar_button.bind("<Return>", self.open_calendar)
        ttk.Label(body, text="Заметка (необязательно)", style="Field.TLabel").grid(row=4, column=0, sticky=tk.W)
        ttk.Entry(body, textvariable=self.note_var).grid(row=5, column=0, sticky=tk.EW, pady=(4, 20))
        actions = ttk.Frame(body)
        actions.grid(row=6, column=0, sticky=tk.E)
        ttk.Button(actions, text="Отмена", command=self.close).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(actions, text="Сохранить", style="Primary.TButton", command=self.save).pack(side=tk.LEFT)
        self.bind("<Return>", self.on_enter)
        self.bind("<Escape>", lambda _event: self.close())
        self.protocol("WM_DELETE_WINDOW", self.close)
        center_window(self, app.root)
        self.grab_set()
        self.date_entry.focus_set()

    def on_enter(self, event):
        if isinstance(event.widget, ttk.Button):
            event.widget.invoke()
        else:
            self.save()
        return "break"

    def open_calendar(self, _event=None):
        DatePicker(self, self.date_var)
        return "break"

    def save(self):
        kind = self.kind_var.get().strip()
        if not kind:
            messagebox.showerror(APP_TITLE, "Введите или выберите название напоминания.", parent=self)
            self.kind_entry.focus_set()
            return
        try:
            due_date = parse_date(self.date_var.get())
        except ValueError:
            messagebox.showerror(APP_TITLE, "Введите существующую дату, например 25.12.2026.", parent=self)
            self.date_entry.focus_set()
            return
        reminder = {"kind": kind, "due_date": format_date(due_date), "note": self.note_var.get().strip()}
        updated = list(self.app.reminders)
        if self.index is None:
            updated.append(reminder)
        else:
            updated[self.index] = reminder
        if self.app.commit(updated, parent=self, selected_item=reminder):
            hidden = self.app.urgent_only.get() and self.app.selected_index() is None
            self.close()
            if hidden:
                messagebox.showinfo(
                    APP_TITLE, "Запись сохранена и скрыта фильтром «Только срочные».",
                    parent=self.app.root,
                )

    def close(self):
        self.grab_release()
        self.app.editor = None
        self.destroy()
        self.app.tree.focus_set()


class CarReminderApp:
    def __init__(self, root):
        self.root = root
        root.title(APP_TITLE)
        icon = os.path.join(os.path.dirname(os.path.abspath(__file__)), "car-reminder.ico")
        if os.name == "nt" and os.path.isfile(icon):
            try:
                root.iconbitmap(default=icon)
            except tk.TclError:
                pass
        root.geometry("940x540")
        root.minsize(720, 380)
        self.editor = None
        self.load_error = False
        self.last_deleted = None
        try:
            self.reminders = load_reminders()
        except (OSError, ValueError):
            self.reminders = []
            self.load_error = True
        self.current_day = date.today()
        self.build_ui()
        self.refresh_table()
        self.timer = root.after(30_000, self.check_day)
        root.protocol("WM_DELETE_WINDOW", self.close)
        if self.load_error:
            messagebox.showerror(
                APP_TITLE,
                "Не удалось прочитать reminders.json. Исходный файл сохранён. "
                "Можно восстановить данные из копии через меню «Данные».",
                parent=root,
            )

    def build_ui(self):
        apply_theme(self.root)
        toolbar = ttk.Frame(self.root, padding=(20, 18))
        toolbar.pack(fill=tk.X)
        brand = ttk.Frame(toolbar)
        brand.pack(side=tk.LEFT)
        ttk.Label(brand, text="\ue804", style="Car.TLabel").pack(side=tk.LEFT, padx=(0, 12))
        ttk.Label(brand, text="Сроки автомобиля", style="Title.TLabel").pack(side=tk.LEFT)
        self.add_button = ttk.Button(toolbar, text="+ Добавить", style="Primary.TButton", command=self.open_editor)
        self.add_button.pack(side=tk.RIGHT)
        if self.load_error:
            self.add_button.state(["disabled"])
        data_button = ttk.Menubutton(toolbar, text="Данные")
        data_button.pack(side=tk.RIGHT, padx=(0, 8))
        data_menu = tk.Menu(data_button, tearoff=False)
        data_menu.add_command(label="Сохранить копию…", command=self.export_backup)
        data_menu.add_command(label="Восстановить из копии…", command=self.restore_backup)
        if self.load_error:
            data_menu.entryconfigure(0, state=tk.DISABLED)
        self.data_menu = data_menu
        data_button.configure(menu=data_menu)
        self.actions = ttk.Frame(toolbar)
        self.delete_button = ttk.Button(
            self.actions, text="\ue74d", width=3, style="Danger.Icon.TButton", command=self.delete_selected,
        )
        self.delete_button.pack(side=tk.RIGHT, padx=(8, 12))
        Tooltip(self.delete_button, "Удалить")
        ttk.Button(self.actions, text="Изменить", command=self.edit_selected).pack(side=tk.RIGHT)
        ttk.Separator(self.root).pack(fill=tk.X)
        container = ttk.Frame(self.root, padding=(20, 0, 20, 16), style="Page.TFrame")
        container.pack(fill=tk.BOTH, expand=True)
        self.undo_bar = ttk.Frame(container, style="Page.TFrame")
        ttk.Label(self.undo_bar, text="Запись удалена", style="Summary.TLabel").pack(side=tk.LEFT)
        ttk.Button(self.undo_bar, text="Отменить удаление", command=self.undo_delete).pack(side=tk.RIGHT)
        overview = ttk.Frame(container, style="Page.TFrame")
        overview.pack(fill=tk.X, pady=(16, 16))
        self.urgent_only = tk.BooleanVar(master=self.root, value=False)
        ttk.Style(self.root).configure("Overview.TCheckbutton", background=COLORS["background"])
        ttk.Checkbutton(
            overview, text="Только срочные", variable=self.urgent_only,
            command=self.apply_filter, style="Overview.TCheckbutton",
        ).pack(side=tk.RIGHT, padx=(12, 0))
        self.summary = ttk.Label(overview, anchor=tk.W, style="Summary.TLabel")
        self.summary.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.summary.bind("<Configure>", lambda event: self.summary.configure(wraplength=max(1, event.width)))
        list_frame = ttk.Frame(container)
        list_frame.pack(fill=tk.BOTH, expand=True)
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)
        columns = ("kind", "due_date", "status", "note")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="browse")
        for name, title, width, minimum in (
            ("kind", "Напоминание", 270, 225),
            ("due_date", "Дата", 110, 100),
            ("status", "Срок", 185, 180),
            ("note", "Заметка", 270, 160),
        ):
            self.tree.heading(name, text=title, anchor=tk.W)
            self.tree.column(name, width=width, minwidth=minimum, anchor=tk.W)
        vertical = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        horizontal = ttk.Scrollbar(list_frame, orient=tk.HORIZONTAL, command=self.tree.xview)
        def update_scrollbar(scrollbar, first, last):
            scrollbar.set(first, last)
            if float(first) <= 0 and float(last) >= 1:
                scrollbar.grid_remove()
            else:
                scrollbar.grid()

        self.tree.configure(
            yscrollcommand=lambda first, last: update_scrollbar(vertical, first, last),
            xscrollcommand=lambda first, last: update_scrollbar(horizontal, first, last),
        )
        self.tree.grid(row=0, column=0, sticky=tk.NSEW)
        vertical.grid(row=0, column=1, sticky=tk.NS)
        horizontal.grid(row=1, column=0, sticky=tk.EW)
        self.empty_label = ttk.Label(self.tree, text="Напоминаний пока нет", anchor=tk.CENTER, style="Empty.TLabel")
        self.tree.tag_configure("overdue", background=COLORS["danger_background"], foreground=COLORS["danger"])
        self.tree.tag_configure("soon", background=COLORS["warning_background"], foreground=COLORS["warning"])
        self.tree.tag_configure("alternate", background="#f8faf9")
        self.tree.bind("<<TreeviewSelect>>", self.on_select)
        self.tree.bind("<Double-1>", self.on_double_click)
        self.tree.bind("<Return>", self.edit_selected)
        self.tree.bind("<Delete>", self.delete_selected)
        self.tree.bind("<Escape>", self.clear_selection)

    def selected_index(self):
        selected = self.tree.selection()
        return int(selected[0]) if selected else None

    def apply_filter(self):
        index = self.selected_index()
        selected_item = self.reminders[index] if index is not None else None
        self.refresh_table(selected_item)

    def open_editor(self, index=None):
        if self.load_error:
            return
        if self.editor is not None:
            self.editor.lift()
            return
        self.editor = ReminderDialog(self, index)

    def edit_selected(self, _event=None):
        index = self.selected_index()
        if index is not None:
            self.open_editor(index)

    def on_double_click(self, event):
        row = self.tree.identify_row(event.y)
        if row and self.tree.identify_region(event.x, event.y) == "cell":
            self.tree.selection_set(row)
            self.open_editor(int(row))

    def clear_selection(self, _event=None):
        self.tree.selection_remove(self.tree.selection())
        self.on_select()

    def on_select(self, _event=None):
        if self.selected_index() is None:
            self.actions.pack_forget()
        else:
            self.actions.pack(side=tk.RIGHT)

    def commit(self, updated, parent=None, selected_item=None, restoring=False):
        if self.load_error and not restoring:
            return False
        try:
            save_reminders(updated)
        except (OSError, UnicodeError):
            messagebox.showerror(
                APP_TITLE,
                "Не удалось сохранить изменения. Проверьте доступ к папке и свободное место на диске. "
                "Изменения не применены.",
                parent=parent or self.root,
            )
            return False
        self.reminders = updated
        if restoring:
            self.load_error = False
            self.add_button.state(["!disabled"])
            self.data_menu.entryconfigure(0, state=tk.NORMAL)
            self.last_deleted = None
            self.undo_bar.pack_forget()
        self.refresh_table(selected_item)
        return True

    def export_backup(self):
        if self.load_error:
            return
        path = filedialog.asksaveasfilename(
            parent=self.root, title="Сохранить копию напоминаний",
            defaultextension=".json", filetypes=[("Файл JSON", "*.json")],
            initialfile=f"car-reminders-backup-{date.today().isoformat()}.json",
        )
        if not path:
            return
        try:
            if is_active_data_file(path):
                raise ValueError("Выберите другой файл: это рабочий файл напоминаний.")
            write_json(path, {"format": BACKUP_FORMAT, "version": 1, "reminders": self.reminders})
        except (OSError, ValueError) as error:
            messagebox.showerror(APP_TITLE, f"Не удалось сохранить копию.\n{error}", parent=self.root)
            return
        messagebox.showinfo(APP_TITLE, f"Копия сохранена. Записей: {len(self.reminders)}.", parent=self.root)

    def restore_backup(self):
        path = filedialog.askopenfilename(
            parent=self.root, title="Восстановить из копии", filetypes=[("Файл JSON", "*.json")],
        )
        if not path:
            return
        try:
            if is_active_data_file(path):
                raise ValueError("Выберите копию, а не рабочий файл напоминаний.")
            restored = read_backup(path)
        except (OSError, ValueError) as error:
            messagebox.showerror(APP_TITLE, f"Не удалось прочитать копию.\n{error}", parent=self.root)
            return
        current = "Рабочий файл не читается." if self.load_error else f"Сейчас записей: {len(self.reminders)}."
        if not messagebox.askyesno(
            APP_TITLE, f"{current}\nЗаписей в копии: {len(restored)}.\n\n"
            "Заменить текущие записи? Если рабочий файл существует, его копия будет сохранена.",
            default=messagebox.NO, parent=self.root,
        ):
            return
        try:
            safety_path = preserve_data_file()
        except OSError as error:
            messagebox.showerror(APP_TITLE, f"Не удалось сохранить прежние данные.\n{error}", parent=self.root)
            return
        if self.commit(restored, restoring=True):
            detail = f"\nПрежний файл: {safety_path}" if safety_path else ""
            messagebox.showinfo(APP_TITLE, f"Восстановлено записей: {len(restored)}.{detail}", parent=self.root)

    def refresh_table(self, selected_item=None):
        def sort_key(item):
            try:
                return parse_date(item["due_date"])
            except ValueError:
                return date.max

        self.reminders.sort(key=sort_key)
        self.tree.delete(*self.tree.get_children())
        today = date.today()
        overdue = soon = invalid = 0
        for index, item in enumerate(self.reminders):
            tag = "alternate" if index % 2 else ""
            try:
                due_date = parse_date(item["due_date"])
            except ValueError:
                status, tag = "Ошибка даты", "overdue"
                invalid += 1
            else:
                days_left = (due_date - today).days
                status = reminder_status(due_date, today)
                if days_left < 0:
                    tag = "overdue"
                    overdue += 1
                elif days_left <= WARNING_DAYS:
                    tag = "soon"
                    soon += 1
                elif self.urgent_only.get():
                    continue
            self.tree.insert(
                "", tk.END, iid=str(index),
                values=(item["kind"], item["due_date"], status, item.get("note", "")),
                tags=(tag,) if tag else (),
            )
            if item is selected_item:
                self.tree.selection_set(str(index))
                self.tree.focus(str(index))
                self.tree.see(str(index))
        summary = (
            f"Всего: {len(self.reminders)}    ·    Просрочено: {overdue}"
            f"    ·    В ближайшие {WARNING_DAYS} дней: {soon}"
        )
        if invalid:
            summary += f"    ·    Ошибка даты: {invalid}"
        self.summary.configure(text="Файл напоминаний недоступен" if self.load_error else summary)
        if self.tree.get_children() or self.load_error:
            self.empty_label.place_forget()
        else:
            self.empty_label.configure(text=(
                "Срочных напоминаний нет" if self.urgent_only.get() else "Напоминаний пока нет"
            ))
            self.empty_label.place(relx=0.5, rely=0.5, anchor=tk.CENTER)
        self.on_select()

    def delete_selected(self, _event=None):
        index = self.selected_index()
        if index is None:
            return
        item = self.reminders[index]
        if messagebox.askyesno(APP_TITLE, f"Удалить напоминание «{item['kind']}»?", parent=self.root):
            updated = list(self.reminders)
            del updated[index]
            if self.commit(updated):
                self.last_deleted = item
                self.undo_bar.pack(side=tk.BOTTOM, fill=tk.X, pady=(8, 0), before=self.summary.master)

    def undo_delete(self):
        item = self.last_deleted
        if item is not None and self.commit([*self.reminders, item], selected_item=item):
            self.last_deleted = None
            self.undo_bar.pack_forget()

    def check_day(self):
        today = date.today()
        # Keep editor indexes stable until the modal form has closed.
        if today != self.current_day and self.editor is None:
            index = self.selected_index()
            item = self.reminders[index] if index is not None else None
            self.current_day = today
            self.refresh_table(item)
        self.timer = self.root.after(30_000, self.check_day)

    def close(self):
        self.root.after_cancel(self.timer)
        self.root.destroy()

def run_app():
    instance = None
    try:
        if os.name == "nt":
            from windows_instance import WindowsInstance

            try:
                instance = WindowsInstance(DATA_FILE)
            except OSError:
                root = tk.Tk()
                root.withdraw()
                messagebox.showerror(APP_TITLE, "Не удалось проверить, запущена ли программа.", parent=root)
                root.destroy()
                return
            if not instance.primary:
                return

        root = tk.Tk()
        app = CarReminderApp(root)
        if instance is not None:
            def check_activation():
                if instance.activation_requested():
                    root.deiconify()
                    root.lift()
                    active = root.grab_current()
                    target = active.winfo_toplevel() if active is not None else root
                    target.lift()
                    target.focus_force()
                root.after(250, check_activation)

            root.after(250, check_activation)
        root.mainloop()
    finally:
        if instance is not None:
            instance.close()


if __name__ == "__main__":
    run_app()
