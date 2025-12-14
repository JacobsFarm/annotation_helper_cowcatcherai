import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import cv2
from PIL import Image, ImageTk
import os
import shutil
import numpy as np
from logic.model_handler import ModelHandler

class AnnotateSegTab(ctk.CTkFrame):
    def __init__(self, parent, config):
        super().__init__(parent)
        self.config = config
        
        # --- DATA & STATE ---
        self.image_files = []
        self.current_index = 0
        self.current_cv_image = None
        self.current_path = None  # Nieuw: pad onthouden voor refresh
        self.annotations = []
        
        # Schaling
        self.scale = 1.0
        self.off_x = 0
        self.off_y = 0
        
        # Segmentatie State
        self.current_points = []
        self.draw_mode = "polygon" 
        
        # Logic laden
        self.model_handler = ModelHandler(config)
        
        # UI & Shortcuts
        self.setup_ui()
        self.setup_shortcuts()
        
        # Start laden
        self.after(100, self.refresh_file_list)

    def setup_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        keys = self.config.get('keys_annotate', {"save_next": "s", "skip": "space", "delete": "Delete", "undo": "z"})

        # --- TOOLBAR (Links) ---
        self.frame_tools = ctk.CTkFrame(self, width=200)
        self.frame_tools.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        ctk.CTkLabel(self.frame_tools, text="SEGMENTATIE TOOLS", font=("Arial", 16, "bold"), text_color="#3498db").pack(pady=10)

        # AI Instellingen
        self.var_use_ai = ctk.BooleanVar(value=True)
        self.switch_ai = ctk.CTkSwitch(self.frame_tools, text="Auto AI (Dual Model)", variable=self.var_use_ai)
        self.switch_ai.pack(pady=5, padx=10, anchor="w")
        
        # 1. Crop Expansie
        ctk.CTkLabel(self.frame_tools, text="Crop Expansie (%)").pack(pady=(10,0))
        self.slider_expand = ctk.CTkSlider(self.frame_tools, from_=0, to=0.5, number_of_steps=10)
        self.slider_expand.set(0.2)
        self.slider_expand.pack(pady=2)

        # 2. NIEUW: Min Confidence Slider
        self.lbl_conf = ctk.CTkLabel(self.frame_tools, text="Min Confidence: 0.30")
        self.lbl_conf.pack(pady=(10,0))
        
        self.slider_conf = ctk.CTkSlider(self.frame_tools, from_=0.0, to=1.0, number_of_steps=20, command=self.update_conf_label)
        self.slider_conf.set(0.3)
        self.slider_conf.pack(pady=2)

        # 3. NIEUW: Max Masks Slider
        self.lbl_max_masks = ctk.CTkLabel(self.frame_tools, text="Max Masks: 1")
        self.lbl_max_masks.pack(pady=(10,0))
        
        self.slider_max_masks = ctk.CTkSlider(self.frame_tools, from_=1, to=10, number_of_steps=9, command=self.update_max_masks_label)
        self.slider_max_masks.set(1)
        self.slider_max_masks.pack(pady=2)

        # 4. NIEUW: Refresh Knop
        ctk.CTkButton(self.frame_tools, text="Refresh Prediction", fg_color="#555555", command=self.run_ai_prediction).pack(pady=10, padx=10, fill="x")

        ctk.CTkLabel(self.frame_tools, text="L-Click: Punt zetten\nR-Click: Afronden", font=("Arial", 11), text_color="gray").pack(pady=15)

        # Actie Knoppen
        ctk.CTkButton(self.frame_tools, text=f"Save & Next ({keys.get('save_next', 'S').upper()})", fg_color="green", command=self.save_and_next).pack(pady=15, padx=10, fill="x")
        ctk.CTkButton(self.frame_tools, text=f"Skip ({keys.get('skip', 'Space').upper()})", fg_color="orange", command=self.skip_image).pack(pady=5, padx=10, fill="x")
        ctk.CTkButton(self.frame_tools, text=f"Delete ({keys.get('delete', 'Del').upper()})", fg_color="red", command=self.delete_image).pack(pady=5, padx=10, fill="x")
        ctk.CTkButton(self.frame_tools, text=f"Undo ({keys.get('undo', 'Z').upper()})", fg_color="gray", command=self.undo).pack(pady=20, padx=10, fill="x")
        
        ctk.CTkLabel(self.frame_tools, text="KLASSE").pack(pady=(10,5))
        self.combo_classes = ctk.CTkOptionMenu(self.frame_tools, values=[c['name'] for c in self.config['classes']])
        self.combo_classes.pack(padx=10)

        # --- CANVAS (Midden) ---
        self.frame_canvas = ctk.CTkFrame(self)
        self.frame_canvas.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        
        self.canvas = tk.Canvas(self.frame_canvas, bg="#202020", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        
        self.canvas.bind("<Button-1>", self.on_left_click)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.canvas.bind("<Configure>", lambda e: self.redraw())
        self.canvas.bind("<Enter>", lambda e: self.canvas.focus_set())

    def update_conf_label(self, value):
        self.lbl_conf.configure(text=f"Min Confidence: {value:.2f}")

    def update_max_masks_label(self, value):
        self.lbl_max_masks.configure(text=f"Max Masks: {int(value)}")

    def setup_shortcuts(self):
        root = self.winfo_toplevel()
        keys = self.config.get('keys_annotate', {})

        def if_active(func):
            def wrapper(event=None):
                if self.winfo_viewable():
                    func()
            return wrapper

        k_save = keys.get("save_next", "s")
        if k_save:
            root.bind(f"<{k_save.lower()}>", if_active(self.save_and_next))
            root.bind(f"<{k_save.upper()}>", if_active(self.save_and_next))
        
        k_skip = keys.get("skip", "space")
        if k_skip == "space": root.bind("<space>", if_active(self.skip_image))
        elif k_skip: root.bind(f"<{k_skip}>", if_active(self.skip_image))
        
        k_undo = keys.get("undo", "z")
        if k_undo:
             root.bind(f"<{k_undo.lower()}>", if_active(self.undo))
             root.bind(f"<{k_undo.upper()}>", if_active(self.undo))
             
        k_del = keys.get("delete", "Delete")
        if k_del: root.bind(f"<{k_del}>", if_active(self.delete_image))

    # --- LOGICA ---
    def refresh_file_list(self):
        folder = self.config.get('input_folder', '')
        if not os.path.exists(folder): return
        self.image_files = [f for f in os.listdir(folder) if f.lower().endswith(('.jpg', '.png', '.jpeg'))]
        if self.image_files: self.load_image()
        else: 
            self.canvas.delete("all")
            self.canvas.create_text(400, 300, text="Geen afbeeldingen!", fill="white")

    def load_image(self):
        filename = self.image_files[self.current_index]
        self.current_path = os.path.join(self.config['input_folder'], filename)
        
        self.current_cv_image = cv2.imread(self.current_path)
        if self.current_cv_image is not None:
            self.current_cv_image = cv2.cvtColor(self.current_cv_image, cv2.COLOR_BGR2RGB)
        
        self.annotations = []
        self.current_points = []
        
        # Directe aanroep vervangen door flexibele functie
        self.run_ai_prediction()

    def run_ai_prediction(self):
        """Voert AI uit en filtert op basis van sliders"""
        if not self.var_use_ai.get() or self.current_cv_image is None:
            self.redraw()
            return

        # Oude handmatige annotaties wissen als we refreshen (optioneel, maar logisch bij 'Auto AI')
        self.annotations = []
        
        try:
            # 1. Haal alle predictions op
            preds = self.model_handler.predict_advanced_dual(self.current_path, self.slider_expand.get())
            
            # 2. Filteren op Confidence
            min_conf = self.slider_conf.get()
            filtered_preds = []
            
            for p in preds:
                # Als 'score' of 'conf' beschikbaar is in de prediction dict
                score = p.get('score', p.get('conf', 1.0)) 
                if score >= min_conf:
                    filtered_preds.append(p)
            
            # 3. Sorteren op score (hoogste eerst)
            filtered_preds.sort(key=lambda x: x.get('score', x.get('conf', 0)), reverse=True)
            
            # 4. Beperken tot Max Masks
            max_masks = int(self.slider_max_masks.get())
            final_preds = filtered_preds[:max_masks]
            
            self.annotations.extend(final_preds)
            
        except Exception as e:
            print(f"AI Error: {e}")
        
        self.redraw()

    def redraw(self):
        self.canvas.delete("all")
        if self.current_cv_image is None: return
        
        h_img, w_img = self.current_cv_image.shape[:2]
        w_can = self.canvas.winfo_width()
        h_can = self.canvas.winfo_height()
        
        if w_can < 10: return
        
        self.scale = min(w_can / w_img, h_can / h_img) * 0.95
        new_w, new_h = int(w_img * self.scale), int(h_img * self.scale)
        self.off_x, self.off_y = (w_can - new_w) // 2, (h_can - new_h) // 2
        
        img_res = cv2.resize(self.current_cv_image, (new_w, new_h))
        self.tk_img = ImageTk.PhotoImage(Image.fromarray(img_res))
        self.canvas.create_image(self.off_x, self.off_y, image=self.tk_img, anchor="nw")
        
        # Annotaties tekenen
        for ann in self.annotations:
            col = self.get_color(ann['class_id'])
            if ann['type'] == 'polygon':
                pts = []
                for x, y in ann['points']:
                    pts.extend([x * self.scale + self.off_x, y * self.scale + self.off_y])
                if len(pts) >= 4:
                    self.canvas.create_polygon(pts, outline=col, fill='', width=2)
            
            elif ann['type'] == 'bbox':
                x1, y1, x2, y2 = ann['coords']
                self.canvas.create_rectangle(
                    x1*self.scale+self.off_x, y1*self.scale+self.off_y,
                    x2*self.scale+self.off_x, y2*self.scale+self.off_y,
                    outline=col, dash=(2,2))

        # Huidige punten tekenen
        if self.current_points:
            pts = []
            for x, y in self.current_points:
                cx, cy = x * self.scale + self.off_x, y * self.scale + self.off_y
                pts.extend([cx, cy])
                self.canvas.create_oval(cx-2, cy-2, cx+2, cy+2, fill="yellow")
            if len(pts) >= 4:
                self.canvas.create_line(pts, fill="yellow", width=1)

    # --- INTERACTIE ---
    def on_left_click(self, event):
        ix = (event.x - self.off_x) / self.scale
        iy = (event.y - self.off_y) / self.scale
        self.current_points.append([ix, iy])
        self.redraw()

    def on_right_click(self, event):
        if len(self.current_points) > 2:
            self.annotations.append({
                "type": "polygon", 
                "class_id": self.get_class_id(), 
                "points": self.current_points,
                "score": 1.0 # Handmatig is altijd zeker
            })
            self.current_points = []
            self.redraw()

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

    # --- SAVE ---
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
                if ann['type'] == 'polygon':
                    line = f"{cid}"
                    for px, py in ann['points']:
                        line += f" {px/w:.6f} {py/h:.6f}"
                    f.write(line + "\n")
                elif ann['type'] == 'bbox':
                     x1, y1, x2, y2 = ann['coords']
                     cx, cy = ((x1+x2)/2)/w, ((y1+y2)/2)/h
                     bw, bh = (x2-x1)/w, (y2-y1)/h
                     f.write(f"{cid} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")

        if self.config.get('delete_mode', False):
            try: shutil.move(src, os.path.join(self.config['delete_folder'], fname))
            except: pass

        self.next_img()

    def skip_image(self):
        if self.config.get('move_skip', False):
             if not self.image_files: return
             fname = self.image_files[self.current_index]
             try: shutil.move(os.path.join(self.config['input_folder'], fname), os.path.join(self.config['delete_folder'], fname))
             except: pass
        self.next_img()

    def delete_image(self):
        if not self.image_files: return
        fname = self.image_files[self.current_index]
        try: shutil.move(os.path.join(self.config['input_folder'], fname), os.path.join(self.config['delete_folder'], fname))
        except: pass
        self.next_img()

    def next_img(self):
        if self.current_index < len(self.image_files) - 1:
            self.current_index += 1
            self.load_image()
        else:
            messagebox.showinfo("Klaar", "Alle beelden verwerkt!")