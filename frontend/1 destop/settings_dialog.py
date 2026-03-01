import os
import configparser
from PyQt5.QtWidgets import (QWidget,QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QComboBox, QCheckBox,
                             QSpinBox, QListWidget, QTabWidget, QGroupBox,
                             QFormLayout, QTextEdit, QFileDialog, QMessageBox,
                             QInputDialog, QListWidgetItem)
from PyQt5.QtCore import Qt

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Настройки")
        self.setGeometry(200, 200, 600, 500)
        self.setup_ui()
        self.load_settings()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Вкладки настроек
        self.tabs = QTabWidget()
        
        # Основные настройки
        general_tab = QWidget()
        self.setup_general_tab(general_tab)
        self.tabs.addTab(general_tab, "Основные")
        
        # Настройки тегов
        tags_tab = QWidget()
        self.setup_tags_tab(tags_tab)
        self.tabs.addTab(tags_tab, "Теги")
        
        # Настройки поиска
        search_tab = QWidget()
        self.setup_search_tab(search_tab)
        self.tabs.addTab(search_tab, "Поиск")
        
        # Настройки интерфейса
        neuris_tab = QWidget()
        self.setup_neuros_tab(neuris_tab)
        self.tabs.addTab(neuris_tab, "Нейронные сети")
        
        # Настройки интерфейса
        interface_tab = QWidget()
        self.setup_interface_tab(interface_tab)
        self.tabs.addTab(interface_tab, "Интерфейс")
        
        layout.addWidget(self.tabs)
        
        # Кнопки
        button_layout = QHBoxLayout()
        
        reset_btn = QPushButton("Сброс")
        reset_btn.setToolTip("Вернуть настройки по умолчанию")
        reset_btn.clicked.connect(self.reset_settings)
        
        cancel_btn = QPushButton("Отмена")
        cancel_btn.clicked.connect(self.reject)
        
        save_btn = QPushButton("Сохранить")
        save_btn.setDefault(True)
        save_btn.clicked.connect(self.save_settings)
        
        button_layout.addWidget(reset_btn)
        button_layout.addStretch()
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(save_btn)
        
        layout.addLayout(button_layout)
        
    def setup_general_tab(self, parent):
        layout = QVBoxLayout(parent)
        
        # Хранилище
        storage_group = QGroupBox("Хранилище")
        storage_layout = QFormLayout()
        
        self.storage_path = QLineEdit()
        self.storage_path.setPlaceholderText("Путь к библиотеке")
        self.storage_path.setToolTip("Основная папка для хранения медиафайлов")
        
        browse_btn = QPushButton("Обзор")
        browse_btn.clicked.connect(self.browse_storage_path)
        
        path_layout = QHBoxLayout()
        path_layout.addWidget(self.storage_path)
        path_layout.addWidget(browse_btn)
        
        self.auto_cleanup = QCheckBox("Автоочистка временных файлов")
        self.auto_cleanup.setToolTip("Автоматически удалять временные файлы")
        
        self.cleanup_days = QSpinBox()
        self.cleanup_days.setRange(1, 365)
        self.cleanup_days.setSuffix(" дней")
        self.cleanup_days.setToolTip("Срок хранения временных файлов")
        
        storage_layout.addRow("Папка:", path_layout)
        storage_layout.addRow(self.auto_cleanup)
        storage_layout.addRow("Хранить файлы:", self.cleanup_days)
        
        storage_group.setLayout(storage_layout)
        layout.addWidget(storage_group)
        
        # Обработка
        processing_group = QGroupBox("Обработка")
        processing_layout = QFormLayout()
        
        self.auto_analysis = QCheckBox("Автоанализ новых файлов")
        self.auto_analysis.setToolTip("Автоматически анализировать новые файлы")
        
        self.max_file_size = QSpinBox()
        self.max_file_size.setRange(1, 10000)
        self.max_file_size.setSuffix(" МБ")
        self.max_file_size.setToolTip("Максимальный размер файла для анализа")
        
        self.parallel_processing = QSpinBox()
        self.parallel_processing.setRange(1, 16)
        self.parallel_processing.setSuffix(" потоков")
        self.parallel_processing.setToolTip("Количество потоков для обработки")
        
        processing_layout.addRow(self.auto_analysis)
        processing_layout.addRow("Макс. размер:", self.max_file_size)
        processing_layout.addRow("Потоки:", self.parallel_processing)
        
        processing_group.setLayout(processing_layout)
        layout.addWidget(processing_group)
        
        layout.addStretch()
        
    def setup_tags_tab(self, parent):
        layout = QVBoxLayout(parent)
        
        # Теги
        tags_group = QGroupBox("Пользовательские теги")
        tags_layout = QVBoxLayout()
        
        self.tags_list = QListWidget()
        self.tags_list.setToolTip("Список пользовательских тегов")
        
        tags_buttons_layout = QHBoxLayout()
        add_tag_btn = QPushButton("Добавить")
        add_tag_btn.setToolTip("Добавить новый тег")
        edit_tag_btn = QPushButton("Изменить")
        edit_tag_btn.setToolTip("Изменить выбранный тег")
        remove_tag_btn = QPushButton("Удалить")
        remove_tag_btn.setToolTip("Удалить выбранный тег")
        
        add_tag_btn.clicked.connect(self.add_tag)
        edit_tag_btn.clicked.connect(self.edit_tag)
        remove_tag_btn.clicked.connect(self.remove_tag)
        
        tags_buttons_layout.addWidget(add_tag_btn)
        tags_buttons_layout.addWidget(edit_tag_btn)
        tags_buttons_layout.addWidget(remove_tag_btn)
        tags_buttons_layout.addStretch()
        
        tags_layout.addWidget(QLabel("Мои теги:"))
        tags_layout.addWidget(self.tags_list)
        tags_layout.addLayout(tags_buttons_layout)
        tags_group.setLayout(tags_layout)
        layout.addWidget(tags_group)
        
        # Автотеги
        auto_tag_group = QGroupBox("Автоматическое тегирование")
        auto_tag_layout = QFormLayout()
        
        self.auto_tagging = QCheckBox("Включить автотегирование")
        self.auto_tagging.setToolTip("Автоматически добавлять теги к файлам")
        
        self.tag_confidence = QSpinBox()
        self.tag_confidence.setRange(1, 100)
        self.tag_confidence.setSuffix("%")
        self.tag_confidence.setToolTip("Минимальная уверенность для автотегирования")
        
        auto_tag_layout.addRow(self.auto_tagging)
        auto_tag_layout.addRow("Уверенность:", self.tag_confidence)
        
        auto_tag_group.setLayout(auto_tag_layout)
        layout.addWidget(auto_tag_group)
        
        layout.addStretch()
        
    def setup_search_tab(self, parent):
        layout = QVBoxLayout(parent)
        
        # История
        history_group = QGroupBox("История поиска")
        history_layout = QFormLayout()
        
        self.save_search_history = QCheckBox("Сохранять историю")
        self.save_search_history.setToolTip("Сохранять историю поисковых запросов")
        
        self.search_history_limit = QSpinBox()
        self.search_history_limit.setRange(10, 1000)
        self.search_history_limit.setSuffix(" записей")
        self.search_history_limit.setToolTip("Максимальное количество записей в истории")
        
        self.clear_history_btn = QPushButton("Очистить историю")
        self.clear_history_btn.clicked.connect(self.clear_search_history)
        
        history_layout.addRow(self.save_search_history)
        history_layout.addRow("Лимит:", self.search_history_limit)
        history_layout.addRow(self.clear_history_btn)
        
        history_group.setLayout(history_layout)
        layout.addWidget(history_group)
        
        # Поиск
        search_config_group = QGroupBox("Настройки поиска")
        search_config_layout = QFormLayout()
        
        self.fuzzy_search = QCheckBox("Нечеткий поиск")
        self.fuzzy_search.setToolTip("Искать похожие варианты запроса")
        
        self.search_timeout = QSpinBox()
        self.search_timeout.setRange(1, 60)
        self.search_timeout.setSuffix(" сек.")
        self.search_timeout.setToolTip("Максимальное время выполнения поиска")
        
        self.default_search_type = QComboBox()
        self.default_search_type.addItems(["Семантический", "По тегам", "По метаданным", "По содержанию"])
        self.default_search_type.setToolTip("Тип поиска по умолчанию")
        
        search_config_layout.addRow(self.fuzzy_search)
        search_config_layout.addRow("Таймаут:", self.search_timeout)
        search_config_layout.addRow("Тип:", self.default_search_type)
        
        search_config_group.setLayout(search_config_layout)
        layout.addWidget(search_config_group)
        
        layout.addStretch()
        
    def setup_interface_tab(self, parent):
        layout = QVBoxLayout(parent)
        
        # Внешний вид
        appearance_group = QGroupBox("Внешний вид")
        appearance_layout = QFormLayout()
        
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Светлая", "Темная", "Системная"])
        self.theme_combo.setToolTip("Цветовая тема интерфейса")
        
        self.language_combo = QComboBox()
        self.language_combo.addItems(["Русский", "Английский"])
        self.language_combo.setToolTip("Язык интерфейса")
        
        self.font_size = QSpinBox()
        self.font_size.setRange(8, 20)
        self.font_size.setSuffix(" pt")
        self.font_size.setToolTip("Размер шрифта интерфейса")
        
        appearance_layout.addRow("Тема:", self.theme_combo)
        appearance_layout.addRow("Язык:", self.language_combo)
        appearance_layout.addRow("Шрифт:", self.font_size)
        
        appearance_group.setLayout(appearance_layout)
        layout.addWidget(appearance_group)
        
        # Уведомления (сгруппированные)
        notifications_group = QGroupBox("Уведомления")
        notifications_layout = QVBoxLayout()
        
        self.notify_completion = QCheckBox("Завершение операций")
        self.notify_completion.setToolTip("Уведомлять о завершении анализа и загрузки файлов")
        
        self.notify_errors = QCheckBox("Ошибки")
        self.notify_errors.setToolTip("Уведомлять об ошибках в системе")
        
        notifications_layout.addWidget(self.notify_completion)
        notifications_layout.addWidget(self.notify_errors)
        
        notifications_group.setLayout(notifications_layout)
        layout.addWidget(notifications_group)
        
        layout.addStretch()
        
    def setup_neuros_tab(self, parent):
        layout = QVBoxLayout(parent)
        
        # Основные модели нейросетей
        models_group = QGroupBox("Основные модели")
        models_layout = QFormLayout()
        
        self.detection_model = QComboBox()
        self.detection_model.addItems(["YOLOv8", "YOLOv7", "Faster R-CNN"])
        self.detection_model.setToolTip("Модель для обнаружения объектов")
        
        self.semantic_model = QComboBox()
        self.semantic_model.addItems(["CLIP", "OpenCLIP", "Custom Model"])
        self.semantic_model.setToolTip("Модель для семантического поиска")
        
        self.audio_model = QComboBox()
        self.audio_model.addItems(["Whisper Large", "Whisper Medium", "Whisper Small"])
        self.audio_model.setToolTip("Модель для распознавания речи")
        
        models_layout.addRow("Детекция:", self.detection_model)
        models_layout.addRow("Семантический поиск:", self.semantic_model)
        models_layout.addRow("Транскрибация:", self.audio_model)
        
        models_group.setLayout(models_layout)
        layout.addWidget(models_group)
        
        # Настройки производительности
        performance_group = QGroupBox("Производительность")
        performance_layout = QFormLayout()
        
        self.gpu_acceleration = QCheckBox("Использовать GPU")
        self.gpu_acceleration.setToolTip("Аппаратное ускорение на видеокарте")
        
        self.batch_size = QSpinBox()
        self.batch_size.setRange(1, 16)
        self.batch_size.setValue(4)
        self.batch_size.setSuffix(" файлов")
        self.batch_size.setToolTip("Количество файлов для параллельной обработки")
        
        self.model_precision = QComboBox()
        self.model_precision.addItems(["FP32", "FP16", "INT8"])
        self.model_precision.setToolTip("Точность вычислений моделей")
        
        performance_layout.addRow(self.gpu_acceleration)
        performance_layout.addRow("Размер батча:", self.batch_size)
        performance_layout.addRow("Точность:", self.model_precision)
        
        performance_group.setLayout(performance_layout)
        layout.addWidget(performance_group)
        
        # Параметры обработки
        processing_group = QGroupBox("Параметры обработки")
        processing_layout = QFormLayout()
        
        self.detection_confidence = QSpinBox()
        self.detection_confidence.setRange(1, 100)
        self.detection_confidence.setValue(70)
        self.detection_confidence.setSuffix("%")
        self.detection_confidence.setToolTip("Минимальная уверенность детекции")
        
        self.auto_detection = QCheckBox("Автоматическая детекция")
        self.auto_detection.setToolTip("Автоматически обнаруживать объекты")
        
        self.audio_language = QComboBox()
        self.audio_language.addItems(["Авто", "Русский", "Английский"])
        self.audio_language.setToolTip("Язык для распознавания речи")
        
        processing_layout.addRow("Уверенность:", self.detection_confidence)
        processing_layout.addRow(self.auto_detection)
        processing_layout.addRow("Язык аудио:", self.audio_language)
        
        processing_group.setLayout(processing_layout)
        layout.addWidget(processing_group)
        
        # Управление моделями
        management_group = QGroupBox("Управление моделями")
        management_layout = QHBoxLayout()
        
        self.download_btn = QPushButton("Загрузить модели")
        self.download_btn.setToolTip("Загрузить выбранные модели")
        
        self.test_btn = QPushButton("Тестировать")
        self.test_btn.setToolTip("Протестировать производительность")
        
        management_layout.addWidget(self.download_btn)
        management_layout.addWidget(self.test_btn)
        management_layout.addStretch()
        
        management_group.setLayout(management_layout)
        layout.addWidget(management_group)
        
        # Статус
        status_group = QGroupBox("Статус моделей")
        status_layout = QVBoxLayout()
        
        self.models_status = QTextEdit()
        self.models_status.setMaximumHeight(80)
        self.models_status.setReadOnly(True)
        self.models_status.setPlainText("YOLOv8: ✅ Загружена\nCLIP: ✅ Загружена\nWhisper: ⏳ Загрузка...")
        
        status_layout.addWidget(self.models_status)
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)
        
        layout.addStretch()
        
        # Подключаем сигналы
        self.download_btn.clicked.connect(self.download_neural_models)
        self.test_btn.clicked.connect(self.test_neural_models)

    def download_neural_models(self):
        """Загрузка нейросетевых моделей"""
        QMessageBox.information(self, "Загрузка", "Начата загрузка выбранных моделей...")

    def test_neural_models(self):
        """Тестирование нейросетевых моделей"""
        QMessageBox.information(self, "Тестирование", "Запущено тестирование моделей...") 
        
    def browse_storage_path(self):
        path = QFileDialog.getExistingDirectory(self, "Выберите папку для хранения")
        if path:
            self.storage_path.setText(path)
            
    def add_tag(self):
        tag, ok = QInputDialog.getText(self, "Добавить тег", "Введите название тега:")
        if ok and tag:
            self.tags_list.addItem(tag)
            
    def edit_tag(self):
        current_item = self.tags_list.currentItem()
        if current_item:
            new_tag, ok = QInputDialog.getText(self, "Изменить тег", "Введите новое название:", text=current_item.text())
            if ok and new_tag:
                current_item.setText(new_tag)
                
    def remove_tag(self):
        current_row = self.tags_list.currentRow()
        if current_row >= 0:
            self.tags_list.takeItem(current_row)
            
    def clear_search_history(self):
        reply = QMessageBox.question(self, "Очистка истории", "Очистить историю поиска?")
        if reply == QMessageBox.Yes:
            if hasattr(self.parent, 'search_history'):
                self.parent.search_history.clear()
            QMessageBox.information(self, "Готово", "История поиска очищена")
            
    def load_settings(self):
        """Загрузка настроек из конфигурации"""
        try:
            config = configparser.ConfigParser()
            if os.path.exists('mediaflow_config.ini'):
                config.read('mediaflow_config.ini')
                
                if 'General' in config:
                    self.storage_path.setText(config['General'].get('storage_path', ''))
                    self.auto_cleanup.setChecked(config['General'].getboolean('auto_cleanup', True))
                    self.cleanup_days.setValue(config['General'].getint('cleanup_days', 30))
                    
                if 'Processing' in config:
                    self.auto_analysis.setChecked(config['Processing'].getboolean('auto_analysis', True))
                    self.max_file_size.setValue(config['Processing'].getint('max_file_size', 500))
                    self.parallel_processing.setValue(config['Processing'].getint('parallel_processing', 4))
                    
                if 'Tags' in config:
                    tags = config['Tags'].get('user_tags', '').split(';')
                    for tag in tags:
                        if tag:
                            self.tags_list.addItem(tag)
                    self.auto_tagging.setChecked(config['Tags'].getboolean('auto_tagging', True))
                    self.tag_confidence.setValue(config['Tags'].getint('tag_confidence', 80))
                    
                if 'Search' in config:
                    self.save_search_history.setChecked(config['Search'].getboolean('save_history', True))
                    self.search_history_limit.setValue(config['Search'].getint('history_limit', 100))
                    self.fuzzy_search.setChecked(config['Search'].getboolean('fuzzy_search', True))
                    self.search_timeout.setValue(config['Search'].getint('search_timeout', 10))
                    
                if 'Interface' in config:
                    self.theme_combo.setCurrentText(config['Interface'].get('theme', 'Светлая'))
                    self.language_combo.setCurrentText(config['Interface'].get('language', 'Русский'))
                    self.font_size.setValue(config['Interface'].getint('font_size', 10))
                    self.notify_completion.setChecked(config['Interface'].getboolean('notify_completion', True))
                    self.notify_errors.setChecked(config['Interface'].getboolean('notify_errors', True))
                    
        except Exception as e:
            print(f"Ошибка загрузки настроек: {e}")
            
    def save_settings(self):
        """Сохранение настроек в конфигурацию"""
        try:
            config = configparser.ConfigParser()
            
            config['General'] = {
                'storage_path': self.storage_path.text(),
                'auto_cleanup': str(self.auto_cleanup.isChecked()),
                'cleanup_days': str(self.cleanup_days.value())
            }
            
            config['Processing'] = {
                'auto_analysis': str(self.auto_analysis.isChecked()),
                'max_file_size': str(self.max_file_size.value()),
                'parallel_processing': str(self.parallel_processing.value())
            }
            
            user_tags = []
            for i in range(self.tags_list.count()):
                user_tags.append(self.tags_list.item(i).text())
            config['Tags'] = {
                'user_tags': ';'.join(user_tags),
                'auto_tagging': str(self.auto_tagging.isChecked()),
                'tag_confidence': str(self.tag_confidence.value())
            }
            
            config['Search'] = {
                'save_history': str(self.save_search_history.isChecked()),
                'history_limit': str(self.search_history_limit.value()),
                'fuzzy_search': str(self.fuzzy_search.isChecked()),
                'search_timeout': str(self.search_timeout.value()),
                'default_search_type': self.default_search_type.currentText()
            }
            
            config['Interface'] = {
                'theme': self.theme_combo.currentText(),
                'language': self.language_combo.currentText(),
                'font_size': str(self.font_size.value()),
                'notify_completion': str(self.notify_completion.isChecked()),
                'notify_errors': str(self.notify_errors.isChecked())
            }
            
            config['NeuralNetworks'] = {
                'detection_model': self.detection_model.currentText(),
                'semantic_model': self.semantic_model.currentText(),
                'audio_model': self.audio_model.currentText(),
                'gpu_acceleration': str(self.gpu_acceleration.isChecked()),
                'batch_size': str(self.batch_size.value()),
                'model_precision': self.model_precision.currentText(),
                'detection_confidence': str(self.detection_confidence.value()),
                'auto_detection': str(self.auto_detection.isChecked()),
                'audio_language': self.audio_language.currentText()
            }
            
            
            
            with open('mediaflow_config.ini', 'w') as configfile:
                config.write(configfile)
                
            QMessageBox.information(self, "Сохранено", "Настройки сохранены")
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка сохранения: {e}")
            
    def reset_settings(self):
        """Сброс настроек к значениям по умолчанию"""
        reply = QMessageBox.question(self, "Сброс настроек", 
                                   "Сбросить все настройки?")
        if reply == QMessageBox.Yes:
            self.storage_path.clear()
            self.auto_cleanup.setChecked(True)
            self.cleanup_days.setValue(30)
            self.auto_analysis.setChecked(True)
            self.max_file_size.setValue(500)
            self.parallel_processing.setValue(4)
            self.tags_list.clear()
            self.auto_tagging.setChecked(True)
            self.tag_confidence.setValue(80)
            self.save_search_history.setChecked(True)
            self.search_history_limit.setValue(100)
            self.fuzzy_search.setChecked(True)
            self.search_timeout.setValue(10)
            self.theme_combo.setCurrentText("Светлая")
            self.language_combo.setCurrentText("Русский")
            self.font_size.setValue(10)
            self.notify_completion.setChecked(True)
            self.notify_errors.setChecked(True)
            self.detection_model.setCurrentIndex(0)
            self.semantic_model.setCurrentIndex(0)
            self.audio_model.setCurrentIndex(0)
            self.gpu_acceleration.setChecked(True)
            self.batch_size.setValue(4)
            self.model_precision.setCurrentIndex(1)  # FP16
            self.detection_confidence.setValue(70)
            self.auto_detection.setChecked(True)
            self.audio_language.setCurrentIndex(0)