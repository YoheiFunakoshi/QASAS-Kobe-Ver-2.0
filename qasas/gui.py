from __future__ import annotations

import queue
import re
import threading
import traceback
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
from matplotlib import font_manager, rcParams

from .database_formats import (
    COV_ABDAB_DATABASE_FORMAT,
    DATABASE_FORMAT_CHOICES,
    database_format_label,
    resolve_database_format,
)
from .engine import analyse
from .export import export_result_xlsx
from .input_formats import (
    AUTO_INPUT_FORMAT,
    INPUT_FORMAT_CHOICES,
    input_format_label,
    resolve_input_format,
)
from .loaders import load_database, load_sample
from .models import AnalysisResult
from .modes import GUI_MODE_LABELS, MatchingMode, mode_specification, parse_matching_mode


APP_TITLE = "QASAS Kobe Ver 2.0"


def _configure_matplotlib_japanese_font() -> None:
    available = {font.name for font in font_manager.fontManager.ttflist}
    for candidate in ("Yu Gothic", "Meiryo", "MS Gothic"):
        if candidate in available:
            rcParams["font.family"] = candidate
            return


class QASASApplication:
    def __init__(self, root: tk.Tk) -> None:
        _configure_matplotlib_japanese_font()
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("1220x800")
        self.root.minsize(980, 680)
        self.app_dir = Path(__file__).resolve().parent.parent
        self.events: queue.Queue[tuple[str, object]] = queue.Queue()
        self.result: AnalysisResult | None = None
        self.worker: threading.Thread | None = None

        self.sample_path = tk.StringVar()
        self.database_path = tk.StringVar()
        self.database_format = tk.StringVar(value=COV_ABDAB_DATABASE_FORMAT)
        self.input_format = tk.StringVar(value=AUTO_INPUT_FORMAT)
        default_mode = mode_specification(MatchingMode.KOBE)
        self.matching_mode = tk.StringVar(value=default_mode.label)
        self.mode_description = tk.StringVar(value=default_mode.description)
        self.status_text = tk.StringVar(value="検体ファイルとデータベースを選択してください。")
        self.sample_summary = tk.StringVar(value="未解析")
        self.database_summary = tk.StringVar(value="未解析")
        self.match_summary = tk.StringVar(value="未解析")

        self._configure_style()
        self._build_ui()
        self._set_default_paths()
        self.root.after(100, self._poll_events)

    def _configure_style(self) -> None:
        style = ttk.Style(self.root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Title.TLabel", font=("Yu Gothic UI", 18, "bold"), foreground="#17365D")
        style.configure("Subtitle.TLabel", font=("Yu Gothic UI", 9), foreground="#4F6070")
        style.configure("CardTitle.TLabel", font=("Yu Gothic UI", 9), foreground="#536577")
        style.configure("CardValue.TLabel", font=("Yu Gothic UI", 12, "bold"), foreground="#17365D")
        style.configure("Run.TButton", font=("Yu Gothic UI", 11, "bold"), padding=(18, 8))
        style.configure("Treeview", rowheight=26, font=("Yu Gothic UI", 9))
        style.configure("Treeview.Heading", font=("Yu Gothic UI", 9, "bold"))

    def _create_input_format_buttons(
        self,
        parent: tk.Misc,
        variable: tk.StringVar,
    ) -> tuple[ttk.Frame, tuple[ttk.Radiobutton, ...]]:
        frame = ttk.Frame(parent)
        enabled_buttons: list[ttk.Radiobutton] = []
        for column, choice in enumerate(INPUT_FORMAT_CHOICES):
            button = ttk.Radiobutton(
                frame,
                text=choice.label,
                variable=variable,
                value=choice.value,
            )
            button.grid(row=0, column=column, sticky="w", padx=(0, 12))
            if choice.enabled:
                enabled_buttons.append(button)
            else:
                button.state(["disabled"])
        ttk.Label(
            frame,
            text="※ 参照したファイルからRG/CPMを自動選択します。",
            style="Subtitle.TLabel",
        ).grid(
            row=1,
            column=0,
            columnspan=len(INPUT_FORMAT_CHOICES),
            sticky="w",
            pady=(2, 0),
        )
        return frame, tuple(enabled_buttons)

    def _resolve_input_format(self, path: Path, variable: tk.StringVar) -> str:
        resolved = resolve_input_format(variable.get(), path)
        variable.set(resolved)
        return resolved

    def _auto_select_input_format(self, path: Path, variable: tk.StringVar, status: tk.StringVar) -> None:
        resolved = resolve_input_format(AUTO_INPUT_FORMAT, path)
        variable.set(resolved)
        status.set(f"入力形式を自動判定しました: {input_format_label(resolved)}")

    def _create_database_format_buttons(
        self,
        parent: tk.Misc,
        variable: tk.StringVar,
    ) -> tuple[ttk.Frame, tuple[ttk.Radiobutton, ...]]:
        frame = ttk.Frame(parent)
        enabled_buttons: list[ttk.Radiobutton] = []
        for column, choice in enumerate(DATABASE_FORMAT_CHOICES):
            button = ttk.Radiobutton(
                frame,
                text=choice.label,
                variable=variable,
                value=choice.value,
            )
            button.grid(row=0, column=column, sticky="w", padx=(0, 12))
            if choice.enabled:
                enabled_buttons.append(button)
            else:
                button.state(["disabled"])
        ttk.Label(
            frame,
            text="※ 現在はCoV-AbDabのみ対応しています。",
            style="Subtitle.TLabel",
        ).grid(row=1, column=0, columnspan=len(DATABASE_FORMAT_CHOICES), sticky="w", pady=(2, 0))
        return frame, tuple(enabled_buttons)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=14)
        outer.pack(fill="both", expand=True)

        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 10))
        ttk.Label(header, text=APP_TITLE, style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            header,
            text="旧QASAS／Kobe Ver 1.0／CDR3のみを選択してLV0・LV1・LV2照合（単独検体）",
            style="Subtitle.TLabel",
        ).pack(anchor="w")

        input_frame = ttk.LabelFrame(outer, text="入力", padding=10)
        input_frame.pack(fill="x")
        input_frame.columnconfigure(1, weight=1)

        ttk.Label(input_frame, text="検体レパトア").grid(row=0, column=0, sticky="w", padx=(0, 8), pady=4)
        self.sample_entry = ttk.Entry(input_frame, textvariable=self.sample_path)
        self.sample_entry.grid(row=0, column=1, sticky="ew", pady=4)
        self.sample_button = ttk.Button(input_frame, text="参照…", command=self._browse_sample)
        self.sample_button.grid(row=0, column=2, padx=(8, 0), pady=4)

        ttk.Label(input_frame, text="入力様式").grid(row=1, column=0, sticky="w", padx=(0, 8), pady=4)
        self.format_frame, self.format_buttons = self._create_input_format_buttons(
            input_frame,
            self.input_format,
        )
        self.format_frame.grid(row=1, column=1, columnspan=2, sticky="w", pady=4)

        ttk.Label(input_frame, text="照合方式").grid(row=2, column=0, sticky="w", padx=(0, 8), pady=4)
        mode_frame = ttk.Frame(input_frame)
        mode_frame.grid(row=2, column=1, sticky="ew", pady=4)
        self.mode_box = ttk.Combobox(
            mode_frame,
            textvariable=self.matching_mode,
            values=GUI_MODE_LABELS,
            state="readonly",
            width=36,
        )
        self.mode_box.pack(side="left")
        self.mode_box.bind("<<ComboboxSelected>>", self._on_mode_changed)
        ttk.Label(
            mode_frame,
            textvariable=self.mode_description,
            style="Subtitle.TLabel",
            wraplength=620,
        ).pack(side="left", padx=(10, 0))

        ttk.Label(input_frame, text="DB形式").grid(row=3, column=0, sticky="w", padx=(0, 8), pady=4)
        self.database_format_frame, self.database_format_buttons = self._create_database_format_buttons(
            input_frame,
            self.database_format,
        )
        self.database_format_frame.grid(row=3, column=1, columnspan=2, sticky="w", pady=4)

        ttk.Label(input_frame, text="抗体DBファイル").grid(row=4, column=0, sticky="w", padx=(0, 8), pady=4)
        self.database_entry = ttk.Entry(input_frame, textvariable=self.database_path)
        self.database_entry.grid(row=4, column=1, sticky="ew", pady=4)
        self.database_button = ttk.Button(input_frame, text="参照…", command=self._browse_database)
        self.database_button.grid(row=4, column=2, padx=(8, 0), pady=4)

        action_frame = ttk.Frame(outer)
        action_frame.pack(fill="x", pady=10)
        self.run_button = ttk.Button(action_frame, text="QASAS解析を実行", style="Run.TButton", command=self._start_analysis)
        self.run_button.pack(side="left")
        self.save_button = ttk.Button(action_frame, text="結果をExcel保存…", command=self._save_result, state="disabled")
        self.save_button.pack(side="left", padx=(8, 0))
        ttk.Label(action_frame, text="※ 照合方式は画面・ログ・Excelへ記録されます", style="Subtitle.TLabel").pack(side="right")

        cards = ttk.Frame(outer)
        cards.pack(fill="x", pady=(0, 10))
        for column, (title, variable) in enumerate(
            (
                ("検体", self.sample_summary),
                ("データベース", self.database_summary),
                ("選択方式のLV0〜LV2一致", self.match_summary),
            )
        ):
            cards.columnconfigure(column, weight=1)
            card = ttk.LabelFrame(cards, padding=(10, 6))
            card.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 5, 0))
            ttk.Label(card, text=title, style="CardTitle.TLabel").pack(anchor="w")
            ttk.Label(card, textvariable=variable, style="CardValue.TLabel").pack(anchor="w")

        notebook = ttk.Notebook(outer)
        notebook.pack(fill="both", expand=True)
        summary_tab = ttk.Frame(notebook, padding=8)
        matches_tab = ttk.Frame(notebook, padding=8)
        log_tab = ttk.Frame(notebook, padding=8)
        notebook.add(summary_tab, text="サマリー・グラフ")
        notebook.add(matches_tab, text="一致クローン")
        notebook.add(log_tab, text="処理ログ")

        summary_tab.columnconfigure(0, weight=2)
        summary_tab.columnconfigure(1, weight=5)
        summary_tab.rowconfigure(0, weight=1)
        self.summary_tree = ttk.Treeview(
            summary_tab,
            columns=("kind", "level", "clones", "reads", "frequency"),
            show="headings",
            height=10,
        )
        headings = {
            "kind": "集計",
            "level": "距離",
            "clones": "ユニーククローン",
            "reads": "総リード",
            "frequency": "頻度 (%)",
        }
        widths = {"kind": 80, "level": 70, "clones": 120, "reads": 105, "frequency": 120}
        for column in headings:
            self.summary_tree.heading(column, text=headings[column])
            self.summary_tree.column(column, width=widths[column], anchor="center")
        self.summary_tree.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        self.figure = Figure(figsize=(7.2, 3.6), dpi=100, facecolor="white")
        self.chart_canvas = FigureCanvasTkAgg(self.figure, master=summary_tab)
        self.chart_canvas.get_tk_widget().grid(row=0, column=1, sticky="nsew")
        self._draw_empty_chart()

        matches_tab.columnconfigure(0, weight=1)
        matches_tab.rowconfigure(0, weight=1)
        match_columns = ("lv", "v", "j", "cdr3", "reads", "frequency", "name", "binds", "epitope")
        self.matches_tree = ttk.Treeview(matches_tab, columns=match_columns, show="headings")
        match_headings = {
            "lv": "距離",
            "v": "IGHV",
            "j": "IGHJ",
            "cdr3": "CDR3 AA（正規化）",
            "reads": "Reads",
            "frequency": "頻度 (%)",
            "name": "DB Name",
            "binds": "Binds to",
            "epitope": "Protein + Epitope",
        }
        match_widths = {
            "lv": 55,
            "v": 120,
            "j": 100,
            "cdr3": 190,
            "reads": 85,
            "frequency": 105,
            "name": 160,
            "binds": 180,
            "epitope": 220,
        }
        for column in match_columns:
            self.matches_tree.heading(column, text=match_headings[column])
            anchor = "e" if column in {"reads", "frequency"} else "w"
            self.matches_tree.column(column, width=match_widths[column], minwidth=50, anchor=anchor)
        vertical = ttk.Scrollbar(matches_tab, orient="vertical", command=self.matches_tree.yview)
        horizontal = ttk.Scrollbar(matches_tab, orient="horizontal", command=self.matches_tree.xview)
        self.matches_tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.matches_tree.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")

        log_tab.columnconfigure(0, weight=1)
        log_tab.rowconfigure(0, weight=1)
        self.log_text = tk.Text(log_tab, wrap="word", state="disabled", font=("Consolas", 9))
        self.log_text.grid(row=0, column=0, sticky="nsew")
        log_scroll = ttk.Scrollbar(log_tab, orient="vertical", command=self.log_text.yview)
        log_scroll.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=log_scroll.set)

        status_frame = ttk.Frame(outer)
        status_frame.pack(fill="x", pady=(8, 0))
        self.progress = ttk.Progressbar(status_frame, mode="indeterminate", length=230)
        self.progress.pack(side="left")
        ttk.Label(status_frame, textvariable=self.status_text).pack(side="left", padx=(10, 0))

    def _set_default_paths(self) -> None:
        sample_dir = self.app_dir / "QASAS レパトアデータ"
        database_dir = self.app_dir / "QASAS データベース CoV-AbDab"
        if sample_dir.is_dir():
            candidates = sorted(
                [*sample_dir.glob("*.csv"), *sample_dir.glob("*.xlsx")],
                key=lambda path: path.name.lower(),
            )
            if candidates:
                self.sample_path.set(str(candidates[0]))
                self._auto_select_input_format(candidates[0], self.input_format, self.status_text)
        if database_dir.is_dir():
            candidates = sorted(database_dir.glob("*.csv"), key=lambda path: path.name.lower())
            if candidates:
                self.database_path.set(str(candidates[0]))

    def _browse_sample(self) -> None:
        initial = Path(self.sample_path.get()).parent if self.sample_path.get() else self.app_dir
        selected = filedialog.askopenfilename(
            title="検体レパトアを選択",
            initialdir=initial,
            filetypes=(
                ("QASAS repertoire", "*.csv *.tsv *.xlsx *.xlsm"),
                ("CPM CSV", "*.csv *.tsv"),
                ("RG Excel", "*.xlsx *.xlsm"),
                ("All files", "*.*"),
            ),
        )
        if selected:
            self.sample_path.set(selected)
            try:
                self._auto_select_input_format(Path(selected), self.input_format, self.status_text)
            except ValueError as exc:
                self.input_format.set(AUTO_INPUT_FORMAT)
                messagebox.showerror(APP_TITLE, f"入力形式を判定できませんでした。\n\n{exc}")

    def _browse_database(self) -> None:
        initial = Path(self.database_path.get()).parent if self.database_path.get() else self.app_dir
        selected = filedialog.askopenfilename(
            title="抗原結合性データベースを選択",
            initialdir=initial,
            filetypes=(("CSV database", "*.csv *.tsv"), ("All files", "*.*")),
        )
        if selected:
            self.database_path.set(selected)

    def _on_mode_changed(self, _event: object | None = None) -> None:
        spec = mode_specification(self.matching_mode.get())
        self.mode_description.set(spec.description)
        self.status_text.set(f"照合方式: {spec.label}")

    def _set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        for widget in (self.run_button, self.sample_button, self.database_button, self.sample_entry, self.database_entry):
            widget.configure(state=state)
        for button in self.format_buttons:
            button.configure(state=state)
        for button in self.database_format_buttons:
            button.configure(state=state)
        self.mode_box.configure(state="disabled" if busy else "readonly")
        if busy:
            self.save_button.configure(state="disabled")
            self.progress.configure(mode="indeterminate")
            self.progress.start(12)
        else:
            self.progress.stop()
            self.progress.configure(mode="determinate", value=100 if self.result else 0)
            self.save_button.configure(state="normal" if self.result else "disabled")

    def _start_analysis(self) -> None:
        sample = Path(self.sample_path.get().strip())
        database = Path(self.database_path.get().strip())
        if not sample.is_file():
            messagebox.showerror(APP_TITLE, "検体レパトアファイルを選択してください。")
            return
        if not database.is_file():
            messagebox.showerror(APP_TITLE, "抗原結合性データベースCSVを選択してください。")
            return
        if self.worker and self.worker.is_alive():
            return
        try:
            input_format = self._resolve_input_format(sample, self.input_format)
            database_format = resolve_database_format(self.database_format.get())
        except ValueError as exc:
            messagebox.showerror(APP_TITLE, str(exc))
            return
        self.result = None
        self._clear_results()
        self._set_busy(True)
        self.status_text.set("解析を開始しています…")
        self._append_log(f"\n[{datetime.now():%Y-%m-%d %H:%M:%S}] QASAS解析開始")
        self._append_log(f"検体: {sample}")
        self._append_log(f"DB  : {database}")
        self._append_log(f"入力形式: {input_format_label(input_format)}")
        self._append_log(f"DB形式: {database_format_label(database_format)}")
        matching_mode = parse_matching_mode(self.matching_mode.get())
        self._append_log(f"方式: {mode_specification(matching_mode).label} [{matching_mode.value}]")
        self.worker = threading.Thread(
            target=self._analysis_worker,
            args=(sample, database, input_format, database_format, matching_mode),
            daemon=True,
            name="QASAS-analysis",
        )
        self.worker.start()

    def _analysis_worker(
        self,
        sample_path: Path,
        database_path: Path,
        input_format: str,
        database_format: str,
        matching_mode: MatchingMode,
    ) -> None:
        try:
            status = lambda text: self.events.put(("status", text))
            sample = load_sample(
                sample_path,
                input_format,
                status,
                matching_mode=matching_mode,
            )
            database = load_database(
                database_path,
                status,
                matching_mode=matching_mode,
                database_format=database_format,
            )
            self.events.put(
                ("status", f"{mode_specification(matching_mode).short_label}方式でCDR3距離を照合しています…")
            )
            result = analyse(
                sample,
                database,
                max_distance=2,
                progress_callback=lambda done, total: self.events.put(("progress", (done, total))),
                matching_mode=matching_mode,
            )
            self.events.put(("done", result))
        except Exception as exc:
            self.events.put(("error", (exc, traceback.format_exc())))

    def _poll_events(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "status":
                    self.status_text.set(str(payload))
                    self._append_log(str(payload))
                elif kind == "progress":
                    done, total = payload
                    self.progress.stop()
                    self.progress.configure(mode="determinate", maximum=max(total, 1), value=done)
                    self.status_text.set(f"照合中: {done:,} / {total:,} クローン")
                elif kind == "done":
                    assert isinstance(payload, AnalysisResult)
                    self.result = payload
                    self._render_result(payload)
                    self._set_busy(False)
                    self.status_text.set("解析が完了しました。結果を確認またはExcel保存できます。")
                    self._append_log("解析完了")
                elif kind == "error":
                    exc, trace = payload
                    self._set_busy(False)
                    self.status_text.set("解析中にエラーが発生しました。")
                    self._append_log(trace)
                    messagebox.showerror(APP_TITLE, f"解析を完了できませんでした。\n\n{exc}")
        except queue.Empty:
            pass
        self.root.after(100, self._poll_events)

    def _clear_results(self) -> None:
        for tree in (self.summary_tree, self.matches_tree):
            tree.delete(*tree.get_children())
        self.sample_summary.set("解析中…")
        self.database_summary.set("解析中…")
        self.match_summary.set("解析中…")
        self._draw_empty_chart()

    def _render_result(self, result: AnalysisResult) -> None:
        if result.sample.listed_reads == result.sample.total_reads:
            read_text = f"{result.sample.total_reads:,} reads"
        else:
            read_text = (
                f"{result.sample.listed_reads:,} listed reads / "
                f"{result.sample.total_reads:,} denominator"
            )
        self.sample_summary.set(f"{result.sample.sample_id} | {len(result.sample.clones):,} clones / {read_text}")
        database_format = result.database.metadata.get("Database input format", "未指定")
        self.database_summary.set(
            f"{database_format_label(database_format)} | "
            f"{len(result.database.entries):,} unique keys / {result.database.usable_rows:,} usable rows"
        )
        self.match_summary.set(
            f"{mode_specification(result.matching_mode).short_label} | "
            f"{len(result.matches):,} clones / {sum(match.clone.reads for match in result.matches):,} reads"
        )
        for item in result.exact_summaries:
            self.summary_tree.insert(
                "",
                "end",
                values=("個別", item.label, f"{item.unique_clones:,}", f"{item.total_reads:,}", f"{item.frequency_percent:.9f}"),
            )
        for item in result.cumulative_summaries:
            self.summary_tree.insert(
                "",
                "end",
                values=("累積", item.label, f"{item.unique_clones:,}", f"{item.total_reads:,}", f"{item.frequency_percent:.9f}"),
            )
        for match in result.matches:
            self.matches_tree.insert(
                "",
                "end",
                values=(
                    f"LV{match.distance}",
                    match.clone.display_v_gene,
                    match.clone.display_j_gene,
                    match.clone.cdr3_aa,
                    f"{match.clone.reads:,}",
                    f"{match.clone.frequency_percent:.9f}",
                    match.combined_annotation("Name"),
                    match.combined_annotation("Binds to"),
                    match.combined_annotation("Protein + Epitope"),
                ),
            )
        self._draw_chart(result)
        self._append_log(f"照合方式: {result.matching_mode_label} [{result.matching_mode.value}]")
        for item in result.exact_summaries:
            self._append_log(
                f"{item.label}: unique={item.unique_clones:,}, reads={item.total_reads:,}, frequency={item.frequency_percent:.9f}%"
            )

    def _draw_empty_chart(self) -> None:
        self.figure.clear()
        axis = self.figure.add_subplot(111)
        axis.text(0.5, 0.5, "方式を選択して解析するとLV0・LV1・LV2を表示します", ha="center", va="center", color="#6B7785")
        axis.set_axis_off()
        self.figure.tight_layout()
        self.chart_canvas.draw_idle()

    def _draw_chart(self, result: AnalysisResult) -> None:
        self.figure.clear()
        labels = [item.label for item in result.exact_summaries]
        values = [
            [item.unique_clones for item in result.exact_summaries],
            [item.total_reads for item in result.exact_summaries],
            [item.frequency_percent for item in result.exact_summaries],
        ]
        titles = ["Unique clones", "Total reads", "Frequency (%)"]
        colors = ["#1F77B4", "#4C9F70", "#D9822B"]
        for index, (data, title, color) in enumerate(zip(values, titles, colors, strict=True), start=1):
            axis = self.figure.add_subplot(1, 3, index)
            bars = axis.bar(labels, data, color=color, width=0.62)
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
        self.figure.tight_layout()
        self.chart_canvas.draw_idle()

    def _save_result(self) -> None:
        if not self.result:
            return
        output_dir = self.app_dir / "QASAS 結果"
        output_dir.mkdir(parents=True, exist_ok=True)
        safe_sample = re.sub(r"[^A-Za-z0-9_.-]+", "_", self.result.sample.sample_id).strip("_") or "sample"
        mode_code = self.result.matching_mode.value.replace("-", "_")
        default_name = f"QASAS_{safe_sample}_{mode_code}_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
        selected = filedialog.asksaveasfilename(
            title="QASAS結果を保存",
            initialdir=output_dir,
            initialfile=default_name,
            defaultextension=".xlsx",
            filetypes=(("Excel workbook", "*.xlsx"),),
        )
        if not selected:
            return
        try:
            destination = export_result_xlsx(self.result, selected)
        except Exception as exc:
            self._append_log(traceback.format_exc())
            messagebox.showerror(APP_TITLE, f"結果を保存できませんでした。\n\n{exc}")
            return
        self._append_log(f"結果保存: {destination}")
        self.status_text.set(f"結果を保存しました: {destination.name}")
        messagebox.showinfo(APP_TITLE, f"結果を保存しました。\n\n{destination}")

    def _append_log(self, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message.rstrip() + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")


def main() -> None:
    root = tk.Tk()
    QASASApplication(root)
    root.mainloop()
