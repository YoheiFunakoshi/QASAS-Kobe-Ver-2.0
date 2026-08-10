from __future__ import annotations

import queue
import re
import threading
import traceback
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure

from . import gui as single_gui
from .gui import QASASApplication as SingleSampleApplication
from .modes import GUI_MODE_LABELS, MatchingMode, mode_specification, parse_matching_mode
from .timecourse import (
    TimeCourseResult,
    TimepointSpec,
    analyse_timecourse,
    format_day,
    parse_day,
)
from .timecourse_export import export_timecourse_xlsx


APP_TITLE = "QASAS Kobe Ver 2.0"


class QASASV2Application(SingleSampleApplication):
    """Ver 1.0 single-sample GUI plus an independent longitudinal workflow."""

    def __init__(self, root: tk.Tk) -> None:
        # The inherited single-sample methods use their module-level title for
        # dialogs.  This changes only the copied Ver 2.0 repository.
        single_gui.APP_TITLE = APP_TITLE
        self.tc_events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.tc_worker: threading.Thread | None = None
        self.tc_result: TimeCourseResult | None = None
        self.tc_specs: list[TimepointSpec] = []
        self.tc_expanded_window: tk.Toplevel | None = None
        self.tc_expanded_figure: Figure | None = None
        self.tc_expanded_canvas: FigureCanvasTkAgg | None = None

        self.tc_series_name = tk.StringVar(master=root, value="")
        self.tc_database_path = tk.StringVar(master=root, value="")
        default_mode = mode_specification(MatchingMode.KOBE)
        self.tc_matching_mode = tk.StringVar(master=root, value=default_mode.label)
        self.tc_mode_description = tk.StringVar(master=root, value=default_mode.description)
        self.tc_day = tk.StringVar(master=root, value="")
        self.tc_label = tk.StringVar(master=root, value="")
        self.tc_sample_path = tk.StringVar(master=root, value="")
        self.tc_input_format = tk.StringVar(master=root, value="自動判定")
        self.tc_status_text = tk.StringVar(master=root, value="Dayと検体を2件以上追加してください。")
        self.tc_series_summary = tk.StringVar(master=root, value="未解析")
        self.tc_database_summary = tk.StringVar(master=root, value="未解析")
        self.tc_match_summary = tk.StringVar(master=root, value="未解析")
        self.tc_summary_kind = tk.StringVar(master=root, value="累積")
        self.tc_chart_layout = tk.StringVar(master=root, value="論文形式（2×3）")
        self.tc_selected_point = tk.StringVar(master=root, value="")

        super().__init__(root)
        self.root.geometry("1320x900")
        self.root.minsize(1060, 720)
        self._set_timecourse_default_paths()
        self.root.after(100, self._poll_timecourse_events)

    def _build_ui(self) -> None:
        """Place the untouched Ver 1.0 screen and the new screen in tabs."""

        host = ttk.Frame(self.root, padding=4)
        host.pack(fill="both", expand=True)
        workflow = ttk.Notebook(host)
        workflow.pack(fill="both", expand=True)
        single_tab = ttk.Frame(workflow)
        timecourse_tab = ttk.Frame(workflow)
        workflow.add(single_tab, text="単独検体解析（Ver 1.0画面）")
        workflow.add(timecourse_tab, text="経時・複数検体解析（Ver 2.0）")

        # The base builder only needs a Tk-compatible parent.  Temporarily
        # using the tab as its parent preserves every Ver 1.0 widget and Fig.
        real_root = self.root
        try:
            self.root = single_tab
            single_gui.QASASApplication._build_ui(self)
        finally:
            self.root = real_root

        self._build_timecourse_ui(timecourse_tab)

    def _build_timecourse_ui(self, parent: ttk.Frame) -> None:
        outer = ttk.Frame(parent, padding=12)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(5, weight=1)

        header = ttk.Frame(outer)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(header, text=APP_TITLE, style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="同一DB・同一照合方式で各検体を独立解析し、任意のDayで経時表示します。",
            style="Subtitle.TLabel",
        ).pack(anchor="w")

        common = ttk.LabelFrame(outer, text="共通設定", padding=8)
        common.grid(row=1, column=0, sticky="ew")
        common.columnconfigure(1, weight=1)
        ttk.Label(common, text="系列名（任意）").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=3)
        self.tc_series_entry = ttk.Entry(common, textvariable=self.tc_series_name)
        self.tc_series_entry.grid(row=0, column=1, sticky="ew", pady=3)
        ttk.Label(common, text="抗体DB (CSV)").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=3)
        self.tc_database_entry = ttk.Entry(common, textvariable=self.tc_database_path)
        self.tc_database_entry.grid(row=1, column=1, sticky="ew", pady=3)
        self.tc_database_button = ttk.Button(common, text="参照…", command=self._browse_tc_database)
        self.tc_database_button.grid(row=1, column=2, padx=(8, 0), pady=3)
        ttk.Label(common, text="照合方式").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=3)
        mode_frame = ttk.Frame(common)
        mode_frame.grid(row=2, column=1, columnspan=2, sticky="ew", pady=3)
        self.tc_mode_box = ttk.Combobox(
            mode_frame,
            textvariable=self.tc_matching_mode,
            values=GUI_MODE_LABELS,
            state="readonly",
            width=36,
        )
        self.tc_mode_box.pack(side="left")
        self.tc_mode_box.bind("<<ComboboxSelected>>", self._on_tc_mode_changed)
        ttk.Label(
            mode_frame,
            textvariable=self.tc_mode_description,
            style="Subtitle.TLabel",
            wraplength=680,
        ).pack(side="left", padx=(10, 0))

        samples = ttk.LabelFrame(outer, text="時点の追加（Dayは負数・0・正数・小数を入力可）", padding=8)
        samples.grid(row=2, column=0, sticky="nsew", pady=(8, 0))
        samples.columnconfigure(5, weight=1)
        ttk.Label(samples, text="Day").grid(row=0, column=0, sticky="w")
        self.tc_day_entry = ttk.Entry(samples, textvariable=self.tc_day, width=11)
        self.tc_day_entry.grid(row=1, column=0, sticky="ew", padx=(0, 6))
        ttk.Label(samples, text="表示名（任意）").grid(row=0, column=1, sticky="w")
        self.tc_label_entry = ttk.Entry(samples, textvariable=self.tc_label, width=18)
        self.tc_label_entry.grid(row=1, column=1, sticky="ew", padx=(0, 6))
        ttk.Label(samples, text="入力様式").grid(row=0, column=2, sticky="w")
        self.tc_format_box = ttk.Combobox(
            samples,
            textvariable=self.tc_input_format,
            values=("自動判定", "CPM様式", "RG様式"),
            state="readonly",
            width=12,
        )
        self.tc_format_box.grid(row=1, column=2, sticky="ew", padx=(0, 6))
        ttk.Label(samples, text="検体レパトア").grid(row=0, column=3, columnspan=3, sticky="w")
        self.tc_sample_entry = ttk.Entry(samples, textvariable=self.tc_sample_path)
        self.tc_sample_entry.grid(row=1, column=3, columnspan=3, sticky="ew")
        self.tc_sample_button = ttk.Button(samples, text="参照…", command=self._browse_tc_sample)
        self.tc_sample_button.grid(row=1, column=6, padx=(6, 0))

        edit_buttons = ttk.Frame(samples)
        edit_buttons.grid(row=2, column=0, columnspan=7, sticky="w", pady=(6, 5))
        self.tc_add_button = ttk.Button(edit_buttons, text="時点を追加", command=self._add_tc_point)
        self.tc_add_button.pack(side="left")
        self.tc_update_button = ttk.Button(edit_buttons, text="選択行を更新", command=self._update_tc_point)
        self.tc_update_button.pack(side="left", padx=(6, 0))
        self.tc_remove_button = ttk.Button(edit_buttons, text="選択行を削除", command=self._remove_tc_point)
        self.tc_remove_button.pack(side="left", padx=(6, 0))
        self.tc_clear_button = ttk.Button(edit_buttons, text="全行をクリア", command=self._clear_tc_points)
        self.tc_clear_button.pack(side="left", padx=(6, 0))
        ttk.Label(
            edit_buttons,
            text="※ 同じDayは自動平均せず、重複として停止します。",
            style="Subtitle.TLabel",
        ).pack(side="left", padx=(12, 0))

        self.tc_input_tree = ttk.Treeview(
            samples,
            columns=("day", "label", "sample", "format", "path"),
            show="headings",
            height=4,
        )
        tc_input_headings = {
            "day": "Day",
            "label": "表示名",
            "sample": "ファイル名",
            "format": "様式",
            "path": "保存場所",
        }
        tc_input_widths = {"day": 75, "label": 130, "sample": 230, "format": 90, "path": 500}
        for column, heading in tc_input_headings.items():
            self.tc_input_tree.heading(column, text=heading)
            self.tc_input_tree.column(column, width=tc_input_widths[column], anchor="w")
        self.tc_input_tree.grid(row=3, column=0, columnspan=7, sticky="nsew")
        self.tc_input_tree.bind("<<TreeviewSelect>>", self._load_selected_tc_point)

        action = ttk.Frame(outer)
        action.grid(row=3, column=0, sticky="ew", pady=8)
        self.tc_run_button = ttk.Button(
            action,
            text="経時QASAS解析を実行",
            style="Run.TButton",
            command=self._start_timecourse_analysis,
        )
        self.tc_run_button.pack(side="left")
        self.tc_save_excel_button = ttk.Button(
            action,
            text="経時結果をExcel保存…",
            command=self._save_timecourse_excel,
            state="disabled",
        )
        self.tc_save_excel_button.pack(side="left", padx=(8, 0))
        self.tc_save_figure_button = ttk.Button(
            action,
            text="Figを画像保存…",
            command=self._save_timecourse_figure,
            state="disabled",
        )
        self.tc_save_figure_button.pack(side="left", padx=(8, 0))
        self.tc_expand_figure_button = ttk.Button(
            action,
            text="Figを大きく表示",
            command=self._show_expanded_timecourse_chart,
            state="disabled",
        )
        self.tc_expand_figure_button.pack(side="left", padx=(8, 0))

        cards = ttk.Frame(outer)
        cards.grid(row=4, column=0, sticky="ew", pady=(0, 8))
        for column, (title, variable) in enumerate(
            (
                ("系列", self.tc_series_summary),
                ("共通データベース", self.tc_database_summary),
                ("経時解析", self.tc_match_summary),
            )
        ):
            cards.columnconfigure(column, weight=1)
            card = ttk.LabelFrame(cards, padding=(9, 5))
            card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 5, 0))
            ttk.Label(card, text=title, style="CardTitle.TLabel").pack(anchor="w")
            ttk.Label(card, textvariable=variable, style="CardValue.TLabel").pack(anchor="w")

        results = ttk.Notebook(outer)
        results.grid(row=5, column=0, sticky="nsew")
        chart_tab = ttk.Frame(results, padding=6)
        selected_tab = ttk.Frame(results, padding=6)
        table_tab = ttk.Frame(results, padding=6)
        log_tab = ttk.Frame(results, padding=6)
        results.add(chart_tab, text="経時グラフ")
        results.add(selected_tab, text="選択検体の単独Fig")
        results.add(table_tab, text="経時サマリー")
        results.add(log_tab, text="処理ログ")

        chart_tab.columnconfigure(0, weight=1)
        chart_tab.rowconfigure(1, weight=1)
        chart_controls = ttk.Frame(chart_tab)
        chart_controls.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        ttk.Label(chart_controls, text="集計:").pack(side="left")
        self.tc_kind_box = ttk.Combobox(
            chart_controls,
            textvariable=self.tc_summary_kind,
            values=("累積", "個別"),
            state="readonly",
            width=8,
        )
        self.tc_kind_box.pack(side="left", padx=(4, 12))
        self.tc_kind_box.bind("<<ComboboxSelected>>", lambda _event: self._draw_timecourse_chart())
        ttk.Label(chart_controls, text="表示:").pack(side="left")
        self.tc_layout_box = ttk.Combobox(
            chart_controls,
            textvariable=self.tc_chart_layout,
            values=("論文形式（2×3）", "3指標（3×3）"),
            state="readonly",
            width=18,
        )
        self.tc_layout_box.pack(side="left", padx=(4, 0))
        self.tc_layout_box.bind("<<ComboboxSelected>>", lambda _event: self._draw_timecourse_chart())
        ttk.Label(
            chart_controls,
            text="論文形式: 上段=ユニーククローン、下段=頻度（%）",
            style="Subtitle.TLabel",
        ).pack(side="right")
        self.tc_figure = Figure(figsize=(10.8, 5.3), dpi=100, facecolor="white")
        self.tc_chart_canvas = FigureCanvasTkAgg(self.tc_figure, master=chart_tab)
        self.tc_chart_canvas.get_tk_widget().grid(row=1, column=0, sticky="nsew")
        self.tc_chart_canvas.get_tk_widget().bind(
            "<Double-Button-1>", lambda _event: self._show_expanded_timecourse_chart()
        )
        self._draw_empty_timecourse_chart()

        selected_tab.columnconfigure(0, weight=1)
        selected_tab.rowconfigure(1, weight=1)
        selected_controls = ttk.Frame(selected_tab)
        selected_controls.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        ttk.Label(selected_controls, text="時点:").pack(side="left")
        self.tc_selected_box = ttk.Combobox(
            selected_controls,
            textvariable=self.tc_selected_point,
            state="readonly",
            width=72,
        )
        self.tc_selected_box.pack(side="left", padx=(5, 0))
        self.tc_selected_box.bind("<<ComboboxSelected>>", lambda _event: self._draw_selected_single_chart())
        self.tc_single_figure = Figure(figsize=(8.5, 4.2), dpi=100, facecolor="white")
        self.tc_single_canvas = FigureCanvasTkAgg(self.tc_single_figure, master=selected_tab)
        self.tc_single_canvas.get_tk_widget().grid(row=1, column=0, sticky="nsew")
        self._draw_empty_selected_chart()

        table_tab.columnconfigure(0, weight=1)
        table_tab.rowconfigure(0, weight=1)
        summary_columns = ("day", "label", "sample", "kind", "level", "clones", "reads", "frequency")
        self.tc_summary_tree = ttk.Treeview(table_tab, columns=summary_columns, show="headings")
        summary_headings = {
            "day": "Day",
            "label": "表示名",
            "sample": "Sample ID",
            "kind": "集計",
            "level": "距離",
            "clones": "ユニーククローン",
            "reads": "総リード",
            "frequency": "頻度 (%)",
        }
        summary_widths = {
            "day": 70,
            "label": 130,
            "sample": 150,
            "kind": 75,
            "level": 75,
            "clones": 120,
            "reads": 110,
            "frequency": 130,
        }
        for column in summary_columns:
            self.tc_summary_tree.heading(column, text=summary_headings[column])
            self.tc_summary_tree.column(column, width=summary_widths[column], anchor="center")
        table_vertical = ttk.Scrollbar(table_tab, orient="vertical", command=self.tc_summary_tree.yview)
        self.tc_summary_tree.configure(yscrollcommand=table_vertical.set)
        self.tc_summary_tree.grid(row=0, column=0, sticky="nsew")
        table_vertical.grid(row=0, column=1, sticky="ns")

        log_tab.columnconfigure(0, weight=1)
        log_tab.rowconfigure(0, weight=1)
        self.tc_log_text = tk.Text(log_tab, wrap="word", state="disabled", font=("Consolas", 9))
        self.tc_log_text.grid(row=0, column=0, sticky="nsew")
        log_scroll = ttk.Scrollbar(log_tab, orient="vertical", command=self.tc_log_text.yview)
        log_scroll.grid(row=0, column=1, sticky="ns")
        self.tc_log_text.configure(yscrollcommand=log_scroll.set)

        status = ttk.Frame(outer)
        status.grid(row=6, column=0, sticky="ew", pady=(6, 0))
        self.tc_progress = ttk.Progressbar(status, mode="determinate", length=250)
        self.tc_progress.pack(side="left")
        ttk.Label(status, textvariable=self.tc_status_text).pack(side="left", padx=(10, 0))

        self._tc_edit_widgets = (
            self.tc_series_entry,
            self.tc_database_entry,
            self.tc_database_button,
            self.tc_mode_box,
            self.tc_day_entry,
            self.tc_label_entry,
            self.tc_format_box,
            self.tc_sample_entry,
            self.tc_sample_button,
            self.tc_add_button,
            self.tc_update_button,
            self.tc_remove_button,
            self.tc_clear_button,
            self.tc_run_button,
        )

    def _set_timecourse_default_paths(self) -> None:
        self.tc_database_path.set(self.database_path.get())

    def _browse_tc_database(self) -> None:
        initial = Path(self.tc_database_path.get()).parent if self.tc_database_path.get() else self.app_dir
        selected = filedialog.askopenfilename(
            title="経時解析で共通使用する抗原結合性データベースを選択",
            initialdir=initial,
            filetypes=(("CSV database", "*.csv *.tsv"), ("All files", "*.*")),
        )
        if selected:
            self.tc_database_path.set(selected)

    def _browse_tc_sample(self) -> None:
        initial = Path(self.tc_sample_path.get()).parent if self.tc_sample_path.get() else self.app_dir
        selected = filedialog.askopenfilename(
            title="Dayを設定する検体レパトアを選択",
            initialdir=initial,
            filetypes=(
                ("QASAS repertoire", "*.csv *.tsv *.xlsx *.xlsm"),
                ("CPM CSV", "*.csv *.tsv"),
                ("RG Excel", "*.xlsx *.xlsm"),
                ("All files", "*.*"),
            ),
        )
        if selected:
            self.tc_sample_path.set(selected)
            if not self.tc_label.get().strip():
                self.tc_label.set(Path(selected).stem)

    def _on_tc_mode_changed(self, _event: object | None = None) -> None:
        spec = mode_specification(self.tc_matching_mode.get())
        self.tc_mode_description.set(spec.description)
        self.tc_status_text.set(f"照合方式: {spec.label}")

    def _point_from_editor(self, replacing_index: int | None = None) -> TimepointSpec:
        day = parse_day(self.tc_day.get())
        sample_path = Path(self.tc_sample_path.get().strip())
        if not sample_path.is_file():
            raise ValueError("検体レパトアファイルを選択してください。")
        for index, existing in enumerate(self.tc_specs):
            if index != replacing_index and existing.day == day:
                raise ValueError(
                    f"Day {format_day(day)} は既に追加されています。"
                    "同一Dayは自動平均しないため、別のDayを入力してください。"
                )
        return TimepointSpec(
            day=day,
            label=self.tc_label.get().strip() or sample_path.stem,
            sample_path=sample_path,
            input_format=self.tc_input_format.get(),
        )

    def _add_tc_point(self) -> None:
        try:
            point = self._point_from_editor()
        except Exception as exc:
            messagebox.showerror(APP_TITLE, str(exc))
            return
        self.tc_specs.append(point)
        self.tc_specs.sort(key=lambda item: item.day)
        self._render_tc_input_rows()
        self.tc_day.set("")
        self.tc_label.set("")
        self.tc_sample_path.set("")
        self.tc_status_text.set(f"{len(self.tc_specs)}件の時点を登録しました。")

    def _selected_tc_index(self) -> int | None:
        selection = self.tc_input_tree.selection()
        if not selection:
            return None
        try:
            return int(selection[0])
        except ValueError:
            return None

    def _update_tc_point(self) -> None:
        index = self._selected_tc_index()
        if index is None or index >= len(self.tc_specs):
            messagebox.showwarning(APP_TITLE, "更新する行を選択してください。")
            return
        try:
            point = self._point_from_editor(replacing_index=index)
        except Exception as exc:
            messagebox.showerror(APP_TITLE, str(exc))
            return
        self.tc_specs[index] = point
        self.tc_specs.sort(key=lambda item: item.day)
        self._render_tc_input_rows()
        self.tc_status_text.set("選択した時点を更新しました。")

    def _remove_tc_point(self) -> None:
        index = self._selected_tc_index()
        if index is None or index >= len(self.tc_specs):
            messagebox.showwarning(APP_TITLE, "削除する行を選択してください。")
            return
        del self.tc_specs[index]
        self._render_tc_input_rows()
        self.tc_status_text.set(f"{len(self.tc_specs)}件の時点が登録されています。")

    def _clear_tc_points(self) -> None:
        if not self.tc_specs:
            return
        if not messagebox.askyesno(APP_TITLE, "登録した時点をすべてクリアしますか？"):
            return
        self.tc_specs.clear()
        self._render_tc_input_rows()
        self.tc_status_text.set("登録した時点をクリアしました。")

    def _load_selected_tc_point(self, _event: object | None = None) -> None:
        index = self._selected_tc_index()
        if index is None or index >= len(self.tc_specs):
            return
        point = self.tc_specs[index]
        self.tc_day.set(format_day(point.day))
        self.tc_label.set(point.label)
        self.tc_sample_path.set(str(point.sample_path))
        self.tc_input_format.set(point.input_format)

    def _render_tc_input_rows(self) -> None:
        self.tc_input_tree.delete(*self.tc_input_tree.get_children())
        for index, point in enumerate(self.tc_specs):
            self.tc_input_tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    format_day(point.day),
                    point.label,
                    point.sample_path.name,
                    point.input_format,
                    str(point.sample_path.parent),
                ),
            )

    def _set_timecourse_busy(self, busy: bool) -> None:
        for widget in self._tc_edit_widgets:
            if isinstance(widget, ttk.Combobox):
                widget.configure(state="disabled" if busy else "readonly")
            else:
                widget.configure(state="disabled" if busy else "normal")
        if busy:
            self.tc_save_excel_button.configure(state="disabled")
            self.tc_save_figure_button.configure(state="disabled")
            self.tc_expand_figure_button.configure(state="disabled")
        else:
            state = "normal" if self.tc_result else "disabled"
            self.tc_save_excel_button.configure(state=state)
            self.tc_save_figure_button.configure(state=state)
            self.tc_expand_figure_button.configure(state=state)

    def _start_timecourse_analysis(self) -> None:
        database = Path(self.tc_database_path.get().strip())
        if len(self.tc_specs) < 2:
            messagebox.showerror(APP_TITLE, "経時解析にはDayを設定した検体を2件以上追加してください。")
            return
        if not database.is_file():
            messagebox.showerror(APP_TITLE, "共通の抗原結合性データベースCSVを選択してください。")
            return
        if self.tc_worker and self.tc_worker.is_alive():
            return
        self.tc_result = None
        self._clear_timecourse_results()
        self._set_timecourse_busy(True)
        self.tc_progress.configure(maximum=100, value=0)
        self.tc_status_text.set("経時解析を開始しています…")
        self._append_tc_log(f"\n[{datetime.now():%Y-%m-%d %H:%M:%S}] 経時QASAS解析開始")
        self._append_tc_log(f"系列: {self.tc_series_name.get().strip() or 'QASAS time course'}")
        self._append_tc_log(f"DB  : {database}")
        mode = parse_matching_mode(self.tc_matching_mode.get())
        self._append_tc_log(f"方式: {mode_specification(mode).label} [{mode.value}]")
        for point in self.tc_specs:
            self._append_tc_log(
                f"Day {format_day(point.day)} | {point.label} | {point.input_format} | {point.sample_path}"
            )
        self.tc_worker = threading.Thread(
            target=self._timecourse_worker,
            args=(tuple(self.tc_specs), database, mode, self.tc_series_name.get()),
            daemon=True,
            name="QASAS-timecourse-analysis",
        )
        self.tc_worker.start()

    def _timecourse_worker(
        self,
        specs: tuple[TimepointSpec, ...],
        database: Path,
        mode: MatchingMode,
        series_name: str,
    ) -> None:
        try:
            result = analyse_timecourse(
                specs,
                database,
                matching_mode=mode,
                series_name=series_name,
                status_callback=lambda text: self.tc_events.put(("status", text)),
                progress_callback=lambda sample_no, sample_total, done, total: self.tc_events.put(
                    ("progress", (sample_no, sample_total, done, total))
                ),
            )
            self.tc_events.put(("done", result))
        except Exception as exc:
            self.tc_events.put(("error", (exc, traceback.format_exc())))

    def _poll_timecourse_events(self) -> None:
        try:
            while True:
                kind, payload = self.tc_events.get_nowait()
                if kind == "status":
                    self.tc_status_text.set(str(payload))
                    self._append_tc_log(str(payload))
                elif kind == "progress":
                    sample_no, sample_total, done, total = payload
                    within = done / max(total, 1)
                    overall = ((sample_no - 1) + within) / max(sample_total, 1) * 100
                    self.tc_progress.configure(maximum=100, value=overall)
                    self.tc_status_text.set(
                        f"時点 {sample_no}/{sample_total} 照合中: {done:,}/{total:,} クローン"
                    )
                elif kind == "done":
                    assert isinstance(payload, TimeCourseResult)
                    self.tc_result = payload
                    self._render_timecourse_result(payload)
                    self._set_timecourse_busy(False)
                    self.tc_progress.configure(maximum=100, value=100)
                    self.tc_status_text.set("経時解析が完了しました。ExcelまたはFigを保存できます。")
                    self._append_tc_log("経時解析完了")
                elif kind == "error":
                    exc, trace = payload
                    self._set_timecourse_busy(False)
                    self.tc_status_text.set("経時解析中にエラーが発生しました。")
                    self._append_tc_log(trace)
                    messagebox.showerror(APP_TITLE, f"経時解析を完了できませんでした。\n\n{exc}")
        except queue.Empty:
            pass
        self.root.after(100, self._poll_timecourse_events)

    def _clear_timecourse_results(self) -> None:
        self._close_expanded_timecourse_chart()
        self.tc_summary_tree.delete(*self.tc_summary_tree.get_children())
        self.tc_series_summary.set("解析中…")
        self.tc_database_summary.set("解析中…")
        self.tc_match_summary.set("解析中…")
        self.tc_selected_box.configure(values=())
        self.tc_selected_point.set("")
        self._draw_empty_timecourse_chart()
        self._draw_empty_selected_chart()

    def _render_timecourse_result(self, result: TimeCourseResult) -> None:
        self.tc_series_summary.set(
            f"{result.series_name} | {len(result.timepoints)} time points | "
            f"Day {format_day(result.timepoints[0].spec.day)}〜{format_day(result.timepoints[-1].spec.day)}"
        )
        self.tc_database_summary.set(
            f"{len(result.database.entries):,} unique keys / {result.database.usable_rows:,} usable rows"
        )
        total_matched = sum(len(point.analysis.matches) for point in result.timepoints)
        self.tc_match_summary.set(
            f"{mode_specification(result.matching_mode).short_label} | "
            f"{total_matched:,} matched sample-clones"
        )
        for point in result.timepoints:
            for kind, summaries in (
                ("個別", point.analysis.exact_summaries),
                ("累積", point.analysis.cumulative_summaries),
            ):
                for item in summaries:
                    self.tc_summary_tree.insert(
                        "",
                        "end",
                        values=(
                            format_day(point.spec.day),
                            point.spec.label,
                            point.analysis.sample.sample_id,
                            kind,
                            item.label,
                            f"{item.unique_clones:,}",
                            f"{item.total_reads:,}",
                            f"{item.frequency_percent:.9f}",
                        ),
                    )
        point_labels = [
            f"Day {format_day(point.spec.day)} | {point.spec.label} | {point.analysis.sample.sample_id}"
            for point in result.timepoints
        ]
        self.tc_selected_box.configure(values=point_labels)
        if point_labels:
            self.tc_selected_point.set(point_labels[0])
        self._draw_timecourse_chart()
        self._draw_selected_single_chart()

    def _draw_empty_timecourse_chart(self) -> None:
        self.tc_figure.clear()
        axis = self.tc_figure.add_subplot(111)
        axis.text(
            0.5,
            0.5,
            "2件以上の検体にDayを設定して解析すると、LV0・LV1・LV2の経時変化を表示します",
            ha="center",
            va="center",
            color="#6B7785",
        )
        axis.set_axis_off()
        self.tc_figure.tight_layout()
        self.tc_chart_canvas.draw_idle()

    def _draw_timecourse_chart(self) -> None:
        if self.tc_result is None:
            self._draw_empty_timecourse_chart()
            return
        self._populate_timecourse_figure(self.tc_figure, expanded=False)
        self.tc_chart_canvas.draw_idle()
        self._refresh_expanded_timecourse_chart()

    def _populate_timecourse_figure(self, figure: Figure, *, expanded: bool) -> None:
        assert self.tc_result is not None
        figure.clear()
        cumulative = self.tc_summary_kind.get() == "累積"
        summary_sets = [
            point.analysis.cumulative_summaries if cumulative else point.analysis.exact_summaries
            for point in self.tc_result.timepoints
        ]
        days = [point.spec.day for point in self.tc_result.timepoints]
        if self.tc_chart_layout.get().startswith("3指標"):
            metrics = (
                ("unique_clones", "Number of clones", "#102A83"),
                ("total_reads", "Total reads", "#4C9F70"),
                ("frequency_percent", "%Frequency", "#127A22"),
            )
        else:
            metrics = (
                ("unique_clones", "Number of clones", "#102A83"),
                ("frequency_percent", "%Frequency", "#127A22"),
            )
        rows = len(metrics)
        axes = figure.subplots(rows, 3, squeeze=False)
        for row_index, (attribute, y_label, color) in enumerate(metrics):
            for distance in range(3):
                axis = axes[row_index][distance]
                values = [getattr(summaries[distance], attribute) for summaries in summary_sets]
                axis.plot(days, values, color=color, marker="o", linewidth=2, markersize=5)
                comparator = "<=" if cumulative else "="
                axis.set_title(
                    f"CDR3 AA Distance {comparator} {distance}",
                    fontsize=10 if expanded else 8,
                    pad=6 if expanded else 2,
                )
                if expanded or row_index == rows - 1:
                    axis.set_xlabel("Day", fontsize=9 if expanded else 7, labelpad=4 if expanded else 1)
                axis.set_ylabel(y_label, fontsize=9 if expanded else 7, labelpad=5 if expanded else 2)
                axis.grid(alpha=0.28, linestyle="--")
                axis.tick_params(labelsize=8 if expanded else 6, pad=3 if expanded else 1)
                axis.margins(x=0.04)
                if values and min(values) >= 0:
                    axis.set_ylim(bottom=0)
        if expanded:
            figure.suptitle(
                f"{self.tc_result.series_name} | "
                f"{mode_specification(self.tc_result.matching_mode).short_label}",
                fontsize=13,
                y=0.985,
            )
            figure.subplots_adjust(
                left=0.065,
                right=0.985,
                bottom=0.08,
                top=0.91,
                wspace=0.34,
                hspace=0.58 if rows == 2 else 0.72,
            )
        else:
            # The embedded canvas is intentionally compact because the input
            # controls occupy most of the screen.  Omit duplicate upper-row
            # x labels and reserve extra vertical space so titles never overlap.
            figure.subplots_adjust(
                left=0.055,
                right=0.995,
                bottom=0.14,
                top=0.96,
                wspace=0.40,
                hspace=1.05 if rows == 2 else 1.30,
            )

    def _show_expanded_timecourse_chart(self) -> None:
        if self.tc_result is None:
            return
        if self.tc_expanded_window is not None and self.tc_expanded_window.winfo_exists():
            self.tc_expanded_window.deiconify()
            self.tc_expanded_window.lift()
            self.tc_expanded_window.focus_force()
            self._refresh_expanded_timecourse_chart()
            return

        window = tk.Toplevel(self.root)
        window.title(f"{APP_TITLE} - 経時グラフ（拡大表示）")
        window.geometry("1400x850")
        window.minsize(900, 600)
        window.protocol("WM_DELETE_WINDOW", self._close_expanded_timecourse_chart)

        host = ttk.Frame(window, padding=(6, 6, 6, 2))
        host.pack(fill="both", expand=True)
        host.columnconfigure(0, weight=1)
        host.rowconfigure(0, weight=1)
        figure = Figure(figsize=(14, 8), dpi=100, facecolor="white")
        canvas = FigureCanvasTkAgg(figure, master=host)
        canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")
        toolbar = NavigationToolbar2Tk(canvas, host, pack_toolbar=False)
        toolbar.update()
        toolbar.grid(row=1, column=0, sticky="ew", pady=(4, 0))

        self.tc_expanded_window = window
        self.tc_expanded_figure = figure
        self.tc_expanded_canvas = canvas
        self._refresh_expanded_timecourse_chart()
        window.update_idletasks()
        try:
            window.state("zoomed")
        except tk.TclError:
            pass

    def _refresh_expanded_timecourse_chart(self) -> None:
        if (
            self.tc_result is None
            or self.tc_expanded_window is None
            or not self.tc_expanded_window.winfo_exists()
            or self.tc_expanded_figure is None
            or self.tc_expanded_canvas is None
        ):
            return
        self._populate_timecourse_figure(self.tc_expanded_figure, expanded=True)
        self.tc_expanded_canvas.draw_idle()

    def _close_expanded_timecourse_chart(self) -> None:
        window = self.tc_expanded_window
        self.tc_expanded_window = None
        self.tc_expanded_figure = None
        self.tc_expanded_canvas = None
        if window is not None and window.winfo_exists():
            window.destroy()

    def _draw_empty_selected_chart(self) -> None:
        self.tc_single_figure.clear()
        axis = self.tc_single_figure.add_subplot(111)
        axis.text(0.5, 0.5, "経時解析後に時点を選択すると、従来の単独Figを表示します", ha="center", va="center", color="#6B7785")
        axis.set_axis_off()
        self.tc_single_figure.tight_layout()
        self.tc_single_canvas.draw_idle()

    def _draw_selected_single_chart(self) -> None:
        if not self.tc_result:
            self._draw_empty_selected_chart()
            return
        labels = list(self.tc_selected_box.cget("values"))
        selected = self.tc_selected_point.get()
        try:
            point_index = labels.index(selected)
        except ValueError:
            point_index = 0
        point = self.tc_result.timepoints[point_index]
        result = point.analysis
        self.tc_single_figure.clear()
        distance_labels = [item.label for item in result.exact_summaries]
        values = [
            [item.unique_clones for item in result.exact_summaries],
            [item.total_reads for item in result.exact_summaries],
            [item.frequency_percent for item in result.exact_summaries],
        ]
        titles = ["Unique clones", "Total reads", "Frequency (%)"]
        colors = ["#1F77B4", "#4C9F70", "#D9822B"]
        for index, (data, title, color) in enumerate(zip(values, titles, colors, strict=True), start=1):
            axis = self.tc_single_figure.add_subplot(1, 3, index)
            bars = axis.bar(distance_labels, data, color=color, width=0.62)
            axis.set_title(title, fontsize=10)
            axis.grid(axis="y", alpha=0.25, linestyle="--")
            axis.tick_params(labelsize=8)
            for bar, value in zip(bars, data, strict=True):
                label = f"{value:.3g}" if isinstance(value, float) else f"{value:,}"
                axis.annotate(
                    label,
                    (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha="center",
                    va="bottom",
                    fontsize=7,
                )
        self.tc_single_figure.suptitle(
            f"Day {format_day(point.spec.day)} | {point.spec.label} | {result.sample.sample_id}",
            fontsize=11,
        )
        self.tc_single_figure.tight_layout(rect=(0, 0, 1, 0.94))
        self.tc_single_canvas.draw_idle()

    def _timecourse_default_stem(self) -> str:
        assert self.tc_result is not None
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", self.tc_result.series_name).strip("_") or "timecourse"
        mode_code = self.tc_result.matching_mode.value.replace("-", "_")
        return f"QASAS_{safe}_{mode_code}_{datetime.now():%Y%m%d_%H%M%S}"

    def _save_timecourse_excel(self) -> None:
        if not self.tc_result:
            return
        output_dir = self.app_dir / "QASAS 結果"
        output_dir.mkdir(parents=True, exist_ok=True)
        selected = filedialog.asksaveasfilename(
            title="経時QASAS結果を保存",
            initialdir=output_dir,
            initialfile=self._timecourse_default_stem() + ".xlsx",
            defaultextension=".xlsx",
            filetypes=(("Excel workbook", "*.xlsx"),),
        )
        if not selected:
            return
        try:
            destination = export_timecourse_xlsx(self.tc_result, selected)
        except Exception as exc:
            self._append_tc_log(traceback.format_exc())
            messagebox.showerror(APP_TITLE, f"経時結果を保存できませんでした。\n\n{exc}")
            return
        self._append_tc_log(f"経時結果保存: {destination}")
        self.tc_status_text.set(f"経時結果を保存しました: {destination.name}")
        messagebox.showinfo(APP_TITLE, f"経時結果を保存しました。\n\n{destination}")

    def _save_timecourse_figure(self) -> None:
        if not self.tc_result:
            return
        output_dir = self.app_dir / "QASAS 結果"
        output_dir.mkdir(parents=True, exist_ok=True)
        selected = filedialog.asksaveasfilename(
            title="経時QASAS Figを保存",
            initialdir=output_dir,
            initialfile=self._timecourse_default_stem() + ".png",
            defaultextension=".png",
            filetypes=(("PNG image", "*.png"), ("PDF document", "*.pdf")),
        )
        if not selected:
            return
        try:
            destination = Path(selected)
            destination.parent.mkdir(parents=True, exist_ok=True)
            export_figure = Figure(figsize=(14, 8), dpi=100, facecolor="white")
            self._populate_timecourse_figure(export_figure, expanded=True)
            export_figure.savefig(destination, dpi=300, bbox_inches="tight")
        except Exception as exc:
            self._append_tc_log(traceback.format_exc())
            messagebox.showerror(APP_TITLE, f"Figを保存できませんでした。\n\n{exc}")
            return
        self._append_tc_log(f"Fig保存: {destination}")
        self.tc_status_text.set(f"Figを保存しました: {destination.name}")
        messagebox.showinfo(APP_TITLE, f"Figを保存しました。\n\n{destination}")

    def _append_tc_log(self, message: str) -> None:
        self.tc_log_text.configure(state="normal")
        self.tc_log_text.insert("end", message.rstrip() + "\n")
        self.tc_log_text.see("end")
        self.tc_log_text.configure(state="disabled")


def main() -> None:
    root = tk.Tk()
    QASASV2Application(root)
    root.mainloop()
