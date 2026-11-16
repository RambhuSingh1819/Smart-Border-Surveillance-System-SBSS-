"""Train a dedicated dangerous-item detector from a YOLO-format dataset.

Dataset layout must follow Ultralytics YOLO format and the YAML must define
class names such as knife, pistol, rifle, shotgun, grenade, axe, and machete.
"""

import argparse
import os
import shutil
from pathlib import Path

from ultralytics import YOLO


def main():
    parser = argparse.ArgumentParser(description="Train the Project 129 weapon detector")
    parser.add_argument("--data", required=True, help="Path to dataset.yaml")
    parser.add_argument("--base", default="yolov8n.pt", help="Base YOLO weights")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--project", default="runs/weapon_detector")
    args = parser.parse_args()

    dataset_path = Path(args.data).expanduser().resolve()
    if not dataset_path.is_file():
        raise SystemExit(f"Dataset YAML not found: {dataset_path}")
    if args.epochs < 1 or args.imgsz < 320:
        raise SystemExit("epochs must be positive and imgsz must be at least 320")

    model = YOLO(args.base)
    result = model.train(
        data=str(dataset_path),
        epochs=args.epochs,
        imgsz=args.imgsz,
        project=args.project,
        name="project129",
        pretrained=True,
        patience=25,
        plots=True,
    )

    best_weights = Path(result.save_dir) / "weights" / "best.pt"
    if not best_weights.is_file():
        raise SystemExit(f"Training completed without best.pt: {best_weights}")

    output_path = Path("models/weapon_detector.pt")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(best_weights, output_path)
    print(f"Installed specialized weapon detector: {output_path.resolve()}")
    print("Restart the Streamlit app before testing detection.")


if __name__ == "__main__":
    main()
