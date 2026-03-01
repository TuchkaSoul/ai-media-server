from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QComboBox, QFrame, QScrollArea, 
                             QGridLayout, QTextEdit, QGroupBox, QMessageBox,
                             QDialog, QMenu, QSplitter, QTabWidget, QToolBar,
                             QSizePolicy, QDockWidget, QMainWindow)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QPixmap, QImage, QIcon, QFont

class CameraWidget(QWidget):
    """Виджет для отображения одной камеры"""
    closed = pyqtSignal(str)  # Сигнал при закрытии камеры
    
    def __init__(self, camera_id, camera_name, parent=None):
        super().__init__(parent)
        self.camera_id = camera_id
        self.camera_name = camera_name
        self.is_popout = False
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Заголовок камеры
        self.header_frame = QFrame()
        self.header_frame.setStyleSheet("""
            QFrame {
                background-color: #2b579a;
                border-radius: 4px;
                padding: 4px;
            }
        """)
        header_layout = QHBoxLayout(self.header_frame)
        header_layout.setContentsMargins(8, 4, 8, 4)
        
        self.title_label = QLabel(f"📹 {self.camera_name}")
        self.title_label.setStyleSheet("color: white; font-weight: bold; font-size: 12px;")
        
        self.status_indicator = QLabel("●")
        self.status_indicator.setStyleSheet("color: #4CAF50; font-size: 16px;")
        
        header_layout.addWidget(self.title_label)
        header_layout.addStretch()
        header_layout.addWidget(self.status_indicator)
        
        layout.addWidget(self.header_frame)
        
        # Область видео
        self.video_frame = QFrame()
        self.video_frame.setFrameStyle(QFrame.Box)
        self.video_frame.setStyleSheet("""
            QFrame {
                background-color: #000000;
                border: 2px solid #555555;
                border-radius: 4px;
            }
        """)
        self.video_frame.setMinimumSize(320, 240)
        
        video_layout = QVBoxLayout(self.video_frame)
        self.video_label = QLabel("Камера неактивна")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet("color: #888888; font-size: 12px; padding: 20px;")
        video_layout.addWidget(self.video_label)
        
        layout.addWidget(self.video_frame)
        
        # Панель управления камерой
        control_layout = QHBoxLayout()
        
        self.record_btn = QPushButton("⏺️")
        self.record_btn.setToolTip("Начать запись")
        self.record_btn.setFixedSize(30, 30)
        self.record_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                border: none;
                border-radius: 4px;
                color: white;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
        """)
        
        self.snapshot_btn = QPushButton("📷")
        self.snapshot_btn.setToolTip("Сделать снимок")
        self.snapshot_btn.setFixedSize(30, 30)
        
        self.popout_btn = QPushButton("⬈")
        self.popout_btn.setToolTip("Вынести в отдельное окно")
        self.popout_btn.setFixedSize(30, 30)
        
        # Стили для кнопок
        button_style = """
            QPushButton {
                background-color: #555555;
                border: none;
                border-radius: 4px;
                color: white;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #666666;
            }
        """
        self.snapshot_btn.setStyleSheet(button_style)
        self.popout_btn.setStyleSheet(button_style)
        
        control_layout.addWidget(self.record_btn)
        control_layout.addWidget(self.snapshot_btn)
        control_layout.addStretch()
        control_layout.addWidget(self.popout_btn)
        
        layout.addLayout(control_layout)
        
        # Информация о камере
        info_layout = QHBoxLayout()
        self.fps_label = QLabel("FPS: 0")
        self.fps_label.setStyleSheet("color: #888888; font-size: 10px;")
        self.resolution_label = QLabel("1920x1080")
        self.resolution_label.setStyleSheet("color: #888888; font-size: 10px;")
        
        info_layout.addWidget(self.fps_label)
        info_layout.addStretch()
        info_layout.addWidget(self.resolution_label)
        
        layout.addLayout(info_layout)
        
        # Подключаем сигналы
        self.snapshot_btn.clicked.connect(self.take_snapshot)
        self.popout_btn.clicked.connect(self.toggle_popout)
        
    def update_stream_info(self, fps, resolution):
        """Обновление информации о потоке"""
        self.fps_label.setText(f"FPS: {fps}")
        self.resolution_label.setText(resolution)
        
    def set_stream_active(self, active):
        """Установка статуса активности"""
        if active:
            self.status_indicator.setStyleSheet("color: #4CAF50; font-size: 16px;")
            self.video_label.setText("📹 Трансляция активна")
            self.video_label.setStyleSheet("color: #4CAF50; font-size: 12px; padding: 20px;")
        else:
            self.status_indicator.setStyleSheet("color: #f44336; font-size: 16px;")
            self.video_label.setText("Камера неактивна")
            self.video_label.setStyleSheet("color: #888888; font-size: 12px; padding: 20px;")
            
    def take_snapshot(self):
        """Создание снимка"""
        QMessageBox.information(self, "Снимок", f"Снимок с камеры {self.camera_name} сохранен")
        
    def toggle_popout(self):
        """Переключение режима выноса в отдельное окно"""
        self.popout_btn.setText("⬋" if self.is_popout else "⬈")
        self.popout_btn.setToolTip("Вернуть в основное окно" if self.is_popout else "Вынести в отдельное окно")
        
        if not self.is_popout:
            # Создаем отдельное окно для камеры
            self.popout_window = QDialog(self)
            self.popout_window.setWindowTitle(f"Камера: {self.camera_name}")
            self.popout_window.setMinimumSize(400, 300)
            self.popout_window.setStyleSheet("""
                QDialog {
                    background-color: #1e1e1e;
                }
            """)
            
            # Переносим виджет в новое окно
            layout = QVBoxLayout(self.popout_window)
            layout.addWidget(self)
            
            self.popout_window.finished.connect(self.return_to_main)
            self.popout_window.show()
            self.is_popout = True
        else:
            # Возвращаем в основное окно
            self.popout_window.close()
            
    def return_to_main(self):
        """Возврат камеры в основное окно"""
        self.is_popout = False
        self.popout_btn.setText("⬈")
        self.popout_btn.setToolTip("Вынести в отдельное окно")
        self.closed.emit(self.camera_id)


class MultiCameraView(QWidget):
    """Виджет для отображения нескольких камер"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.cameras = {}
        self.current_layout = "grid"  # grid, single, quad
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Панель управления
        control_layout = QHBoxLayout()
        
        # Выбор режима отображения
        self.layout_combo = QComboBox()
        self.layout_combo.addItems(["Сетка 2x2", "Одна камера", "Квадро"])
        self.layout_combo.setToolTip("Режим отображения камер")
        self.layout_combo.currentTextChanged.connect(self.change_layout)
        
        # Кнопки управления
        self.start_all_btn = QPushButton("▶️ Все камеры")
        self.start_all_btn.setToolTip("Запустить все камеры")
        self.stop_all_btn = QPushButton("⏹️ Все камеры")
        self.stop_all_btn.setToolTip("Остановить все камеры")
        
        control_layout.addWidget(QLabel("Режим:"))
        control_layout.addWidget(self.layout_combo)
        control_layout.addStretch()
        control_layout.addWidget(self.start_all_btn)
        control_layout.addWidget(self.stop_all_btn)
        
        layout.addLayout(control_layout)
        
        # Область отображения камер
        self.cameras_container = QWidget()
        self.cameras_layout = QGridLayout(self.cameras_container)
        self.cameras_layout.setSpacing(5)
        self.cameras_layout.setContentsMargins(0, 0, 0, 0)
        
        # Добавляем прокрутку
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(self.cameras_container)
        scroll_area.setStyleSheet("QScrollArea { border: none; }")
        
        layout.addWidget(scroll_area)
        
        # Подключаем сигналы
        self.start_all_btn.clicked.connect(self.start_all_cameras)
        self.stop_all_btn.clicked.connect(self.stop_all_cameras)
        
        # Создаем демо-камеры
        self.create_demo_cameras()
        
    def create_demo_cameras(self):
        """Создание демо-камер"""
        cameras = [
            ("cam1", "Камера 1 "),
            ("cam2", "Камера 2 "),
            ("cam3", "Камера 3 "),
            ("cam4", "Камера 4 ")
        ]
        
        for cam_id, cam_name in cameras:
            camera_widget = CameraWidget(cam_id, cam_name)
            camera_widget.closed.connect(self.on_camera_closed)
            self.cameras[cam_id] = camera_widget
            
        self.update_camera_layout()
        
    def update_camera_layout(self):
        """Обновление расположения камер"""
        # Очищаем layout
        for i in reversed(range(self.cameras_layout.count())): 
            self.cameras_layout.itemAt(i).widget().setParent(None)
            
        cameras_list = list(self.cameras.values())
        
        if self.current_layout == "grid" or self.current_layout == "Сетка 2x2":
            # Сетка 2x2
            for i, camera in enumerate(cameras_list):
                row = i // 2
                col = i % 2
                self.cameras_layout.addWidget(camera, row, col)
                
        elif self.current_layout == "single" or self.current_layout == "Одна камера":
            # Только первая камера крупно
            if cameras_list:
                self.cameras_layout.addWidget(cameras_list[0], 0, 0)
                
        elif self.current_layout == "quad" or self.current_layout == "Квадро":
            # Квадро-режим (одна большая, остальные маленькие)
            if cameras_list:
                self.cameras_layout.addWidget(cameras_list[0], 0, 0, 2, 2)  # Большая камера
                for i, camera in enumerate(cameras_list[1:], 1):
                    if i < 5:  # Максимум 4 дополнительные камеры
                        row = (i-1) // 2
                        col = (i-1) % 2
                        camera.setFixedSize(200, 150)
                        self.cameras_layout.addWidget(camera, row, col + 2)
        
    def change_layout(self, layout_name):
        """Изменение режима отображения"""
        layout_map = {
            "Сетка 2x2": "grid",
            "Одна камера": "single", 
            "Квадро": "quad"
        }
        self.current_layout = layout_map.get(layout_name, "grid")
        self.update_camera_layout()
        
    def start_all_cameras(self):
        """Запуск всех камер"""
        for camera_id, camera_widget in self.cameras.items():
            camera_widget.set_stream_active(True)
            # Имитация обновления FPS
            import random
            camera_widget.update_stream_info(random.randint(20, 30), "1920x1080")
            
    def stop_all_cameras(self):
        """Остановка всех камер"""
        for camera_id, camera_widget in self.cameras.items():
            camera_widget.set_stream_active(False)
            camera_widget.update_stream_info(0, "N/A")
            
    def on_camera_closed(self, camera_id):
        """Обработка закрытия камеры в отдельном окне"""
        # Камера вернулась в основное окно, обновляем layout
        self.update_camera_layout()


class VideoStreamWidget(QWidget):
    """Основной виджет системы видеонаблюдения"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(5)
        
        # Компактный заголовок
        header_layout = QHBoxLayout()
        
        title_label = QLabel("🎥 Система видеонаблюдения")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #2b579a;")
        
        status_label = QLabel("● Активна")
        status_label.setStyleSheet("color: #4CAF50; font-size: 12px;")
        
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        header_layout.addWidget(status_label)
        
        layout.addLayout(header_layout)
        
        # Создаем вкладки для разных режимов
        self.tabs = QTabWidget()
        
        # Вкладка многокамерного просмотра
        self.multi_camera_view = MultiCameraView()
        self.tabs.addTab(self.multi_camera_view, "👁️ Многокамерный просмотр")
        
        # Вкладка управления камерами
        self.management_tab = QWidget()
        self.setup_management_tab()
        self.tabs.addTab(self.management_tab, "⚙️ Управление камерами")
        
        layout.addWidget(self.tabs)
        
    def setup_management_tab(self):
        """Настройка вкладки управления камерами"""
        layout = QVBoxLayout(self.management_tab)
        
        # Группа настроек камер
        settings_group = QGroupBox("Настройки камер")
        settings_layout = QVBoxLayout()
        
        # Настройки записи
        record_layout = QHBoxLayout()
        record_layout.addWidget(QLabel("Автозапись:"))
        self.auto_record_combo = QComboBox()
        self.auto_record_combo.addItems(["Выключено", "При движении", "По расписанию", "Всегда"])
        record_layout.addWidget(self.auto_record_combo)
        record_layout.addStretch()
        
        # Настройки качества
        quality_layout = QHBoxLayout()
        quality_layout.addWidget(QLabel("Качество:"))
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["Высокое (1080p)", "Среднее (720p)", "Низкое (480p)"])
        quality_layout.addWidget(self.quality_combo)
        quality_layout.addStretch()
        
        settings_layout.addLayout(record_layout)
        settings_layout.addLayout(quality_layout)
        settings_group.setLayout(settings_layout)
        
        layout.addWidget(settings_group)
        
        self.stats_text = QTextEdit()
        self.stats_text.setPlainText(
            "Активные камеры: 4 из 4\n"
            "Общий FPS: 95\n"
            "Запись: 2.3 ГБ/день\n"
            "Доступно места: 245 ГБ\n"
            "Последнее движение: 2 мин назад"
        )
        self.stats_text.setReadOnly(True)
        self.stats_text.setMaximumHeight(120)

        layout.addWidget(self.stats_text)
        layout.addStretch()