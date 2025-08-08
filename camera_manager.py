# camera_manager.py
import cv2

def find_available_cameras(max_scan=10):
    available = []
    for i in range(max_scan):
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
        if cap is None:
            continue
        opened = cap.isOpened()
        if opened:
            # try to grab a frame quickly
            ret, _ = cap.read()
            if ret:
                available.append(i)
        cap.release()
    return available
