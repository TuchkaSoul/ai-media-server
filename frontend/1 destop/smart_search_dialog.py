from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QTextEdit, QComboBox, QGroupBox, QGridLayout,
                             QDateEdit, QTimeEdit, QPushButton,QMessageBox, QLineEdit)
from PyQt5.QtCore import Qt,QDate, QTime
from PyQt5.QtGui import QFont

class SmartSearchDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔍 Интеллектуальный поиск")
        self.setGeometry(200, 200, 600, 400)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Заголовок
        title_label = QLabel("Интеллектуальный поиск")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # Типы поиска
        type_group = QGroupBox("Тип поиска")
        type_layout = QVBoxLayout()
        
        self.search_type = QComboBox()
        self.search_type.addItems([
            "🔍 Семантический поиск - Поиск по смыслу содержимого",
            "📝 Поиск по тексту - Поиск по распознанной речи", 
            "🎯 Поиск по объектам - Поиск конкретных объектов",
            "🎵 Поиск по звукам - Поиск по аудиособытиям"
        ])
        self.search_type.setToolTip("Выберите тип поиска в зависимости от ваших потребностей")
        type_layout.addWidget(self.search_type)
        type_group.setLayout(type_layout)
        layout.addWidget(type_group)
        
        # Поле поиска
        search_group = QGroupBox("Поисковый запрос")
        search_layout = QVBoxLayout()
        
        self.search_text = QTextEdit()
        self.search_text.setPlaceholderText("Опишите что вы ищете...\nНапример: 'люди на пляже в солнечный день'")
        self.search_text.setMaximumHeight(100)
        self.search_text.setToolTip("Введите текстовый запрос для семантического поиска")
        search_layout.addWidget(self.search_text)
        search_group.setLayout(search_layout)
        layout.addWidget(search_group)
        
        # Фильтры даты и времени
        date_group = QGroupBox("📅 Фильтр по дате и времени")
        date_layout = QGridLayout()
        
        # Дата начала
        date_layout.addWidget(QLabel("Дата начала:"), 0, 0)
        self.start_date = QDateEdit()
        self.start_date.setDate(QDate.currentDate())
        self.start_date.setCalendarPopup(True)
        self.start_date.setToolTip("Дата начала периода поиска")
        date_layout.addWidget(self.start_date, 0, 1)
        
        self.start_time = QTimeEdit()
        self.start_time.setTime(QTime(0, 0, 0))  # 00:00:00 по умолчанию
        self.start_time.setToolTip("Время начала периода поиска")
        date_layout.addWidget(self.start_time, 0, 2)
        
        # Дата окончания
        date_layout.addWidget(QLabel("Дата окончания:"), 1, 0)
        self.end_date = QDateEdit()
        self.end_date.setDate(QDate.currentDate())
        self.end_date.setCalendarPopup(True)
        self.end_date.setToolTip("Дата окончания периода поиска")
        date_layout.addWidget(self.end_date, 1, 1)
        
        self.end_time = QTimeEdit()
        self.end_time.setTime(QTime(23, 59, 59))  # 23:59:59 по умолчанию
        self.end_time.setToolTip("Время окончания периода поиска")
        date_layout.addWidget(self.end_time, 1, 2)
        
        date_group.setLayout(date_layout)
        layout.addWidget(date_group)
        
        # Дополнительные фильтры
        filters_group = QGroupBox("Дополнительные фильтры")
        filters_layout = QGridLayout()
        
        filters = [
            ("⏱️ Длительность от:", QLineEdit("0:00")),
            ("⏱️ Длительность до:", QLineEdit("30:00")),
            ("📏 Разрешение:", QComboBox()),
            ("🎞️ Формат:", QComboBox())
        ]
        
        filters[2][1].addItems(["Все", "720p", "1080p", "4K"])
        filters[2][1].setToolTip("Фильтр по разрешению видео")
        filters[3][1].addItems(["Все форматы", "MP4", "AVI", "MOV", "MKV"])
        filters[3][1].setToolTip("Фильтр по формату файла")
        
        for i, (label, widget) in enumerate(filters):
            filters_layout.addWidget(QLabel(label), i//2, (i%2)*2)
            widget.setToolTip(f"Фильтр: {label}")
            filters_layout.addWidget(widget, i//2, (i%2)*2+1)
            
        filters_group.setLayout(filters_layout)
        layout.addWidget(filters_group)
        
        # Кнопки
        button_layout = QHBoxLayout()
        
        search_btn = QPushButton("🔍 Найти")
        search_btn.setToolTip("Выполнить поиск по заданным критериям")
        clear_btn = QPushButton("🧹 Очистить")
        clear_btn.setToolTip("Очистить все поля формы")
        save_btn = QPushButton("💾 Сохранить поиск")
        save_btn.setToolTip("Сохранить параметры поиска для повторного использования")
        
        search_btn.setStyleSheet("background-color: #007acc; color: white; font-weight: bold;")
        
        button_layout.addWidget(save_btn)
        button_layout.addWidget(clear_btn)
        button_layout.addStretch()
        button_layout.addWidget(search_btn)
        
        layout.addLayout(button_layout)
        
        # Подключение сигналов
        search_btn.clicked.connect(self.perform_search)
        clear_btn.clicked.connect(self.clear_form)
        save_btn.clicked.connect(self.save_search)
        
    def perform_search(self):
        # Формируем строку с датами для отображения
        start_dt = f"{self.start_date.date().toString('dd.MM.yyyy')} {self.start_time.time().toString('hh:mm:ss')}"
        end_dt = f"{self.end_date.date().toString('dd.MM.yyyy')} {self.end_time.time().toString('hh:mm:ss')}"
        
        QMessageBox.information(
            self,
            "Результаты поиска",
            f"Поиск выполнен!\n\n"
            f"Период: с {start_dt} по {end_dt}\n"
            f"Тип поиска: {self.search_type.currentText()}\n\n"
            "В реальной системе будут показаны релевантные файлы\n"
            "на основе семантического анализа контента."
        )
        
    def clear_form(self):
        self.search_text.clear()
        self.search_type.setCurrentIndex(0)
        self.start_date.setDate(QDate.currentDate())
        self.start_time.setTime(QTime(0, 0, 0))
        self.end_date.setDate(QDate.currentDate())
        self.end_time.setTime(QTime(23, 59, 59))
        
    def save_search(self):
        QMessageBox.information(self, "Сохранение", "Параметры поиска сохранены")