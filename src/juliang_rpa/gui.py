from __future__ import annotations

import asyncio
import csv
from dataclasses import replace
from dataclasses import fields
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Callable

import yaml
from playwright.async_api import BrowserContext, Error as PlaywrightError

from .browser import (
    browser_mode_label,
    first_page,
    fresh_page,
    goto_base,
    goto_login,
    persistent_context,
    save_debug_snapshot,
)
from .config import DEFAULT_CONFIG_PATH, AppSettings, PROJECT_ROOT, load_settings
from .tasks.new_ad import NewAdOptions, run_new_ad


PRESET_PATH = PROJECT_ROOT / "config" / "ad_presets.yaml"

FIELD_SPECS: tuple[tuple[str, str, str], ...] = (
    ("account_id", "账户 ID", "entry"),
    ("mini_game_name", "字节小游戏名称", "entry"),
    ("mini_game_asset_id", "字节小游戏资产 ID", "entry"),
    ("mini_game_app_id", "字节小游戏 APP ID", "entry"),
    ("optimization_goal", "优化目标", "entry"),
    ("deep_optimization_goal", "深度优化目标", "entry"),
    ("douyin_id", "抖音号 ID", "entry"),
    ("douyin_name", "抖音号名称", "entry"),
    ("daily_budget", "日预算", "entry"),
    ("roi_coefficient", "ROI 系数", "entry"),
    ("ad_texts", "文案（每行一条）", "text"),
    ("mini_program_link", "小游戏链接", "text"),
    ("backup_site_link", "备用网页链接", "text"),
    ("product_name", "产品名称", "entry"),
    ("product_image_path", "产品主图图片", "file"),
    ("auto_add_videos", "自动添加视频", "checkbox"),
    ("auto_add_video_count", "自动添加视频数量", "choice"),
    ("specific_video_count", "指定添加视频数量", "entry"),
    ("change_douyin_nickname", "修改自定义抖音号昵称", "checkbox"),
    ("douyin_nickname", "自定义抖音号昵称", "entry"),
    ("submit_project", "提交项目", "checkbox"),
    ("product_selling_points", "产品卖点", "entry"),
    ("call_to_actions", "行动号召", "entry"),
    ("project_name_prefix", "项目名称前缀", "entry"),
)

EXTRA_CONFIG_LABELS: dict[str, str] = {
    "account_id_list": "账户 ID 列表（每行一个）",
    "batch_delay_seconds": "账号间等待秒数",
}


class JuliangRpaApp(tk.Tk):
    def __init__(self, config_path: Path = DEFAULT_CONFIG_PATH) -> None:
        super().__init__()
        self.title("巨量广告 RPA")
        self.geometry("1040x840")
        self.minsize(900, 700)

        self.config_path = config_path
        self.settings = load_settings(config_path)
        self.events: queue.Queue[tuple[str, str]] = queue.Queue()
        self.login_stop_event: threading.Event | None = None
        self.open_stop_event: threading.Event | None = None
        self.ad_context: BrowserContext | None = None
        self.ad_context_manager = None
        self.ad_loop = asyncio.new_event_loop()
        self.ad_loop_thread = threading.Thread(
            target=self._run_ad_loop,
            name="juliang-rpa-ad-browser-loop",
            daemon=True,
        )
        self.ad_loop_thread.start()
        self.busy = False

        self.field_vars: dict[str, tk.StringVar] = {}
        self.text_widgets: dict[str, tk.Text] = {}
        self.field_widgets: list[tk.Widget] = []
        self.preset_var = tk.StringVar()
        self.presets = self._load_presets()
        self.use_system_chrome_var = tk.BooleanVar(value=self.settings.browser.use_system_chrome)

        self._init_field_vars()
        self.account_queue_index = 0
        self.completed_account_ids: set[str] = set()
        self.batch_delay_var = tk.StringVar(value="8")
        self.account_queue_widgets: list[tk.Widget] = []
        self._build_ui()
        self._refresh_preset_combo()
        self._sync_account_list_from_text()
        self.after(150, self._poll_events)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _run_ad_loop(self) -> None:
        asyncio.set_event_loop(self.ad_loop)
        self.ad_loop.run_forever()

    def _init_field_vars(self) -> None:
        defaults = self._new_ad_defaults()
        for name, _, kind in FIELD_SPECS:
            if kind != "text":
                value = defaults.get(name, "")
                if kind == "checkbox":
                    value = "true" if bool(value) else "false"
                self.field_vars[name] = tk.StringVar(value=str(value))

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=3)
        self.rowconfigure(5, weight=1)

        header = ttk.Frame(self, padding=(16, 14, 16, 8))
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(1, weight=1)

        ttk.Label(header, text="巨量广告 RPA", font=("Microsoft YaHei UI", 16, "bold")).grid(
            row=0,
            column=0,
            sticky="w",
        )
        ttk.Label(header, text="登录态目录").grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Label(header, text=str(self.settings.browser.user_data_dir)).grid(
            row=1,
            column=1,
            sticky="ew",
            padx=(12, 0),
            pady=(10, 0),
        )
        ttk.Label(header, text="登录地址").grid(row=2, column=0, sticky="w", pady=(6, 0))
        ttk.Label(header, text=self.settings.login_url).grid(
            row=2,
            column=1,
            sticky="ew",
            padx=(12, 0),
            pady=(6, 0),
        )
        ttk.Label(header, text="浏览器").grid(row=3, column=0, sticky="w", pady=(6, 0))
        browser_row = ttk.Frame(header)
        browser_row.grid(row=3, column=1, sticky="ew", padx=(12, 0), pady=(6, 0))
        browser_row.columnconfigure(1, weight=1)
        self.use_system_chrome_check = ttk.Checkbutton(
            browser_row,
            text="优先使用本机 Chrome（失败则使用项目内 Chromium）",
            variable=self.use_system_chrome_var,
            command=self._refresh_browser_settings,
        )
        self.use_system_chrome_check.grid(row=0, column=0, sticky="w")
        self.browser_mode_var = tk.StringVar(value=browser_mode_label(self.settings))
        ttk.Label(browser_row, textvariable=self.browser_mode_var).grid(
            row=0,
            column=1,
            sticky="e",
            padx=(12, 0),
        )

        presets = ttk.LabelFrame(self, text="配置方案", padding=(16, 10))
        presets.grid(row=1, column=0, sticky="ew", padx=16, pady=(4, 8))
        presets.columnconfigure(1, weight=1)

        ttk.Label(presets, text="当前方案").grid(row=0, column=0, sticky="w")
        self.preset_combo = ttk.Combobox(presets, textvariable=self.preset_var, state="readonly")
        self.preset_combo.grid(row=0, column=1, sticky="ew", padx=(10, 8))
        self.preset_combo.bind("<<ComboboxSelected>>", lambda _event: self.load_selected_preset())

        self.load_preset_button = ttk.Button(presets, text="切换", command=self.load_selected_preset)
        self.load_preset_button.grid(row=0, column=2, padx=4)
        self.save_preset_button = ttk.Button(presets, text="保存当前方案", command=self.save_preset)
        self.save_preset_button.grid(row=0, column=3, padx=4)
        self.delete_preset_button = ttk.Button(presets, text="删除方案", command=self.delete_preset)
        self.delete_preset_button.grid(row=0, column=4, padx=4)
        self.reload_preset_button = ttk.Button(presets, text="重载", command=self.reload_presets)
        self.reload_preset_button.grid(row=0, column=5, padx=4)
        self.export_csv_button = ttk.Button(presets, text="导出CSV", command=self.export_csv_config)
        self.export_csv_button.grid(row=0, column=6, padx=4)
        self.import_csv_button = ttk.Button(presets, text="导入CSV", command=self.import_csv_config)
        self.import_csv_button.grid(row=0, column=7, padx=(4, 0))

        account_queue = ttk.LabelFrame(self, text="账户队列", padding=(16, 10))
        account_queue.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 8))
        account_queue.columnconfigure(0, weight=1)
        account_queue.columnconfigure(1, weight=1)

        left_queue = ttk.Frame(account_queue)
        left_queue.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        left_queue.columnconfigure(0, weight=1)
        ttk.Label(left_queue, text="账户 ID 列表（每行一个，也支持逗号/空格分隔）").grid(
            row=0,
            column=0,
            sticky="w",
        )
        self.account_list_text = tk.Text(left_queue, height=4, wrap=tk.WORD)
        self.account_list_text.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        self.account_list_text.bind("<KeyRelease>", lambda _event: self._sync_account_list_from_text())
        self.account_list_text.bind("<FocusOut>", lambda _event: self._sync_account_list_from_text())
        self.account_queue_widgets.append(self.account_list_text)

        right_queue = ttk.Frame(account_queue)
        right_queue.grid(row=0, column=1, sticky="nsew")
        right_queue.columnconfigure(0, weight=1)
        self.account_queue_status_var = tk.StringVar(value="账户 0/0，已完成 0/0")
        ttk.Label(right_queue, textvariable=self.account_queue_status_var).grid(
            row=0,
            column=0,
            sticky="w",
        )
        self.account_queue_listbox = tk.Listbox(right_queue, height=4)
        self.account_queue_listbox.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        self.account_queue_listbox.bind("<<ListboxSelect>>", self._on_account_listbox_select)
        nav = ttk.Frame(right_queue)
        nav.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        for index in range(5):
            nav.columnconfigure(index, weight=1)
        self.prev_account_button = ttk.Button(nav, text="上一个账户", command=self.previous_account)
        self.prev_account_button.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.next_account_button = ttk.Button(nav, text="下一个账户", command=self.next_account)
        self.next_account_button.grid(row=0, column=1, sticky="ew", padx=6)
        self.clear_account_marks_button = ttk.Button(nav, text="清除完成标记", command=self.clear_account_marks)
        self.clear_account_marks_button.grid(row=0, column=2, sticky="ew", padx=6)
        ttk.Label(nav, text="账号间等待(秒)").grid(row=0, column=3, sticky="e", padx=(8, 4))
        self.batch_delay_entry = ttk.Entry(nav, textvariable=self.batch_delay_var, width=6)
        self.batch_delay_entry.grid(row=0, column=4, sticky="w")
        self.account_queue_widgets.extend(
            [
                self.account_queue_listbox,
                self.prev_account_button,
                self.next_account_button,
                self.clear_account_marks_button,
                self.batch_delay_entry,
            ]
        )

        form_outer = ttk.LabelFrame(self, text="广告参数", padding=(0, 0))
        form_outer.grid(row=3, column=0, sticky="nsew", padx=16, pady=(0, 8))
        form_outer.columnconfigure(0, weight=1)
        form_outer.rowconfigure(0, weight=1)

        canvas = tk.Canvas(form_outer, highlightthickness=0)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(form_outer, orient=tk.VERTICAL, command=canvas.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        canvas.configure(yscrollcommand=scrollbar.set)

        form = ttk.Frame(canvas, padding=(16, 12))
        form_window = canvas.create_window((0, 0), window=form, anchor="nw")
        form.columnconfigure(1, weight=1)

        def configure_scroll(_event: tk.Event) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def configure_width(event: tk.Event) -> None:
            canvas.itemconfigure(form_window, width=event.width)

        form.bind("<Configure>", configure_scroll)
        canvas.bind("<Configure>", configure_width)

        for row, (name, label, kind) in enumerate(FIELD_SPECS):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="nw", pady=5)
            if kind == "text":
                text = tk.Text(form, height=4, wrap=tk.WORD)
                text.insert("1.0", str(self._new_ad_defaults().get(name, "")))
                text.grid(row=row, column=1, sticky="ew", padx=(12, 0), pady=5)
                self.text_widgets[name] = text
                self.field_widgets.append(text)
            else:
                if kind == "checkbox":
                    check = ttk.Checkbutton(
                        form,
                        text="启用",
                        variable=self.field_vars[name],
                        onvalue="true",
                        offvalue="false",
                    )
                    check.grid(row=row, column=1, sticky="w", padx=(12, 0), pady=5)
                    self.field_widgets.append(check)
                elif kind == "choice":
                    combo = ttk.Combobox(
                        form,
                        textvariable=self.field_vars[name],
                        values=("40", "80", "120", "160"),
                        state="readonly",
                        width=12,
                    )
                    combo.grid(row=row, column=1, sticky="w", padx=(12, 0), pady=5)
                    self.field_widgets.append(combo)
                elif kind == "file":
                    file_row = ttk.Frame(form)
                    file_row.grid(row=row, column=1, sticky="ew", padx=(12, 0), pady=5)
                    file_row.columnconfigure(0, weight=1)
                    entry = ttk.Entry(file_row, textvariable=self.field_vars[name])
                    entry.grid(row=0, column=0, sticky="ew")
                    button = ttk.Button(
                        file_row,
                        text="选择",
                        command=lambda field_name=name: self.choose_file(field_name),
                    )
                    button.grid(row=0, column=1, padx=(8, 0))
                    self.field_widgets.extend([entry, button])
                else:
                    entry = ttk.Entry(form, textvariable=self.field_vars[name])
                    entry.grid(row=row, column=1, sticky="ew", padx=(12, 0), pady=5)
                    self.field_widgets.append(entry)
                    if name == "account_id":
                        self.account_id_entry = entry

        actions = ttk.Frame(self, padding=(16, 8))
        actions.grid(row=4, column=0, sticky="ew")
        for index in range(6):
            actions.columnconfigure(index, weight=1)

        self.login_button = ttk.Button(actions, text="打开登录页", command=self.open_login)
        self.login_button.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        self.save_login_button = ttk.Button(
            actions,
            text="保存登录态并关闭",
            command=self.save_login_and_close,
            state=tk.DISABLED,
        )
        self.save_login_button.grid(row=0, column=1, sticky="ew", padx=8)

        self.open_button = ttk.Button(actions, text="打开后台", command=self.open_backend)
        self.open_button.grid(row=0, column=2, sticky="ew", padx=8)

        self.dry_run_button = ttk.Button(actions, text="Dry Run", command=self.run_dry_run)
        self.dry_run_button.grid(row=0, column=3, sticky="ew", padx=8)

        self.new_ad_button = ttk.Button(actions, text="运行新建广告", command=self.run_new_ad)
        self.new_ad_button.grid(row=0, column=4, sticky="ew", padx=(8, 0))

        self.batch_new_ad_button = ttk.Button(actions, text="批量运行", command=self.run_batch_new_ads)
        self.batch_new_ad_button.grid(row=0, column=5, sticky="ew", padx=(8, 0))

        log_frame = ttk.Frame(self, padding=(16, 8, 16, 16))
        log_frame.grid(row=5, column=0, sticky="nsew")
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)

        self.log_text = tk.Text(log_frame, wrap=tk.WORD, height=12)
        self.log_text.grid(row=0, column=0, sticky="nsew")
        log_scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        log_scrollbar.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=log_scrollbar.set)

        self.status_var = tk.StringVar(value="准备就绪")
        ttk.Label(self, textvariable=self.status_var, padding=(16, 0, 16, 12)).grid(
            row=6,
            column=0,
            sticky="ew",
        )

        self._log("准备就绪。第一次使用请点击“打开登录页”。运行新建广告前请填写账户 ID。")

    def open_login(self) -> None:
        if self.busy:
            return
        self._refresh_browser_settings()
        self.login_stop_event = threading.Event()
        self._set_busy(True)
        self.save_login_button.configure(state=tk.NORMAL)
        self._start_thread(
            "login",
            lambda: asyncio.run(self._login_session(self.login_stop_event)),
        )

    def save_login_and_close(self) -> None:
        if self.login_stop_event is not None:
            self._log("正在保存登录态并关闭登录浏览器...")
            self.login_stop_event.set()
            self.save_login_button.configure(state=tk.DISABLED)

    def open_backend(self) -> None:
        if self.busy:
            return
        self._refresh_browser_settings()
        self.open_stop_event = threading.Event()
        self._set_busy(True)
        self._start_thread(
            "open",
            lambda: asyncio.run(self._open_session(self.open_stop_event)),
        )

    def run_dry_run(self) -> None:
        account_id = self._account_id_or_warn()
        if account_id is None:
            return
        self._refresh_browser_settings()
        options = self._options_from_form(account_id=account_id, dry_run=True)
        self._run_single("dry-run", lambda: self._run_new_ad_task(options=options))

    def run_new_ad(self) -> None:
        account_id = self._account_id_or_warn()
        if account_id is None:
            return
        self._refresh_browser_settings()
        options = self._options_from_form(account_id=account_id, dry_run=False)
        self._run_single("new-ad", lambda: self._run_new_ad_task(options=options))

    def run_batch_new_ads(self) -> None:
        account_ids = self._account_ids_from_queue()
        if not account_ids:
            messagebox.showwarning("缺少账户列表", "请先在账户 ID 列表中填写至少一个账户。")
            self.account_list_text.focus_set()
            return
        self._sync_account_list_from_text()
        self._refresh_browser_settings()
        start_index = min(max(self.account_queue_index, 0), len(account_ids) - 1)
        base_values = self._form_values()
        self._run_single(
            "batch-new-ad",
            lambda: self._run_batch_new_ad_task(
                account_ids=account_ids,
                start_index=start_index,
                base_values=base_values,
                delay_seconds=self._batch_delay_seconds(),
            ),
        )

    def previous_account(self) -> None:
        account_ids = self._account_ids_from_queue()
        if not account_ids:
            return
        self.account_queue_index = max(0, self.account_queue_index - 1)
        self._apply_current_account_from_queue(account_ids)

    def next_account(self) -> None:
        account_ids = self._account_ids_from_queue()
        if not account_ids:
            return
        self.account_queue_index = min(len(account_ids) - 1, self.account_queue_index + 1)
        self._apply_current_account_from_queue(account_ids)

    def clear_account_marks(self) -> None:
        self.completed_account_ids.clear()
        self._refresh_account_queue_view()

    def choose_file(self, field_name: str) -> None:
        path = filedialog.askopenfilename(
            title="选择产品主图图片",
            filetypes=(
                ("图片文件", "*.jpg *.jpeg *.png *.webp *.bmp"),
                ("所有文件", "*.*"),
            ),
        )
        if path:
            self.field_vars[field_name].set(path)

    def save_preset(self) -> None:
        current_name = self.preset_var.get().strip()
        name = simpledialog.askstring("保存配置方案", "请输入方案名称：", initialvalue=current_name)
        if name is None:
            return
        name = name.strip()
        if not name:
            messagebox.showwarning("方案名称为空", "请填写一个方案名称。")
            return
        self.presets[name] = self._form_values()
        self._save_presets()
        self.preset_var.set(name)
        self._refresh_preset_combo()
        self._log(f"已保存配置方案：{name}")

    def load_selected_preset(self) -> None:
        name = self.preset_var.get().strip()
        if not name:
            return
        values = self.presets.get(name)
        if values is None:
            messagebox.showwarning("方案不存在", f"找不到配置方案：{name}")
            return
        self._apply_form_values(values)
        self._sync_account_list_from_text()
        self._log(f"已切换配置方案：{name}")

    def delete_preset(self) -> None:
        name = self.preset_var.get().strip()
        if not name:
            return
        if name not in self.presets:
            return
        if not messagebox.askyesno("删除配置方案", f"确定删除配置方案“{name}”？"):
            return
        del self.presets[name]
        self._save_presets()
        self.preset_var.set("")
        self._refresh_preset_combo()
        self._log(f"已删除配置方案：{name}")

    def reload_presets(self) -> None:
        self.presets = self._load_presets()
        self._refresh_preset_combo()
        self._log("已重载配置方案。")

    def export_csv_config(self) -> None:
        preset_name = self.preset_var.get().strip() or "未命名方案"
        default_name = f"{preset_name}.csv"
        path = filedialog.asksaveasfilename(
            title="导出CSV配置",
            defaultextension=".csv",
            initialfile=default_name,
            filetypes=(("CSV配置", "*.csv"), ("TXT配置", "*.txt"), ("所有文件", "*.*")),
        )
        if not path:
            return
        values = self._form_values()
        with Path(path).open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["字段", "名称", "内容"])
            writer.writerow(["preset_name", "方案名称", preset_name])
            for field_name, label, kind in FIELD_SPECS:
                writer.writerow([field_name, label, self._csv_export_value(field_name, values.get(field_name, ""), kind)])
            for field_name, label in EXTRA_CONFIG_LABELS.items():
                writer.writerow([field_name, label, values.get(field_name, "")])
        self._log(f"已导出CSV配置：{path}")

    def import_csv_config(self) -> None:
        path = filedialog.askopenfilename(
            title="导入CSV配置",
            filetypes=(("CSV配置", "*.csv"), ("TXT配置", "*.txt"), ("YAML文件", "*.yaml *.yml"), ("所有文件", "*.*")),
        )
        if not path:
            return
        try:
            values, preset_name = self._read_config_file(Path(path))
        except Exception as exc:  # noqa: BLE001 - surface import errors in the GUI.
            messagebox.showerror("导入失败", f"无法导入配置：{exc}")
            return
        self._apply_form_values(values)
        self._sync_account_list_from_text()
        if preset_name:
            self.preset_var.set(preset_name)
        self._log(f"已导入CSV配置：{path}")

    def _read_config_file(self, path: Path) -> tuple[dict[str, object], str]:
        if path.suffix.lower() == ".csv":
            return self._read_csv_config(path)
        try:
            return self._read_csv_config(path)
        except Exception:
            return self._read_yaml_like_config(path)

    def _read_csv_config(self, path: Path) -> tuple[dict[str, object], str]:
        last_decode_error: UnicodeDecodeError | None = None
        for encoding in ("utf-8-sig", "gb18030", "gbk", "utf-8"):
            try:
                return self._read_csv_config_with_encoding(path, encoding)
            except UnicodeDecodeError as exc:
                last_decode_error = exc
                continue
        if last_decode_error is not None:
            raise last_decode_error
        return self._read_csv_config_with_encoding(path, "utf-8-sig")

    def _read_csv_config_with_encoding(self, path: Path, encoding: str) -> tuple[dict[str, object], str]:
        with path.open("r", encoding=encoding, newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames or "字段" not in reader.fieldnames or "内容" not in reader.fieldnames:
                raise ValueError("CSV表头必须包含：字段、内容。")
            values: dict[str, object] = {}
            preset_name = ""
            for row in reader:
                field_name = (row.get("字段") or "").strip()
                if not field_name:
                    continue
                value = row.get("内容") or ""
                if field_name == "preset_name":
                    preset_name = value.strip()
                else:
                    values[field_name] = self._csv_import_value(field_name, value)
        self._validate_imported_values(values)
        return values, preset_name

    def _csv_export_value(self, field_name: str, value: object, kind: str) -> str:
        text = "" if value is None else str(value)
        if kind == "checkbox":
            return "开启" if self._truthy_config_value(text) else "关闭"
        return text

    def _csv_import_value(self, field_name: str, value: object) -> str:
        text = "" if value is None else str(value).strip()
        field_kinds = {name: kind for name, _label, kind in FIELD_SPECS}
        if field_kinds.get(field_name) == "checkbox":
            return "true" if self._truthy_config_value(text) else "false"
        return text

    def _truthy_config_value(self, value: object) -> bool:
        return str(value).strip().lower() in {
            "1",
            "true",
            "yes",
            "y",
            "on",
            "是",
            "启用",
            "开启",
            "打开",
        }

    def _read_yaml_like_config(self, path: Path) -> tuple[dict[str, object], str]:
        with path.open("r", encoding="utf-8-sig") as handle:
            raw = yaml.safe_load(handle) or {}
        if not isinstance(raw, dict):
            raise ValueError("配置文件内容必须是键值结构。")

        preset_name = str(raw.get("preset_name", "")).strip()
        if isinstance(raw.get("config"), dict):
            values = raw["config"]
        elif isinstance(raw.get("values"), dict):
            values = raw["values"]
        elif isinstance(raw.get("presets"), dict):
            presets = raw["presets"]
            selected_name = preset_name if preset_name in presets else next(iter(presets), "")
            if not selected_name:
                raise ValueError("presets 中没有可导入的方案。")
            preset_name = str(selected_name)
            values = presets[selected_name]
        else:
            values = raw

        if not isinstance(values, dict):
            raise ValueError("配置字段必须是键值结构。")
        normalized = {str(key): "" if value is None else str(value) for key, value in values.items()}
        self._validate_imported_values(normalized)
        return normalized, preset_name

    def _validate_imported_values(self, values: dict[str, object]) -> None:
        known_fields = {name for name, _, _ in FIELD_SPECS} | {"account_id_list", "batch_delay_seconds"}
        if not any(key in values for key in known_fields):
            raise ValueError("未识别到有效的RPA配置字段。")

    def _account_id_or_warn(self) -> str | None:
        self._sync_account_list_from_text()
        account_id = self.field_vars["account_id"].get().strip()
        if not account_id:
            messagebox.showwarning("缺少账户 ID", "请先填写账户 ID。")
            self.account_id_entry.focus_set()
            return None
        return account_id

    def _options_from_form(self, account_id: str, dry_run: bool) -> NewAdOptions:
        return self._options_from_values(self._form_values(), account_id=account_id, dry_run=dry_run)

    def _options_from_values(
        self,
        values: dict[str, str],
        account_id: str,
        dry_run: bool,
    ) -> NewAdOptions:
        return NewAdOptions(
            account_id=account_id,
            mini_game_name=values["mini_game_name"],
            mini_game_asset_id=values["mini_game_asset_id"],
            mini_game_app_id=values["mini_game_app_id"],
            optimization_goal=values["optimization_goal"],
            deep_optimization_goal=values["deep_optimization_goal"],
            douyin_id=values["douyin_id"],
            douyin_name=values["douyin_name"],
            daily_budget=values["daily_budget"],
            roi_coefficient=values["roi_coefficient"],
            ad_texts=values["ad_texts"],
            mini_program_link=values["mini_program_link"],
            backup_site_link=values["backup_site_link"],
            product_name=values["product_name"],
            product_image_path=values["product_image_path"],
            auto_add_videos=self._truthy_config_value(values["auto_add_videos"]),
            auto_add_video_count=values["auto_add_video_count"],
            specific_video_count=values["specific_video_count"],
            change_douyin_nickname=self._truthy_config_value(values["change_douyin_nickname"]),
            douyin_nickname=values["douyin_nickname"],
            submit_project=self._truthy_config_value(values["submit_project"]),
            product_selling_points=values["product_selling_points"],
            call_to_actions=values["call_to_actions"],
            project_name_prefix=values["project_name_prefix"],
            dry_run=dry_run,
        )

    def _form_values(self) -> dict[str, str]:
        values: dict[str, str] = {}
        for name, _, kind in FIELD_SPECS:
            if kind == "text":
                values[name] = self.text_widgets[name].get("1.0", "end-1c").strip()
            else:
                values[name] = self.field_vars[name].get().strip()
        values["account_id_list"] = self.account_list_text.get("1.0", "end-1c").strip()
        values["batch_delay_seconds"] = self.batch_delay_var.get().strip()

        defaults = self._new_ad_defaults()
        for name, _, _ in FIELD_SPECS:
            if not values.get(name) and name not in {"account_id", "specific_video_count", "douyin_nickname"}:
                values[name] = str(defaults.get(name, ""))
        return values

    def _apply_form_values(self, values: dict[str, object]) -> None:
        defaults = self._new_ad_defaults()
        for name, _, kind in FIELD_SPECS:
            value = str(values.get(name, defaults.get(name, "")))
            if kind == "text":
                widget = self.text_widgets[name]
                widget.delete("1.0", tk.END)
                widget.insert("1.0", value)
            elif kind == "checkbox":
                self.field_vars[name].set(
                    "true" if self._truthy_config_value(value) else "false"
                )
            else:
                self.field_vars[name].set(value)
        account_list = str(values.get("account_id_list", values.get("account_id", ""))).strip()
        self.account_list_text.delete("1.0", tk.END)
        self.account_list_text.insert("1.0", account_list)
        self.batch_delay_var.set(str(values.get("batch_delay_seconds", self.batch_delay_var.get() or "8")))

    def _new_ad_defaults(self) -> dict[str, object]:
        defaults = {field.name: field.default for field in fields(NewAdOptions)}
        defaults["account_id"] = ""
        return defaults

    def _account_ids_from_queue(self) -> list[str]:
        raw = self.account_list_text.get("1.0", "end-1c")
        normalized = raw.replace(",", "\n").replace("，", "\n").replace(";", "\n").replace("；", "\n")
        account_ids: list[str] = []
        seen: set[str] = set()
        for chunk in normalized.splitlines():
            for item in chunk.split():
                account_id = item.strip()
                if not account_id or account_id in seen:
                    continue
                account_ids.append(account_id)
                seen.add(account_id)
        return account_ids

    def _sync_account_list_from_text(self) -> None:
        account_ids = self._account_ids_from_queue()
        if account_ids and not self.field_vars["account_id"].get().strip():
            self.account_queue_index = 0
            self.field_vars["account_id"].set(account_ids[0])
        if account_ids:
            current = self.field_vars["account_id"].get().strip()
            if current in account_ids:
                self.account_queue_index = account_ids.index(current)
            else:
                self.account_queue_index = min(self.account_queue_index, len(account_ids) - 1)
                self.field_vars["account_id"].set(account_ids[self.account_queue_index])
        else:
            self.account_queue_index = 0
            self.completed_account_ids.clear()
        self.completed_account_ids = {account_id for account_id in self.completed_account_ids if account_id in account_ids}
        self._refresh_account_queue_view(account_ids)

    def _apply_current_account_from_queue(self, account_ids: list[str] | None = None) -> None:
        if account_ids is None:
            account_ids = self._account_ids_from_queue()
        if not account_ids:
            self._refresh_account_queue_view(account_ids)
            return
        self.account_queue_index = min(max(self.account_queue_index, 0), len(account_ids) - 1)
        self.field_vars["account_id"].set(account_ids[self.account_queue_index])
        self._refresh_account_queue_view(account_ids)

    def _refresh_account_queue_view(self, account_ids: list[str] | None = None) -> None:
        if account_ids is None:
            account_ids = self._account_ids_from_queue()
        if not hasattr(self, "account_queue_listbox"):
            return
        self.account_queue_listbox.delete(0, tk.END)
        total = len(account_ids)
        self.account_queue_index = min(max(self.account_queue_index, 0), max(total - 1, 0))
        for index, account_id in enumerate(account_ids):
            marker = "✓" if account_id in self.completed_account_ids else " "
            current = "▶" if total and index == self.account_queue_index else " "
            self.account_queue_listbox.insert(tk.END, f"{current} {marker} {index + 1}. {account_id}")
        if total:
            self.account_queue_listbox.selection_clear(0, tk.END)
            self.account_queue_listbox.selection_set(self.account_queue_index)
            self.account_queue_listbox.see(self.account_queue_index)
        completed = sum(1 for account_id in account_ids if account_id in self.completed_account_ids)
        current_number = self.account_queue_index + 1 if total else 0
        self.account_queue_status_var.set(f"账户 {current_number}/{total}，已完成 {completed}/{total}")

    def _on_account_listbox_select(self, _event: tk.Event) -> None:
        if self.busy:
            return
        selection = self.account_queue_listbox.curselection()
        if not selection:
            return
        self.account_queue_index = int(selection[0])
        self._apply_current_account_from_queue()

    def _batch_delay_seconds(self) -> float:
        raw = self.batch_delay_var.get().strip()
        try:
            delay = float(raw)
        except ValueError:
            delay = 8.0
        return max(0.0, delay)

    def _refresh_browser_settings(self) -> None:
        self.settings = replace(
            self.settings,
            browser=replace(
                self.settings.browser,
                use_system_chrome=self.use_system_chrome_var.get(),
            ),
        )
        self.browser_mode_var.set(browser_mode_label(self.settings))

    def _load_presets(self) -> dict[str, dict[str, str]]:
        if not PRESET_PATH.exists():
            return {}
        with PRESET_PATH.open("r", encoding="utf-8") as handle:
            raw = yaml.safe_load(handle) or {}
        presets = raw.get("presets", {}) if isinstance(raw, dict) else {}
        if not isinstance(presets, dict):
            return {}
        return {
            str(name): {str(key): str(value) for key, value in values.items()}
            for name, values in presets.items()
            if isinstance(values, dict)
        }

    def _save_presets(self) -> None:
        PRESET_PATH.parent.mkdir(parents=True, exist_ok=True)
        with PRESET_PATH.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(
                {"presets": self.presets},
                handle,
                allow_unicode=True,
                sort_keys=False,
            )

    def _refresh_preset_combo(self) -> None:
        names = sorted(self.presets)
        self.preset_combo.configure(values=names)
        if self.preset_var.get() not in self.presets:
            self.preset_var.set(names[0] if names else "")

    def _run_single(self, name: str, target: Callable[[], None]) -> None:
        if self.busy:
            return
        self._set_busy(True)
        self._start_thread(name, target)

    def _start_thread(self, name: str, target: Callable[[], None]) -> None:
        def guarded_target() -> None:
            try:
                target()
            except Exception as exc:  # noqa: BLE001 - surface worker errors in the GUI.
                self._emit("error", str(exc))

        thread = threading.Thread(target=guarded_target, name=f"juliang-rpa-{name}", daemon=True)
        thread.start()

    async def _login_session(self, stop_event: threading.Event) -> None:
        self._emit("status", "正在打开登录页...")
        async with persistent_context(self.settings) as context:
            page = await first_page(context)
            await goto_login(page, self.settings)
            self._emit("log", "登录页已打开。请在浏览器里完成登录，然后点击“保存登录态并关闭”。")
            while not stop_event.is_set():
                await asyncio.sleep(0.25)
            try:
                screenshot_path, html_path = await save_debug_snapshot(
                    page,
                    self.settings.artifacts.logs_dir,
                    "after_login",
                )
            except PlaywrightError:
                self._emit("log", "登录浏览器已关闭，跳过登录快照保存。")
            else:
                self._emit("log", f"已保存登录快照：{screenshot_path}")
                self._emit("log", f"已保存登录 HTML：{html_path}")
        self._emit("done", "登录态已保存")

    async def _open_session(self, stop_event: threading.Event) -> None:
        self._emit("status", "正在打开后台...")
        async with persistent_context(self.settings) as context:
            page = await first_page(context)
            await goto_base(page, self.settings)
            self._emit("log", "后台已打开。关闭浏览器窗口后，界面会恢复可操作。")
            while context.pages and not stop_event.is_set():
                await asyncio.sleep(0.5)
        self._emit("done", "后台窗口已关闭")

    def _run_new_ad_task(self, options: NewAdOptions) -> None:
        if options.dry_run:
            asyncio.run(self._run_new_ad_task_async(options=options))
            return
        future = asyncio.run_coroutine_threadsafe(
            self._run_new_ad_task_async(options=options),
            self.ad_loop,
        )
        future.result()

    def _run_batch_new_ad_task(
        self,
        account_ids: list[str],
        start_index: int,
        base_values: dict[str, str],
        delay_seconds: float,
    ) -> None:
        future = asyncio.run_coroutine_threadsafe(
            self._run_batch_new_ad_task_async(
                account_ids=account_ids,
                start_index=start_index,
                base_values=base_values,
                delay_seconds=delay_seconds,
            ),
            self.ad_loop,
        )
        future.result()

    async def _run_new_ad_task_async(self, options: NewAdOptions, emit_done: bool = True) -> None:
        label = "Dry Run" if options.dry_run else "新建广告"
        self._emit("status", f"正在运行 {label}，账户 ID: {options.account_id}...")
        if options.dry_run:
            async with persistent_context(self.settings, close_on_exit=True) as context:
                page = await first_page(context)
                await run_new_ad(
                    page,
                    self.settings,
                    options,
                    progress=lambda message: self._emit("log", message),
                )
            if emit_done:
                self._emit("done", f"{label} 已完成")
            return

        context = await self._ad_browser_context()
        try:
            page = await fresh_page(context)
        except PlaywrightError:
            await self._close_ad_browser_context()
            context = await self._ad_browser_context()
            page = await fresh_page(context)

        await run_new_ad(
            page,
            self.settings,
            options,
            progress=lambda message: self._emit("log", message),
        )
        self._emit("log", "新建广告页面已保留在当前浏览器。下次运行会自动清理旧标签页。")
        if emit_done:
            self._emit("account_queue_completed_by_id", options.account_id)
            self._emit("done", f"{label} 已完成")

    async def _run_batch_new_ad_task_async(
        self,
        account_ids: list[str],
        start_index: int,
        base_values: dict[str, str],
        delay_seconds: float,
    ) -> None:
        total = len(account_ids)
        self._emit("status", f"正在批量创建广告：从第 {start_index + 1}/{total} 个账户开始...")
        for index in range(start_index, total):
            account_id = account_ids[index]
            self._emit("account_queue_current", str(index))
            self._emit("log", f"批量创建：开始第 {index + 1}/{total} 个账户，账户 ID: {account_id}")
            options = self._options_from_values(base_values, account_id=account_id, dry_run=False)
            await self._run_new_ad_task_async(options=options, emit_done=False)
            self._emit("account_queue_completed_by_id", account_id)
            self._emit("log", f"批量创建：第 {index + 1}/{total} 个账户已完成。")
            if index < total - 1 and delay_seconds > 0:
                self._emit("log", f"等待 {delay_seconds:g} 秒，确认上一个账户创建完成后进入下一个账户。")
                await asyncio.sleep(delay_seconds)
        self._emit("done", f"批量创建广告 已完成：{total - start_index}/{total}")

    async def _ad_browser_context(self) -> BrowserContext:
        if self.ad_context is not None:
            return self.ad_context
        self.ad_context_manager = persistent_context(self.settings, close_on_exit=False)
        self.ad_context = await self.ad_context_manager.__aenter__()
        return self.ad_context

    async def _close_ad_browser_context(self) -> None:
        if self.ad_context_manager is None:
            self.ad_context = None
            return
        try:
            await self.ad_context_manager.__aexit__(None, None, None)
        finally:
            self.ad_context = None
            self.ad_context_manager = None

    def _poll_events(self) -> None:
        try:
            while True:
                event_type, message = self.events.get_nowait()
                if event_type == "log":
                    self._log(message)
                elif event_type == "status":
                    self.status_var.set(message)
                    self._log(message)
                elif event_type == "done":
                    self.status_var.set(message)
                    self._log(message)
                    self._set_busy(False)
                    self.save_login_button.configure(state=tk.DISABLED)
                elif event_type == "account_queue_current":
                    account_ids = self._account_ids_from_queue()
                    try:
                        self.account_queue_index = int(message)
                    except ValueError:
                        self.account_queue_index = 0
                    if account_ids and 0 <= self.account_queue_index < len(account_ids):
                        self.field_vars["account_id"].set(account_ids[self.account_queue_index])
                    self._refresh_account_queue_view(account_ids)
                elif event_type == "account_queue_completed":
                    account_ids = self._account_ids_from_queue()
                    try:
                        completed_index = int(message)
                    except ValueError:
                        completed_index = -1
                    if 0 <= completed_index < len(account_ids):
                        self.completed_account_ids.add(account_ids[completed_index])
                    self._refresh_account_queue_view(account_ids)
                elif event_type == "account_queue_completed_by_id":
                    account_ids = self._account_ids_from_queue()
                    if message in account_ids:
                        self.completed_account_ids.add(message)
                        self.account_queue_index = account_ids.index(message)
                        self.field_vars["account_id"].set(message)
                    self._refresh_account_queue_view(account_ids)
                elif event_type == "account_queue_refresh":
                    self._refresh_account_queue_view()
                elif event_type == "error":
                    self.status_var.set("执行失败")
                    self._log(message)
                    self._set_busy(False)
                    self.save_login_button.configure(state=tk.DISABLED)
                    messagebox.showerror("执行失败", message)
        except queue.Empty:
            pass
        self.after(150, self._poll_events)

    def _emit(self, event_type: str, message: str) -> None:
        self.events.put((event_type, message))

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        state = tk.DISABLED if busy else tk.NORMAL
        self.login_button.configure(state=state)
        self.open_button.configure(state=state)
        self.dry_run_button.configure(state=state)
        self.new_ad_button.configure(state=state)
        self.batch_new_ad_button.configure(state=state)
        self.load_preset_button.configure(state=state)
        self.save_preset_button.configure(state=state)
        self.delete_preset_button.configure(state=state)
        self.reload_preset_button.configure(state=state)
        self.preset_combo.configure(state=tk.DISABLED if busy else "readonly")
        for widget in self.account_queue_widgets:
            widget.configure(state=state)
        for widget in self.field_widgets:
            if isinstance(widget, ttk.Combobox):
                widget.configure(state=tk.DISABLED if busy else "readonly")
            else:
                widget.configure(state=state)

    def _log(self, message: str) -> None:
        self.log_text.insert(tk.END, f"{message}\n")
        self.log_text.see(tk.END)

    def _on_close(self) -> None:
        if self.login_stop_event is not None:
            self.login_stop_event.set()
        if self.open_stop_event is not None:
            self.open_stop_event.set()
        if self.ad_loop.is_running():
            future = asyncio.run_coroutine_threadsafe(self._close_ad_browser_context(), self.ad_loop)
            try:
                future.result(timeout=5)
            except Exception:  # noqa: BLE001 - closing the GUI should not be blocked by browser shutdown.
                pass
            self.ad_loop.call_soon_threadsafe(self.ad_loop.stop)
        self.destroy()


def main(config_path: Path = DEFAULT_CONFIG_PATH) -> None:
    app = JuliangRpaApp(config_path)
    app.mainloop()
