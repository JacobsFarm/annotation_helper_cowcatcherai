import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import cv2
from PIL import Image, ImageTk
import os
import shutil
import numpy as np
from logic.model_handler import ModelHandler

class AnnotateTab(ctk.CTkFrame):
    def __init__(self, parent, config):
        super().__init__(parent)
        self.config = config
        
        # --- DATA & STATE ---
        self.image_files = []
        self.current_index = 0
        self.current_cv_image = None
        self.annotations = []
        
        # Schaling variabelen
        self.scale = 1.0
        self.off_x = 0
        self.off_y = 0
        
        # Teken status
        self.draw_mode = "bbox" 
        self.is_drawing = False
        self.start_pt = (0, 0)
        self.current_points = []
        self.temp_item = None
        
        # Logic laden
        self.model_handler = ModelHandler(config)
        
        # UI & Shortcuts Opzetten
        self.setup_ui()
        self.setup_shortcuts()
        
        # Start laden
        self.after(100, self.refresh_file_list)

    def setup_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        keys = self.config.get('keys', {
            "save_next": "s", "skip": "space", "delete": "Delete", "undo": "z"
        })

        # --- 1. TOOLBAR (Links) ---
        self.frame_tools = ctk.CTkFrame(self, width=200)
        self.frame_tools.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        ctk.CTkLabel(self.frame_tools, text="TOOLS", font=("Arial", 16, "bold")).pack(pady=10)

        self.var_use_ai = ctk.BooleanVar(value=True)
        self.switch_ai = ctk.CTkSwitch(self.frame_tools, text="Auto AI", variable=self.var_use_ai)
        self.switch_ai.pack(pady=5, padx=10, anchor="w")
        
        self.var_advanced = ctk.BooleanVar(value=False)
        self.chk_adv = ctk.CTkCheckBox(self.frame_tools, text="Dual Model (Adv)", variable=self.var_advanced)
        self.chk_adv.pack(pady=5, padx=10, anchor="w")
        
        ctk.CTkLabel(self.frame_tools, text="Box Expansie:").pack(pady=(10,0))
        self.slider_expand = ctk.CTkSlider(self.frame_tools, from_=0, to=0.5, number_of_steps=10)
        self.slider_expand.set(0.1)
        self.slider_expand.pack(pady=5)

        ctk.CTkLabel(self.frame_tools, text="TEKEN MODUS").pack(pady=(15,5))
        self.seg_mode = ctk.CTkSegmentedButton(self.frame_tools, values=["BBox", "Polygon"], command=self.set_mode)
        self.seg_mode.set("BBox")
        self.seg_mode.pack(pady=5)
        
        ctk.CTkLabel(self.frame_tools, text="Links: Tekenen\nRechts: Polygon Afronden", font=("Arial", 11), text_color="gray").pack(pady=5)

        # Knoppen met keys uit config
        ctk.CTkButton(self.frame_tools, text=f"Save & Next ({keys['save_next'].upper()})", fg_color="green", command=self.save_and_next).pack(pady=15, padx=10, fill="x")
        ctk.CTkButton(self.frame_tools, text=f"Skip ({keys['skip'].upper()})", fg_color="orange", command=self.skip_image).pack(pady=5, padx=10, fill="x")
        ctk.CTkButton(self.frame_tools, text=f"Delete ({keys['delete'].upper()})", fg_color="red", command=self.delete_image).pack(pady=5, padx=10, fill="x")
        ctk.CTkButton(self.frame_tools, text=f"Undo ({keys['undo'].upper()})", fg_color="gray", command=self.undo).pack(pady=20, padx=10, fill="x")
        
        ctk.CTkLabel(self.frame_tools, text="KLASSE").pack(pady=(10,5))
        self.combo_classes = ctk.CTkOptionMenu(self.frame_tools, values=[c['name'] for c in self.config['classes']])
        self.combo_classes.pack(padx=10)

        # --- 2. CANVAS (Midden) ---
        self.frame_canvas = ctk.CTkFrame(self)
        self.frame_canvas.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        
        self.canvas = tk.Canvas(self.frame_canvas, bg="#202020", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        
        self.canvas.bind("<Button-1>", self.on_left_down)
        self.canvas.bind("<B1-Motion>", self.on_left_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_left_up)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.canvas.bind("<Configure>", lambda e: self.redraw())

    def setup_shortcuts(self):
        """Gebruikt exact dezelfde logica als ControlTab omdat die werkt"""
        root = self.winfo_toplevel()
        
        keys = self.config.get('keys', {
            "save_next": "s", "skip": "space", "delete": "Delete", "undo": "z"
        })

        def if_active(func):
            def wrapper(event=None):
                if self.winfo_viewable():
                    func()
            return wrapper

        # SAVE (S) - Met haakjes, net als in ControlTab
        k_save = keys['save_next']
        root.bind(f"<{k_save.lower()}>", if_active(self.save_and_next))
        root.bind(f"<{k_save.upper()}>", if_active(self.save_and_next))
        
        # SKIP (SPACE)
        k_skip = keys['skip']
        root.bind(f"<{k_skip}>", if_active(self.skip_image))
        
        # DELETE
        k_del = keys['delete']
        root.bind(f"<{k_del}>", if_active(self.delete_image))
        
        # UNDO (Z)
        k_undo = keys['undo']
        root.bind(f"<{k_undo.lower()}>", if_active(self.undo))
        root.bind(f"<{k_undo.upper()}>", if_active(self.undo))
        
        # Focus fix
        self.canvas.bind("<Enter>", lambda e: self.canvas.focus_set())

    # --- INITIALISATIE & LADEN ---
    def set_mode(self, val):
        self.draw_mode = "bbox" if val == "BBox" else "polygon"
        self.current_points = []
        self.redraw()

    def refresh_file_list(self):
        folder = self.config.get('input_folder', '')
        if not os.path.exists(folder): return
        self.image_files = [f for f in os.listdir(folder) if f.lower().endswith(('.jpg', '.png', '.jpeg'))]
        
        if self.image_files:
            self.load_image()
        else:
            self.canvas.delete("all")
            self.canvas.create_text(400, 300, text="Geen afbeeldingen meer!", fill="white", font=("Arial", 20))

    def load_image(self):
        filename = self.image_files[self.current_index]
        path = os.path.join(self.config['input_folder'], filename)
        
        self.current_cv_image = cv2.imread(path)
        if self.current_cv_image is not None:
            self.current_cv_image = cv2.cvtColor(self.current_cv_image, cv2.COLOR_BGR2RGB)
        
        self.annotations = []
        self.current_points = []
        
        if self.var_use_ai.get():
            try:
                if self.var_advanced.get():
                    preds = self.model_handler.predict_advanced_dual(path, self.slider_expand.get())
                else:
                    preds = self.model_handler.predict_standard(path)
                self.annotations.extend(preds)
            except Exception as e:
                print(f"AI Error: {e}")
        
        self.redraw()

    # --- TEKEN LOGICA (RESIZING FIX) ---
    def redraw(self):
        self.canvas.delete("all")
        if self.current_cv_image is None: return
        
        h_img, w_img = self.current_cv_image.shape[:2]
        w_can = self.canvas.winfo_width()
        h_can = self.canvas.winfo_height()
        
        if w_can < 10 or h_can < 10: return
        
        self.scale = min(w_can / w_img, h_can / h_img) * 0.95
        
        new_w = int(w_img * self.scale)
        new_h = int(h_img * self.scale)
        
        self.off_x = (w_can - new_w) // 2
        self.off_y = (h_can - new_h) // 2
        
        # --- CRASH FIX: Check of afmetingen geldig zijn ---
        if new_w <= 0 or new_h <= 0:
            return
        # --------------------------------------------------

        img_res = cv2.resize(self.current_cv_image, (new_w, new_h))
        self.tk_img = ImageTk.PhotoImage(Image.fromarray(img_res))
        self.canvas.create_image(self.off_x, self.off_y, image=self.tk_img, anchor="nw")
        
        for ann in self.annotations:
            col = self.get_color(ann['class_id'])
            if ann['type'] == 'bbox':
                x1, y1, x2, y2 = ann['coords']
                cx1 = x1 * self.scale + self.off_x
                cy1 = y1 * self.scale + self.off_y
                cx2 = x2 * self.scale + self.off_x
                cy2 = y2 * self.scale + self.off_y
                self.canvas.create_rectangle(cx1, cy1, cx2, cy2, outline=col, width=2)
                
            elif ann['type'] == 'polygon':
                pts = []
                for x, y in ann['points']:
                    pts.extend([x * self.scale + self.off_x, y * self.scale + self.off_y])
                if len(pts) >= 4:
                    self.canvas.create_polygon(pts, outline=col, fill='', width=2)

        if self.draw_mode == "polygon" and self.current_points:
            pts = []
            r = 3
            for x, y in self.current_points:
                cx = x * self.scale + self.off_x
                cy = y * self.scale + self.off_y
                pts.extend([cx, cy])
                self.canvas.create_oval(cx-r, cy-r, cx+r, cy+r, fill="yellow")
            if len(pts) >= 4:
                self.canvas.create_line(pts, fill="yellow", width=1)

    # --- MUIS INTERACTIE ---
    def on_left_down(self, event):
        ix = (event.x - self.off_x) / self.scale
        iy = (event.y - self.off_y) / self.scale
        
        if self.draw_mode == "bbox":
            self.is_drawing = True
            self.start_pt = (ix, iy)
            self.temp_item = self.canvas.create_rectangle(event.x, event.y, event.x, event.y, outline="yellow", dash=(4,4))
            
        elif self.draw_mode == "polygon":
            self.current_points.append([ix, iy])
            self.redraw()

    def on_left_drag(self, event):
        if self.draw_mode == "bbox" and self.is_drawing:
            start_cx = self.start_pt[0] * self.scale + self.off_x
            start_cy = self.start_pt[1] * self.scale + self.off_y
            self.canvas.coords(self.temp_item, start_cx, start_cy, event.x, event.y)

    def on_left_up(self, event):
        if self.draw_mode == "bbox" and self.is_drawing:
            self.is_drawing = False
            self.canvas.delete(self.temp_item)
            
            ex = (event.x - self.off_x) / self.scale
            ey = (event.y - self.off_y) / self.scale
            
            x1, x2 = sorted([self.start_pt[0], ex])
            y1, y2 = sorted([self.start_pt[1], ey])
            
            if (x2-x1) > 2 and (y2-y1) > 2:
                self.annotations.append({
                    "type": "bbox", 
                    "class_id": self.get_class_id(), 
                    "coords": [x1, y1, x2, y2]
                })
            self.redraw()

    def on_right_click(self, event):
        if self.draw_mode == "polygon" and len(self.current_points) > 2:
            self.annotations.append({
                "type": "polygon", 
                "class_id": self.get_class_id(), 
                "points": self.current_points
            })
            self.current_points = []
            self.redraw()

    # --- ACTIES & HELPERS ---
    def get_class_id(self):
        name = self.combo_classes.get()
        for c in self.config['classes']:
            if c['name'] == name: return c['id']
        return 0

    def get_color(self, cid):
        for c in self.config['classes']:
            if c['id'] == cid: return c['color']
        return "red"

    def undo(self):
        if self.annotations:
            self.annotations.pop()
            self.redraw()

    def save_and_next(self):
        if not self.image_files: return
        fname = self.image_files[self.current_index]
        base = os.path.splitext(fname)[0]
        
        src = os.path.join(self.config['input_folder'], fname)
        dst = os.path.join(self.config['output_img_folder'], fname)
        shutil.copy(src, dst)
        
        label_path = os.path.join(self.config['output_label_folder'], f"{base}.txt")
        h, w = self.current_cv_image.shape[:2]
        
        with open(label_path, 'w') as f:
            for ann in self.annotations:
                cid = ann['class_id']
                if ann['type'] == 'bbox':
                    x1, y1, x2, y2 = ann['coords']
                    cx = ((x1+x2)/2)/w
                    cy = ((y1+y2)/2)/h
                    bw = (x2-x1)/w
                    bh = (y2-y1)/h
                    f.write(f"{cid} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")
                elif ann['type'] == 'polygon':
                    line = f"{cid}"
                    for px, py in ann['points']:
                        line += f" {px/w:.6f} {py/h:.6f}"
                    f.write(line + "\n")

        if self.config.get('delete_mode', False):
            shutil.move(src, os.path.join(self.config['delete_folder'], fname))

        self.next_img()

    def skip_image(self):
        self.next_img()

    def delete_image(self):
        if not self.image_files: return
        fname = self.image_files[self.current_index]
        src = os.path.join(self.config['input_folder'], fname)
        dst = os.path.join(self.config['delete_folder'], fname)
        shutil.move(src, dst)
        self.next_img()

    def next_img(self):
        if self.current_index < len(self.image_files) - 1:
            self.current_index += 1
            self.load_image()
        else:
            messagebox.showinfo("Klaar", "Alle beelden gehad!")