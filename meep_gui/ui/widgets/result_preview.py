from __future__ import annotations

import os

from PyQt5 import QtCore, QtGui, QtWidgets

from ...results import ArtifactDisplayEntry


class ResultPreviewWidget(QtWidgets.QWidget):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        self.preview_stack = QtWidgets.QStackedWidget()
        layout.addWidget(self.preview_stack)

        self._media_available = False
        try:
            from PyQt5 import QtMultimedia, QtMultimediaWidgets  # type: ignore

            self._media_available = True
            self._media = QtMultimedia
            self._media_widgets = QtMultimediaWidgets
        except Exception:
            self._media_available = False
            self._media = None
            self._media_widgets = None

        if self._media_available:
            video_container = QtWidgets.QWidget()
            video_layout = QtWidgets.QVBoxLayout(video_container)
            self.player = self._media.QMediaPlayer(self)  # type: ignore[assignment]
            self.video_widget = self._media_widgets.QVideoWidget()  # type: ignore[assignment]
            self.player.setVideoOutput(self.video_widget)
            self.play_button = QtWidgets.QPushButton("Play")
            self.progress = QtWidgets.QSlider(QtCore.Qt.Horizontal)
            self.progress.setRange(0, 0)
            control_row = QtWidgets.QHBoxLayout()
            control_row.addWidget(self.play_button)
            control_row.addWidget(self.progress)
            video_layout.addWidget(self.video_widget)
            video_layout.addLayout(control_row)
            self.preview_stack.addWidget(video_container)
            self.play_button.clicked.connect(self.toggle_play)
            self.progress.sliderMoved.connect(self.on_seek)
            self.player.positionChanged.connect(self.on_position)
            self.player.durationChanged.connect(self.on_duration)
            self.player.stateChanged.connect(self.on_state)
        else:
            self.player = None
            self.video_widget = None
            self.play_button = None
            self.progress = None
            self.preview_stack.addWidget(QtWidgets.QLabel("QtMultimedia not available"))

        self.image_label = QtWidgets.QLabel("No preview")
        self.image_label.setAlignment(QtCore.Qt.AlignCenter)
        self.image_label.setMinimumWidth(360)
        self.image_label.setScaledContents(False)
        self.image_label.setWordWrap(True)
        self.preview_stack.addWidget(self.image_label)

        self.text_preview = QtWidgets.QTextEdit()
        self.text_preview.setReadOnly(True)
        self.preview_stack.addWidget(self.text_preview)

    def show_artifact(self, artifact: ArtifactDisplayEntry) -> None:
        path = artifact.path
        if artifact.preview_kind == "media" and self._media_available and path and os.path.exists(path):
            media = self._media.QMediaContent(QtCore.QUrl.fromLocalFile(path))
            self.player.setMedia(media)
            self.player.pause()
            if self.play_button is not None:
                self.play_button.setText("Play")
            self.preview_stack.setCurrentIndex(0)
            return
        if artifact.preview_kind == "image" and path and os.path.exists(path):
            pix = QtGui.QPixmap(path)
            if pix.isNull():
                self.show_text("Could not load image.")
                return
            self.image_label.setPixmap(
                pix.scaled(
                    self.image_label.width(),
                    self.image_label.height(),
                    QtCore.Qt.KeepAspectRatio,
                    QtCore.Qt.SmoothTransformation,
                )
            )
            self.preview_stack.setCurrentIndex(1)
            return
        if artifact.text:
            self.show_text(artifact.text)
            return
        if path and os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as handle:
                    text = handle.read()
            except Exception as exc:
                text = f"Failed to read file: {exc}"
            self.show_text(text)
            return
        self.show_text("No preview available.")

    def show_text(self, text: str) -> None:
        self.text_preview.setPlainText(text)
        self.preview_stack.setCurrentIndex(2)

    def clear_preview(self) -> None:
        if self._media_available and self.player is not None:
            self.player.stop()
            self.player.setMedia(self._media.QMediaContent())
            if self.progress is not None:
                self.progress.setRange(0, 0)
                self.progress.setValue(0)
            if self.play_button is not None:
                self.play_button.setText("Play")
        self.image_label.clear()
        self.image_label.setText("No preview")
        self.show_text("")

    def toggle_play(self) -> None:
        if self._media_available:
            if self.player.state() == self._media.QMediaPlayer.PlayingState:
                self.player.pause()
            else:
                self.player.play()

    def on_seek(self, value: int) -> None:
        if self._media_available and self.player is not None:
            self.player.setPosition(value)

    def on_position(self, position: int) -> None:
        if self.progress is not None:
            self.progress.setValue(position)

    def on_duration(self, duration: int) -> None:
        if self.progress is not None:
            self.progress.setRange(0, duration)

    def on_state(self, state) -> None:
        if self.play_button is None:
            return
        if state == self._media.QMediaPlayer.PlayingState:
            self.play_button.setText("Pause")
        else:
            self.play_button.setText("Play")
