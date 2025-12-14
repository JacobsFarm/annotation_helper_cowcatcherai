import customtkinter as ctk
import tkinter as tk
import cv2
from PIL import Image, ImageTk
import os
import shutil
import numpy as np

class ControlTab(ctk.CTkFrame):
    def __init__(self, parent, settings, callbacks=None):
        """
        :param parent: Het ouder-frame of venster.
        :param settings: De dictionary met instellingen (config).
        :param callbacks: (Optioneel) Wordt geaccepteerd voor compatibiliteit met main_window, 
                          maar we gebruiken nu de interne logica.
        """
        super().__init__(parent)
        self.settings = settings
        # We hoeven self.callbacks niet op te slaan, want we gebruiken interne functies (next_img etc.)
        
        # Variabelen voor logica
        self.image_files = []
        self.current_index = 0
        self.tk_img = None 

        # Koppel de boolean aan de setting
        self.edit_mode_var = ctk.BooleanVar(value=self.settings.get("delete_mode", False))

        # UI Opbouwen
        self._setup_ui()
        
        # Sneltoetsen instellen
        self._setup_shortcuts()
        
        # Starten
        self._update_button_states()
        self.after(200, self.refresh)

    def _setup_ui(self):
        # --- 1. Titel ---
        self.lbl_title = ctk.CTkLabel(self, text="Controle Paneel", font=("Arial", 20, "bold"))
        self.lbl_title.pack(pady=(10, 5))

        # --- 2. HET BEELD (Canvas) ---
        # Dit zat niet in je nieuwe UI, maar is essentieel voor annotatie controle
        self.frame_view = ctk.CTkFrame(self, fg_color="#2b2b2b")
        self.frame_view.pack(fill="both", expand=True, padx=10, pady=5)
        
        self.canvas = tk.Canvas(self.frame_view, bg="#2b2b2b", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        # Zorg dat canvas focus pakt bij hover (voor sneltoetsen)
        self.canvas.bind("<Enter>", lambda e: self.canvas.focus_set())

        # --- 3. VEILIGHEIDSSCHAKELAAR ---
        self.switch_edit_mode = ctk.CTkSwitch(
            self, 
            text="Bewerkmodus (Verwijderen/Afkeuren)", 
            variable=self.edit_mode_var,
            command=self._on_mode_toggle,
            font=("Arial", 14),
            progress_color="green"
        )
        self.switch_edit_mode.pack(pady=5, anchor="center")

        ctk.CTkLabel(self, text="-------------------------").pack(pady=2)

        # --- 4. Navigatie (Werkt altijd) ---
        self.frame_nav = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_nav.pack(fill="x", pady=2, padx=10)

        keys_cfg = self.settings.get('keys_control', {})
        key_prev = keys_cfg.get('prev', 'A').upper()
        key_next = keys_cfg.get('save_next', 'S').upper()

        self.btn_prev = ctk.CTkButton(
            self.frame_nav, 
            text=f"Vorige ({key_prev})", 
            command=self.prev_img,
            width=120,
            fg_color="gray"
        )
        self.btn_prev.pack(side="left", padx=5, expand=True)

        self.btn_next = ctk.CTkButton(
            self.frame_nav, 
            text=f"Volgende ({key_next})", 
            command=self.next_img,
            width=120
        )
        self.btn_next.pack(side="right", padx=5, expand=True)

        # --- 5. Acties (Worden uitgeschakeld door switch) ---
        self.lbl_actions = ctk.CTkLabel(self, text="Acties", font=("Arial", 16, "bold"))
        self.lbl_actions.pack(pady=2)

        key_rej = keys_cfg.get('reject', 'E').upper()
        key_del = keys_cfg.get('delete', 'T').upper()

        # Approve Button (Is eigenlijk hetzelfde als volgende in jouw logica, maar expliciet groen)
        self.btn_approve = ctk.CTkButton(
            self, 
            text=f"Goedkeuren & Volgende ({key_next})", 
            command=self.next_img,
            fg_color="green", 
            hover_color="darkgreen"
        )
        self.btn_approve.pack(fill="x", padx=20, pady=2)

        # Reject Button (Terug naar input folder)
        self.btn_reject = ctk.CTkButton(
            self, 
            text=f"Afkeuren ({key_rej})", 
            command=self.reject_img,
            fg_color="#d69e2e", # Oranje
            hover_color="#b7791f"
        )
        self.btn_reject.pack(fill="x", padx=20, pady=2)

        # Delete Button (Definitief verwijderen - optioneel toegevoegd op basis van je UI)
        self.btn_delete = ctk.CTkButton(
            self, 
            text=f"Verwijderen ({key_del})", 
            command=self.delete_img, # Nieuwe functie voor 'Echt' verwijderen
            fg_color="red", 
            hover_color="darkred"
        )
        self.btn_delete.pack(fill="x", padx=20, pady=(2, 10))

        # --- 6. Folder Info ---
        self.frame_info = ctk.CTkFrame(self)
        self.frame_info.pack(fill="x", padx=10, pady=5, side="bottom")
        
        folder_name = os.path.basename(self.settings.get('output_img_folder', 'Onbekend'))
        self.lbl_path = ctk.CTkLabel(self.frame_info, text=f"Map: {folder_name}", text_color="gray")
        self.lbl_path.pack(anchor="center", padx=5, pady=2)

    # ================= UI LOGICA =================

    def _on_mode_toggle(self):
        """Wordt aangeroepen als de switch verandert."""
        self.settings['delete_mode'] = self.edit_mode_var.get()
        self._update_button_states()

    def _update_button_states(self):
        """Zet knoppen op normal of disabled gebaseerd op de switch."""
        if self.edit_mode_var.get():
            state = "normal"
            self.lbl_actions.configure(text="Acties (ACTIEF)", text_color="green")
        else:
            state = "disabled"
            self.lbl_actions.configure(text="Acties (Alleen lezen)", text_color="gray")

        # Goedkeuren mag altijd (is gewoon volgende), of wil je dat ook blokkeren? 
        # Meestal mag je wel gewoon bladeren.
        # self.btn_approve.configure(state=state) 
        
        self.btn_reject.configure(state=state)
        self.btn_delete.configure(state=state)

    def _setup_shortcuts(self):
        root = self.winfo_toplevel()
        keys = self.settings.get('keys_control', {
            "save_next": "s", "prev": "a", "reject": "e", 
            "delete": "t", "reset_view": "r"
        })

        def if_active(func):
            def wrapper(event=None):
                if self.winfo_viewable():
                    func()
            return wrapper

        # Binds
        for key_name, func in [
            ("save_next", self.next_img),
            ("prev", self.prev_img),
            ("reject", self.reject_img),
            ("delete", self.delete_img),
            ("reset_view", self.refresh)
        ]:
            k = keys.get(key_name)
            if k:
                root.bind(f"<{k.lower()}>", if_active(func))
                root.bind(f"<{k.upper()}>", if_active(func))

    # ================= BEELD LOGICA (Uit je oude code) =================

    def refresh(self):
        folder = self.settings.get('output_img_folder', '')
        if not os.path.exists(folder): 
            print(f"Map niet gevonden: {folder}")
            return
        
        self.image_files = [f for f in os.listdir(folder) if f.lower().endswith(('.jpg','.png', '.jpeg'))]
        self.current_index = 0
        self.load_image()

    def load_image(self):
        self.canvas.delete("all")
        
        # UI Update: titel aanpassen met index
        if self.image_files:
            self.lbl_title.configure(text=f"Controle ({self.current_index + 1}/{len(self.image_files)})")
        else:
            self.lbl_title.configure(text="Geen afbeeldingen")
            self.canvas.create_text(self.canvas.winfo_width()//2, self.canvas.winfo_height()//2, 
                                    text="Klaar! Geen beelden meer.", fill="white", font=("Arial", 16))
            return

        fname = self.image_files[self.current_index]
        img_path = os.path.join(self.settings['output_img_folder'], fname)
        base_name = os.path.splitext(fname)[0]
        lbl_path = os.path.join(self.settings['output_label_folder'], f"{base_name}.txt")
        
        # 1. Beeld inlezen met OpenCV
        img = cv2.imread(img_path)
        if img is None: return
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        h, w = img.shape[:2]
        
        # 2. Labels tekenen (YOLO formaat)
        if os.path.exists(lbl_path):
            with open(lbl_path, 'r') as f:
                for line in f.readlines():
                    try:
                        parts = list(map(float, line.strip().split()))
                        cls = int(parts[0])
                        coords = parts[1:]
                        
                        if len(coords) == 4: # Bounding Box
                            cx, cy, bw, bh = coords
                            x1 = int((cx - bw/2)*w)
                            y1 = int((cy - bh/2)*h)
                            x2 = int((cx + bw/2)*w)
                            y2 = int((cy + bh/2)*h)
                            cv2.rectangle(img, (x1, y1), (x2, y2), (0,255,0), 2)
                        elif len(coords) > 4: # Segmentatie/Polygoon
                            pts = []
                            for i in range(0, len(coords), 2):
                                pts.append([int(coords[i]*w), int(coords[i+1]*h)])
                            pts = np.array(pts, np.int32).reshape((-1,1,2))
                            cv2.polylines(img, [pts], True, (0,255,0), 2)
                    except Exception as e:
                        print(f"Fout bij lezen label: {e}")
        
        # 3. Schalen naar Canvas grootte
        cw = self.canvas.winfo_width() or 800
        ch = self.canvas.winfo_height() or 500 # Iets minder hoog ivm knoppen
        
        scale = min(cw/w, ch/h) * 0.95
        nw, nh = int(w*scale), int(h*scale)
        
        if nw <= 0 or nh <= 0: return # Voorkom crash bij minimaliseren
        
        img_res = cv2.resize(img, (nw, nh))
        
        # 4. Naar Tkinter converteren en tonen
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

    def reject_img(self):
        """Verplaatst bestand terug naar input map (Afkeuren)"""
        if not self.edit_mode_var.get(): return # Check switch
        if not self.image_files: return

        fname = self.image_files[self.current_index]
        base = os.path.splitext(fname)[0]
        
        src = os.path.join(self.settings['output_img_folder'], fname)
        dst = os.path.join(self.settings['input_folder'], fname)
        lbl = os.path.join(self.settings['output_label_folder'], f"{base}.txt")
        
        # Verplaatsen
        try:
            if os.path.exists(src): shutil.move(src, dst)
            if os.path.exists(lbl): os.remove(lbl)
            print(f"Afgekeurd: {fname} -> terug naar input.")
        except Exception as e:
            print(f"Fout bij afkeuren: {e}")

        self._remove_from_list_and_refresh()

    def delete_img(self):
        """Verwijdert bestand permanent"""
        if not self.edit_mode_var.get(): return # Check switch
        if not self.image_files: return
        
        fname = self.image_files[self.current_index]
        base = os.path.splitext(fname)[0]
        
        src = os.path.join(self.settings['output_img_folder'], fname)
        lbl = os.path.join(self.settings['output_label_folder'], f"{base}.txt")
        
        try:
            if os.path.exists(src): os.remove(src)
            if os.path.exists(lbl): os.remove(lbl)
            print(f"Verwijderd: {fname}")
        except Exception as e:
            print(f"Fout bij verwijderen: {e}")

        self._remove_from_list_and_refresh()

    def _remove_from_list_and_refresh(self):
        """Hulpmiddel om item uit de lijst te halen na actie"""
        self.image_files.pop(self.current_index)
        if self.current_index >= len(self.image_files):
            self.current_index = len(self.image_files) - 1
        
        # Als lijst leeg is, index op 0 (voorkomt -1)
        if self.current_index < 0: self.current_index = 0
            
        self.load_image()