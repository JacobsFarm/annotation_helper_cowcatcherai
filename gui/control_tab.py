import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import cv2
from PIL import Image, ImageTk
import os
import shutil
import numpy as np

class ControlTab(ctk.CTkFrame):
    def __init__(self, parent, config):
        super().__init__(parent)
        self.config = config
        self.image_files = []
        self.current_index = 0
        
        self.setup_ui()
        self.setup_shortcuts() # Activeer sneltoetsen
        
        # Auto refresh bij start (kleine vertraging)
        self.after(200, self.refresh)
        
    def setup_ui(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # Keys ophalen voor labels
        keys = self.config.get('keys', {
            "save_next": "s", "prev": "a", "reject": "e", "reset_view": "r"
        })
        
        # Canvas Frame
        self.frame_view = ctk.CTkFrame(self)
        self.frame_view.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        self.canvas = tk.Canvas(self.frame_view, bg="#404040", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        
        # Knoppen Balk Onder
        self.frame_btns = ctk.CTkFrame(self, height=50)
        self.frame_btns.grid(row=1, column=0, sticky="ew", padx=10, pady=10)
        
        # Knoppen met dynamische toetsaanduiding
        ctk.CTkButton(self.frame_btns, text=f"Refresh ({keys.get('reset_view', 'r').upper()})", command=self.refresh).pack(side="right", padx=10, pady=5)
        
        ctk.CTkButton(self.frame_btns, text=f"GOED ({keys.get('save_next', 's').upper()})", fg_color="green", command=self.next_img).pack(side="right", padx=10)
        
        ctk.CTkButton(self.frame_btns, text=f"AFKEUREN ({keys.get('reject', 'e').upper()})", fg_color="red", command=self.reject).pack(side="right", padx=10)
        
        ctk.CTkButton(self.frame_btns, text=f"Vorige ({keys.get('prev', 'a').upper()})", fg_color="gray", command=self.prev_img).pack(side="left", padx=10)

    def setup_shortcuts(self):
        """Bindt toetsen aan het hoofdvenster, alleen actief als tab zichtbaar is"""
        root = self.winfo_toplevel()
        
        keys = self.config.get('keys', {
            "save_next": "s", "prev": "a", "reject": "e", "reset_view": "r"
        })

        def if_active(func):
            def wrapper(event=None):
                if self.winfo_viewable():
                    func()
            return wrapper

        # Goedkeuren / Volgende
        k_next = keys.get('save_next', 's')
        root.bind(f"<{k_next.lower()}>", if_active(self.next_img))
        root.bind(f"<{k_next.upper()}>", if_active(self.next_img))

        # Vorige
        k_prev = keys.get('prev', 'a')
        root.bind(f"<{k_prev.lower()}>", if_active(self.prev_img))
        root.bind(f"<{k_prev.upper()}>", if_active(self.prev_img))
        
        # Afkeuren
        k_reject = keys.get('reject', 'e')
        root.bind(f"<{k_reject.lower()}>", if_active(self.reject))
        root.bind(f"<{k_reject.upper()}>", if_active(self.reject))
        
        # Refresh
        k_refresh = keys.get('reset_view', 'r')
        root.bind(f"<{k_refresh.lower()}>", if_active(self.refresh))
        root.bind(f"<{k_refresh.upper()}>", if_active(self.refresh))
        
        # Zorg dat canvas focus pakt
        self.canvas.bind("<Enter>", lambda e: self.canvas.focus_set())

    def refresh(self):
        folder = self.config.get('output_img_folder', '')
        if not os.path.exists(folder): return
        
        self.image_files = [f for f in os.listdir(folder) if f.lower().endswith(('.jpg','.png', '.jpeg'))]
        self.current_index = 0
        self.load_image()

    def load_image(self):
        self.canvas.delete("all")
        if not self.image_files:
            self.canvas.create_text(400, 300, text="Geen output beelden gevonden", fill="white")
            return

        fname = self.image_files[self.current_index]
        img_path = os.path.join(self.config['output_img_folder'], fname)
        base_name = os.path.splitext(fname)[0]
        lbl_path = os.path.join(self.config['output_label_folder'], f"{base_name}.txt")
        
        # Laden
        img = cv2.imread(img_path)
        if img is None: return
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        h, w = img.shape[:2]
        
        # Labels tekenen
        if os.path.exists(lbl_path):
            with open(lbl_path, 'r') as f:
                for line in f.readlines():
                    try:
                        parts = list(map(float, line.strip().split()))
                        cls = int(parts[0])
                        coords = parts[1:]
                        
                        if len(coords) == 4: # BBox
                            cx, cy, bw, bh = coords
                            x1 = int((cx - bw/2)*w)
                            y1 = int((cy - bh/2)*h)
                            x2 = int((cx + bw/2)*w)
                            y2 = int((cy + bh/2)*h)
                            cv2.rectangle(img, (x1, y1), (x2, y2), (0,255,0), 2)
                        elif len(coords) > 4: # Polygon
                            pts = []
                            for i in range(0, len(coords), 2):
                                pts.append([int(coords[i]*w), int(coords[i+1]*h)])
                            pts = np.array(pts, np.int32).reshape((-1,1,2))
                            cv2.polylines(img, [pts], True, (0,255,0), 2)
                    except: pass
        
        # Schalen
        cw = self.canvas.winfo_width() or 800
        ch = self.canvas.winfo_height() or 600
        scale = min(cw/w, ch/h) * 0.95
        nw, nh = int(w*scale), int(h*scale)
        if nw <= 0 or nh <= 0:
            return
        
        img_res = cv2.resize(img, (nw, nh))
        self.tk_img = ImageTk.PhotoImage(Image.fromarray(img_res))
        self.canvas.create_image(cw//2, ch//2, anchor="center", image=self.tk_img)

    def next_img(self):
        if self.current_index < len(self.image_files)-1:
            self.current_index += 1
            self.load_image()

    def prev_img(self):
        if self.current_index > 0:
            self.current_index -= 1
            self.load_image()

    def reject(self):
        if not self.image_files: return
        fname = self.image_files[self.current_index]
        base = os.path.splitext(fname)[0]
        
        src = os.path.join(self.config['output_img_folder'], fname)
        dst = os.path.join(self.config['input_folder'], fname)
        lbl = os.path.join(self.config['output_label_folder'], f"{base}.txt")
        
        # Verplaatsen
        if os.path.exists(src): shutil.move(src, dst)
        if os.path.exists(lbl): os.remove(lbl)
        
        # Update lijst
        self.image_files.pop(self.current_index)
        if self.current_index >= len(self.image_files):
            self.current_index = len(self.image_files) - 1
            
        self.load_image()