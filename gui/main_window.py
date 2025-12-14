import customtkinter as ctk
# Importeer de nieuwe tabbladen (hernoem de oude annotate_tab in je hoofd naar annotate_box_tab voor duidelijkheid, 
# maar hier gebruiken we annotate_tab als de 'Box' tab).
from gui.annotate_tab import AnnotateTab 
from gui.annotate_seg_tab import AnnotateSegTab # <--- NIEUW
from gui.control_tab import ControlTab
from gui.settings_tab import SettingsTab

class MainWindow:
    def __init__(self, root, config):
        self.root = root
        self.config = config
        
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        # --- TABBLADEN ---
        self.tab_view = ctk.CTkTabview(self.root)
        self.tab_view.pack(fill="both", expand=True, padx=10, pady=10)

        # 4 Tabs aanmaken
        self.tab_view.add("Box Annotatie (F1)")
        self.tab_view.add("Seg Annotatie (F2)") # <--- NIEUW
        self.tab_view.add("Controleren (F3)")
        self.tab_view.add("Instellingen (F4)")

        # --- INHOUD KOPPELEN ---
        
        # 1. Box Tab (De originele annotate_tab, kun je later strippen van polygon logica)
        self.tab_box = AnnotateTab(self.tab_view.tab("Box Annotatie (F1)"), self.config)
        self.tab_box.pack(fill="both", expand=True)

        # 2. Seg Tab (De nieuwe file)
        self.tab_seg = AnnotateSegTab(self.tab_view.tab("Seg Annotatie (F2)"), self.config)
        self.tab_seg.pack(fill="both", expand=True)

        # 3. Control Tab
        callbacks = {} # (niet meer nodig in jouw nieuwe control tab logica, maar voor compatibiliteit leeg meegeven)
        self.tab_control = ControlTab(self.tab_view.tab("Controleren (F3)"), self.config, callbacks)
        self.tab_control.pack(fill="both", expand=True)
        
        # 4. Settings Tab
        self.tab_settings = SettingsTab(self.tab_view.tab("Instellingen (F4)"), self.config)
        self.tab_settings.pack(fill="both", expand=True)

        # Sneltoetsen binden
        self.bind_shortcuts()

    def bind_shortcuts(self):
        self.root.bind('<F1>', lambda e: self.tab_view.set("Box Annotatie (F1)"))
        self.root.bind('<F2>', lambda e: self.tab_view.set("Seg Annotatie (F2)"))
        self.root.bind('<F3>', lambda e: self.tab_view.set("Controleren (F3)"))
        self.root.bind('<F4>', lambda e: self.tab_view.set("Instellingen (F4)"))
        self.root.bind('<Escape>', lambda e: self.root.quit())