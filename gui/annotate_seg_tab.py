import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import cv2
from PIL import Image, ImageTk
import os
import shutil
import numpy as np
from ultralytics import YOLO 

class AnnotateSegTab(ctk.CTkFrame):
    def __init__(self, parent, config):
        super().__init__(parent)
        self.config = config
        
        # --- INSTELLINGEN ---
        self.input_folder = config.get('input_folder', 'input')
        self.output_img = config.get('output_img_folder', 'output/images')
        self.output_lbl = config.get('output_label_folder', 'output/labels')
        
        model_path = config.get('model_path_seg', 'yolov11m-seg.pt')
        try:
            self.model = YOLO(model_path)
        except:
            print(f"Kon model niet laden: {model_path}")
            self.model = None
        
        # State
        self.image_files = []
        self.current_index = 0
        self.cv_img = None
        self.polygon_points = []
        self.selected_point_idx = None
        
        # Zoom & Pan variabelen
        self.scale = 1.0
        self.offset = [0, 0]     # [x, y] offset op het canvas
        self.fit_to_screen = True # Start altijd passend in scherm
        self.is_panning = False  # Is de spatiebalk ingedrukt?
        self.is_dragging_pan = False # Zijn we daadwerkelijk aan het slepen?
        self.pan_start = (0, 0)  # Startpunt van slepen

        # UI Opbouw
        self.setup_ui()
        self.after(100, self.refresh_list)

    def setup_ui(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(self, bg="#202020", highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        
        # --- EVENTS ---
        # Muis interacties
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        
        # Rechtermuisknop om punten te verwijderen
        self.canvas.bind("<Button-3>", self.on_right_click)
        
        # Window resize
        self.canvas.bind("<Configure>", self.on_resize)

        # ZOOM: Ctrl + Scroll (Windows/Linux)
        # Windows gebruikt <MouseWheel>, Linux <Button-4/5>
        self.canvas.bind("<Control-MouseWheel>", self.on_zoom) 
        self.canvas.bind("<Control-Button-4>", self.on_zoom) # Linux scroll up
        self.canvas.bind("<Control-Button-5>", self.on_zoom) # Linux scroll down

        # PAN: Spatiebalk logic
        # We moeten binden aan het root window zodat spatie overal werkt
        root = self.winfo_toplevel()
        root.bind("<KeyPress-space>", self.start_pan_mode)
        root.bind("<KeyRelease-space>", self.stop_pan_mode)
        root.bind("<Return>", lambda e: self.save_and_next())

        # Knoppenbalk
        frame_controls = ctk.CTkFrame(self, height=50)
        frame_controls.grid(row=1, column=0, sticky="ew", padx=10, pady=10)
        
        self.lbl_info = ctk.CTkLabel(frame_controls, text="Laden...")
        self.lbl_info.pack(side="left", padx=20)

        ctk.CTkButton(frame_controls, text="Save & Next (Enter)", command=self.save_and_next, fg_color="green").pack(side="right", padx=10)
        ctk.CTkButton(frame_controls, text="Reset AI", command=self.run_ai, fg_color="#444").pack(side="right", padx=10)
        
        # Instructie labeltje
        ctk.CTkLabel(frame_controls, text="[Ctrl+Scroll]: Zoom | [Spatie+Sleep]: Pan", text_color="gray").pack(side="right", padx=20)

    # --- LIST & LOADING ---
    def refresh_list(self):
        if os.path.exists(self.input_folder):
            self.image_files = [f for f in os.listdir(self.input_folder) if f.lower().endswith(('.jpg', '.png', '.jpeg'))]
            if self.image_files:
                self.load_image()
            else:
                self.lbl_info.configure(text="Geen afbeeldingen!")

    def load_image(self):
        path = os.path.join(self.input_folder, self.image_files[self.current_index])
        self.cv_img = cv2.imread(path)
        if self.cv_img is not None:
            self.cv_img = cv2.cvtColor(self.cv_img, cv2.COLOR_BGR2RGB)
            self.lbl_info.configure(text=f"{self.image_files[self.current_index]} ({self.current_index+1}/{len(self.image_files)})")
            
            # Reset zoom bij nieuwe foto
            self.fit_to_screen = True 
            
            self.run_ai()
        else:
            print(f"Fout laden: {path}")

    def run_ai(self):
        if self.model is None or self.cv_img is None: return
        results = self.model(self.cv_img, verbose=False)
        self.polygon_points = []
        if results and results[0].masks:
            masks = results[0].masks.xy
            if len(masks) > 0:
                poly = masks[0]
                if len(poly) > 60: 
                    indices = np.linspace(0, len(poly)-1, 50, dtype=int)
                    poly = poly[indices]
                self.polygon_points = poly.tolist()
        self.draw()

    # --- DRAWING ---
    def on_resize(self, event):
        # Alleen hertekenen als we in "fit mode" zijn, of gewoon update
        if self.fit_to_screen:
            self.draw()

    def draw(self):
        self.canvas.delete("all")
        if self.cv_img is None: return

        h_img, w_img = self.cv_img.shape[:2]
        w_can = self.canvas.winfo_width()
        h_can = self.canvas.winfo_height()
        
        if w_can <= 1: return 

        # Bereken schaal en offset
        if self.fit_to_screen:
            # Automatisch passend maken
            self.scale = min(w_can/w_img, h_can/h_img) * 0.95
            nw, nh = int(w_img * self.scale), int(h_img * self.scale)
            ox, oy = (w_can - nw)//2, (h_can - nh)//2
            self.offset = [ox, oy]
        else:
            # Gebruik huidige zoom/pan waarden (worden aangepast door scroll/drag)
            pass

        # Afbeelding tekenen (alleen het zichtbare deel voor performance zou beter zijn, maar dit is makkelijker)
        # We gebruiken warpAffine voor zoom/pan als het heel groot wordt, 
        # maar voor eenvoud resizen we gewoon. Let op: bij extreme zoom kan dit traag worden.
        # Voor deze implementatie gebruiken we de simpele resize methode:
        
        nw = int(w_img * self.scale)
        nh = int(h_img * self.scale)
        
        # Om bugs bij extreme zoom te voorkomen (ImageTk limiet), cappen we de grootte of gebruiken we een crop.
        # Voor nu houden we het simpel:
        if nw < 1 or nh < 1: return

        # PIL image maken
        pil_img = Image.fromarray(self.cv_img)
        pil_img = pil_img.resize((nw, nh), Image.Resampling.NEAREST) # Nearest is sneller
        self.tk_img = ImageTk.PhotoImage(pil_img)
        
        self.canvas.create_image(self.offset[0], self.offset[1], image=self.tk_img, anchor="nw")

        # Polygon tekenen
        if len(self.polygon_points) > 1:
            display_pts = []
            ox, oy = self.offset
            for px, py in self.polygon_points:
                cx = px * self.scale + ox
                cy = py * self.scale + oy
                display_pts.extend([cx, cy])
            
            # Lijnen
            self.canvas.create_polygon(display_pts, outline="#00ff00", fill="", width=2, tags="poly")
            
            # Punten (alleen tekenen als ze in beeld zijn, optimalisatie)
            for i, (px, py) in enumerate(self.polygon_points):
                cx = px * self.scale + ox
                cy = py * self.scale + oy
                
                # Check of punt binnen canvas valt (beetje marge)
                if -10 < cx < w_can + 10 and -10 < cy < h_can + 10:
                    col = "#ff3333" if i == self.selected_point_idx else "#ffff00"
                    r = 5 if i == self.selected_point_idx else 3
                    self.canvas.create_oval(cx-r, cy-r, cx+r, cy+r, fill=col, outline="black", tags=f"pt_{i}")

            self.canvas.tag_raise("pt_")

    # --- ZOOM & PAN LOGICA ---
    
    def start_pan_mode(self, event):
        self.is_panning = True
        self.canvas.configure(cursor="hand2") # Handje cursor

    def stop_pan_mode(self, event):
        self.is_panning = False
        self.is_dragging_pan = False
        self.canvas.configure(cursor="arrow") # Terug naar pijl

    def on_zoom(self, event):
        """Zoom in op de muispositie"""
        if self.cv_img is None: return

        # Bepaal scroll richting
        if event.num == 5 or event.delta < 0:
            factor = 0.9 # Uitzoomen
        else:
            factor = 1.1 # Inzoomen

        # Muispositie op canvas
        mouse_x = self.canvas.canvasx(event.x)
        mouse_y = self.canvas.canvasy(event.y)

        # Bereken waar de muis is relatief aan de afbeelding (voor de zoom)
        # Oude offset
        ox, oy = self.offset
        
        # Update schaal
        new_scale = self.scale * factor
        
        # Limiteer zoom (niet te klein, niet te bizar groot)
        if new_scale < 0.1 or new_scale > 50: return

        # De magie: verschuif offset zodat muis op zelfde plek in afbeelding blijft
        self.offset[0] = mouse_x - (mouse_x - ox) * factor
        self.offset[1] = mouse_y - (mouse_y - oy) * factor
        
        self.scale = new_scale
        self.fit_to_screen = False # We zitten nu in manual mode
        self.draw()

    # --- CLICK & DRAG ---
# --- CLICK & DRAG ---
    def on_click(self, event):
        # Optie 1: Expliciete Pan-modus met Spatiebalk (bestaande functionaliteit behouden)
        if self.is_panning:
            self.is_dragging_pan = True
            self.pan_start = (event.x, event.y)
            self.canvas.configure(cursor="fleur")
            return

        # --- LOGICA VOOR PUNTEN/LIJNEN/ACHTERGROND ---
        click_pt = np.array([event.x, event.y])
        ox, oy = self.offset
        
        # A. Bestaand punt? (Drempelwaarde hardcoded: 15px)
        best_dist = 15
        best_idx = None
        for i, (px, py) in enumerate(self.polygon_points):
            cx = px * self.scale + ox
            cy = py * self.scale + oy
            dist = ((cx - event.x)**2 + (cy - event.y)**2)**0.5
            if dist < best_dist:
                best_dist = dist
                best_idx = i
        
        if best_idx is not None:
            self.selected_point_idx = best_idx
            self.draw()
            return # We hebben een punt, dus we gaan NIET pannen

        # B. Lijn klik? (Drempelwaarde hardcoded: 10px)
        if len(self.polygon_points) > 1:
            line_threshold = 10
            for i in range(len(self.polygon_points)):
                p1_idx = i
                p2_idx = (i + 1) % len(self.polygon_points)
                p1_raw = self.polygon_points[p1_idx]
                p2_raw = self.polygon_points[p2_idx]
                
                p1 = np.array([p1_raw[0] * self.scale + ox, p1_raw[1] * self.scale + oy])
                p2 = np.array([p2_raw[0] * self.scale + ox, p2_raw[1] * self.scale + oy])
                
                p1_to_p2 = p2 - p1
                p1_to_click = click_pt - p1
                len_sq = np.dot(p1_to_p2, p1_to_p2)
                
                dist_to_line = float('inf')
                if len_sq > 0:
                    t = max(0, min(1, np.dot(p1_to_click, p1_to_p2) / len_sq))
                    proj = p1 + t * p1_to_p2
                    dist_to_line = np.linalg.norm(click_pt - proj)
                
                if dist_to_line < line_threshold:
                    # Nieuw punt toevoegen op de lijn
                    new_img_x = (event.x - ox) / self.scale
                    new_img_y = (event.y - oy) / self.scale
                    self.polygon_points.insert(p1_idx + 1, [new_img_x, new_img_y])
                    self.selected_point_idx = p1_idx + 1
                    self.draw()
                    return # We hebben een lijn, dus we gaan NIET pannen

        # C. ACHTERGROND KLIK -> AUTOMATISCH PANNEN
        # Als we hier zijn, is er niet op een punt en niet op een lijn geklikt.
        # We activeren de sleep-modus.
        self.selected_point_idx = None
        self.is_dragging_pan = True
        self.pan_start = (event.x, event.y)
        self.canvas.configure(cursor="fleur")
        self.draw()

    def on_drag(self, event):
        # 1. Panning logica
        # AANGEPAST: We checken alleen 'is_dragging_pan'. 
        # Dit staat aan als we spatie gebruiken OF als we op de achtergrond klikten.
        if self.is_dragging_pan:
            dx = event.x - self.pan_start[0]
            dy = event.y - self.pan_start[1]
            
            self.offset[0] += dx
            self.offset[1] += dy
            
            self.pan_start = (event.x, event.y)
            self.fit_to_screen = False
            self.draw()
            return

        # 2. Punt verplaatsen logica
        if self.selected_point_idx is not None:
            ox, oy = self.offset
            img_x = (event.x - ox) / self.scale
            img_y = (event.y - oy) / self.scale
            self.polygon_points[self.selected_point_idx] = [img_x, img_y]
            self.draw()

    def on_release(self, event):
        if self.is_dragging_pan:
            self.is_dragging_pan = False
            # Alleen cursor terugzetten naar 'hand' als we nog steeds de spatiebalk inhouden,
            # anders terug naar pijl.
            if self.is_panning:
                self.canvas.configure(cursor="hand2")
            else:
                self.canvas.configure(cursor="arrow")
        
        self.selected_point_idx = None

    def on_release(self, event):
        if self.is_dragging_pan:
            self.is_dragging_pan = False
            if self.is_panning:
                self.canvas.configure(cursor="hand2")
        
        self.selected_point_idx = None
        # Niet redrawen hier nodig, on_drag deed het al

    def on_right_click(self, event):
        """Verwijder punt"""
        ox, oy = self.offset
        best_dist = 15
        best_idx = None
        for i, (px, py) in enumerate(self.polygon_points):
            cx = px * self.scale + ox
            cy = py * self.scale + oy
            dist = ((cx - event.x)**2 + (cy - event.y)**2)**0.5
            if dist < best_dist:
                best_dist = dist
                best_idx = i
        
        if best_idx is not None and len(self.polygon_points) > 3:
            self.polygon_points.pop(best_idx)
            self.selected_point_idx = None
            self.draw()

    def save_and_next(self):
        if not self.image_files: return
        if self.cv_img is None: return

        filename = self.image_files[self.current_index]
        base_name = os.path.splitext(filename)[0]
        
        os.makedirs(self.output_img, exist_ok=True)
        os.makedirs(self.output_lbl, exist_ok=True)

        shutil.copy(os.path.join(self.input_folder, filename), os.path.join(self.output_img, filename))
        
        if self.polygon_points:
            h, w = self.cv_img.shape[:2]
            label_path = os.path.join(self.output_lbl, f"{base_name}.txt")
            with open(label_path, "w") as f:
                line_parts = ["0"] # Class 0
                for px, py in self.polygon_points:
                    nx = max(0.0, min(1.0, px / w))
                    ny = max(0.0, min(1.0, py / h))
                    line_parts.append(f"{nx:.6f} {ny:.6f}")
                f.write(" ".join(line_parts) + "\n")
        
        if self.current_index < len(self.image_files) - 1:
            self.current_index += 1
            self.load_image()
        else:
            messagebox.showinfo("Klaar", "Alle afbeeldingen verwerkt!")
