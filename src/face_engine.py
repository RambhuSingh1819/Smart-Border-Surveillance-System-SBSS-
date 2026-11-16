import os
# pyrefly: ignore [missing-import]
import cv2
# pyrefly: ignore [missing-import]
import numpy as np
# pyrefly: ignore [missing-import]
from PIL import Image

class FaceVerifier:
    def __init__(self, db_path="data/authorized_faces"):
        self.db_path = db_path
        self.torch = None
        self.device = None
        self.mtcnn = None
        self.resnet = None
        self.known_embeddings = []
        self.known_names = []

    def _ensure_models(self):
        if self.resnet is not None:
            return

        import torch
        from facenet_pytorch import MTCNN, InceptionResnetV1

        self.torch = torch
        self.device = torch.device('cuda:0' if torch.cuda.is_available() else 'cpu')
        self.mtcnn = MTCNN(keep_all=False, select_largest=True, min_face_size=20, device=self.device)
        self.resnet = InceptionResnetV1(pretrained='vggface2').eval().to(self.device)

    def reload_database(self, db_path=None):
        self._ensure_models()
        if db_path:
            self.db_path = db_path
        os.makedirs(self.db_path, exist_ok=True)
        self.known_embeddings = []
        self.known_names = []

        for file in os.listdir(self.db_path):
            if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                img_path = os.path.join(self.db_path, file)
                try:
                    img = Image.open(img_path).convert('RGB')
                    face = self.mtcnn(img)
                    
                    # Fallback for pre-cropped passport photos
                    if face is None:
                        resized = img.resize((160, 160))
                        tensor = self.torch.tensor(np.array(resized)).permute(2, 0, 1).float()
                        face = (tensor - 127.5) / 128.0

                    with self.torch.no_grad():
                        emb = self.resnet(face.unsqueeze(0).to(self.device))
                        self.known_embeddings.append(emb)
                        sample_name = os.path.splitext(file)[0].lower()
                        self.known_names.append(sample_name.split("__", 1)[0])
                except Exception as e:
                    print(f"Error processing {file}: {e}")

    def verify_crop(self, face_bgr_crop, threshold=0.55):
        if face_bgr_crop is None or not isinstance(face_bgr_crop, np.ndarray) or face_bgr_crop.size == 0:
            return False, "Unknown (Invalid Crop)", 0.0

        if self.resnet is None:
            self._ensure_models()
            if not self.known_embeddings:
                self.reload_database()

        if len(self.known_embeddings) == 0:
            return False, "Unknown (No DB)", 0.0

        img_rgb = cv2.cvtColor(face_bgr_crop, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(img_rgb)
        face = self.mtcnn(pil_img)
        
        # Fallback if crop is tightly bounded around the face
        if face is None:
            resized = pil_img.resize((160, 160))
            tensor = self.torch.tensor(np.array(resized)).permute(2, 0, 1).float()
            face = (tensor - 127.5) / 128.0

        with self.torch.no_grad():
            live_emb = self.resnet(face.unsqueeze(0).to(self.device))

        best_score = -1.0
        best_name = "Unknown"

        for known_emb, name in zip(self.known_embeddings, self.known_names):
            sim = self.torch.nn.functional.cosine_similarity(live_emb, known_emb).item()
            if sim > best_score:
                best_score = sim
                best_name = name

        is_authorized = best_score >= threshold
        return is_authorized, best_name if is_authorized else "Intruder", best_score