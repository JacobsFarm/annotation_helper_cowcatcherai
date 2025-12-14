import cv2
import numpy as np
import os

class ModelHandler:
    def __init__(self, config):
        self.config = config
        self.model_detect = None
        self.model_seg = None
        
        # Paden ophalen uit config
        path_detect = self.config.get('model_path_detect', 'cowcatcherV15.pt')
        path_seg = self.config.get('model_path_seg', 'yolo11x-seg.pt')
        
        # Probeer modellen te laden
        try:
            from ultralytics import YOLO
            
            if os.path.exists(path_detect):
                self.model_detect = YOLO(path_detect)
                print(f"Detectie model geladen: {path_detect}")
            else:
                print(f"Let op: Detectie model bestand niet gevonden: {path_detect}")

            if os.path.exists(path_seg):
                self.model_seg = YOLO(path_seg)
                print(f"Segmentatie model geladen: {path_seg}")
            else:
                print(f"Let op: Segmentatie model bestand niet gevonden: {path_seg}")
                
        except ImportError:
            print("Ultralytics niet geïnstalleerd. Installeer met 'pip install ultralytics'")
        except Exception as e:
            print(f"Error loading models: {e}")

    def predict_standard(self, image_path, conf=0.25):
        """Standaard voorspelling (Single Model)"""
        if not self.model_detect:
            return []
        
        # Lezen en voorspellen
        img = cv2.imread(image_path)
        if img is None: return []
        
        results = self.model_detect(img, conf=conf)
        return self._process_results(results)

    def predict_advanced_dual(self, image_path, expand_ratio=0.2):
        """Advanced: Detectie -> Crop -> Segmentatie"""
        if not self.model_detect or not self.model_seg:
            return []

        img_cv = cv2.imread(image_path)
        if img_cv is None: return []
        
        h_orig, w_orig = img_cv.shape[:2]
        det_results = self.model_detect(img_cv, conf=0.25)
        final_annotations = []

        for r in det_results:
            boxes = r.boxes.cpu().numpy()
            for box in boxes:
                # 1. BBox coords
                x1, y1, x2, y2 = box.xyxy[0]
                cls = int(box.cls[0])
                
                # 2. Box vergroten
                bw, bh = x2 - x1, y2 - y1
                nx1 = max(0, x1 - (bw * expand_ratio))
                ny1 = max(0, y1 - (bh * expand_ratio))
                nx2 = min(w_orig, x2 + (bw * expand_ratio))
                ny2 = min(h_orig, y2 + (bh * expand_ratio))
                
                # 3. Crop & Segment
                crop = img_cv[int(ny1):int(ny2), int(nx1):int(nx2)]
                if crop.size == 0: continue

                seg_results = self.model_seg(crop, conf=0.20, verbose=False)
                
                # 4. Resultaat verwerken
                found_mask = False
                for sr in seg_results:
                    if sr.masks is not None:
                        for seg_points in sr.masks.xy:
                            if len(seg_points) > 0:
                                # Terugrekenen naar originele plaatje
                                corrected_points = []
                                for px, py in seg_points:
                                    corrected_points.append([px + nx1, py + ny1])
                                
                                final_annotations.append({
                                    "type": "polygon",
                                    "class_id": cls,
                                    "points": corrected_points
                                })
                                found_mask = True
                
                # Fallback: als seg faalt, gebruik bbox
                if not found_mask:
                    final_annotations.append({
                        "type": "bbox",
                        "class_id": cls,
                        "coords": [x1, y1, x2, y2]
                    })

        return final_annotations

    def _process_results(self, results):
        anns = []
        for r in results:
            if r.masks is not None:
                for i, seg_points in enumerate(r.masks.xy):
                    cls = int(r.boxes.cls[i])
                    anns.append({"type": "polygon", "class_id": cls, "points": seg_points.tolist()})
            elif r.boxes is not None:
                for box in r.boxes:
                    cls = int(box.cls[0])
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    anns.append({"type": "bbox", "class_id": cls, "coords": [x1, y1, x2, y2]})
        return anns