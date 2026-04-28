import os
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
import cv2
from PIL import Image, ImageTk
from lpAppModel import LPAppModel

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}

# Colors
WHITE      = "#ffffff"
BG         = "#f7f7f7"
DARK       = "#1a1a2e"
ACCENT     = "#4361ee"
ACCENT_HOV = "#3a56d4"
BORDER     = "#d0d0d0"
TEXT       = "#2d2d2d"
TEXT2      = "#666666"
GREEN_OK   = "#0d7a2e"
CANVAS_BG  = "#eaeaea"
HEADER_BG  = "#f0f0f0"





class LPApp:
    WINDOW_TITLE = "Nhận dạng biển số xe"
    WINDOW_SIZE = "1200x750"

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(self.WINDOW_TITLE)
        self.root.geometry(self.WINDOW_SIZE)
        self.root.resizable(True, True)
        self.root.configure(bg=WHITE)

        self.lp_model = LPAppModel()

        # State
        self.image_paths = []
        self.current_idx = -1
        self.img_original = None
        self._photo_original = None
        self._photo_result = None
        self._plate_photos = []


        self._apply_theme()
        self._build_ui()

    def _apply_theme(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")

        style.configure(".", background=WHITE, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("TFrame", background=WHITE)
        style.configure("Header.TFrame", background=WHITE)

        style.configure("TButton", background=WHITE, foreground=TEXT, borderwidth=1,
                         relief="solid", padding=(14, 6), font=("Segoe UI", 9))
        style.map("TButton", background=[("active", "#e8e8e8")])

        style.configure("Nav.TButton", padding=(6, 4), font=("Segoe UI", 10))

        style.configure("Accent.TButton", background=ACCENT, foreground="white",
                         borderwidth=0, relief="flat", padding=(18, 7),
                         font=("Segoe UI", 10, "bold"))
        style.map("Accent.TButton",
                  background=[("active", ACCENT_HOV), ("disabled", "#bbb")])

        style.configure("TLabel", background=WHITE, foreground=TEXT, font=("Segoe UI", 10))
        style.configure("Status.TLabel", background=WHITE, foreground=TEXT2,
                         font=("Segoe UI", 9, "italic"))
        style.configure("Section.TLabel", background=WHITE, foreground=TEXT,
                         font=("Segoe UI", 10, "bold"))
        style.configure("PlateText.TLabel", background=WHITE, foreground=TEXT,
                         font=("Consolas", 10, "bold"))

    def _build_ui(self):
        # ─── Header / Toolbar ─────────────────────────────────────────
        header = tk.Frame(self.root, bg=WHITE, pady=8, padx=12)
        header.pack(fill=tk.X)

        # Buttons
        ttk.Button(header, text="📂 Chọn ảnh", command=self._open_image).pack(side=tk.LEFT, padx=3)
        ttk.Button(header, text="📁 Chọn thư mục", command=self._open_folder).pack(side=tk.LEFT, padx=3)

        self.btn_prev = ttk.Button(header, text="◀", style="Nav.TButton",
                                   command=self._prev_image, state=tk.DISABLED, width=3)
        self.btn_prev.pack(side=tk.LEFT, padx=(12, 2))
        self.btn_next = ttk.Button(header, text="▶", style="Nav.TButton",
                                   command=self._next_image, state=tk.DISABLED, width=3)
        self.btn_next.pack(side=tk.LEFT, padx=(2, 12))

        ttk.Button(header, text="🔍 Nhận dạng", style="Accent.TButton",
                   command=self._detect_current).pack(side=tk.LEFT, padx=3)

        self.status_var = tk.StringVar(value="Sẵn sàng.")
        ttk.Label(header, textvariable=self.status_var, style="Status.TLabel").pack(side=tk.RIGHT)

        # Thin separator
        sep = tk.Frame(self.root, bg=BORDER, height=1)
        sep.pack(fill=tk.X)

        # ─── Main Content ─────────────────────────────────────────────
        body = tk.Frame(self.root, bg=BG, padx=12, pady=10)
        body.pack(fill=tk.BOTH, expand=True)

        # Top row: two image canvases
        top = tk.Frame(body, bg=BG)
        top.pack(fill=tk.BOTH, expand=True)

        left_panel = tk.Frame(top, bg=WHITE, bd=1, relief="solid",
                              highlightbackground=BORDER, highlightthickness=1)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))

        lbl_orig = tk.Label(left_panel, text="  Ảnh gốc", bg=HEADER_BG, fg=TEXT,
                            font=("Segoe UI", 9, "bold"), anchor="w", padx=8, pady=4)
        lbl_orig.pack(fill=tk.X)
        tk.Frame(left_panel, bg=BORDER, height=1).pack(fill=tk.X)
        self.canvas_original = tk.Canvas(left_panel, bg=CANVAS_BG, highlightthickness=0)
        self.canvas_original.pack(fill=tk.BOTH, expand=True)

        right_panel = tk.Frame(top, bg=WHITE, bd=1, relief="solid",
                               highlightbackground=BORDER, highlightthickness=1)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(6, 0))

        lbl_result = tk.Label(right_panel, text="  Kết quả phát hiện", bg=HEADER_BG, fg=TEXT,
                              font=("Segoe UI", 9, "bold"), anchor="w", padx=8, pady=4)
        lbl_result.pack(fill=tk.X)
        tk.Frame(right_panel, bg=BORDER, height=1).pack(fill=tk.X)
        self.canvas_result = tk.Canvas(right_panel, bg=CANVAS_BG, highlightthickness=0)
        self.canvas_result.pack(fill=tk.BOTH, expand=True)

        # Bottom row: plates + text results
        bottom = tk.Frame(body, bg=BG, height=180)
        bottom.pack(fill=tk.X, pady=(10, 0))
        bottom.pack_propagate(False)

        plate_panel = tk.Frame(bottom, bg=WHITE, bd=1, relief="solid",
                               highlightbackground=BORDER, highlightthickness=1)
        plate_panel.pack(side=tk.LEFT, fill=tk.BOTH, padx=(0, 6), expand=False)
        plate_panel.configure(width=280)
        plate_panel.pack_propagate(False)

        lbl_plates = tk.Label(plate_panel, text="  Biển số tách được", bg=HEADER_BG, fg=TEXT,
                              font=("Segoe UI", 9, "bold"), anchor="w", padx=8, pady=4)
        lbl_plates.pack(fill=tk.X)
        tk.Frame(plate_panel, bg=BORDER, height=1).pack(fill=tk.X)
        self.plates_container = tk.Frame(plate_panel, bg=WHITE)
        self.plates_container.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        text_panel = tk.Frame(bottom, bg=WHITE, bd=1, relief="solid",
                              highlightbackground=BORDER, highlightthickness=1)
        text_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(6, 0))

        lbl_text = tk.Label(text_panel, text="  Kết quả nhận dạng", bg=HEADER_BG, fg=TEXT,
                            font=("Segoe UI", 9, "bold"), anchor="w", padx=8, pady=4)
        lbl_text.pack(fill=tk.X)
        tk.Frame(text_panel, bg=BORDER, height=1).pack(fill=tk.X)
        self.result_text = tk.Text(text_panel, font=("Consolas", 11), wrap=tk.WORD,
                                   bg=WHITE, fg=TEXT, relief="flat", bd=0,
                                   highlightthickness=0, padx=10, pady=8)
        self.result_text.pack(fill=tk.BOTH, expand=True)

    # ── Actions ───────────────────────────────────────────────────────

    def _open_image(self):
        path = filedialog.askopenfilename(
            title="Chọn ảnh",
            filetypes=[("Ảnh", "*.jpg *.jpeg *.png *.bmp *.tiff"), ("Tất cả", "*.*")]
        )
        if path:
            self.image_paths = [path]
            self._load_image(0)
            self._update_nav()

    def _open_folder(self):
        folder = filedialog.askdirectory(title="Chọn thư mục ảnh")
        if not folder:
            return
        paths = sorted([
            os.path.join(folder, f) for f in os.listdir(folder)
            if os.path.splitext(f)[1].lower() in IMAGE_EXTS
        ])
        if not paths:
            messagebox.showwarning("Thông báo", "Thư mục không có ảnh hợp lệ.")
            return
        self.image_paths = paths
        self._update_nav()

        total = len(paths)
        for i in range(total):
            if not self.root.winfo_exists():
                return
            self.current_idx = i
            path = paths[i]
            img = cv2.imread(path)
            if img is None:
                continue

            self.img_original = img
            self.status_var.set(f"Đang xử lý ({i + 1}/{total}): {os.path.basename(path)}")
            self._display_cv_image(img, self.canvas_original, "original")
            self.root.update_idletasks()

            self.lp_model.detect_n_read(img)
            img_result = self.lp_model.draw_rect()
            self._display_cv_image(img_result, self.canvas_result, "result")

            self._clear_plate_display()
            self.result_text.delete("1.0", tk.END)
            texts = self.lp_model.lp_texts
            lconfs = self.lp_model.lp_confs
            dconfs = self.lp_model.detected_confs
            imgs = self.lp_model.lp_imgs

            if texts:
                for j, (txt, lc, dc) in enumerate(zip(texts, lconfs, dconfs)):
                    if j < len(imgs):
                        self._add_plate_image(imgs[j], txt)
                    d = txt if txt else "(không đọc được)"
                    self.result_text.insert(tk.END, f"Biển {j+1}: {d}   (YOLO: {dc:.2f} | OCR: {lc:.2f})\n")
            else:
                self.result_text.insert(tk.END, "Không tìm thấy biển số.")

            self.root.update_idletasks()

        self._update_nav()
        self.status_var.set(f"✅ Hoàn tất! Đã xử lý {total} ảnh.")

    def _load_image(self, idx):
        self.current_idx = idx
        path = self.image_paths[idx]
        self.img_original = cv2.imread(path)
        if self.img_original is None:
            self.status_var.set(f"Lỗi đọc ảnh: {os.path.basename(path)}")
            return
        self._clear_results()
        self._display_cv_image(self.img_original, self.canvas_original, "original")
        n = len(self.image_paths)
        info = f" ({idx + 1}/{n})" if n > 1 else ""
        self.status_var.set(f"{os.path.basename(path)}{info}")

    def _detect_current(self):
        if self.img_original is None:
            messagebox.showinfo("Thông báo", "Chọn ảnh trước!")
            return
        self.status_var.set("Đang nhận dạng…")
        self.root.update_idletasks()

        self.lp_model.detect_n_read(self.img_original)
        img_result = self.lp_model.draw_rect()
        self._display_cv_image(img_result, self.canvas_result, "result")

        self._clear_plate_display()
        self.result_text.delete("1.0", tk.END)

        texts, lconfs, dconfs = self.lp_model.lp_texts, self.lp_model.lp_confs, self.lp_model.detected_confs
        imgs = self.lp_model.lp_imgs

        if not texts:
            self.result_text.insert(tk.END, "Không tìm thấy biển số nào.")
            self.status_var.set("Không tìm thấy biển số.")
            return

        for i, (txt, lc, dc) in enumerate(zip(texts, lconfs, dconfs)):
            if i < len(imgs):
                self._add_plate_image(imgs[i], txt)
            d = txt if txt else "(không đọc được)"
            self.result_text.insert(tk.END, f"Biển {i + 1}: {d}   (YOLO: {dc:.2f} | OCR: {lc:.2f})\n")

        self.status_var.set(f"Tìm thấy {len(texts)} biển số.")

    # ── Navigation ────────────────────────────────────────────────────

    def _update_nav(self):
        multi = len(self.image_paths) > 1
        self.btn_prev.configure(state=tk.NORMAL if multi and self.current_idx > 0 else tk.DISABLED)
        self.btn_next.configure(state=tk.NORMAL if multi and self.current_idx < len(self.image_paths) - 1 else tk.DISABLED)

    def _prev_image(self):
        if self.current_idx > 0:
            self._load_image(self.current_idx - 1)
            self._update_nav()

    def _next_image(self):
        if self.current_idx < len(self.image_paths) - 1:
            self._load_image(self.current_idx + 1)
            self._update_nav()

    # ── Display Helpers ───────────────────────────────────────────────

    def _display_cv_image(self, cv_img, canvas, tag):
        canvas.update_idletasks()
        cw = canvas.winfo_width() or 500
        ch = canvas.winfo_height() or 400
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

    def _add_plate_image(self, gray_img, text):
        frame = tk.Frame(self.plates_container, bg=WHITE)
        frame.pack(side=tk.LEFT, padx=8, pady=4)
        h, w = gray_img.shape[:2]
        scale = min(120 / w, 70 / h, 1.0)
        resized = cv2.resize(gray_img, (max(1, int(w * scale)), max(1, int(h * scale))))
        if len(resized.shape) == 3:
            resized = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(resized)
        photo = ImageTk.PhotoImage(pil)
        self._plate_photos.append(photo)
        tk.Label(frame, image=photo, bg=WHITE, bd=1, relief="solid").pack()
        tk.Label(frame, text=text or "?", bg=WHITE, fg=TEXT,
                 font=("Consolas", 10, "bold")).pack(pady=(4, 0))

    def _clear_results(self):
        if self.canvas_result.winfo_exists():
            self.canvas_result.delete("all")
        self._photo_result = None
        self._clear_plate_display()
        if self.result_text.winfo_exists():
            self.result_text.delete("1.0", tk.END)

    def _clear_plate_display(self):
        for child in self.plates_container.winfo_children():
            child.destroy()
        self._plate_photos.clear()
