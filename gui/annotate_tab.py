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
        
        # State variabelen
        self.image_files = []
        self.current_index = 0
        self.current_cv_image = None
        self.scale = 1.0 
        self.off_x = 0
        self.off_y = 0
        
        # Teken variabelen (Alleen BBox)
        self.is_drawing = False
        self.start_x = 0 
        self.start_y = 0
        self.temp_item = None    
        self.annotations = []    
        
        # Logic
        self.model_handler = ModelHandler(config)
        
        # UI
        self.setup_ui()
        
        # Bindings pas activeren als tab zichtbaar wordt
        self.bind("<Visibility>", self.enable_shortcuts)
        
        # Start laden
        self.after(100, self.refresh_file_list)

    def setup_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        keys = self.config.get('keys_annotate', {"save_next": "s", "skip": "space", "delete": "Delete", "undo": "z"})

        # --- 1. TOOLBAR ---
        self.frame_tools = ctk.CTkFrame(self, width=200)
        self.frame_tools.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        ctk.CTkLabel(self.frame_tools, text="BOX TOOLS", font=("Arial", 16, "bold")).pack(pady=10)
        
        # AI
        self.var_use_ai = ctk.BooleanVar(value=True)
        ctk.CTkSwitch(self.frame_tools, text="Auto Detect (Box)", variable=self.var_use_ai).pack(pady=5, padx=10, anchor="w")
        
        # Knoppen
        ctk.CTkLabel(self.frame_tools, text="ACTIES").pack(pady=(20,5))
        
        k_save = keys.get('save_next', 'S').upper()
        ctk.CTkButton(self.frame_tools, text=f"Save & Next ({k_save})", command=self.save_and_next, fg_color="green").pack(pady=10, padx=10, fill="x")
        
        k_skip = keys.get('skip', 'SPACE').upper()
        ctk.CTkButton(self.frame_tools, text=f"Skip ({k_skip})", command=self.skip_image, fg_color="orange").pack(pady=5, padx=10, fill="x")
        
        k_del = keys.get('delete', 'DEL').upper()
        ctk.CTkButton(self.frame_tools, text=f"Delete ({k_del})", command=self.delete_image, fg_color="red").pack(pady=5, padx=10, fill="x")
        
        k_undo = keys.get('undo', 'Z').upper()
        ctk.CTkButton(self.frame_tools, text=f"Undo ({k_undo})", command=self.undo_last, fg_color="gray").pack(pady=20, padx=10, fill="x")

        # --- 2. CANVAS ---
        self.frame_canvas = ctk.CTkFrame(self)
        self.frame_canvas.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        
        self.canvas = tk.Canvas(self.frame_canvas, bg="#202020", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        
        # Events (Simpeler: Alleen Left Click & Drag)
        self.canvas.bind("<Button-1>", self.on_click_left)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Configure>", lambda e: self.redraw_canvas())
        
        # Focus
        self.canvas.bind("<Enter>", lambda e: self.canvas.focus_set())

        # --- 3. KLASSE ---
        ctk.CTkLabel(self.frame_tools, text="KLASSE").pack(pady=(20,5))
        self.combo_class = ctk.CTkOptionMenu(self.frame_tools, values=[c['name'] for c in self.config['classes']])
        self.combo_class.pack(pady=5, padx=10)

    def enable_shortcuts(self, event=None):
        """Activeer sneltoetsen ALLEEN als dit tabblad zichtbaar wordt"""
        try:
            root = self.winfo_toplevel()
            keys = self.config.get('keys_annotate', {})
            
            def if_active(func):
                def wrapper(event=None):
                    if self.winfo_viewable():
                        func()
                return wrapper

            k_save = keys.get("save_next", "s")
            root.bind(f"<{k_save.lower()}>", if_active(self.save_and_next))
            root.bind(f"<{k_save.upper()}>", if_active(self.save_and_next))
            
            k_skip = keys.get("skip", "space")
            if k_skip.lower() == "space":
                root.bind("<space>", if_active(self.skip_image))
            else:
                root.bind(f"<{k_skip}>", if_active(self.skip_image))
            
            k_del = keys.get("delete", "Delete")
            root.bind(f"<{k_del}>", if_active(self.delete_image))
            
            k_undo = keys.get("undo", "z")
            root.bind(f"<{k_undo.lower()}>", if_active(self.undo_last))
            root.bind(f"<{k_undo.upper()}>", if_active(self.undo_last))
            
            self.focus_set()
            
        except Exception as e:
            print(f"Kon sneltoetsen niet activeren: {e}")

    # --- LOGICA ---
    def refresh_file_list(self):
        in_folder = self.config.get('input_folder', '')
        if not os.path.exists(in_folder): return
        
        self.image_files = [f for f in os.listdir(in_folder) if f.lower().endswith(('.jpg', '.png', '.jpeg'))]
        if self.image_files:
            self.load_current_image()
        else:
            self.canvas.delete("all")
            self.canvas.create_text(400, 300, text="Geen afbeeldingen in input map!", fill="white")

    def load_current_image(self):
        self.canvas.delete("all")
        self.annotations = []
        
        if self.current_index >= len(self.image_files): self.current_index = 0
        if not self.image_files: return

        filename = self.image_files[self.current_index]
        path = os.path.join(self.config['input_folder'], filename)
        
        self.current_cv_image = cv2.imread(path)
        if self.current_cv_image is not None:
            self.current_cv_image = cv2.cvtColor(self.current_cv_image, cv2.COLOR_BGR2RGB)
        
        if self.var_use_ai.get():
            self.run_ai_prediction(path)
            
        self.redraw_canvas()

    def run_ai_prediction(self, img_path):
        try:
            # Hier gebruiken we ALLEEN de snelle standaard detectie
            preds = self.model_handler.predict_standard(img_path)
            self.annotations.extend(preds)
        except Exception as e:
            print(f"AI Fout: {e}")

    def redraw_canvas(self):
        self.canvas.delete("all")
        if self.current_cv_image is None: return

        h, w = self.current_cv_image.shape[:2]
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        
        if cw < 10 or ch < 10: return
        
        self.scale = min(cw/w, ch/h) * 0.95
        nw, nh = int(w * self.scale), int(h * self.scale)
        self.off_x = (cw - nw) // 2
        self.off_y = (ch - nh) // 2
        
        img_res = cv2.resize(self.current_cv_image, (nw, nh))
        self.tk_img = ImageTk.PhotoImage(Image.fromarray(img_res))
        self.canvas.create_image(self.off_x, self.off_y, image=self.tk_img, anchor="nw")
        
        # Teken bestaande annotaties (Alleen Boxes)
        for ann in self.annotations:
            if ann['type'] == 'bbox':
                color = self.get_color_for_class(ann['class_id'])
                x1, y1, x2, y2 = ann['coords']
                cx1 = x1 * self.scale + self.off_x
                cy1 = y1 * self.scale + self.off_y
                cx2 = x2 * self.scale + self.off_x
                cy2 = y2 * self.scale + self.off_x
                self.canvas.create_rectangle(cx1, cy1, cx2, cy2, outline=color, width=2)
            # Polygonen negeren we hier

    # --- TEKEN INTERACTIES (Alleen Box) ---
    def on_click_left(self, event):
        self.focus_set() 
        img_x = (event.x - self.off_x) / self.scale
        img_y = (event.y - self.off_y) / self.scale
        
        self.is_drawing = True
        self.start_x, self.start_y = img_x, img_y
        self.temp_item = self.canvas.create_rectangle(event.x, event.y, event.x, event.y, outline="yellow", width=2, dash=(4,4))

    def on_drag(self, event):
        if self.is_drawing:
            start_cx = self.start_x * self.scale + self.off_x
            start_cy = self.start_y * self.scale + self.off_y
            self.canvas.coords(self.temp_item, start_cx, start_cy, event.x, event.y)

    def on_release(self, event):
        if self.is_drawing:
            self.is_drawing = False
            self.canvas.delete(self.temp_item)
            
            end_x = (event.x - self.off_x) / self.scale
            end_y = (event.y - self.off_y) / self.scale
            
            x1, x2 = sorted([self.start_x, end_x])
            y1, y2 = sorted([self.start_y, end_y])
            
            # Minimaal 2 pixels groot
            if (x2-x1) > 2 and (y2-y1) > 2:
                self.annotations.append({
                    "type": "bbox", 
                    "class_id": self.get_current_class_id(), 
                    "coords": [x1, y1, x2, y2]
                })
            self.redraw_canvas()

    # --- ACTIES ---
    def get_current_class_id(self):
        name = self.combo_class.get()
        for c in self.config['classes']:
            if c['name'] == name: return c['id']
        return 0

    def get_color_for_class(self, class_id):
        for c in self.config['classes']:
            if c['id'] == class_id: return c['color']
        return "#FF0000"

    def save_and_next(self):
        if not self.image_files: return
        
        filename = self.image_files[self.current_index]
        base_name = os.path.splitext(filename)[0]
        img_src = os.path.join(self.config['input_folder'], filename)
        
        # Save Img
        shutil.copy(img_src, os.path.join(self.config['output_img_folder'], filename))
        
        # Save Label (YOLO BBox Format)
        label_path = os.path.join(self.config['output_label_folder'], f"{base_name}.txt")
        h, w = self.current_cv_image.shape[:2]
        
        with open(label_path, 'w') as f:
            for ann in self.annotations:
                # We slaan alleen BBoxes op in dit tabblad
                if ann['type'] == 'bbox':
                    cid = ann['class_id']
                    x1, y1, x2, y2 = ann['coords']
                    cx = ((x1+x2)/2)/w
                    cy = ((y1+y2)/2)/h
                    bw = (x2-x1)/w
                    bh = (y2-y1)/h
                    f.write(f"{cid} {cx:.6f} {cy:.6f} {bw:.6f} {bh:.6f}\n")
        
        # Delete mode
        if self.config.get('delete_mode', False):
            try: shutil.move(img_src, os.path.join(self.config['delete_folder'], filename))
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
        filename = self.image_files[self.current_index]
        try:
            shutil.move(os.path.join(self.config['input_folder'], filename),
                        os.path.join(self.config['delete_folder'], filename))
        except: pass
        self.next_img()

    def next_img(self):
        if self.current_index < len(self.image_files) - 1:
            self.current_index += 1
            self.load_current_image()
        else:
            messagebox.showinfo("Klaar", "Alle afbeeldingen verwerkt!")

    def undo_last(self):
        if self.annotations:
            self.annotations.pop()
            self.redraw_canvas()