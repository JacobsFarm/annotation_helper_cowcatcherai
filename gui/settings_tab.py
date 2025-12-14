import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, colorchooser, messagebox
import json
import os

class SettingsTab(ctk.CTkFrame):
    def __init__(self, parent, config):
        super().__init__(parent)
        self.config = config
        self.entries = {}      # Voor paden
        self.key_entries = {}  # Voor sneltoetsen (NIEUW)
        self.class_widgets = [] 
        
        # Hoofd container (Scrollbaar)
        self.scroll = ctk.CTkScrollableFrame(self, label_text="Configuratie")
        self.scroll.pack(fill="both", expand=True, padx=10, pady=10)
        
        self.setup_ui()
        
    def setup_ui(self):
        # --- SECTIE 1: MAPPEN ---
        self.add_section_header("📁 Mappen Structuur")
        self.add_path_selector("Input Map (Afbeeldingen):", "input_folder")
        self.add_path_selector("Output Map (Annotated Images):", "output_img_folder")
        self.add_path_selector("Output Map (Labels):", "output_label_folder")
        self.add_path_selector("Delete Map (Prullenbak):", "delete_folder")
        
        # --- SECTIE 2: AI MODELLEN ---
        self.add_section_header("🤖 AI Modellen")
        self.add_path_selector("Detectie Model (Box):", "model_path_detect", is_file=True)
        self.add_path_selector("Segmentatie Model (Mask):", "model_path_seg", is_file=True)
        
        # --- SECTIE 3: SNELTOETSEN (NIEUW) ---
        self.add_section_header("⌨️ Sneltoetsen")
        
        # Zorg dat de keys dictionary bestaat
        if 'keys' not in self.config:
            self.config['keys'] = {
                "save_next": "s", "skip": "space", "delete": "Delete", 
                "undo": "z", "reset_view": "r", "prev": "a", "reject": "e"
            }
            
        # Maak invulvelden (Label | Entry)
        self.add_key_entry("Opslaan / Goedkeuren:", "save_next")
        self.add_key_entry("Overslaan (Skip):", "skip")
        self.add_key_entry("Vorige Afbeelding:", "prev")
        self.add_key_entry("Verwijderen (Delete):", "delete")
        self.add_key_entry("Afkeuren (Control):", "reject")
        self.add_key_entry("Ongedaan maken (Undo):", "undo")
        self.add_key_entry("Reset View (Zoom):", "reset_view")
        
        ctk.CTkLabel(self.scroll, text="(Herstart vereist na wijzigen toetsen)", text_color="gray", font=("Arial", 10)).pack(pady=2)

        # --- SECTIE 4: KLASSEN EDITOR ---
        self.add_section_header("🏷️ Klassen & Kleuren")
        
        self.classes_frame = ctk.CTkFrame(self.scroll, fg_color="transparent")
        self.classes_frame.pack(fill="x", padx=5, pady=5)
        self.refresh_classes_ui()
        
        ctk.CTkButton(self.scroll, text="+ Nieuwe Klasse", command=self.add_class, fg_color="gray").pack(pady=10)

        # --- FOOTER ---
        ctk.CTkFrame(self.scroll, height=2, fg_color="gray").pack(fill="x", pady=20)
        btn_save = ctk.CTkButton(self.scroll, text="💾 Instellingen Opslaan", command=self.save_settings, height=40, font=("Arial", 14, "bold"))
        btn_save.pack(fill="x", padx=20, pady=(0, 20))

    # --- HELPER FUNCTIES ---

    def add_section_header(self, text):
        font = ctk.CTkFont(family="Arial", size=16, weight="bold")
        ctk.CTkLabel(self.scroll, text=text, font=font, anchor="w").pack(fill="x", pady=(20, 5), padx=5)

    def add_path_selector(self, label_text, config_key, is_file=False):
        frame = ctk.CTkFrame(self.scroll, fg_color="transparent")
        frame.pack(fill="x", pady=2)
        ctk.CTkLabel(frame, text=label_text, width=200, anchor="w").pack(side="left", padx=5)
        
        entry = ctk.CTkEntry(frame)
        entry.insert(0, self.config.get(config_key, ""))
        entry.pack(side="left", fill="x", expand=True, padx=5)
        self.entries[config_key] = entry
        
        cmd = lambda: self.browse_path(entry, is_file)
        ctk.CTkButton(frame, text="...", width=40, command=cmd).pack(side="right", padx=5)

    def add_key_entry(self, label_text, key_key):
        """Voegt een rij toe voor een sneltoets"""
        frame = ctk.CTkFrame(self.scroll, fg_color="transparent")
        frame.pack(fill="x", pady=2)
        
        ctk.CTkLabel(frame, text=label_text, width=200, anchor="w").pack(side="left", padx=5)
        
        current_val = self.config['keys'].get(key_key, "")
        entry = ctk.CTkEntry(frame, width=100)
        entry.insert(0, current_val)
        entry.pack(side="left", padx=5)
        
        self.key_entries[key_key] = entry

    def browse_path(self, entry_widget, is_file):
        if is_file:
            path = filedialog.askopenfilename(filetypes=[("Model Files", "*.pt *.engine *.onnx")])
        else:
            path = filedialog.askdirectory()
        if path:
            entry_widget.delete(0, "end")
            entry_widget.insert(0, path)

    # --- KLASSEN LOGICA ---
    def refresh_classes_ui(self):
        for widget in self.classes_frame.winfo_children(): widget.destroy()
        self.class_widgets = []
            
        header = ctk.CTkFrame(self.classes_frame, fg_color="transparent")
        header.pack(fill="x")
        ctk.CTkLabel(header, text="ID", width=30).pack(side="left")
        ctk.CTkLabel(header, text="Naam", width=150).pack(side="left", padx=5)
        ctk.CTkLabel(header, text="Kleur", width=50).pack(side="left", padx=5)
        
        for i, cls in enumerate(self.config['classes']):
            row = ctk.CTkFrame(self.classes_frame)
            row.pack(fill="x", pady=2)
            
            ctk.CTkLabel(row, text=str(cls['id']), width=30).pack(side="left")
            ent_name = ctk.CTkEntry(row, width=150)
            ent_name.insert(0, cls['name'])
            ent_name.pack(side="left", padx=5, fill="x", expand=True)
            
            btn_color = ctk.CTkButton(row, text="", width=40, fg_color=cls['color'])
            btn_color.configure(command=lambda b=btn_color: self.pick_color(b))
            btn_color.pack(side="left", padx=5)
            
            btn_del = ctk.CTkButton(row, text="X", width=30, fg_color="#AA0000", hover_color="#FF0000")
            btn_del.configure(command=lambda idx=i: self.remove_class(idx))
            btn_del.pack(side="right", padx=5)
            
            self.class_widgets.append({"id": cls['id'], "entry_name": ent_name, "btn_color": btn_color})

    def pick_color(self, btn_widget):
        color = colorchooser.askcolor(title="Kies kleur")[1]
        if color: btn_widget.configure(fg_color=color)

    def add_class(self):
        new_id = 0
        if self.config['classes']: new_id = max(c['id'] for c in self.config['classes']) + 1
        self.config['classes'].append({"id": new_id, "name": "nieuw", "color": "#888888"})
        self.refresh_classes_ui()

    def remove_class(self, index):
        if 0 <= index < len(self.config['classes']):
            self.config['classes'].pop(index)
            self.refresh_classes_ui()

    # --- OPSLAAN ---
    def save_settings(self):
        # 1. Paden opslaan
        for key, entry in self.entries.items():
            self.config[key] = entry.get()
            
        # 2. Sneltoetsen opslaan (NIEUW)
        if 'keys' not in self.config: self.config['keys'] = {}
        for key_key, entry in self.key_entries.items():
            val = entry.get().strip()
            if val: # Alleen opslaan als niet leeg
                self.config['keys'][key_key] = val

        # 3. Klassen opslaan
        new_classes = []
        for widget in self.class_widgets:
            new_classes.append({
                "id": widget['id'],
                "name": widget['entry_name'].get(),
                "color": widget['btn_color'].cget("fg_color")
            })
        self.config['classes'] = new_classes
        
        # 4. Wegschrijven
        try:
            settings_to_save = {k: v for k, v in self.config.items() if k != 'classes'}
            with open('config/settings.json', 'w') as f: json.dump(settings_to_save, f, indent=4)
            with open('config/classes.json', 'w') as f: json.dump(self.config['classes'], f, indent=4)
            messagebox.showinfo("Succes", "Instellingen opgeslagen!\nHerstart de applicatie om wijzigingen toe te passen.")
        except Exception as e:
            messagebox.showerror("Fout", f"Kon niet opslaan: {e}")