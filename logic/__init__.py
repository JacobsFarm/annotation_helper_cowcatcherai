def __init__(self, config):
        self.config = config
        self.model_detect = None
        self.model_seg = None
        
        # Laad modellen dynamisch uit config
        path_detect = self.config.get('model_path_detect', 'cowcatcherV15.pt')
        path_seg = self.config.get('model_path_seg', 'yolo11x-seg.pt')
        
        try:
            from ultralytics import YOLO
            
            if os.path.exists(path_detect):
                self.model_detect = YOLO(path_detect)
                print(f"Detectie model geladen: {path_detect}")
            else:
                print(f"Let op: Detectie model niet gevonden op {path_detect}")

            if os.path.exists(path_seg):
                self.model_seg = YOLO(path_seg)
                print(f"Segmentatie model geladen: {path_seg}")
            else:
                print(f"Let op: Segmentatie model niet gevonden op {path_seg}")
                
        except Exception as e:
            print(f"Error loading models: {e}")