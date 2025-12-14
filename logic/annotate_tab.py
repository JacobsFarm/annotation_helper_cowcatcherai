import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import cv2
from PIL import Image, ImageTk
import os
import shutil
import numpy as np

# Importeer de logic handler
from logic.model_handler import ModelHandler

class AnnotateTab(ctk.CTkFrame):
    def __init__(self, parent, config):
        super().__init__(parent)
        self.config = config
        
        # State variabelen
        self.image_files = []
        self.current_index = 0
        self.current_cv_image = None
        self.zoom_scale = 1.0
        
        # Teken variabelen
        self.draw_mode = "bbox" # 'bbox' of 'polygon'
        self.current_class_id = 0
        self.is_drawing = False
        self.current_points = [] # Voor polygon klikken
        self.temp_item = None    # Voor visuele feedback tijdens tekenen
        self.annotations = []    # Lijst met actieve annotaties
        
        # Initialiseer Logic
        self.model_handler = ModelHandler(config)
        
        self.setup_ui()
        self.refresh_file_list()

    def setup_ui(self):
        # --- LAYOUT: 3 kolommen (Tools - Canvas - Info) ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 1. TOOLBAR (Links)
        self.frame_tools = ctk.CTkFrame(self, width=200)
        self.frame_tools.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        
        ctk.CTkLabel(self.frame_tools, text="TOOLS", font=("Arial", 16, "bold")).pack(pady=10)
        
        # AI Opties
        self.var_use_ai = ctk.BooleanVar(value=True)
        self.chk_ai = ctk.CTkSwitch(self.frame_tools, text="Auto AI Predict", variable=self.var_use_ai)
        self.chk_ai.pack(pady=5, padx=10, anchor="w")
        
        self.var_advanced = ctk.BooleanVar(value=False)
        self.chk_advanced = ctk.CTkCheckBox(self.frame_tools, text="Advanced (Dual Model)", variable=self.var_advanced)
        self.chk_advanced.pack(pady=5, padx=10, anchor="w")
        
        ctk.CTkLabel(self.frame_tools, text="Box Expansie (%)").pack(pady=(10,0))
        self.slider_expand = ctk.CTkSlider(self.frame_tools, from_=0, to=0.5, number_of_steps=10)
        self.slider_expand.set(0.1) # 10% standaard
        self.slider_expand.pack(pady=5, padx=10)
        
        # Teken Modus
        ctk.CTkLabel(self.frame_tools, text="TEKEN MODUS").pack(pady=(20,5))
        self.seg_mode = ctk.CTkSegmentedButton(self.frame_tools, values=["BBox", "Polygon"], command=self.set_draw_mode)
        self.seg_mode.set("BBox")
        self.seg_mode.pack(pady=5, padx=10)

        # Navigatie Knoppen
        ctk.CTkButton(self.frame_tools, text="Save & Next (S)", command=self.save_and_next, fg_color="green").pack(pady=20, padx=10, fill="x")
        ctk.CTkButton(self.frame_tools, text="Skip / Delete (Del)", command=self.skip_image, fg_color="red").pack(pady=5, padx=10, fill="x")
        ctk.CTkButton(self.frame_tools, text="Undo (Ctrl+Z)", command=self.undo_last, fg_color="gray").pack(pady=5, padx=10, fill="x")

        # 2. CANVAS (Midden)
        self.frame_canvas = ctk.CTkFrame(self)
        self.frame_canvas.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
        
        # We gebruiken standaard TK Canvas omdat CTk geen draw methods heeft
        self.canvas = tk.Canvas(self.frame_canvas, bg="#2b2b2b", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        
        # Events binden
        self.canvas.bind("<Button-1>", self.on_click_left)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Button-3>", self.on_click_right) # Rechtermuis om polygon af te ronden
        self.canvas.bind("<Return>", lambda e: self.finish_polygon())

        # 3. KLASSE SELECTIE (Onderin of Rechts, laten we Toolbar doen)
        ctk.CTkLabel(self.frame_tools, text="KLASSE").pack(pady=(20,5))
        self.combo_class = ctk.CTkOptionMenu(self.frame_tools, values=[c['name'] for c in self.config['classes']])
        self.combo_class.pack(pady=5, padx=10)

    # --- LOGICA ---

    def refresh_file_list(self):
        in_folder = self.config['input_folder']
        self.image_files = [f for f in os.listdir(in_folder) if f.lower().endswith(('.jpg', '.png'))]
        if self.image_files:
            self.load_current_image()
        else:
            self.canvas.delete("all")
            self.canvas.create_text(400, 300, text="Geen afbeeldingen in input map!", fill="white")

    def load_current_image(self):
        self.canvas.delete("all")
        self.annotations = []
        self.current_points = []
        
        filename = self.image_files[self.current_index]
        path = os.path.join(self.config['input_folder'], filename)
        
        # OpenCV laden
        self.current_cv_image = cv2.imread(path)
        self.current_cv_image = cv2.cvtColor(self.current_cv_image, cv2.COLOR_BGR2RGB)
        
        # Auto-Predict Logic
        if self.var_use_ai.get():
            self.run_ai_prediction(path)
            
        self.redraw_canvas()

    def run_ai_prediction(self, img_path):
        """Roept ModelHandler aan op basis van instellingen"""
        try:
            if self.var_advanced.get():
                # DUAL MODEL
                ratio = self.slider_expand.get()
                preds = self.model_handler.predict_advanced_dual(img_path, expand_ratio=ratio)
            else:
                # SINGLE MODEL
                preds = self.model_handler.predict_standard(img_path)
            
            self.annotations.extend(preds)
            
        except Exception as e:
            print(f"AI Fout: {e}")

    def redraw_canvas(self):
        """Tekent afbeelding + alle annotaties opnieuw"""
        self.canvas.delete("all")
        
        if self.current_cv_image is None: return

        # 1. Afbeelding Schalen en Tonen
        h, w = self.current_cv_image.shape[:2]
        cw = self.canvas.winfo_width() or 800
        ch = self.canvas.winfo_height() or 600
        
        # Bereken schaal
        self.scale = min(cw/w, ch/h) * 0.95
        nw, nh = int(w * self.scale), int(h * self.scale)
        
        # Offset om te centreren
        self.off_x = (cw - nw) // 2
        self.off_y = (ch - nh) // 2
        
        # Resize en converteer voor TK
        img_resized = cv2.resize(self.current_cv_image, (nw, nh))
        self.tk_img = ImageTk.PhotoImage(Image.fromarray(img_resized))
        self.canvas.create_image(self.off_x, self.off_y, image=self.tk_img, anchor="nw")
        
        # 2. Annotaties tekenen
        for ann in self.annotations:
            color = self.get_color_for_class(ann['class_id'])
            
            if ann['type'] == 'bbox':
                x1, y1, x2, y2 = ann['coords']
                # Transformeer naar canvas coords
                cx1 = x1 * self.scale + self.off_x
                cy1 = y1 * self.scale + self.off_y
                cx2 = x2 * self.scale + self.off_x
                cy2 = y2 * self.scale + self.off_y
                self.canvas.create_rectangle(cx1, cy1, cx2, cy2, outline=color, width=2, tags="ann")
                
            elif ann['type'] == 'polygon':
                points = ann['points']
                # Transformeer punten
                canvas_points = []
                for x, y in points:
                    canvas_points.append(x * self.scale + self.off_x)
                    canvas_points.append(y * self.scale + self.off_y)
                
                if len(canvas_points) >= 4:
                    self.canvas.create_polygon(canvas_points, outline=color, fill='', width=2, tags="ann")

        # 3. Update status info
        # (Zou je naar parent kunnen sturen)

    # --- TEKEN INTERACTIES ---

    def set_draw_mode(self, value):
        self.draw_mode = "bbox" if value == "BBox" else "polygon"
        self.current_points = [] # Reset polygon

    def on_click_left(self, event):
        # Convert click to image coords
        img_x = (event.x - self.off_x) / self.scale
        img_y = (event.y - self.off_y) / self.scale
        
        if self.draw_mode == "bbox":
            self.is_drawing = True
            self.start_x, self.start_y = img_x, img_y
            # Visuele feedback placeholder
            self.temp_item = self.canvas.create_rectangle(event.x, event.y, event.x, event.y, outline="yellow", width=2, dash=(4,4))
            
        elif self.draw_mode == "polygon":
            # Voeg punt toe
            self.current_points.append([img_x, img_y])
            # Teken puntje
            r = 3
            self.canvas.create_oval(event.x-r, event.y-r, event.x+r, event.y+r, fill="yellow")
            
            # Teken lijn naar vorig punt
            if len(self.current_points) > 1:
                prev = self.current_points[-2]
                px = prev[0] * self.scale + self.off_x
                py = prev[1] * self.scale + self.off_y
                self.canvas.create_line(px, py, event.x, event.y, fill="yellow", width=2)

    def on_drag(self, event):
        if self.draw_mode == "bbox" and self.is_drawing:
            # Update de tijdelijke rechthoek
            # Let op: start_x is in IMAGE coords, event.x is in CANVAS coords
            start_cx = self.start_x * self.scale + self.off_x
            start_cy = self.start_y * self.scale + self.off_y
            self.canvas.coords(self.temp_item, start_cx, start_cy, event.x, event.y)

    def on_release(self, event):
        if self.draw_mode == "bbox" and self.is_drawing:
            self.is_drawing = False
            self.canvas.delete(self.temp_item)
            
            end_x = (event.x - self.off_x) / self.scale
            end_y = (event.y - self.off_y) / self.scale
            
            # Normaliseer (zodat x1 < x2)
            x1, x2 = sorted([self.start_x, end_x])
            y1, y2 = sorted([self.start_y, end_y])
            
            # Te klein? negeer
            if (x2-x1) < 5 or (y2-y1) < 5: return
            
            # Opslaan
            self.annotations.append({
                "type": "bbox",
                "class_id": self.get_current_class_id(),
                "coords": [x1, y1, x2, y2]
            })
            self.redraw_canvas()

    def on_click_right(self, event):
        if self.draw_mode == "polygon":
            self.finish_polygon()

    def finish_polygon(self):
        if len(self.current_points) < 3:
            self.current_points = []
            self.redraw_canvas()
            return
            
        self.annotations.append({
            "type": "polygon",
            "class_id": self.get_current_class_id(),
            "points": self.current_points
        })
        self.current_points = []
        self.redraw_canvas()

    # --- HELPERS ---

    def get_current_class_id(self):
        name = self.combo_class.get()
        for c in self.config['classes']:
            if c['name'] == name:
                return c['id']
        return 0

    def get_color_for_class(self, class_id):
        for c in self.config['classes']:
            if c['id'] == class_id:
                return c['color']
        return "#FF0000"

    def save_and_next(self):
        if not self.image_files: return
        
        filename = self.image_files[self.current_index]
        base_name = os.path.splitext(filename)[0]
        img_src = os.path.join(self.config['input_folder'], filename)
        
        # 1. Image Kopiëren
        shutil.copy(img_src, os.path.join(self.config['output_img_folder'], filename))
        
        # 2. Label Schrijven (YOLO Formaat)
        label_path = os.path.join(self.config['output_label_folder'], f"{base_name}.txt")
        h_img, w_img = self.current_cv_image.shape[:2]
        
        with open(label_path, 'w') as f:
            for ann in self.annotations:
                cid = ann['class_id']
                if ann['type'] == 'bbox':
                    # Convert to center_x, center_y, w, h (normalized)
                    x1, y1, x2, y2 = ann['coords']
                    cx = ((x1 + x2) / 2) / w_img
                    cy = ((y1 + y2) / 2) / h_img
                    w = (x2 - x1) / w_img
                    h = (y2 - y1) / h_img
                    f.write(f"{cid} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}\n")
                    
                elif ann['type'] == 'polygon':
                    # Convert to x1 y1 x2 y2 ... (normalized)
                    line = f"{cid}"
                    for px, py in ann['points']:
                        line += f" {px/w_img:.6f} {py/h_img:.6f}"
                    f.write(line + "\n")
        
        # 3. Verplaatsen naar DELETE indien nodig (of gewoon lijst opschonen)
        if self.config.get('delete_mode', False):
            shutil.move(img_src, os.path.join(self.config['delete_folder'], filename))
        
        # 4. Volgende
        if self.current_index < len(self.image_files) - 1:
            self.current_index += 1
            self.load_current_image()
        else:
            messagebox.showinfo("Klaar", "Alle afbeeldingen verwerkt!")

    def skip_image(self):
        if self.current_index < len(self.image_files) - 1:
            self.current_index += 1
            self.load_current_image()
            
    def undo_last(self):
        if self.annotations:
            self.annotations.pop()
            self.redraw_canvas()