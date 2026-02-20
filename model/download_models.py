import os
import sys
import urllib.request

WEIGHTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "weights")

MODELS = {
    "deploy.prototxt": {
        "url": "https://raw.githubusercontent.com/opencv/opencv/4.x/samples/dnn/face_detector/deploy.prototxt",
        "desc": "Face detector network architecture",
    },
    "res10_300x300_ssd_iter_140000.caffemodel": {
        "url": (
            "https://github.com/opencv/opencv_3rdparty/raw/"
            "dnn_samples_face_detector_20170830/"
            "res10_300x300_ssd_iter_140000.caffemodel"
        ),
        "desc": "Face detector weights (~10.5 MB)",
    },
    "enet_b0_8_va_mtl.onnx": {
        "url": (
            "https://github.com/sb-ai-lab/EmotiEffLib/raw/main/"
            "models/affectnet_emotions/onnx/enet_b0_8_va_mtl.onnx"
        ),
        "desc": "HSEmotion EfficientNet-B0 MTL — 8 emotions + valence/arousal (~16 MB)",
    },
    "face_landmarker.task": {
        "url": (
            "https://storage.googleapis.com/mediapipe-models/"
            "face_landmarker/face_landmarker/float16/1/face_landmarker.task"
        ),
        "desc": "MediaPipe Face Landmarker — drowsiness detection (~4 MB)",
    },
}

def download(url, dest, desc):
    basename = os.path.basename(dest)
    if os.path.exists(dest):
        size_mb = os.path.getsize(dest) / (1024 * 1024)
        print(f"  [skip] {basename} already exists ({size_mb:.1f} MB)")
        return True

    print(f"  Downloading {desc}...")
    try:
        urllib.request.urlretrieve(url, dest, reporthook=_progress)
        print()
        size_mb = os.path.getsize(dest) / (1024 * 1024)
        if size_mb < 0.001:
            os.remove(dest)
            print(f"  [FAIL] {basename} — file is empty/corrupt")
            return False
        print(f"  [ok] {basename} ({size_mb:.1f} MB)")
        return True
    except Exception as e:
        print(f"\n  [FAIL] {basename}: {e}")
        return False


def _progress(block_num, block_size, total_size):
    downloaded = block_num * block_size
    if total_size > 0:
        pct = min(100, downloaded * 100 / total_size)
        mb = downloaded / (1024 * 1024)
        total_mb = total_size / (1024 * 1024)
        print(f"\r  {pct:5.1f}%  ({mb:.1f}/{total_mb:.1f} MB)", end="", flush=True)
    else:
        mb = downloaded / (1024 * 1024)
        print(f"\r  {mb:.1f} MB downloaded", end="", flush=True)


def main():
    os.makedirs(WEIGHTS_DIR, exist_ok=True)
    print(f"Model directory: {WEIGHTS_DIR}\n")

    all_ok = True
    for filename, info in MODELS.items():
        dest = os.path.join(WEIGHTS_DIR, filename)
        if not download(info["url"], dest, info["desc"]):
            all_ok = False
        print()

    if all_ok:
        print("All models downloaded.")
    else:
        print("Some downloads failed.")

    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
