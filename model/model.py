import argparse
import os
import time
from collections import deque

import cv2
import numpy as np
import onnxruntime as ort

try:
    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision as mp_vision
    _HAS_MEDIAPIPE = True
except ImportError:
    _HAS_MEDIAPIPE = False


WEIGHTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "weights")
FACE_PROTO = os.path.join(WEIGHTS_DIR, "deploy.prototxt")
FACE_MODEL = os.path.join(WEIGHTS_DIR, "res10_300x300_ssd_iter_140000.caffemodel")
EMOTION_MODEL = os.path.join(WEIGHTS_DIR, "enet_b0_8_va_mtl.onnx")
FACE_LANDMARKER_MODEL = os.path.join(WEIGHTS_DIR, "face_landmarker.task")

EMOTIONS = [
    "angry", "contempt", "disgust", "fear",
    "happy", "neutral", "sad", "surprise",
]

EMOTION_COLORS = {
    "angry":    (0, 0, 255),
    "contempt": (0, 180, 180),
    "disgust":  (0, 140, 0),
    "fear":     (180, 0, 180),
    "happy":    (0, 255, 255),
    "neutral":  (180, 180, 180),
    "sad":      (255, 100, 0),
    "surprise": (0, 165, 255),
}

STATE_COLORS = {
    "ok":         (0, 200, 0),
    "drowsy":     (0, 0, 255),
    "fatigued":   (0, 100, 255),
    "distressed": (0, 50, 200),
    "not_locked_in":   (0, 200, 255),
}

RIGHT_EYE = [33, 160, 158, 133, 153, 144]
LEFT_EYE = [362, 385, 387, 263, 373, 380]
UPPER_LIP = 13
LOWER_LIP = 14
MOUTH_LEFT = 78
MOUTH_RIGHT = 308

EAR_THRESHOLD = 0.23
MAR_THRESHOLD = 0.65
PERCLOS_WINDOW_SEC = 20
PERCLOS_DROWSY = 0.15

def softmax(x):
    e = np.exp(x - np.max(x))
    return e / e.sum()


def _dist(a, b):
    return np.linalg.norm(np.array(a) - np.array(b))


def _ear(landmarks, indices, w, h):
    pts = [(landmarks[i].x * w, landmarks[i].y * h) for i in indices]
    vertical_1 = _dist(pts[1], pts[5])
    vertical_2 = _dist(pts[2], pts[4])
    horizontal = _dist(pts[0], pts[3])
    if horizontal < 1e-6:
        return 0.0
    return (vertical_1 + vertical_2) / (2.0 * horizontal)


def _mar(landmarks, w, h):
    top = (landmarks[UPPER_LIP].x * w, landmarks[UPPER_LIP].y * h)
    bot = (landmarks[LOWER_LIP].x * w, landmarks[LOWER_LIP].y * h)
    left = (landmarks[MOUTH_LEFT].x * w, landmarks[MOUTH_LEFT].y * h)
    right = (landmarks[MOUTH_RIGHT].x * w, landmarks[MOUTH_RIGHT].y * h)
    horizontal = _dist(left, right)
    if horizontal < 1e-6:
        return 0.0
    return _dist(top, bot) / horizontal


class FaceDetector:
    def __init__(self, use_cuda=False):
        for p in (FACE_PROTO, FACE_MODEL):
            if not os.path.isfile(p):
                raise FileNotFoundError(f"Missing: {p}\nRun download_models.py")

        self.net = cv2.dnn.readNetFromCaffe(FACE_PROTO, FACE_MODEL)

        if use_cuda and cv2.cuda.getCudaEnabledDeviceCount() > 0:
            self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_CUDA)
            self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CUDA)

    def detect(self, frame, threshold=0.5):
        h, w = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(frame, 1.0, (300, 300), (104.0, 177.0, 123.0))
        self.net.setInput(blob)
        dets = self.net.forward()

        faces = []
        for i in range(dets.shape[2]):
            conf = float(dets[0, 0, i, 2])
            if conf < threshold:
                continue
            box = dets[0, 0, i, 3:7] * np.array([w, h, w, h])
            x1, y1, x2, y2 = box.astype(int)
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(w, x2), min(h, y2)
            if x2 > x1 and y2 > y1:
                faces.append((x1, y1, x2, y2, conf))
        return faces


class EmotionAnalyzer:
    img_size = 224
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)

    def __init__(self, use_cuda=False):
        if not os.path.isfile(EMOTION_MODEL):
            raise FileNotFoundError(f"Missing: {EMOTION_MODEL}\nRun download_models.py")

        providers = (
            ["CUDAExecutionProvider", "CPUExecutionProvider"]
            if use_cuda else ["CPUExecutionProvider"]
        )
        print(f'Using providers: {providers}')
        self.session = ort.InferenceSession(EMOTION_MODEL, providers=providers)
        self.input_name = self.session.get_inputs()[0].name

    def _preprocess(self, face_bgr):
        rgb = cv2.cvtColor(face_bgr, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, (self.img_size, self.img_size))
        img = resized.astype(np.float32) / 255.0
        img = (img - self.mean) / self.std
        return img.transpose(2, 0, 1)[np.newaxis, ...]

    def predict(self, face_bgr):
        blob = self._preprocess(face_bgr)
        output = self.session.run(None, {self.input_name: blob})[0][0]

        emotion_logits = output[:8]
        valence = float(output[8])
        arousal = float(output[9])

        probs = softmax(emotion_logits)
        idx = int(np.argmax(probs))

        return {
            "emotion": EMOTIONS[idx],
            "emotion_confidence": float(probs[idx]),
            "probabilities": {EMOTIONS[i]: float(probs[i]) for i in range(8)},
            "valence": valence,
            "arousal": arousal,
        }


class DrowsinessDetector:
    def __init__(self):
        base_options = mp_python.BaseOptions(
            model_asset_path=FACE_LANDMARKER_MODEL
        )
        options = mp_vision.FaceLandmarkerOptions(
            base_options=base_options,
            running_mode=mp_vision.RunningMode.VIDEO,
            num_faces=1,
        )
        self.landmarker = mp_vision.FaceLandmarker.create_from_options(options)
        self.ear_history = deque()
        self._frame_ts_ms = 0

    def process(self, frame_bgr):
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        self._frame_ts_ms += 33
        result = self.landmarker.detect_for_video(mp_image, self._frame_ts_ms)

        if not result.face_landmarks:
            return None

        lms = result.face_landmarks[0]
        h, w = frame_bgr.shape[:2]

        left_ear = _ear(lms, LEFT_EYE, w, h)
        right_ear = _ear(lms, RIGHT_EYE, w, h)
        ear = (left_ear + right_ear) / 2.0

        mar = _mar(lms, w, h)

        now = time.time()
        self.ear_history.append((now, ear))
        while self.ear_history and (now - self.ear_history[0][0]) > PERCLOS_WINDOW_SEC:
            self.ear_history.popleft()

        perclos = None
        if len(self.ear_history) >= 15:
            closed = sum(1 for _, e in self.ear_history if e < EAR_THRESHOLD)
            perclos = closed / len(self.ear_history)

        return ear, mar, perclos


def assess_wellness(emotion, valence, arousal, ear, mar, perclos):
    negative_emotion = emotion in ("sad", "fear", "angry", "disgust", "contempt")
    low_mood = valence < -0.3
    low_energy = arousal < -0.3
    eyes_closing = ear is not None and ear < EAR_THRESHOLD
    yawning = mar is not None and mar > MAR_THRESHOLD
    consistent_eye_closure = perclos is not None and perclos > PERCLOS_DROWSY

    if consistent_eye_closure or eyes_closing:
        return "drowsy"
    if low_energy and low_mood:
        return "fatigued"
    if negative_emotion or low_mood:
        return "distressed"
    if yawning:
        return "not_locked_in"
    return "ok"


def draw_overlay(frame, results, drowsiness, fps):
    for r in results:
        x1, y1, x2, y2 = r["bbox"]
        emotion = r["emotion"]
        conf = r["emotion_confidence"]
        color = EMOTION_COLORS.get(emotion, (255, 255, 255))

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        label = f"{emotion} {conf:.0%}"
        (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        cv2.rectangle(frame, (x1, y1 - lh - 10), (x1 + lw + 4, y1), color, -1)
        cv2.putText(frame, label, (x1 + 2, y1 - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)

        va_label = f"V:{r['valence']:+.2f}  A:{r['arousal']:+.2f}"
        cv2.putText(frame, va_label, (x1, y2 + 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

    y_offset = 30
    cv2.putText(frame, f"FPS: {fps:.1f}", (10, y_offset),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

    if drowsiness is not None:
        ear, mar, perclos = drowsiness
        y_offset += 30
        cv2.putText(frame, f"EAR: {ear:.2f}", (10, y_offset),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)
        y_offset += 25
        cv2.putText(frame, f"MAR: {mar:.2f}", (10, y_offset),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)
        if perclos is not None:
            y_offset += 25
            pcol = (0, 0, 255) if perclos > PERCLOS_DROWSY else (255, 255, 255)
            cv2.putText(frame, f"PERCLOS: {perclos:.0%}", (10, y_offset),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, pcol, 1)

    if results:
        dominant = max(results, key=lambda r: r["emotion_confidence"])
        ear_val = drowsiness[0] if drowsiness else None
        mar_val = drowsiness[1] if drowsiness else None
        pcl_val = drowsiness[2] if drowsiness else None
        state = assess_wellness(
            dominant["emotion"], dominant["valence"], dominant["arousal"],
            ear_val, mar_val, pcl_val,
        )
        sc = STATE_COLORS.get(state, (255, 255, 255))
        cv2.putText(frame, state.upper(), (frame.shape[1] - 200, 35),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.9, sc, 2)

    return frame


def main():
    parser = argparse.ArgumentParser(description="Emotion & Wellness Detection")
    parser.add_argument("--camera", type=int, default=0,
                        help="USB camera index (default: 0)")
    parser.add_argument("--cuda", action="store_true",
                        help="Enable CUDA (Jetson Nano / NVIDIA GPU)")
    parser.add_argument("--confidence", type=float, default=0.5,
                        help="Face detection confidence threshold")
    parser.add_argument("--headless", action="store_true",
                        help="No display window (SSH / headless)")
    parser.add_argument("--no-drowsiness", action="store_true",
                        help="Disable MediaPipe drowsiness detection")
    args = parser.parse_args()

    face_det = FaceDetector(use_cuda=args.cuda)
    emotion_analyzer = EmotionAnalyzer(use_cuda=args.cuda)

    drowsiness_det = None
    if not args.no_drowsiness:
        if _HAS_MEDIAPIPE:
            drowsiness_det = DrowsinessDetector()
            print("[INFO] MediaPipe drowsiness detection enabled")
        else:
            print("[WARN] mediapipe not installed — drowsiness detection disabled")
            print("       pip install mediapipe   (to enable)")

    print(f"[INFO] Opening USB camera index {args.camera}")
    cap = cv2.VideoCapture(args.camera)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    if not cap.isOpened():
        print("[ERROR] Cannot open camera")
        return 1

    print("[INFO] Camera ready. Press 'q' to quit.")

    fps = 0.0
    frame_count = 0
    fps_start = time.time()

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("[ERROR] Frame capture failed")
                break

            faces = face_det.detect(frame, args.confidence)

            results = []
            for x1, y1, x2, y2, fconf in faces:
                face_img = frame[y1:y2, x1:x2]
                if face_img.size == 0:
                    continue
                pred = emotion_analyzer.predict(face_img)
                pred["bbox"] = [x1, y1, x2, y2]
                pred["face_confidence"] = fconf
                results.append(pred)

            drowsiness = None
            if drowsiness_det is not None:
                drowsiness = drowsiness_det.process(frame)

            frame_count += 1
            elapsed = time.time() - fps_start
            if elapsed >= 1.0:
                fps = frame_count / elapsed
                frame_count = 0
                fps_start = time.time()

            if not args.headless:
                draw_overlay(frame, results, drowsiness, fps)
                cv2.imshow("Emotion & Wellness Detection", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
            elif results:
                dominant = max(results, key=lambda r: r["emotion_confidence"])
                ear_v = drowsiness[0] if drowsiness else None
                mar_v = drowsiness[1] if drowsiness else None
                pcl_v = drowsiness[2] if drowsiness else None
                state = assess_wellness(
                    dominant["emotion"], dominant["valence"], dominant["arousal"],
                    ear_v, mar_v, pcl_v,
                )
                parts = [
                    f"[{fps:.1f} FPS]",
                    f"{dominant['emotion']} ({dominant['emotion_confidence']:.0%})",
                    f"V:{dominant['valence']:+.2f} A:{dominant['arousal']:+.2f}",
                ]
                if ear_v is not None:
                    parts.append(f"EAR:{ear_v:.2f}")
                parts.append(f"-> {state}")
                print("  ".join(parts))
    finally:
        cap.release()
        if not args.headless:
            cv2.destroyAllWindows()
        print("[INFO] Shut down.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
