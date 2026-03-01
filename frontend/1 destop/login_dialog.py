import sys
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QComboBox, QProgressBar,
                             QMessageBox, QFormLayout)
from PyQt5.QtCore import Qt, QTimer

class LoginDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("MediaFlow Desktop - Вход в систему")
        self.setGeometry(300, 300, 400, 300)
        self.setModal(True)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Заголовок
        title_label = QLabel("MediaFlow Desktop")
        title_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #007acc; margin: 20px;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # Форма входа
        form_layout = QFormLayout()
        
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Введите имя пользователя")
        self.username_input.setStyleSheet("padding: 8px; border: 1px solid #ccc; border-radius: 4px;")
        
        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Введите пароль")
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setStyleSheet("padding: 8px; border: 1px solid #ccc; border-radius: 4px;")
        
        self.server_combo = QComboBox()
        self.server_combo.addItems(["Основной сервер", "Резервный сервер", "Локальный сервер"])
        self.server_combo.setStyleSheet("padding: 8px; border: 1px solid #ccc; border-radius: 4px;")
        self.server_combo.setToolTip("Выберите сервер для подключения")
        
        form_layout.addRow("👤 Имя пользователя:", self.username_input)
        form_layout.addRow("🔒 Пароль:", self.password_input)
        form_layout.addRow("🌐 Сервер:", self.server_combo)
        
        layout.addLayout(form_layout)
        
        # Кнопки
        button_layout = QHBoxLayout()
        
        self.login_btn = QPushButton("Войти в систему")
        self.login_btn.setStyleSheet("""
            QPushButton {
                background-color: #007acc;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #005a9e;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)
        self.login_btn.clicked.connect(self.start_login)
        
        cancel_btn = QPushButton("Отмена")
        cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #007acc;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: red;
            }
            QPushButton:disabled {
                background-color: red;
            }
        """)
        cancel_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(self.login_btn)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        
        # Прогресс бар
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        
        # Статус
        self.status_label = QLabel("Готов к подключению...")
        self.status_label.setStyleSheet("color: #666; font-size: 12px;")
        layout.addWidget(self.status_label)
        
    def start_login(self):
        """Запуск процесса входа"""
        if not self.username_input.text() or not self.password_input.text():
            QMessageBox.warning(self, "Ошибка", "Пожалуйста, заполните все поля")
            return
            
        self.login_btn.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_label.setText("Подключение к серверу...")
        
        # Имитация подключения
        self.progress_timer = QTimer()
        self.progress_timer.timeout.connect(self.update_progress)
        self.progress_value = 0
        self.progress_timer.start(50)
        
    def update_progress(self):
        """Обновление прогресса подключения"""
        self.progress_value += 2
        self.progress_bar.setValue(self.progress_value)
        
        if self.progress_value >= 100:
            self.progress_timer.stop()
            self.status_label.setText("✅ Успешный вход!")
            QTimer.singleShot(500, self.accept)