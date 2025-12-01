# Disclaimer:
# This project is part of the open-source “Cowcatcher AI” initiative
# and is a fork of the annotation_helper from the development repository.
# The source code is distributed under the GPL-3.0/AGPL license.
# This is a conceptual project intended for non-commercial use.
# The authors provide no warranty for the accuracy, performance,
# or suitability of this software. Use at your own risk.

import os
import sys
import cv2
import numpy as np
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk
import shutil
from pathlib import Path
import json

# Configuration - adjust these paths to match your project structure
model_path = "yolo11x.pt"
input_folder = r"F:/data/annotate"
output_img_folder = r"F:/data/annotated_images"
output_label_folder = r"F:/data/annotated_labels"
delete_folder = r"F:/data/deleted"
enable_delete_mode = True

class YoloAnnotationApp:
    def __init__(self, root, model_path, input_folder, output_img_folder, output_label_folder, delete_folder, enable_delete_mode):
        self.root = root
        self.root.title("CowCatcher Annotation Helper - Colorful Edition")
        self.root.geometry("1200x800")
        
        # Set up folders and model path
        self.model_path = model_path
        self.input_folder = input_folder
        self.output_img_folder = output_img_folder
        self.output_label_folder = output_label_folder
        self.delete_folder = delete_folder
        self.delete_mode_enabled = enable_delete_mode
        
        # --- KLEURENPALET ---
        # Formaat: (Tkinter Hex, OpenCV BGR)
        # BGR is omgekeerd van RGB (Blue, Green, Red)
        self.colors = [
            ('#FF0000', (0, 0, 255)),       # 0: Rood
            ('#00FF00', (0, 255, 0)),       # 1: Groen
            ('#0000FF', (255, 0, 0)),       # 2: Blauw
            ('#FFFF00', (0, 255, 255)),     # 3: Geel
            ('#00FFFF', (255, 255, 0)),     # 4: Cyaan
            ('#FF00FF', (255, 0, 255)),     # 5: Magenta
            ('#FFA500', (0, 165, 255)),     # 6: Oranje
            ('#800080', (128, 0, 128)),     # 7: Paars
            ('#A52A2A', (42, 42, 165)),     # 8: Bruin
            ('#FFC0CB', (203, 192, 255))    # 9: Roze
        ]
        
        # --- Classes Laden ---
        self.class_config_file = "config_classes.json"
        self.classes = []
        self.load_classes()
        # ---------------------
        
        # Create output folders
        os.makedirs(self.output_img_folder, exist_ok=True)
        os.makedirs(self.output_label_folder, exist_ok=True)
        os.makedirs(self.delete_folder, exist_ok=True)
        
        # Get all images
        self.image_files = [f for f in os.listdir(self.input_folder) 
                            if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
        self.current_index = 0
        
        # Variables for manual bounding box drawing
        self.drawing_mode = False
        self.start_x = None
        self.start_y = None
        self.current_rectangle = None 
        
        # Lijst voor meerdere boxes
        self.manual_bboxes = [] 
        
        self.current_img = None
        self.current_image_info = {}
        
        # Undo functionality
        self.last_action = None
        
        # Load the YOLO model
        self.load_model()
        
        # UI setup
        self.setup_menu()
        self.setup_ui()
        
        # Load the first image
        if self.image_files:
            self.root.update_idletasks()
            self.root.after(100, self.load_current_image)
    
    def get_color(self, class_id):
        """Geeft de (Hex, BGR) tuple terug voor een class ID"""
        # Gebruik modulo (%) zodat we niet crashen als er meer dan 10 classes zijn.
        # Dan begint hij gewoon weer bij rood.
        return self.colors[class_id % len(self.colors)]

    def load_classes(self):
        if os.path.exists(self.class_config_file):
            try:
                with open(self.class_config_file, 'r') as f:
                    data = json.load(f)
                    self.classes = data.get("classes", ["mounting"])
            except Exception as e:
                print(f"Error loading config: {e}")
                self.classes = ["mounting"]
        else:
            self.classes = ["mounting"]
            self.save_classes()

    def save_classes(self):
        try:
            with open(self.class_config_file, 'w') as f:
                json.dump({"classes": self.classes}, f, indent=4)
        except Exception as e:
            messagebox.showerror("Error", f"Kon config niet opslaan: {e}")

    def load_model(self):
        try:
            from ultralytics import YOLO
            self.model = YOLO(self.model_path)
            self.model_type = "ultralytics"
            print("Model loaded with ultralytics YOLO")
        except Exception as e:
            print(f"Error loading model with ultralytics: {e}")
            try:
                import torch
                self.model = torch.hub.load('ultralytics/yolov5', 'custom', path=self.model_path, force_reload=True)
                self.model_type = "torch_hub"
                print("Model loaded with torch.hub")
            except Exception as e2:
                print(f"Both loading methods failed: {e2}")
                raise Exception("Could not load YOLO model. Install 'pip install ultralytics'")
    
    def setup_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        settings_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Opties", menu=settings_menu)
        settings_menu.add_command(label="Beheer Classes", command=self.open_class_manager)

    def open_class_manager(self):
        manager = tk.Toplevel(self.root)
        manager.title("Class Manager")
        manager.geometry("400x400")
        
        lbl = ttk.Label(manager, text="Huidige Classes (Index = ID):")
        lbl.pack(pady=5)
        
        listbox = tk.Listbox(manager)
        listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        for cls in self.classes:
            listbox.insert(tk.END, cls)
            
        frame_add = ttk.Frame(manager)
        frame_add.pack(fill=tk.X, padx=10, pady=5)
        
        entry_cls = ttk.Entry(frame_add)
        entry_cls.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        def add_class():
            new_cls = entry_cls.get().strip()
            if new_cls and new_cls not in self.classes:
                self.classes.append(new_cls)
                listbox.insert(tk.END, new_cls)
                self.save_classes()
                entry_cls.delete(0, tk.END)
                self.update_class_selector()
            elif new_cls in self.classes:
                messagebox.showwarning("Warning", "Class bestaat al!")

        btn_add = ttk.Button(frame_add, text="Toevoegen", command=add_class)
        btn_add.pack(side=tk.RIGHT, padx=5)
        
        def delete_class():
            sel = listbox.curselection()
            if sel:
                idx = sel[0]
                cls_name = listbox.get(idx)
                if messagebox.askyesno("Confirm", f"Verwijder '{cls_name}'?\nLet op: Indexen verschuiven hierdoor!"):
                    self.classes.pop(idx)
                    listbox.delete(idx)
                    self.save_classes()
                    self.update_class_selector()

        ttk.Button(manager, text="Geselecteerde verwijderen", command=delete_class).pack(pady=5)

    def setup_ui(self):
        self.image_frame = ttk.Frame(self.root)
        self.image_frame.pack(pady=10, fill=tk.BOTH, expand=True)
        
        # Left: original image
        self.original_frame = ttk.LabelFrame(self.image_frame, text="Original Image")
        self.original_frame.pack(side=tk.LEFT, padx=10, fill=tk.BOTH, expand=True)
        self.original_canvas = tk.Canvas(self.original_frame, highlightthickness=0)
        self.original_canvas.pack(fill=tk.BOTH, expand=True)
        
        # Right: image with predictions
        self.prediction_frame = ttk.LabelFrame(self.image_frame, text="Image with YOLO Predictions")
        self.prediction_frame.pack(side=tk.RIGHT, padx=10, fill=tk.BOTH, expand=True)
        self.prediction_canvas = tk.Canvas(self.prediction_frame, highlightthickness=0)
        self.prediction_canvas.pack(fill=tk.BOTH, expand=True)
        
        # Mouse events
        self.original_canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.original_canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.original_canvas.bind("<ButtonRelease-1>", self.on_mouse_up)
        self.original_canvas.bind("<ButtonPress-3>", self.undo_last_bbox) 
        
        # Footer
        self.button_frame = ttk.Frame(self.root)
        self.button_frame.pack(pady=10)
        
        self.status_label = ttk.Label(self.button_frame, text="")
        self.status_label.grid(row=0, column=0, columnspan=10, pady=5)
        
        # Class Selector
        ttk.Label(self.button_frame, text="Active Class:").grid(row=1, column=0, padx=5)
        self.class_var = tk.StringVar()
        self.class_combo = ttk.Combobox(self.button_frame, textvariable=self.class_var, state="readonly")
        self.class_combo.grid(row=1, column=1, columnspan=2, padx=5, sticky="ew")
        self.class_combo.bind("<<ComboboxSelected>>", lambda e: self.root.focus_set())
        self.update_class_selector()
        
        # Delete mode
        self.delete_mode_var = tk.BooleanVar(value=self.delete_mode_enabled)
        self.delete_mode_checkbox = ttk.Checkbutton(
            self.button_frame, text="Enable Delete Mode", 
            variable=self.delete_mode_var, command=self.toggle_delete_mode
        )
        self.delete_mode_checkbox.grid(row=1, column=3, columnspan=4, pady=5)
        
        # Buttons
        ttk.Button(self.button_frame, text="Previous (A)", command=self.prev_image).grid(row=2, column=0, padx=5)
        ttk.Button(self.button_frame, text="Next (D)", command=self.next_image).grid(row=2, column=1, padx=5)
        ttk.Button(self.button_frame, text="Save (S)", command=self.save_current).grid(row=2, column=2, padx=5)
        ttk.Button(self.button_frame, text="Null (N)", command=self.save_as_null).grid(row=2, column=3, padx=5)
        ttk.Button(self.button_frame, text="Skip (O)", command=self.skip_current).grid(row=2, column=4, padx=5)
        ttk.Button(self.button_frame, text="Draw (T)", command=self.toggle_drawing_mode).grid(row=2, column=5, padx=5)
        
        self.undo_button = ttk.Button(self.button_frame, text="Undo (U)", command=self.undo_last_action)
        self.undo_button.grid(row=2, column=6, padx=5)
        self.undo_button.config(state='disabled')
        
        ttk.Button(self.button_frame, text="Exit (Q)", command=self.root.quit).grid(row=2, column=7, padx=5)
        
        # --- KEY BINDINGS ---
        self.root.bind("<a>", lambda e: self.prev_image())
        self.root.bind("<A>", lambda e: self.prev_image())
        self.root.bind("<d>", lambda e: self.next_image())
        self.root.bind("<D>", lambda e: self.next_image())
        self.root.bind("<s>", lambda e: self.save_current())
        self.root.bind("<S>", lambda e: self.save_current())
        self.root.bind("<n>", lambda e: self.save_as_null())
        self.root.bind("<N>", lambda e: self.save_as_null())
        self.root.bind("<o>", lambda e: self.skip_current())
        self.root.bind("<space>", lambda e: self.skip_current())
        self.root.bind("<t>", lambda e: self.toggle_drawing_mode())
        self.root.bind("<T>", lambda e: self.toggle_drawing_mode())
        self.root.bind("<u>", lambda e: self.undo_last_action())
        self.root.bind("<Return>", lambda e: self.confirm_manual_bbox() if self.drawing_mode and self.manual_bboxes else None)
        self.root.bind("<Escape>", lambda e: self.root.quit())
        self.root.bind("<BackSpace>", lambda e: self.undo_last_bbox(None))
        
        # Sneltoetsen 0-9 voor classes
        for i in range(10):
            self.root.bind(str(i), lambda event, idx=i: self.set_active_class(idx))
    
    def set_active_class(self, index):
        """Wisselt de actieve class in de dropdown op basis van index (sneltoets)"""
        if index < len(self.classes):
            self.class_combo.current(index)
            cls_name = self.classes[index]
            self.status_label.config(text=f"Switched active class to: {index} ({cls_name})")
        else:
            self.status_label.config(text=f"Class index {index} does not exist!")

    def update_class_selector(self):
        self.class_combo['values'] = [f"{i}: {name}" for i, name in enumerate(self.classes)]
        if self.classes:
            current = self.class_combo.current()
            if current == -1 or current >= len(self.classes):
                self.class_combo.current(0)
    
    def toggle_delete_mode(self):
        self.delete_mode_enabled = self.delete_mode_var.get()
        status = "Delete mode enabled" if self.delete_mode_enabled else "Delete mode disabled"
        self.status_label.config(text=status)
    
    def store_action_for_undo(self, action_type, img_filename, was_moved_to_delete=False):
        self.last_action = {
            'type': action_type,
            'filename': img_filename,
            'was_moved_to_delete': was_moved_to_delete,
            'current_index': self.current_index
        }
        self.undo_button.config(state='normal')
    
    def undo_last_action(self):
        if not self.last_action: return
        
        action = self.last_action
        img_filename = action['filename']
        base_name = os.path.splitext(img_filename)[0]
        
        try:
            if action['type'] in ['save', 'null', 'manual']:
                annotated_img_path = os.path.join(self.output_img_folder, img_filename)
                if os.path.exists(annotated_img_path): os.remove(annotated_img_path)
                
                label_path = os.path.join(self.output_label_folder, f"{base_name}.txt")
                if os.path.exists(label_path): os.remove(label_path)
            
            if action['was_moved_to_delete']:
                delete_path = os.path.join(self.delete_folder, img_filename)
                input_path = os.path.join(self.input_folder, img_filename)
                if os.path.exists(delete_path):
                    shutil.move(delete_path, input_path)
                    if img_filename not in self.image_files:
                        self.image_files.insert(action['current_index'], img_filename)
            
            self.status_label.config(text=f"Undid action for: {img_filename}")
            self.last_action = None
            self.undo_button.config(state='disabled')
            self.load_current_image()
            
        except Exception as e:
            self.status_label.config(text=f"Error during undo: {str(e)}")
    
    def move_to_delete_if_enabled(self, img_filename):
        if not self.delete_mode_enabled: return
        try:
            shutil.move(os.path.join(self.input_folder, img_filename), 
                       os.path.join(self.delete_folder, img_filename))
        except Exception as e:
            print(f"Error moving to delete: {e}")

    def load_current_image(self):
        if not self.image_files:
            self.status_label.config(text="No images found!")
            return
        
        # Reset drawing variables
        self.drawing_mode = False
        self.manual_bboxes = []
        self.current_rectangle = None
        
        status_text = f"Image {self.current_index + 1} of {len(self.image_files)}: {self.image_files[self.current_index]}"
        if self.delete_mode_enabled: status_text += " | Delete Mode: ON"
        self.status_label.config(text=status_text)
        
        img_path = os.path.join(self.input_folder, self.image_files[self.current_index])
        original_img = cv2.imread(img_path)
        original_img = cv2.cvtColor(original_img, cv2.COLOR_BGR2RGB)
        
        prediction_img = original_img.copy()
        
        try:
            if self.model_type == "ultralytics":
                results = self.model(img_path, conf=0.3)
            else:
                self.model.conf = 0.3
                results = self.model(img_path)
        except Exception as e:
            print(f"Error prediction: {e}")
            results = None
        
        self.current_results = results
        self.current_img_path = img_path
        self.current_img = original_img
        
        self.draw_predictions(prediction_img, results)
        self.display_image(original_img, self.original_canvas)
        self.display_image(prediction_img, self.prediction_canvas)
    
    def draw_predictions(self, img, results):
        if results is None: return
        try:
            if self.model_type == "ultralytics":
                if len(results) > 0:
                    for r in results:
                        for box in r.boxes:
                            x1, y1, x2, y2 = map(int, box.xyxy[0].cpu().numpy())
                            conf = float(box.conf[0].cpu().numpy())
                            cls_id = int(box.cls[0].item())
                            
                            # KLEUR OPHALEN VOOR PREDICTIONS (BGR)
                            _, color_bgr = self.get_color(cls_id)
                            
                            cls_name = self.classes[cls_id] if cls_id < len(self.classes) else str(cls_id)
                            cv2.rectangle(img, (x1, y1), (x2, y2), color_bgr, 2)
                            cv2.putText(img, f"{cls_name}: {conf:.2f}", (x1, y1-10), 
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_bgr, 2)
            else:
                for pred in results.xyxy[0].cpu().numpy():
                    x1, y1, x2, y2, conf, cls = pred
                    cls_id = int(cls)
                    
                    # KLEUR OPHALEN (BGR)
                    _, color_bgr = self.get_color(cls_id)
                    
                    cls_name = self.classes[cls_id] if cls_id < len(self.classes) else str(cls_id)
                    cv2.rectangle(img, (int(x1), int(y1)), (int(x2), int(y2)), color_bgr, 2)
                    cv2.putText(img, f"{cls_name}: {conf:.2f}", (int(x1), int(y1)-10), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, color_bgr, 2)
        except Exception: pass
    
    def display_image(self, cv_img, canvas):
        canvas_width = canvas.winfo_width() or 500
        canvas_height = canvas.winfo_height() or 500
        height, width = cv_img.shape[:2]
        scale = min(canvas_width / width, canvas_height / height) * 0.9
        
        new_width = int(width * scale)
        new_height = int(height * scale)
        
        if scale != 1.0: cv_img = cv2.resize(cv_img, (new_width, new_height))
        
        pil_img = Image.fromarray(cv_img)
        tk_img = ImageTk.PhotoImage(pil_img)
        
        canvas.delete("all")
        x_offset = (canvas_width - new_width) // 2
        y_offset = (canvas_height - new_height) // 2
        
        canvas.create_image(x_offset, y_offset, anchor=tk.NW, image=tk_img)
        canvas.image = tk_img
        
        self.current_image_info = {
            'width': width, 'height': height,
            'display_width': new_width, 'display_height': new_height,
            'x_offset': x_offset, 'y_offset': y_offset, 'scale': scale
        }

    def next_image(self):
        if self.current_index < len(self.image_files) - 1:
            self.current_index += 1
            self.load_current_image()
    
    def prev_image(self):
        if self.current_index > 0:
            self.current_index -= 1
            self.load_current_image()
            
    def skip_current(self):
        img_filename = self.image_files[self.current_index]
        was_moved = self.delete_mode_enabled
        self.store_action_for_undo('skip', img_filename, was_moved)
        self.move_to_delete_if_enabled(img_filename)
        self.status_label.config(text=f"Image skipped: {img_filename}")
        self.next_image()
    
    def save_current(self):
        if not self.image_files: return
            
        # If manual boxes exist, use manual save logic
        if self.drawing_mode and self.manual_bboxes:
            self.save_with_manual_bbox()
            return
        
        # Automatic save logic
        img_filename = self.image_files[self.current_index]
        base_name = os.path.splitext(img_filename)[0]
        
        img_dest = os.path.join(self.output_img_folder, img_filename)
        try: shutil.copy2(self.current_img_path, img_dest)
        except: return
        
        label_path = os.path.join(self.output_label_folder, f"{base_name}.txt")
        try:
            self.write_label_file(label_path)
            was_moved = self.delete_mode_enabled
            self.store_action_for_undo('save', img_filename, was_moved)
            self.move_to_delete_if_enabled(img_filename)
            self.status_label.config(text=f"Image saved: {img_filename}")
            self.next_image()
        except Exception as e:
            self.status_label.config(text=f"Error: {str(e)}")
    
    def save_as_null(self):
        if not self.image_files: return
        img_filename = self.image_files[self.current_index]
        base_name = os.path.splitext(img_filename)[0]
        
        img_dest = os.path.join(self.output_img_folder, img_filename)
        try: shutil.copy2(self.current_img_path, img_dest)
        except: return
        
        label_path = os.path.join(self.output_label_folder, f"{base_name}.txt")
        open(label_path, 'w').close()
        
        was_moved = self.delete_mode_enabled
        self.store_action_for_undo('null', img_filename, was_moved)
        self.move_to_delete_if_enabled(img_filename)
        self.status_label.config(text=f"Image saved as NULL: {img_filename}")
        self.next_image()
    
    def write_label_file(self, label_path):
        img = cv2.imread(self.current_img_path)
        height, width = img.shape[:2]
        lines_to_write = []
        
        if self.model_type == "ultralytics":
            if len(self.current_results) > 0:
                for box in self.current_results[0].boxes:
                    xyxy = box.xyxy[0].cpu().numpy()
                    x1, y1, x2, y2 = xyxy
                    cls_id = int(box.cls[0].item())
                    x_center = ((x1 + x2) / 2) / width
                    y_center = ((y1 + y2) / 2) / height
                    w = (x2 - x1) / width
                    h = (y2 - y1) / height
                    lines_to_write.append(f"{cls_id} {x_center} {y_center} {w} {h}")
        else:
            detections = self.current_results.xyxy[0].cpu().numpy()
            for detection in detections:
                x1, y1, x2, y2, conf, cls = detection
                cls_id = int(cls)
                x_center = ((x1 + x2) / 2) / width
                y_center = ((y1 + y2) / 2) / height
                w = (x2 - x1) / width
                h = (y2 - y1) / height
                lines_to_write.append(f"{cls_id} {x_center} {y_center} {w} {h}")
        
        if lines_to_write:
            with open(label_path, 'w') as f:
                f.write('\n'.join(lines_to_write))
        else:
            open(label_path, 'w').close()
            
    # --- Multi-Box Drawing Logic ---
    def toggle_drawing_mode(self):
        if self.drawing_mode and self.manual_bboxes:
            response = messagebox.askyesnocancel(
                "Confirm Drawing", 
                "Save drawn boxes and continue?\nYes = Save\nNo = Clear & Redraw\nCancel = Exit draw mode"
            )
            if response is True:
                self.save_with_manual_bbox()
                return
            elif response is False:
                # Clear all boxes
                self.manual_bboxes = []
                self.display_image(self.current_img, self.original_canvas)
                self.status_label.config(text="Canvas cleared. Draw new boxes.")
                return
            else:
                self.drawing_mode = False
                self.load_current_image()
                return
                
        self.drawing_mode = not self.drawing_mode
        
        if self.drawing_mode:
            # Clear canvas, ready to draw
            self.manual_bboxes = []
            self.display_image(self.current_img, self.original_canvas)
            self.status_label.config(text="Draw Mode: 0-9 to switch class. Click & drag to draw. Right-click undo. Enter save.")
        else:
            self.load_current_image()
            self.status_label.config(text="Drawing mode disabled")
    
    def confirm_manual_bbox(self):
        if not self.drawing_mode or not self.manual_bboxes: return
        if messagebox.askyesno("Confirm", f"Save {len(self.manual_bboxes)} boxes and next?"):
            self.save_with_manual_bbox()
    
    def on_mouse_down(self, event):
        if not self.drawing_mode: return
        self.start_x = event.x
        self.start_y = event.y
        
        # Get active class for color
        idx = self.class_combo.current()
        cls_id = idx if idx != -1 else 0
        color_hex, _ = self.get_color(cls_id)
        
        # Create a new rectangle with class specific color
        self.current_rectangle = self.original_canvas.create_rectangle(
            self.start_x, self.start_y, self.start_x, self.start_y,
            outline=color_hex, width=2
        )
    
    def on_mouse_drag(self, event):
        if not self.drawing_mode or not self.current_rectangle: return
        self.original_canvas.coords(self.current_rectangle, self.start_x, self.start_y, event.x, event.y)
    
    def on_mouse_up(self, event):
        if not self.drawing_mode or not self.current_rectangle: return
        
        end_x, end_y = event.x, event.y
        x1 = min(self.start_x, end_x)
        y1 = min(self.start_y, end_y)
        x2 = max(self.start_x, end_x)
        y2 = max(self.start_y, end_y)
        
        # Update visual rectangle
        self.original_canvas.coords(self.current_rectangle, x1, y1, x2, y2)
        
        # Calculate image coordinates
        info = self.current_image_info
        x1_img = (x1 - info['x_offset']) / info['scale']
        y1_img = (y1 - info['y_offset']) / info['scale']
        x2_img = (x2 - info['x_offset']) / info['scale']
        y2_img = (y2 - info['y_offset']) / info['scale']
        
        # Constraint
        x1_img = max(0, min(x1_img, info['width']))
        y1_img = max(0, min(y1_img, info['height']))
        x2_img = max(0, min(x2_img, info['width']))
        y2_img = max(0, min(y2_img, info['height']))
        
        # Ignore tiny clicks
        if abs(x2_img - x1_img) < 2 or abs(y2_img - y1_img) < 2:
            self.original_canvas.delete(self.current_rectangle)
            self.current_rectangle = None
            return

        # Get active class and color
        idx = self.class_combo.current()
        class_id = idx if idx != -1 else 0
        cls_name = self.classes[class_id] if class_id < len(self.classes) else str(class_id)
        color_hex, _ = self.get_color(class_id)
        
        # Add Label Text to canvas for visual feedback
        text_id = self.original_canvas.create_text(x1, y1-10, text=cls_name, fill=color_hex, anchor="sw")

        # Save to list
        self.manual_bboxes.append({
            'coords': (x1_img, y1_img, x2_img, y2_img),
            'class_id': class_id,
            'rect_id': self.current_rectangle,
            'text_id': text_id
        })
        
        self.status_label.config(text=f"Added box {len(self.manual_bboxes)}: {cls_name}. (Right-click to remove last)")
        self.current_rectangle = None # Reset for next box

    def undo_last_bbox(self, event):
        """Removes the last manually drawn box"""
        if not self.drawing_mode or not self.manual_bboxes: return
        
        last_box = self.manual_bboxes.pop()
        self.original_canvas.delete(last_box['rect_id'])
        self.original_canvas.delete(last_box['text_id'])
        self.status_label.config(text=f"Removed last box. Total: {len(self.manual_bboxes)}")

    def save_with_manual_bbox(self):
        if not self.manual_bboxes:
            self.status_label.config(text="Draw at least one box first!")
            return
            
        img_filename = self.image_files[self.current_index]
        base_name = os.path.splitext(img_filename)[0]
        
        img_dest = os.path.join(self.output_img_folder, img_filename)
        try: shutil.copy2(self.current_img_path, img_dest)
        except Exception as e: return
        
        label_path = os.path.join(self.output_label_folder, f"{base_name}.txt")
        height, width = self.current_img.shape[:2]
        
        lines = []
        # Loop door ALLE getekende boxes
        for box in self.manual_bboxes:
            x1, y1, x2, y2 = box['coords']
            class_id = box['class_id']
            
            x_center = ((x1 + x2) / 2) / width
            y_center = ((y1 + y2) / 2) / height
            w = (x2 - x1) / width
            h = (y2 - y1) / height
            
            lines.append(f"{class_id} {x_center} {y_center} {w} {h}")
        
        with open(label_path, 'w') as f:
            f.write('\n'.join(lines))
        
        was_moved = self.delete_mode_enabled
        self.store_action_for_undo('manual', img_filename, was_moved)
        self.move_to_delete_if_enabled(img_filename)
        
        self.status_label.config(text=f"Saved {len(lines)} manual boxes: {img_filename}")
        self.drawing_mode = False
        self.manual_bboxes = []
        self.next_image()

def main():
    root = tk.Tk()
    app = YoloAnnotationApp(root, model_path, input_folder, output_img_folder, output_label_folder, delete_folder, enable_delete_mode)
    root.mainloop()

if __name__ == "__main__":
    main()
