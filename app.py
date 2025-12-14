import customtkinter as ctk
from tkinter import messagebox
import json
import sys
import os
from gui.main_window import MainWindow

# Configuratie laden (blijft hetzelfde)
def load_config():
    try:
        with open('config/settings.json', 'r') as f:
            settings = json.load(f)
        with open('config/classes.json', 'r') as f:
            classes = json.load(f)
        return settings, classes
    except FileNotFoundError:
        messagebox.showerror("Error", "Configuratiebestanden niet gevonden!")
        sys.exit()

def main():
    # 1. CustomTkinter Setup
    ctk.set_appearance_mode("Light")  # Forceer Light mode (of "System")
    ctk.set_default_color_theme("blue")  # Thema kleur voor knoppen/schuifbalken

    # 2. Setup Root Window (Gebruik CTk i.p.v. tk.Tk)
    root = ctk.CTk()
    root.title("CowCatcher Annotation Suite v2.0")
    root.geometry("1400x900")
    
    # 3. Config Laden
    settings, classes = load_config()
    settings['classes'] = classes
    
    # 4. Start Hoofdvenster
    app = MainWindow(root, settings)
    
    # 5. Start Loop
    root.mainloop()

if __name__ == "__main__":
    main()
