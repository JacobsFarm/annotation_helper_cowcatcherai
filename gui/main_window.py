import customtkinter as ctk
from gui.annotate_tab import AnnotateTab
from gui.control_tab import ControlTab
from gui.settings_tab import SettingsTab

class MainWindow:
    def __init__(self, root, config):
        self.root = root
        self.config = config
        
        # Grid layout van root instellen
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        # --- TABBLADEN ---
        # Gebruik CTkTabview i.p.v. ttk.Notebook
        self.tab_view = ctk.CTkTabview(self.root)
        self.tab_view.pack(fill="both", expand=True, padx=10, pady=10)

        # Tabs aanmaken
        self.tab_view.add("Annoteren (F1)")
        self.tab_view.add("Controleren (F2)")
        self.tab_view.add("Instellingen (F3)")

        # --- INHOUD KOPPELEN ---
        # Let op: tab_view.tab("Naam") geeft het frame terug waar we in bouwen
        
        self.tab_annotate = AnnotateTab(self.tab_view.tab("Annoteren (F1)"), self.config)
        self.tab_annotate.pack(fill="both", expand=True)

        self.tab_control = ControlTab(self.tab_view.tab("Controleren (F2)"), self.config)
        self.tab_control.pack(fill="both", expand=True)
        
        # (Settings doen we later)
        self.tab_settings = SettingsTab(self.tab_view.tab("Instellingen (F3)"), self.config)
        self.tab_settings.pack(fill="both", expand=True)

        # Sneltoetsen
        self.bind_shortcuts()

    def bind_shortcuts(self):
        self.root.bind('<F1>', lambda e: self.tab_view.set("Annoteren (F1)"))
        self.root.bind('<F2>', lambda e: self.tab_view.set("Controleren (F2)"))
        self.root.bind('<F3>', lambda e: self.tab_view.set("Instellingen (F3)"))
        self.root.bind('<Escape>', lambda e: self.root.quit())