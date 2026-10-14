"""
Tkinter GUI для Mini CRM.

Запуск:
    python -m gui.app
    # или напрямую:
    python gui/app.py
"""

import os
import sys
import threading
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

import requests

API_BASE = os.getenv("CRM_API_URL", "http://localhost:8000")

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def api(method: str, path: str, **kwargs):
    url = f"{API_BASE}{path}"
    try:
        resp = getattr(requests, method)(url, timeout=10, **kwargs)
        resp.raise_for_status()
        if resp.status_code == 204:
            return None
        return resp.json()
    except requests.exceptions.ConnectionError:
        messagebox.showerror("Ошибка", f"Нет подключения к API: {API_BASE}")
        return None
    except requests.exceptions.HTTPError as e:
        messagebox.showerror("Ошибка API", str(e))
        return None


# ---------------------------------------------------------------------------
# Main application
# ---------------------------------------------------------------------------

class CRMApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Mini CRM")
        self.geometry("1100x700")
        self.resizable(True, True)
        self._build_ui()
        self._refresh_all()

    def _build_ui(self):
        # Top stats bar
        stats_frame = tk.Frame(self, bg="#2c3e50", height=60)
        stats_frame.pack(fill="x")

        self.stat_clients = self._stat_label(stats_frame, "Клиенты", "0")
        self.stat_deals = self._stat_label(stats_frame, "Сделки", "0")
        self.stat_revenue = self._stat_label(stats_frame, "Выручка, ₽", "0")
        self.stat_pipeline = self._stat_label(stats_frame, "В работе, ₽", "0")
        self.stat_tasks = self._stat_label(stats_frame, "Задачи (откр.)", "0")

        # Notebook tabs
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self.clients_tab = ClientsTab(notebook, self)
        self.deals_tab = DealsTab(notebook, self)
        self.tasks_tab = TasksTab(notebook, self)
        self.google_tab = GoogleTab(notebook, self)

        notebook.add(self.clients_tab, text="  Клиенты  ")
        notebook.add(self.deals_tab, text="  Сделки  ")
        notebook.add(self.tasks_tab, text="  Задачи  ")
        notebook.add(self.google_tab, text="  Google Export  ")

    def _stat_label(self, parent, title, value):
        frame = tk.Frame(parent, bg="#2c3e50")
        frame.pack(side="left", padx=20, pady=8)
        tk.Label(frame, text=title, fg="#95a5a6", bg="#2c3e50", font=("Arial", 9)).pack()
        val_label = tk.Label(frame, text=value, fg="white", bg="#2c3e50", font=("Arial", 14, "bold"))
        val_label.pack()
        return val_label

    def _refresh_all(self):
        stats = api("get", "/api/stats")
        if stats:
            self.stat_clients.config(text=str(stats["total_clients"]))
            self.stat_deals.config(text=str(stats["total_deals"]))
            self.stat_revenue.config(text=f"{stats['revenue']:,.0f}")
            self.stat_pipeline.config(text=f"{stats['pipeline']:,.0f}")
            self.stat_tasks.config(text=str(stats["open_tasks"]))

        self.clients_tab.refresh()
        self.deals_tab.refresh()
        self.tasks_tab.refresh()


# ---------------------------------------------------------------------------
# Clients tab
# ---------------------------------------------------------------------------

class ClientsTab(tk.Frame):
    COLS = ("id", "Имя", "Email", "Телефон", "Компания", "Город", "Статус")
    STATUSES = ["lead", "active", "churned"]

    def __init__(self, parent, app: CRMApp):
        super().__init__(parent)
        self.app = app
        self._build()

    def _build(self):
        toolbar = tk.Frame(self)
        toolbar.pack(fill="x", pady=4)

        tk.Label(toolbar, text="Поиск:").pack(side="left")
        self.search_var = tk.StringVar()
        tk.Entry(toolbar, textvariable=self.search_var, width=25).pack(side="left", padx=4)
        tk.Button(toolbar, text="Найти", command=self.refresh).pack(side="left")

        tk.Label(toolbar, text="  Статус:").pack(side="left")
        self.status_var = tk.StringVar(value="")
        ttk.Combobox(toolbar, textvariable=self.status_var, values=[""] + self.STATUSES, width=12, state="readonly").pack(side="left", padx=4)
        self.status_var.trace_add("write", lambda *_: self.refresh())

        tk.Button(toolbar, text="+ Добавить", command=self._add_dialog, bg="#27ae60", fg="white").pack(side="right", padx=4)
        tk.Button(toolbar, text="Обновить", command=self.refresh).pack(side="right")

        self.tree = ttk.Treeview(self, columns=self.COLS, show="headings", height=22)
        widths = [40, 180, 200, 130, 160, 100, 80]
        for col, w in zip(self.COLS, widths):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", self._edit_dialog)

        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")

    def refresh(self):
        params = {}
        if self.search_var.get():
            params["search"] = self.search_var.get()
        if self.status_var.get():
            params["status"] = self.status_var.get()
        clients = api("get", "/api/clients", params=params) or []
        self.tree.delete(*self.tree.get_children())
        for c in clients:
            self.tree.insert("", "end", iid=c["id"], values=(
                c["id"], c["name"], c.get("email", ""), c.get("phone", ""),
                c.get("company", ""), c.get("city", ""), c["status"],
            ))

    def _add_dialog(self):
        ClientDialog(self, self.app, mode="add")

    def _edit_dialog(self, event):
        sel = self.tree.selection()
        if sel:
            ClientDialog(self, self.app, mode="edit", client_id=int(sel[0]))


class ClientDialog(tk.Toplevel):
    FIELDS = [("Имя*", "name"), ("Email", "email"), ("Телефон", "phone"),
              ("Компания", "company"), ("Город", "city"), ("Заметки", "notes")]

    def __init__(self, parent_tab: ClientsTab, app: CRMApp, mode="add", client_id=None):
        super().__init__(app)
        self.parent_tab = parent_tab
        self.app = app
        self.mode = mode
        self.client_id = client_id
        self.title("Добавить клиента" if mode == "add" else "Редактировать клиента")
        self.resizable(False, False)
        self.entries = {}

        for label, key in self.FIELDS:
            row = tk.Frame(self)
            row.pack(fill="x", padx=10, pady=3)
            tk.Label(row, text=label, width=12, anchor="e").pack(side="left")
            e = tk.Entry(row, width=35)
            e.pack(side="left")
            self.entries[key] = e

        row = tk.Frame(self)
        row.pack(fill="x", padx=10, pady=3)
        tk.Label(row, text="Статус", width=12, anchor="e").pack(side="left")
        self.status_var = tk.StringVar(value="lead")
        ttk.Combobox(row, textvariable=self.status_var,
                     values=["lead", "active", "churned"], width=33, state="readonly").pack(side="left")

        if mode == "edit" and client_id:
            c = api("get", f"/api/clients/{client_id}")
            if c:
                for key, e in self.entries.items():
                    e.insert(0, c.get(key) or "")
                self.status_var.set(c["status"])

        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=8)
        tk.Button(btn_frame, text="Сохранить", command=self._save, bg="#2980b9", fg="white", width=12).pack(side="left", padx=4)
        if mode == "edit":
            tk.Button(btn_frame, text="Удалить", command=self._delete, bg="#e74c3c", fg="white", width=12).pack(side="left", padx=4)
        tk.Button(btn_frame, text="Отмена", command=self.destroy, width=12).pack(side="left")

    def _save(self):
        data = {k: e.get().strip() or None for k, e in self.entries.items()}
        data["status"] = self.status_var.get()
        if not data.get("name"):
            messagebox.showwarning("Ошибка", "Имя обязательно", parent=self)
            return
        if self.mode == "add":
            api("post", "/api/clients", json=data)
        else:
            api("patch", f"/api/clients/{self.client_id}", json=data)
        self.parent_tab.refresh()
        self.app._refresh_all()
        self.destroy()

    def _delete(self):
        if messagebox.askyesno("Удалить?", "Удалить клиента и все его данные?", parent=self):
            api("delete", f"/api/clients/{self.client_id}")
            self.parent_tab.refresh()
            self.app._refresh_all()
            self.destroy()


# ---------------------------------------------------------------------------
# Deals tab
# ---------------------------------------------------------------------------

class DealsTab(tk.Frame):
    COLS = ("id", "Клиент", "Сделка", "Продукт", "Сумма, ₽", "Стадия")
    STAGES = ["new", "negotiation", "won", "lost"]

    def __init__(self, parent, app: CRMApp):
        super().__init__(parent)
        self.app = app
        self._build()

    def _build(self):
        toolbar = tk.Frame(self)
        toolbar.pack(fill="x", pady=4)

        tk.Label(toolbar, text="Стадия:").pack(side="left")
        self.stage_var = tk.StringVar(value="")
        ttk.Combobox(toolbar, textvariable=self.stage_var, values=[""] + self.STAGES, width=14, state="readonly").pack(side="left", padx=4)
        self.stage_var.trace_add("write", lambda *_: self.refresh())

        tk.Button(toolbar, text="+ Добавить", command=self._add_dialog, bg="#27ae60", fg="white").pack(side="right", padx=4)
        tk.Button(toolbar, text="Обновить", command=self.refresh).pack(side="right")

        self.tree = ttk.Treeview(self, columns=self.COLS, show="headings", height=22)
        widths = [40, 180, 220, 160, 110, 100]
        for col, w in zip(self.COLS, widths):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", self._edit_dialog)

        self._clients_cache = {}

    def refresh(self):
        params = {}
        if self.stage_var.get():
            params["stage"] = self.stage_var.get()
        deals = api("get", "/api/deals", params=params) or []
        clients = api("get", "/api/clients", params={"limit": 500}) or []
        self._clients_cache = {c["id"]: c["name"] for c in clients}

        self.tree.delete(*self.tree.get_children())
        for d in deals:
            self.tree.insert("", "end", iid=d["id"], values=(
                d["id"],
                self._clients_cache.get(d["client_id"], d["client_id"]),
                d["title"],
                d.get("product") or "",
                f"{d['amount']:,.0f}",
                d["stage"],
            ))

    def _add_dialog(self):
        DealDialog(self, self.app, mode="add", clients_cache=self._clients_cache)

    def _edit_dialog(self, event):
        sel = self.tree.selection()
        if sel:
            DealDialog(self, self.app, mode="edit", deal_id=int(sel[0]), clients_cache=self._clients_cache)


class DealDialog(tk.Toplevel):
    def __init__(self, parent_tab: DealsTab, app: CRMApp, mode="add", deal_id=None, clients_cache=None):
        super().__init__(app)
        self.parent_tab = parent_tab
        self.app = app
        self.mode = mode
        self.deal_id = deal_id
        self.clients_cache = clients_cache or {}
        self.title("Добавить сделку" if mode == "add" else "Редактировать сделку")
        self.resizable(False, False)

        row = tk.Frame(self); row.pack(fill="x", padx=10, pady=3)
        tk.Label(row, text="Клиент*", width=12, anchor="e").pack(side="left")
        self.client_var = tk.StringVar()
        client_names = [f"{cid}: {name}" for cid, name in self.clients_cache.items()]
        self.client_combo = ttk.Combobox(row, textvariable=self.client_var, values=client_names, width=33)
        self.client_combo.pack(side="left")

        self.entries = {}
        for label, key in [("Название*", "title"), ("Продукт", "product"), ("Сумма", "amount"), ("Заметки", "notes")]:
            r = tk.Frame(self); r.pack(fill="x", padx=10, pady=3)
            tk.Label(r, text=label, width=12, anchor="e").pack(side="left")
            e = tk.Entry(r, width=35); e.pack(side="left")
            self.entries[key] = e

        row2 = tk.Frame(self); row2.pack(fill="x", padx=10, pady=3)
        tk.Label(row2, text="Стадия", width=12, anchor="e").pack(side="left")
        self.stage_var = tk.StringVar(value="new")
        ttk.Combobox(row2, textvariable=self.stage_var, values=["new", "negotiation", "won", "lost"], width=33, state="readonly").pack(side="left")

        if mode == "edit" and deal_id:
            d = api("get", f"/api/deals/{deal_id}")
            if d:
                cname = self.clients_cache.get(d["client_id"], "")
                self.client_var.set(f"{d['client_id']}: {cname}")
                self.entries["title"].insert(0, d.get("title") or "")
                self.entries["product"].insert(0, d.get("product") or "")
                self.entries["amount"].insert(0, str(d.get("amount") or 0))
                self.entries["notes"].insert(0, d.get("notes") or "")
                self.stage_var.set(d["stage"])

        btn_frame = tk.Frame(self); btn_frame.pack(pady=8)
        tk.Button(btn_frame, text="Сохранить", command=self._save, bg="#2980b9", fg="white", width=12).pack(side="left", padx=4)
        if mode == "edit":
            tk.Button(btn_frame, text="Удалить", command=self._delete, bg="#e74c3c", fg="white", width=12).pack(side="left", padx=4)
        tk.Button(btn_frame, text="Отмена", command=self.destroy, width=12).pack(side="left")

    def _get_client_id(self):
        val = self.client_var.get()
        if ":" in val:
            return int(val.split(":")[0])
        return None

    def _save(self):
        client_id = self._get_client_id()
        if not client_id:
            messagebox.showwarning("Ошибка", "Выберите клиента", parent=self); return
        title = self.entries["title"].get().strip()
        if not title:
            messagebox.showwarning("Ошибка", "Название обязательно", parent=self); return
        try:
            amount = float(self.entries["amount"].get() or 0)
        except ValueError:
            messagebox.showwarning("Ошибка", "Сумма должна быть числом", parent=self); return

        data = {
            "client_id": client_id,
            "title": title,
            "product": self.entries["product"].get().strip() or None,
            "amount": amount,
            "notes": self.entries["notes"].get().strip() or None,
            "stage": self.stage_var.get(),
        }
        if self.mode == "add":
            api("post", "/api/deals", json=data)
        else:
            api("patch", f"/api/deals/{self.deal_id}", json=data)
        self.parent_tab.refresh()
        self.app._refresh_all()
        self.destroy()

    def _delete(self):
        if messagebox.askyesno("Удалить?", "Удалить сделку?", parent=self):
            api("delete", f"/api/deals/{self.deal_id}")
            self.parent_tab.refresh()
            self.app._refresh_all()
            self.destroy()


# ---------------------------------------------------------------------------
# Tasks tab
# ---------------------------------------------------------------------------

class TasksTab(tk.Frame):
    COLS = ("id", "Клиент", "Задача", "Приоритет", "Статус", "Дедлайн")

    def __init__(self, parent, app: CRMApp):
        super().__init__(parent)
        self.app = app
        self._clients_cache = {}
        self._build()

    def _build(self):
        toolbar = tk.Frame(self)
        toolbar.pack(fill="x", pady=4)

        tk.Label(toolbar, text="Статус:").pack(side="left")
        self.status_var = tk.StringVar(value="")
        ttk.Combobox(toolbar, textvariable=self.status_var, values=["", "open", "in_progress", "done"], width=14, state="readonly").pack(side="left", padx=4)
        self.status_var.trace_add("write", lambda *_: self.refresh())

        tk.Button(toolbar, text="+ Добавить", command=self._add_dialog, bg="#27ae60", fg="white").pack(side="right", padx=4)
        tk.Button(toolbar, text="Обновить", command=self.refresh).pack(side="right")

        self.tree = ttk.Treeview(self, columns=self.COLS, show="headings", height=22)
        widths = [40, 180, 260, 90, 100, 130]
        for col, w in zip(self.COLS, widths):
            self.tree.heading(col, text=col)
            self.tree.column(col, width=w, anchor="w")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", self._edit_dialog)

    def refresh(self):
        params = {}
        if self.status_var.get():
            params["status"] = self.status_var.get()
        tasks = api("get", "/api/tasks", params=params) or []
        clients = api("get", "/api/clients", params={"limit": 500}) or []
        self._clients_cache = {c["id"]: c["name"] for c in clients}

        self.tree.delete(*self.tree.get_children())
        for t in tasks:
            due = t.get("due_date", "") or ""
            if due:
                due = due[:10]
            self.tree.insert("", "end", iid=t["id"], values=(
                t["id"],
                self._clients_cache.get(t["client_id"], t["client_id"]),
                t["title"],
                t["priority"],
                t["status"],
                due,
            ))

    def _add_dialog(self):
        TaskDialog(self, self.app, mode="add", clients_cache=self._clients_cache)

    def _edit_dialog(self, event):
        sel = self.tree.selection()
        if sel:
            TaskDialog(self, self.app, mode="edit", task_id=int(sel[0]), clients_cache=self._clients_cache)


class TaskDialog(tk.Toplevel):
    def __init__(self, parent_tab: TasksTab, app: CRMApp, mode="add", task_id=None, clients_cache=None):
        super().__init__(app)
        self.parent_tab = parent_tab
        self.app = app
        self.mode = mode
        self.task_id = task_id
        self.clients_cache = clients_cache or {}
        self.title("Добавить задачу" if mode == "add" else "Редактировать задачу")
        self.resizable(False, False)

        row = tk.Frame(self); row.pack(fill="x", padx=10, pady=3)
        tk.Label(row, text="Клиент*", width=12, anchor="e").pack(side="left")
        self.client_var = tk.StringVar()
        client_names = [f"{cid}: {name}" for cid, name in self.clients_cache.items()]
        ttk.Combobox(row, textvariable=self.client_var, values=client_names, width=33).pack(side="left")

        self.entries = {}
        for label, key in [("Название*", "title"), ("Описание", "description"), ("Дедлайн (YYYY-MM-DD)", "due_date")]:
            r = tk.Frame(self); r.pack(fill="x", padx=10, pady=3)
            tk.Label(r, text=label, width=22, anchor="e").pack(side="left")
            e = tk.Entry(r, width=28); e.pack(side="left")
            self.entries[key] = e

        row2 = tk.Frame(self); row2.pack(fill="x", padx=10, pady=3)
        tk.Label(row2, text="Приоритет", width=12, anchor="e").pack(side="left")
        self.priority_var = tk.StringVar(value="medium")
        ttk.Combobox(row2, textvariable=self.priority_var, values=["low", "medium", "high"], width=33, state="readonly").pack(side="left")

        row3 = tk.Frame(self); row3.pack(fill="x", padx=10, pady=3)
        tk.Label(row3, text="Статус", width=12, anchor="e").pack(side="left")
        self.status_var = tk.StringVar(value="open")
        ttk.Combobox(row3, textvariable=self.status_var, values=["open", "in_progress", "done"], width=33, state="readonly").pack(side="left")

        if mode == "edit" and task_id:
            t = api("get", f"/api/tasks/{task_id}")
            if t:
                cname = self.clients_cache.get(t["client_id"], "")
                self.client_var.set(f"{t['client_id']}: {cname}")
                self.entries["title"].insert(0, t.get("title") or "")
                self.entries["description"].insert(0, t.get("description") or "")
                due = (t.get("due_date") or "")[:10]
                self.entries["due_date"].insert(0, due)
                self.priority_var.set(t["priority"])
                self.status_var.set(t["status"])

        btn_frame = tk.Frame(self); btn_frame.pack(pady=8)
        tk.Button(btn_frame, text="Сохранить", command=self._save, bg="#2980b9", fg="white", width=12).pack(side="left", padx=4)
        if mode == "edit":
            tk.Button(btn_frame, text="Удалить", command=self._delete, bg="#e74c3c", fg="white", width=12).pack(side="left", padx=4)
        tk.Button(btn_frame, text="Отмена", command=self.destroy, width=12).pack(side="left")

    def _get_client_id(self):
        val = self.client_var.get()
        if ":" in val:
            return int(val.split(":")[0])
        return None

    def _save(self):
        client_id = self._get_client_id()
        if not client_id:
            messagebox.showwarning("Ошибка", "Выберите клиента", parent=self); return
        title = self.entries["title"].get().strip()
        if not title:
            messagebox.showwarning("Ошибка", "Название обязательно", parent=self); return

        due_raw = self.entries["due_date"].get().strip()
        due_date = None
        if due_raw:
            try:
                due_date = datetime.strptime(due_raw, "%Y-%m-%d").isoformat()
            except ValueError:
                messagebox.showwarning("Ошибка", "Дедлайн: формат YYYY-MM-DD", parent=self); return

        data = {
            "client_id": client_id,
            "title": title,
            "description": self.entries["description"].get().strip() or None,
            "priority": self.priority_var.get(),
            "status": self.status_var.get(),
            "due_date": due_date,
        }
        if self.mode == "add":
            api("post", "/api/tasks", json=data)
        else:
            api("patch", f"/api/tasks/{self.task_id}", json=data)
        self.parent_tab.refresh()
        self.app._refresh_all()
        self.destroy()

    def _delete(self):
        if messagebox.askyesno("Удалить?", "Удалить задачу?", parent=self):
            api("delete", f"/api/tasks/{self.task_id}")
            self.parent_tab.refresh()
            self.app._refresh_all()
            self.destroy()


# ---------------------------------------------------------------------------
# Google Export tab
# ---------------------------------------------------------------------------

class GoogleTab(tk.Frame):
    def __init__(self, parent, app: CRMApp):
        super().__init__(parent)
        self.app = app
        self._build()

    def _build(self):
        tk.Label(self, text="Экспорт в Google Drive", font=("Arial", 14, "bold")).pack(pady=20)

        # Settings
        settings_frame = tk.LabelFrame(self, text="Настройки Google API", padx=10, pady=10)
        settings_frame.pack(fill="x", padx=20, pady=10)

        tk.Label(settings_frame, text="Путь к service_account.json:").grid(row=0, column=0, sticky="e", pady=3)
        self.sa_var = tk.StringVar(value=os.getenv("GOOGLE_SERVICE_ACCOUNT", "google_integration/service_account.json"))
        tk.Entry(settings_frame, textvariable=self.sa_var, width=50).grid(row=0, column=1, padx=8)

        tk.Label(settings_frame, text="Путь к client_secret.json:").grid(row=1, column=0, sticky="e", pady=3)
        self.cs_var = tk.StringVar(value=os.getenv("GOOGLE_CLIENT_SECRET", "google_integration/client_secret.json"))
        tk.Entry(settings_frame, textvariable=self.cs_var, width=50).grid(row=1, column=1, padx=8)

        tk.Label(settings_frame, text="ID папки Google Drive (опционально):").grid(row=2, column=0, sticky="e", pady=3)
        self.folder_var = tk.StringVar(value=os.getenv("GOOGLE_FOLDER_ID", "1HZJC5XAILxPE-whrS1NaWa51stoXCUQ2"))
        tk.Entry(settings_frame, textvariable=self.folder_var, width=50).grid(row=2, column=1, padx=8)

        # Export buttons
        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=20)

        tk.Button(
            btn_frame, text="📊 Экспорт клиентов в Google Таблицу",
            command=lambda: self._export("clients"),
            bg="#2980b9", fg="white", width=40, height=2
        ).pack(pady=6)

        tk.Button(
            btn_frame, text="💼 Экспорт сделок в Google Таблицу",
            command=lambda: self._export("deals"),
            bg="#8e44ad", fg="white", width=40, height=2
        ).pack(pady=6)

        tk.Button(
            btn_frame, text="✅ Экспорт задач в Google Таблицу",
            command=lambda: self._export("tasks"),
            bg="#16a085", fg="white", width=40, height=2
        ).pack(pady=6)

        tk.Button(
            btn_frame, text="📂 Показать файлы в Drive",
            command=self._list_drive,
            bg="#7f8c8d", fg="white", width=40, height=2
        ).pack(pady=6)

        self.status_var = tk.StringVar(value="")
        tk.Label(self, textvariable=self.status_var, fg="#27ae60", font=("Arial", 11)).pack(pady=10)

        self.log_text = tk.Text(self, height=8, state="disabled")
        self.log_text.pack(fill="x", padx=20)

    def _log(self, msg: str):
        self.log_text.config(state="normal")
        self.log_text.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _export(self, entity: str):
        threading.Thread(target=self._do_export, args=(entity,), daemon=True).start()

    def _do_export(self, entity: str):
        try:
            import pickle
            from google_integration.google_drive import GoogleDrive, OAUTH_SCOPES
            from google.auth.transport.requests import Request
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
        except ImportError as e:
            self._log(f"Ошибка импорта: {e}")
            return

        sa_path = self.sa_var.get().strip()
        cs_path = self.cs_var.get().strip()
        folder_id = self.folder_var.get().strip() or None

        # Получаем OAuth2 credentials
        if os.path.exists(cs_path):
            token_path = os.path.join(os.path.dirname(cs_path), "token.pickle")
            creds = None
            if os.path.exists(token_path):
                with open(token_path, "rb") as f:
                    creds = pickle.load(f)
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(cs_path, OAUTH_SCOPES)
                    creds = flow.run_local_server(port=0)
                with open(token_path, "wb") as f:
                    pickle.dump(creds, f)
            drive_svc = build("drive", "v3", credentials=creds)
            sheets_svc = build("sheets", "v4", credentials=creds)
        elif os.path.exists(sa_path):
            from google.oauth2.service_account import Credentials
            creds = Credentials.from_service_account_file(sa_path, scopes=OAUTH_SCOPES)
            drive_svc = build("drive", "v3", credentials=creds)
            sheets_svc = build("sheets", "v4", credentials=creds)
        else:
            self._log("Не найден ни client_secret.json, ни service_account.json")
            return

        name = f"CRM_{entity}_{datetime.now().strftime('%Y-%m-%d_%H%M')}"
        self._log(f"Создаю таблицу «{name}»...")

        metadata = {"name": name, "mimeType": "application/vnd.google-apps.spreadsheet"}
        if folder_id:
            metadata["parents"] = [folder_id]
        file = drive_svc.files().create(body=metadata, fields="id,name").execute()
        file_id = file["id"]
        url = f"https://docs.google.com/spreadsheets/d/{file_id}/edit"
        self._log(f"Создана: {url}")

        data = api("get", f"/api/{entity}", params={"limit": 500}) or []
        if not data:
            self._log("Нет данных для экспорта")
            return

        headers = list(data[0].keys())
        rows = [[str(row.get(h) or "") for h in headers] for row in data]

        body = {"values": [headers] + rows}
        sheets_svc.spreadsheets().values().update(
            spreadsheetId=file_id,
            range="A1",
            valueInputOption="USER_ENTERED",
            body=body,
        ).execute()

        self._log(f"Экспортировано {len(rows)} строк. Ссылка: {url}")
        self.status_var.set(f"Готово: {url}")

    def _list_drive(self):
        threading.Thread(target=self._do_list_drive, daemon=True).start()

    def _do_list_drive(self):
        try:
            from google_integration.google_drive import GoogleDrive
        except ImportError as e:
            self._log(f"Ошибка импорта: {e}")
            return

        sa_path = self.sa_var.get().strip()
        cs_path = self.cs_var.get().strip()

        if os.path.exists(sa_path):
            drive = GoogleDrive(service_account_path=sa_path)
        elif os.path.exists(cs_path):
            drive = GoogleDrive(oauth_credentials_path=cs_path)
        else:
            self._log("Не найден файл credentials")
            return

        folder_id = self.folder_var.get().strip() or None
        files = drive.list_files(folder_id=folder_id)
        self._log(f"Файлов в Drive: {len(files)}")
        for f in files[:20]:
            self._log(f"  {f['name']} ({f.get('mimeType', '').split('.')[-1]})")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app = CRMApp()
    app.mainloop()
