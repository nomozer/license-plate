import os
import threading
import tkinter as tk
from tkinter import filedialog, ttk, messagebox

import cv2
from PIL import Image, ImageTk

from lpAppModel import LPAppModel

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}

# ── Light-mode colour palette ────────────────────────────────────────────────
BG        = "#f5f5f5"
BG2       = "#ffffff"
BG3       = "#e0e0e0"
ACCENT    = "#1976d2"
ACCENT2   = "#1565c0"
FG        = "#212121"
FG2       = "#757575"
GREEN     = "#2e7d32"
RED       = "#c62828"
YELLOW    = "#f57f17"
SEL_BG    = "#bbdefb"


class LPApp:
    """Giao diện Tkinter cho ứng dụng nhận dạng biển số xe – chế độ Batch."""

    WINDOW_TITLE = "🚗 Nhận Dạng Biển Số Xe – Batch Mode"
    WINDOW_SIZE  = "1400x820"

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(self.WINDOW_TITLE)
        self.root.geometry(self.WINDOW_SIZE)
        self.root.resizable(True, True)
        self.root.configure(bg=BG)
        self.root.option_add("*tearOff", False)

        self._apply_theme()
        self.lp_model = LPAppModel()

        # ── State ────────────────────────────────────────────────────────────
        self.folder_path: str | None = None
        self.image_paths: list[str] = []
        self.current_idx: int = -1
        self.results: dict[str, dict] = {}   # path -> {texts, confs, det_confs}
        self._photo_original = None
        self._photo_result   = None
        self._plate_photos: list = []
        self._processing     = False

        self._build_ui()

    # ── Theme ──────────────────────────────────────────────────────────────

    def _apply_theme(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")

        style.configure(".",
            background=BG, foreground=FG,
            fieldbackground=BG2, troughcolor=BG3,
            selectbackground=SEL_BG, selectforeground=FG,
            font=("Segoe UI", 10))

        style.configure("TFrame",        background=BG)
        style.configure("Card.TFrame",   background=BG2, relief="flat")
        style.configure("TLabel",        background=BG,  foreground=FG)
        style.configure("Card.TLabel",   background=BG2, foreground=FG)
        style.configure("Dim.TLabel",    background=BG2, foreground=FG2, font=("Segoe UI", 9))
        style.configure("Header.TLabel", background=BG,  foreground=ACCENT,
                         font=("Segoe UI", 11, "bold"))

        style.configure("TLabelframe",
            background=BG2, foreground=ACCENT,
            bordercolor=BG3, lightcolor=BG3, darkcolor=BG3)
        style.configure("TLabelframe.Label",
            background=BG2, foreground=ACCENT, font=("Segoe UI", 10, "bold"))

        style.configure("Accent.TButton",
            background=ACCENT, foreground="white",
            borderwidth=0, focusthickness=0, relief="flat",
            font=("Segoe UI", 10, "bold"), padding=(12, 6))
        style.map("Accent.TButton",
            background=[("active", ACCENT2), ("disabled", BG3)],
            foreground=[("active", "white"), ("disabled", FG2)])

        style.configure("TButton",
            background=BG3, foreground=FG,
            borderwidth=0, relief="flat",
            font=("Segoe UI", 10), padding=(10, 5))
        style.map("TButton",
            background=[("active", SEL_BG)])

        style.configure("TProgressbar",
            background=ACCENT, troughcolor=BG3, borderwidth=0, thickness=6)

        style.configure("Treeview",
            background=BG2, foreground=FG,
            fieldbackground=BG2, borderwidth=1,
            rowheight=26, font=("Segoe UI", 9))
        style.configure("Treeview.Heading",
            background=BG3, foreground=FG,
            borderwidth=0, font=("Segoe UI", 9, "bold"))
        style.map("Treeview",
            background=[("selected", SEL_BG)],
            foreground=[("selected", FG)])

        style.configure("TSeparator", background=BG3)
        style.configure("TScrollbar",
            background=BG3, troughcolor=BG2,
            arrowcolor=FG2, borderwidth=0)

    # ── Build UI ───────────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Toolbar ──────────────────────────────────────────────────────
        toolbar = ttk.Frame(self.root, padding=(12, 8))
        toolbar.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(toolbar, text="🚗 BIỂN SỐ XE", style="Header.TLabel").pack(side=tk.LEFT)
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=12)

        self.btn_folder = ttk.Button(toolbar, text="📁 Mở Folder",
                                     style="Accent.TButton", command=self._open_folder)
        self.btn_folder.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_run_all = ttk.Button(toolbar, text="⚡ Nhận Dạng Tất Cả",
                                      command=self._run_all, state=tk.DISABLED)
        self.btn_run_all.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_run_one = ttk.Button(toolbar, text="🔍 Nhận Dạng Ảnh Này",
                                      command=self._run_current, state=tk.DISABLED)
        self.btn_run_one.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_export = ttk.Button(toolbar, text="💾 Xuất Kết Quả",
                                     command=self._export_results, state=tk.DISABLED)
        self.btn_export.pack(side=tk.LEFT, padx=(0, 8))

        # Progress
        self.prog_var = tk.DoubleVar(value=0)
        self.prog_bar = ttk.Progressbar(toolbar, variable=self.prog_var,
                                         maximum=100, length=200)
        self.prog_bar.pack(side=tk.RIGHT, padx=(0, 12))
        self.prog_lbl = ttk.Label(toolbar, text="", style="Card.TLabel")
        self.prog_lbl.pack(side=tk.RIGHT, padx=(0, 6))

        # ── Main PanedWindow ─────────────────────────────────────────────
        main_pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 6))

        # LEFT: File list
        left = self._build_left_panel(main_pane)
        main_pane.add(left, weight=1)

        # MIDDLE: Image viewer
        mid = self._build_mid_panel(main_pane)
        main_pane.add(mid, weight=3)

        # RIGHT: Detection results
        right = self._build_right_panel(main_pane)
        main_pane.add(right, weight=2)

        # ── Status bar ────────────────────────────────────────────────────
        self.status_var = tk.StringVar(value="Sẵn sàng. Hãy mở folder ảnh để bắt đầu.")
        sb = ttk.Label(self.root, textvariable=self.status_var,
                        relief=tk.SUNKEN, anchor=tk.W, padding=(6, 3),
                        background=BG3, foreground=FG2, font=("Segoe UI", 9))
        sb.pack(side=tk.BOTTOM, fill=tk.X)

    def _build_left_panel(self, parent) -> ttk.Frame:
        frame = ttk.LabelFrame(parent, text="📋 Danh Sách Ảnh", padding=6)

        # Search box
        search_row = ttk.Frame(frame, style="Card.TFrame")
        search_row.pack(fill=tk.X, pady=(0, 6))
        ttk.Label(search_row, text="🔎", style="Card.TLabel").pack(side=tk.LEFT, padx=(4, 2))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self._filter_list)
        search_entry = tk.Entry(search_row, textvariable=self.search_var,
                                 bg=BG2, fg=FG, insertbackground=FG,
                                 relief="sunken", font=("Segoe UI", 9), bd=2)
        search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Listbox
        list_frame = ttk.Frame(frame)
        list_frame.pack(fill=tk.BOTH, expand=True)

        self.listbox = tk.Listbox(list_frame,
            bg=BG2, fg=FG, selectbackground=SEL_BG, selectforeground=FG,
            activestyle="none", relief="sunken", borderwidth=1,
            font=("Segoe UI", 9), highlightthickness=0)
        vsb = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=vsb.set)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.listbox.bind("<<ListboxSelect>>", self._on_list_select)

        # Stats
        self.stat_lbl = ttk.Label(frame, text="0 ảnh", style="Dim.TLabel")
        self.stat_lbl.pack(anchor=tk.W, pady=(4, 0))

        return frame

    def _build_mid_panel(self, parent) -> ttk.Frame:
        frame = ttk.Frame(parent, padding=4)

        # File name label
        self.file_name_lbl = ttk.Label(frame, text="—", style="Header.TLabel",
                                        font=("Segoe UI", 10, "bold"))
        self.file_name_lbl.pack(anchor=tk.W, pady=(0, 4))

        img_pane = ttk.PanedWindow(frame, orient=tk.VERTICAL)
        img_pane.pack(fill=tk.BOTH, expand=True)

        orig_frame = ttk.LabelFrame(img_pane, text="Ảnh Gốc", padding=4)
        img_pane.add(orig_frame, weight=1)
        self.canvas_original = tk.Canvas(orig_frame, bg="#e8e8e8", highlightthickness=0)
        self.canvas_original.pack(fill=tk.BOTH, expand=True)

        result_frame = ttk.LabelFrame(img_pane, text="Kết Quả Phát Hiện", padding=4)
        img_pane.add(result_frame, weight=1)
        self.canvas_result = tk.Canvas(result_frame, bg="#e8e8e8", highlightthickness=0)
        self.canvas_result.pack(fill=tk.BOTH, expand=True)

        # Nav buttons
        nav = ttk.Frame(frame)
        nav.pack(fill=tk.X, pady=(6, 0))
        ttk.Button(nav, text="◀ Trước", command=self._prev_image).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(nav, text="Tiếp ▶", command=self._next_image).pack(side=tk.LEFT)
        self.nav_lbl = ttk.Label(nav, text="—", style="Card.TLabel")
        self.nav_lbl.pack(side=tk.RIGHT)

        return frame

    def _build_right_panel(self, parent) -> ttk.Frame:
        frame = ttk.Frame(parent, padding=4)

        # Cropped plates
        plates_frame = ttk.LabelFrame(frame, text="Biển Số Tách Được", padding=6)
        plates_frame.pack(fill=tk.X)
        self.plates_container = ttk.Frame(plates_frame)
        self.plates_container.pack(fill=tk.X)

        # Current result text
        cur_frame = ttk.LabelFrame(frame, text="Kết Quả Ảnh Hiện Tại", padding=6)
        cur_frame.pack(fill=tk.X, pady=(8, 0))
        self.result_text = tk.Text(cur_frame, height=5,
                                    font=("Consolas", 11), wrap=tk.WORD,
                                    bg=BG2, fg=GREEN, insertbackground=FG,
                                    relief="sunken", borderwidth=1,
                                    highlightthickness=0)
        self.result_text.pack(fill=tk.X)

        # Batch results table
        table_frame = ttk.LabelFrame(frame, text="📊 Tổng Hợp Tất Cả Kết Quả", padding=6)
        table_frame.pack(fill=tk.BOTH, expand=True, pady=(8, 0))

        cols = ("file", "plates", "texts")
        self.tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=10)
        self.tree.heading("file",   text="Tên File")
        self.tree.heading("plates", text="Số Biển")
        self.tree.heading("texts",  text="Biển Số Đọc Được")
        self.tree.column("file",   width=130, anchor=tk.W)
        self.tree.column("plates", width=60,  anchor=tk.CENTER)
        self.tree.column("texts",  width=220, anchor=tk.W)

        tsb = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=tsb.set)
        tsb.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        # Tag colours for table rows
        self.tree.tag_configure("found",    background="#e8f5e9", foreground=GREEN)
        self.tree.tag_configure("notfound", background="#ffebee", foreground=RED)
        self.tree.tag_configure("pending",  background=BG2,       foreground=FG2)

        return frame

    # ── Folder / File Loading ──────────────────────────────────────────────

    def _open_folder(self):
        folder = filedialog.askdirectory(title="Chọn Folder Ảnh")
        if not folder:
            return
        self.folder_path = folder
        paths = sorted([
            os.path.join(folder, f)
            for f in os.listdir(folder)
            if os.path.splitext(f)[1].lower() in IMAGE_EXTS
        ])
        if not paths:
            messagebox.showwarning("Không tìm thấy ảnh",
                                   "Folder không chứa file ảnh được hỗ trợ.")
            return
        self.image_paths = paths
        self.results = {}
        self.current_idx = -1
        self._refresh_list()
        self._populate_tree()
        self.btn_run_all.configure(state=tk.NORMAL)
        self.btn_run_one.configure(state=tk.NORMAL)
        self.status_var.set(f"Đã tải {len(paths)} ảnh từ: {folder}")
        self._load_image(0)

    def _refresh_list(self, filter_text: str = ""):
        self.listbox.delete(0, tk.END)
        for p in self.image_paths:
            name = os.path.basename(p)
            if filter_text.lower() in name.lower():
                status = ""
                if p in self.results:
                    n = len(self.results[p].get("texts", []))
                    status = f"  ✔ {n}" if n else "  ✘"
                self.listbox.insert(tk.END, f" {name}{status}")
        self.stat_lbl.configure(text=f"{len(self.image_paths)} ảnh")

    def _filter_list(self, *_):
        self._refresh_list(self.search_var.get())

    def _populate_tree(self):
        for row in self.tree.get_children():
            self.tree.delete(row)
        for p in self.image_paths:
            name = os.path.basename(p)
            if p in self.results:
                texts = self.results[p].get("texts", [])
                joined = " | ".join(t for t in texts if t) or "—"
                tag = "found" if any(texts) else "notfound"
                self.tree.insert("", tk.END, iid=p,
                                  values=(name, len(texts), joined), tags=(tag,))
            else:
                self.tree.insert("", tk.END, iid=p,
                                  values=(name, "—", "Chưa xử lý"), tags=("pending",))

    # ── Image Display ──────────────────────────────────────────────────────

    def _load_image(self, idx: int):
        if not self.image_paths or idx < 0 or idx >= len(self.image_paths):
            return
        self.current_idx = idx
        path = self.image_paths[idx]
        name = os.path.basename(path)

        self.file_name_lbl.configure(text=name)
        self.nav_lbl.configure(text=f"{idx + 1} / {len(self.image_paths)}")

        img = cv2.imread(path)
        if img is None:
            self.status_var.set(f"Không đọc được ảnh: {name}")
            return

        self._display_cv_image(img, self.canvas_original, "original")

        # Sync listbox
        self.listbox.selection_clear(0, tk.END)
        self.listbox.selection_set(idx)
        self.listbox.see(idx)

        # Show cached result if any
        if path in self.results:
            self._show_result_for(path)
        else:
            self.canvas_result.delete("all")
            self._clear_plate_display()
            self.result_text.delete("1.0", tk.END)
            self.result_text.insert(tk.END, "Chưa nhận dạng. Bấm 🔍 để xử lý.")

        self.status_var.set(f"Đang xem: {name}")

    def _display_cv_image(self, cv_img, canvas, tag):
        canvas.update_idletasks()
        cw = canvas.winfo_width()  or 500
        ch = canvas.winfo_height() or 300
        rgb = cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(rgb)
        pil.thumbnail((cw, ch), Image.LANCZOS)
        photo = ImageTk.PhotoImage(pil)
        canvas.delete("all")
        canvas.create_image(cw // 2, ch // 2, anchor=tk.CENTER, image=photo)
        if tag == "original":
            self._photo_original = photo
        else:
            self._photo_result = photo

    def _show_result_for(self, path: str):
        r = self.results[path]
        img_result = r.get("img_result")
        if img_result is not None:
            self._display_cv_image(img_result, self.canvas_result, "result")

        self._clear_plate_display()
        self.result_text.delete("1.0", tk.END)

        lp_imgs   = r.get("lp_imgs",      [])
        texts     = r.get("texts",         [])
        confs     = r.get("lp_confs",      [])
        det_confs = r.get("det_confs",     [])

        if not texts:
            self.result_text.insert(tk.END, "Không tìm thấy biển số nào.")
            return

        for i, (txt, lp_c, det_c) in enumerate(zip(texts, confs, det_confs)):
            if i < len(lp_imgs):
                self._add_plate_image(lp_imgs[i])
            display = txt if txt else "(không đọc được)"
            self.result_text.insert(
                tk.END,
                f"Biển {i + 1}: {display}  "
                f"(YOLO: {det_c:.2f} | OCR: {lp_c:.2f})\n"
            )

    # ── Detection ──────────────────────────────────────────────────────────

    def _run_current(self):
        if self.current_idx < 0 or not self.image_paths:
            return
        path = self.image_paths[self.current_idx]
        self._process_single(path)
        self._show_result_for(path)
        self._populate_tree()
        self._refresh_list(self.search_var.get())

    def _run_all(self):
        if self._processing or not self.image_paths:
            return
        self._processing = True
        self.btn_run_all.configure(state=tk.DISABLED)
        self.btn_folder.configure(state=tk.DISABLED)
        thread = threading.Thread(target=self._batch_worker, daemon=True)
        thread.start()

    def _batch_worker(self):
        total = len(self.image_paths)
        for i, path in enumerate(self.image_paths):
            if path not in self.results:
                self._process_single(path)
            pct = (i + 1) / total * 100
            self.root.after(0, self._update_progress, i + 1, total, pct, path)
        self.root.after(0, self._batch_done)

    def _process_single(self, path: str):
        img = cv2.imread(path)
        if img is None:
            return
        self.lp_model.detect_n_read(img)
        img_result = self.lp_model.draw_rect()
        self.results[path] = {
            "img_result": img_result,
            "lp_imgs":    list(self.lp_model.lp_imgs),
            "texts":      list(self.lp_model.lp_texts),
            "lp_confs":   list(self.lp_model.lp_confs),
            "det_confs":  list(self.lp_model.detected_confs),
        }

    def _update_progress(self, done, total, pct, path):
        self.prog_var.set(pct)
        self.prog_lbl.configure(text=f"{done}/{total}")
        name = os.path.basename(path)
        self.status_var.set(f"Đang xử lý: {name}  ({done}/{total})")
        self._populate_tree()
        self._refresh_list(self.search_var.get())
        if self.current_idx >= 0 and self.image_paths[self.current_idx] == path:
            self._show_result_for(path)

    def _batch_done(self):
        self._processing = False
        self.btn_run_all.configure(state=tk.NORMAL)
        self.btn_folder.configure(state=tk.NORMAL)
        self.btn_export.configure(state=tk.NORMAL)
        self.prog_var.set(100)
        total = len(self.image_paths)
        found = sum(1 for r in self.results.values() if r.get("texts"))
        self.status_var.set(
            f"✅ Hoàn thành! {found}/{total} ảnh có biển số."
        )
        self._populate_tree()
        self._refresh_list(self.search_var.get())

    # ── Navigation ────────────────────────────────────────────────────────

    def _prev_image(self):
        if self.current_idx > 0:
            self._load_image(self.current_idx - 1)

    def _next_image(self):
        if self.current_idx < len(self.image_paths) - 1:
            self._load_image(self.current_idx + 1)

    def _on_list_select(self, _event):
        sel = self.listbox.curselection()
        if sel:
            self._load_image(sel[0])

    def _on_tree_select(self, _event):
        sel = self.tree.selection()
        if sel:
            path = sel[0]
            if path in self.image_paths:
                self._load_image(self.image_paths.index(path))

    # ── Plate Image Display ────────────────────────────────────────────────

    def _add_plate_image(self, gray_img):
        frame = ttk.Frame(self.plates_container, style="Card.TFrame")
        frame.pack(side=tk.LEFT, padx=6, pady=4)
        h, w = gray_img.shape[:2]
        scale = min(160 / w, 70 / h, 1.0)
        resized = cv2.resize(gray_img, (max(1, int(w * scale)), max(1, int(h * scale))))
        if len(resized.shape) == 3:
            resized = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(resized)
        photo = ImageTk.PhotoImage(pil)
        self._plate_photos.append(photo)
        ttk.Label(frame, image=photo, style="Card.TLabel").pack(padx=2, pady=2)

    def _clear_plate_display(self):
        for child in self.plates_container.winfo_children():
            child.destroy()
        self._plate_photos.clear()

    # ── Export ────────────────────────────────────────────────────────────

    def _export_results(self):
        if not self.results:
            return
        save_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text file", "*.txt"), ("CSV", "*.csv")],
            title="Lưu Kết Quả"
        )
        if not save_path:
            return
        with open(save_path, "w", encoding="utf-8") as f:
            f.write("File\tSố Biển\tBiển Số\tYOLO Conf\tOCR Conf\n")
            for path, r in self.results.items():
                name   = os.path.basename(path)
                texts  = r.get("texts",    [])
                lconfs = r.get("lp_confs", [])
                dconfs = r.get("det_confs",[])
                if not texts:
                    f.write(f"{name}\t0\t—\t—\t—\n")
                else:
                    for txt, lc, dc in zip(texts, lconfs, dconfs):
                        f.write(f"{name}\t{len(texts)}\t{txt}\t{dc:.3f}\t{lc:.3f}\n")
        messagebox.showinfo("Đã lưu", f"Kết quả đã được lưu:\n{save_path}")
        self.status_var.set(f"Đã xuất kết quả → {save_path}")
