# Border Surveillance System

This project is a Streamlit-based border surveillance and intrusion detection dashboard with:

- real-time perimeter monitoring
- face verification for authorized personnel
- vehicle ANPR (license plate recognition)
- weapon detection and alert escalation
- SQLite incident logging

## Quick start

1. Create the environment and install dependencies:

   ```bash
   make install
   ```

2. Start the app:

   ```bash
   make run
   ```

3. Open the local app in a browser:

   ```text
   http://localhost:8501/
   ```

4. Run the tests:

   ```bash
   make test
   ```

5. Run compile + validation checks:

   ```bash
   make check
   ```

## Useful notes

- The app entry point is `app.py`.
- The project uses the local virtual environment at `venv/`.
- If `streamlit` is not found, run `make install` first.
- If the port 8501 is busy, Streamlit will print the next available port in the terminal.

## Dedicated danger detector

The bundled `yolov8n.pt` is a general COCO model and is not a reliable knife or firearm detector. The app now shows a warning when specialized weights are missing and labels each detected danger item on the video frame.

For a real detector, download a properly licensed YOLO-format weapon dataset from a reputable source such as Roboflow Universe or Kaggle. Include diverse images, bounding boxes, and classes such as `knife`, `pistol`, `rifle`, `shotgun`, `grenade`, `axe`, and `machete`. Review the dataset license and labels before use.

Train and install the model with:

```bash
make train-weapon DATA=/absolute/path/to/dataset.yaml
```

The training script evaluates the dataset through Ultralytics and copies `best.pt` to `models/weapon_detector.pt`. Do not claim a target accuracy until the held-out validation set reports precision, recall, and mAP for each danger class.
