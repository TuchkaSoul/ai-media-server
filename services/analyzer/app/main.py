from __future__ import annotations

import argparse
from pathlib import Path

import cv2

from analyzer.app.engine import SemanticAnalyzer
from video_stream.models import FrameData
from video_stream.preprocessor import ScenePreprocessor


def run_demo(source: str) -> None:
    cap = cv2.VideoCapture(0 if source == "0" else source)
    if not cap.isOpened():
        raise RuntimeError(f"Unable to open source: {source}")

    preprocessor = ScenePreprocessor()
    analyzer = SemanticAnalyzer()
    frame_number = 0
    output_dir = Path("analyzer_demo_output")
    output_dir.mkdir(exist_ok=True)

    try:
        while True:
            ok, frame = cap.read()
            if not ok or frame is None:
                break

            raw = FrameData(
                frame=frame,
                timestamp=cv2.getTickCount() / cv2.getTickFrequency(),
                frame_number=frame_number,
                source_id="demo_source",
            )
            processed = analyzer.analyze(preprocessor.process(raw))
            analysis = processed.metadata.get("analysis", {})
            description = processed.metadata.get("descriptions", {}).get("short", "")

            overlay = processed.frame.copy()
            cv2.putText(overlay, f"scene={analysis.get('scene_label', 'n/a')}", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 220, 255), 2)
            cv2.putText(overlay, f"score={processed.scene_score:.2f} anomaly={processed.anomaly_score:.2f}", (20, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(overlay, description[:90], (20, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)

            if analysis.get("keyframe", {}).get("should_save"):
                keyframe_path = output_dir / f"keyframe_{frame_number:06d}.jpg"
                cv2.imwrite(str(keyframe_path), processed.frame)

            cv2.imshow("Analyzer Demo", overlay)
            frame_number += 1
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()


def main() -> None:
    parser = argparse.ArgumentParser(description="Semantic analyzer demo")
    parser.add_argument("--source", default="0", help="Camera index or path/URL")
    args = parser.parse_args()
    run_demo(args.source)


if __name__ == "__main__":
    main()
