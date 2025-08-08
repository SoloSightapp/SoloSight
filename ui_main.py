# ui_main.py
import os
import sys
import time
import sys, os

def resource_path(relative_path):
    """Get absolute path to resource, works in dev and after PyInstaller build"""
    try:
        base_path = sys._MEIPASS  # PyInstaller temp dir
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)
import cv2
from PyQt5.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QGridLayout,
    QApplication, QLineEdit, QDialog, QFileDialog, QFrame, QScrollArea,
    QGroupBox, QFormLayout, QMessageBox
)
from PyQt5.QtGui import QImage, QPixmap, QFont, QIcon
from PyQt5.QtCore import QTimer, Qt
from camera_manager import find_available_cameras
from recorder import CameraRecorder
from settings_manager import load_settings, save_settings
import theme

# helper for debug label
def overlay_text(frame, text, x=10, y=20):
    cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255,255,255), 1, cv2.LINE_AA)

class CameraWidget(QWidget):
    def __init__(self, cam_index, label_text, settings, parent=None):
        super().__init__(parent)
        self.cam_index = cam_index
        self.label_text = label_text
        self.settings = settings
        self.cap = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.grab_frame)
        self.recording = False
        self.recorder = None

        # UI components
        self.label = QLabel(self.label_text)
        self.label.setStyleSheet(f"color: {theme.FOREGROUND}; font-family: {theme.LABEL_FONT}; font-size: {theme.BASE_FONT_SIZE + 2}px;")
        self.video = QLabel()
        self.video.setFixedSize(480, 360)
        self.video.setStyleSheet("background: black;")
        self.btn_full = QPushButton("⛶")
        self.btn_full.setFixedWidth(34)
        self.btn_full.clicked.connect(self.toggle_fullscreen)
        self.btn_edit = QPushButton("Edit")
        self.btn_edit.setFixedWidth(44)
        self.btn_edit.clicked.connect(self.edit_label)

        top_row = QHBoxLayout()
        top_row.addWidget(self.label)
        top_row.addStretch()
        top_row.addWidget(self.btn_edit)
        top_row.addWidget(self.btn_full)

        layout = QVBoxLayout()
        layout.addLayout(top_row)
        layout.addWidget(self.video)
        self.debug = QLabel("")
        self.debug.setStyleSheet(f"color:{theme.FOREGROUND}; font-size:8pt;")
        layout.addWidget(self.debug)
        self.setLayout(layout)
        self.in_fullscreen = False

    def open(self):
        # try to open capture with DirectShow on Windows for stability
        try:
            self.cap = cv2.VideoCapture(self.cam_index, cv2.CAP_DSHOW)
        except Exception:
            self.cap = cv2.VideoCapture(self.cam_index)
        if not self.cap.isOpened():
            return False
        # start timer to update
        self.timer.start(30)
        return True

    def close(self):
        self.timer.stop()
        if self.cap:
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None

    def grab_frame(self):
        if not self.cap or not self.cap.isOpened():
            self.debug.setText("No feed")
            return
        ret, frame = self.cap.read()
        if not ret:
            self.debug.setText("Frame grab failed")
            return

        # overlay debug info
        h, w = frame.shape[:2]
        fps_text = f"{int(self.cap.get(cv2.CAP_PROP_FPS) or 30)}FPS"
        cam_name = self.label_text
        overlay_text(frame, f"{cam_name} | {w}x{h} | {fps_text}", 8, 18)

        # convert to Qt image
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb.data, rgb.shape[1], rgb.shape[0], QImage.Format_RGB888)
        pix = QPixmap.fromImage(qimg).scaled(self.video.width(), self.video.height(), Qt.KeepAspectRatio)
        self.video.setPixmap(pix)
        # write to recorder if recording
        if self.recording and self.recorder:
            self.recorder.write_frame(frame)

    def toggle_fullscreen(self):
        if not self.in_fullscreen:
            # create a dialog window to show the video in fullscreen-like
            self.full_win = QDialog(self, Qt.Window)
            self.full_win.setWindowTitle(self.label_text)
            full_layout = QVBoxLayout()
            full_video = QLabel()
            full_layout.addWidget(full_video)
            self.full_win.setLayout(full_layout)
            self.full_label = full_video
            self.full_win.showMaximized()
            # start an internal timer to push frames
            self.full_timer = QTimer()
            self.full_timer.timeout.connect(self._update_full)
            self.full_timer.start(30)
            self.in_fullscreen = True
        else:
            try:
                self.full_timer.stop()
                self.full_win.close()
            except Exception:
                pass
            self.in_fullscreen = False

    def _update_full(self):
        if not self.cap:
            return
        ret, frame = self.cap.read()
        if not ret:
            return
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb.data, rgb.shape[1], rgb.shape[0], QImage.Format_RGB888)
        pix = QPixmap.fromImage(qimg).scaled(self.full_label.width(), self.full_label.height(), Qt.KeepAspectRatio)
        self.full_label.setPixmap(pix)
        # if recording write as well
        if self.recording and self.recorder:
            self.recorder.write_frame(frame)

    def edit_label(self):
        # simple inline edit dialog
        text, ok = QInputDialog.getText(self, "Edit Camera Label", "Label:", QLineEdit.Normal, self.label_text)
        if ok and text:
            self.label_text = text
            self.label.setText(text)

    def start_recording(self, save_dir, chunk_minutes, max_minutes):
        if self.recording:
            return
        self.recorder = CameraRecorder(save_dir, self.cam_index, chunk_minutes=chunk_minutes, max_minutes=max_minutes)
        self.recorder.start()
        self.recording = True

    def stop_recording(self):
        if not self.recording:
            return
        if self.recorder:
            self.recorder.stop()
        self.recording = False

from PyQt5.QtWidgets import QInputDialog, QLineEdit

class MainWindow(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(theme.APP_NAME)
        self.setStyleSheet(f"background:{theme.BACKGROUND}; color:{theme.FOREGROUND};")
        font = QFont(theme.LABEL_FONT, theme.BASE_FONT_SIZE)
        self.setFont(font)

        self.settings = load_settings()
        self.camera_labels = self.settings.get("camera_labels", [])
        self.save_path = self.settings.get("save_path", "recordings")
        self.chunk_minutes = self.settings.get("record_chunk_minutes", theme.RECORD_CHUNK_MINUTES)
        self.max_minutes = self.settings.get("max_record_minutes", theme.RECORD_MAX_MINUTES)

        # UI building
        main_layout = QVBoxLayout()
        header = QHBoxLayout()
        title = QLabel(theme.APP_NAME)
        title.setStyleSheet(f"font-size:16pt; color:{theme.ACCENT};")
        header.addWidget(title)
        header.addStretch()
        self.status_label = QLabel("Ready")
        header.addWidget(self.status_label)
        main_layout.addLayout(header)

        # camera grid area
        self.grid = QGridLayout()
        self.grid_frame = QFrame()
        self.grid_frame.setLayout(self.grid)
        main_layout.addWidget(self.grid_frame)

        # controls
        ctrl = QHBoxLayout()
        self.btn_record = QPushButton("Start Recording")
        self.btn_record.setCheckable(True)
        self.btn_record.clicked.connect(self.on_record_toggle)
        ctrl.addWidget(self.btn_record)
        self.btn_refresh = QPushButton("Refresh Cameras")
        self.btn_refresh.clicked.connect(self.refresh_cameras)
        ctrl.addWidget(self.btn_refresh)
        self.btn_settings = QPushButton("Settings")
        self.btn_settings.clicked.connect(self.open_settings)
        ctrl.addWidget(self.btn_settings)
        main_layout.addLayout(ctrl)

        self.setLayout(main_layout)

        # camera widgets list
        self.camera_widgets = []
        self.detect_and_build()

    def detect_and_build(self):
        # clear existing
        for w in self.camera_widgets:
            try:
                w.close()
                w.setParent(None)
            except Exception:
                pass
        self.camera_widgets.clear()
        # find cameras
        cam_indices = find_available_cameras(8)
        if not cam_indices:
            self.status_label.setText("No cameras found")
            return
        self.status_label.setText(f"Found {len(cam_indices)} cameras")
        # create camera widgets and add to grid
        for idx, cidx in enumerate(cam_indices):
            label_text = self.get_label(idx, cidx)
            cw = CameraWidget(cidx, label_text, self.settings, parent=self)
            opened = cw.open()
            if opened:
                self.camera_widgets.append(cw)
                # grid position
                cols = 2
                row = idx // cols
                col = idx % cols
                self.grid.addWidget(cw, row, col)
            else:
                cw.close()

    def get_label(self, slot_idx, cam_index):
        # if saved labels exist, use them by slot index
        if slot_idx < len(self.camera_labels) and self.camera_labels[slot_idx]:
            return self.camera_labels[slot_idx]
        # fallback to default label using camera index
        return f"Cam {cam_index}"

    def refresh_cameras(self):
        self.detect_and_build()

    def on_record_toggle(self, checked):
        if checked:
            # start recording
            self.btn_record.setText("Stop Recording")
            self.status_label.setText("Recording...")
            for cw in self.camera_widgets:
                cw.start_recording(self.save_path, self.chunk_minutes, self.max_minutes)
        else:
            self.btn_record.setText("Start Recording")
            self.status_label.setText("Ready")
            for cw in self.camera_widgets:
                cw.stop_recording()

    def open_settings(self):
        dlg = SettingsDialog(self)
        if dlg.exec_():
            # apply settings
            data = dlg.get_values()
            self.camera_labels = data.get("camera_labels", self.camera_labels)
            self.save_path = data.get("save_path", self.save_path)
            self.chunk_minutes = data.get("record_chunk_minutes", self.chunk_minutes)
            self.max_minutes = data.get("max_record_minutes", self.max_minutes)
            # persist
            self.settings["camera_labels"] = self.camera_labels
            self.settings["save_path"] = self.save_path
            self.settings["record_chunk_minutes"] = self.chunk_minutes
            self.settings["max_record_minutes"] = self.max_minutes
            save_settings(self.settings)
            # refresh labels displayed
            for i, cw in enumerate(self.camera_widgets):
                if i < len(self.camera_labels):
                    cw.label_text = self.camera_labels[i]
                    cw.label.setText(self.camera_labels[i])

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(420)
        layout = QVBoxLayout()
        form = QFormLayout()

        # camera labels (comma-separated)
        cam_labels = ",".join(parent.camera_labels) if parent.camera_labels else ""
        self.edit_labels = QLineEdit(cam_labels)
        form.addRow("Camera labels (comma-separated)", self.edit_labels)

        # save path
        self.edit_path = QLineEdit(parent.save_path)
        btn_browse = QPushButton("Browse")
        btn_browse.clicked.connect(self.browse_folder)
        h = QHBoxLayout()
        h.addWidget(self.edit_path)
        h.addWidget(btn_browse)
        form.addRow("Recording folder", h)

        # chunk minutes
        self.edit_chunk = QLineEdit(str(parent.chunk_minutes))
        form.addRow("Chunk minutes (5-10)", self.edit_chunk)

        # max minutes
        self.edit_max = QLineEdit(str(parent.max_minutes))
        form.addRow("Max session minutes (<=60)", self.edit_max)

        layout.addLayout(form)

        btns = QHBoxLayout()
        self.btn_ok = QPushButton("OK")
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        btns.addStretch()
        btns.addWidget(self.btn_ok)
        btns.addWidget(self.btn_cancel)
        layout.addLayout(btns)
        self.setLayout(layout)

    def browse_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Select folder", os.getcwd())
        if d:
            self.edit_path.setText(d)

    def get_values(self):
        labels = [s.strip() for s in self.edit_labels.text().split(",") if s.strip()]
        try:
            chunk = max(1, int(self.edit_chunk.text()))
        except:
            chunk = 5
        try:
            mx = min(60, int(self.edit_max.text()))
        except:
            mx = 60
        return {
            "camera_labels": labels,
            "save_path": self.edit_path.text().strip() or "recordings",
            "record_chunk_minutes": chunk,
            "max_record_minutes": mx
        }
