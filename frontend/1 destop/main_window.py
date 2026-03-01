import sys
import os
import configparser
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QPushButton, QTreeWidget, QTreeWidgetItem, QTabWidget,
                             QListWidget, QListWidgetItem, QTableWidget, QTableWidgetItem,
                             QTextEdit, QLineEdit, QComboBox, QCheckBox, QGroupBox,
                             QSplitter, QFrame, QScrollArea, QGridLayout, QToolBar,
                             QStatusBar, QMessageBox, QFileDialog, QDialog, QProgressBar,
                             QToolButton, QMenu, QAction, QSystemTrayIcon, QProgressDialog,
                             QActionGroup, QFormLayout)
from PyQt5.QtCore import Qt, QSize, QTimer, QDateTime
from PyQt5.QtGui import QIcon, QFont, QPixmap

# Импортируем наши модули
from login_dialog import LoginDialog
from settings_dialog import SettingsDialog
from video_stream_widget import VideoStreamWidget
from smart_search_dialog import SmartSearchDialog

class ModernMediaFlowDesktop(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MediaFlow Desktop - Intelligent Media Storage")
        self.setGeometry(100, 100, 1400, 900)
        
        # Инициализация конфигурации
        self.config = configparser.ConfigParser()
        self.load_config()
        
        # Данные приложения
        self.files = [
            {"name": "beach_day.mp4", "duration": "00:45", "type": "📹 Видео", "resolution": "1920x1080", "size": "45 МБ", "date": "2024-01-15", "tags": ["пляж", "море", "отдых"], "path": "/Медиатека/Видео/beach_day.mp4", "codec": "H.264", "bitrate": "8 Мбит/с", "fps": "30"},
            {"name": "interview_2024.mov", "duration": "12:30", "type": "📹 Видео", "resolution": "3840x2160", "size": "1.2 ГБ", "date": "2024-01-14", "tags": ["интервью", "люди", "офис"], "path": "/Медиатека/Видео/interview_2024.mov", "codec": "H.265", "bitrate": "25 Мбит/с", "fps": "24"},
            {"name": "presentation.avi", "duration": "08:15", "type": "📹 Видео", "resolution": "1280x720", "size": "320 МБ", "date": "2024-01-13", "tags": ["презентация", "работа", "документы"], "path": "/Медиатека/Видео/presentation.avi", "codec": "MPEG-4", "bitrate": "5 Мбит/с", "fps": "25"},
        ]
        
        self.current_file = None
        self.search_history = []
        
        self.setup_ui()

    def load_config(self):
        """Загрузка конфигурации"""
        try:
            if os.path.exists('mediaflow_config.ini'):
                self.config.read('mediaflow_config.ini')
        except Exception as e:
            print(f"Ошибка загрузки конфигурации: {e}")
    
    def save_config(self):
        """Сохранение конфигурации"""
        try:
            with open('mediaflow_config.ini', 'w') as configfile:
                self.config.write(configfile)
        except Exception as e:
            print(f"Ошибка сохранения конфигурации: {e}")
    
    def center_window(self):
        """Центрирование окна на экране"""
        screen = QApplication.primaryScreen().geometry()
        size = self.geometry()
        self.move((screen.width() - size.width()) // 2, (screen.height() - size.height()) // 2)
        
            
    def setup_ui(self):
        # ... код setup_ui с ВСЕМИ необходимыми методами:
        
        self.setup_menubar()
        self.setup_toolbars()
        self.setup_main_content()  # этот метод должен вызывать setup_central_panel
        self.setup_statusbar()
        
        QTimer.singleShot(100, self.initialize_statusbar)
        
    def initialize_statusbar(self):
        """Инициализация статусной панели после загрузки"""
        # Обновляем информацию о файлах
        self.update_statusbar(
            files_count=len(self.files),
            camera_count=1  # По умолчанию одна камера
        )

    def setup_main_content(self):
        """Настройка основного контента"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Основной layout
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        
        # Разделитель для левой панели и основного контента
        main_splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(main_splitter)
        
        # Левая панель навигации
        self.setup_navigation_panel(main_splitter)
        
        # Центральная панель с вкладками
        self.setup_central_panel(main_splitter)
        
        # Правая панель деталей
        self.setup_details_panel(main_splitter)
        
        # Установка пропорций
        main_splitter.setSizes([250, 600, 300])

    def setup_central_panel(self, parent):
        """Настройка центральной панели"""
        self.central_tabs = QTabWidget()
        
        # Вкладка сетки
        self.grid_tab = QWidget()
        self.setup_grid_view()  # УБЕДИТЕСЬ ЧТО ЭТОТ МЕТОД СУЩЕСТВУЕТ
        self.central_tabs.addTab(self.grid_tab, "🖼️ Сетка")
        
        # Вкладка списка
        self.list_tab = QWidget()
        self.setup_list_view()  # УБЕДИТЕСЬ ЧТО ЭТОТ МЕТОД СУЩЕСТВУЕТ
        self.central_tabs.addTab(self.list_tab, "📋 Таблица")
        
        # Вкладка загрузки
        self.upload_tab = QWidget()
        self.setup_upload_view()  # УБЕДИТЕСЬ ЧТО ЭТОТ МЕТОД СУЩЕСТВУЕТ
        self.central_tabs.addTab(self.upload_tab, "📤 Загрузка")
        
        # Вкладка видеопотока (обновленная)
        self.video_stream_tab = VideoStreamWidget()
        self.central_tabs.addTab(self.video_stream_tab, "📹 Видеонаблюдение")
        
        parent.addWidget(self.central_tabs)

    # ДОБАВЬТЕ ЭТИ МЕТОДЫ ЕСЛИ ИХ НЕТ:
    def setup_grid_view(self):
        """Настройка представления в виде сетки"""
        layout = QVBoxLayout(self.grid_tab)
        
        # Панель управления
        control_layout = QHBoxLayout()
        control_layout.addWidget(QLabel("Мои файлы"))
        control_layout.addStretch()
        
        refresh_btn = QPushButton("🔄 Обновить")
        refresh_btn.setToolTip("Обновить список файлов")
        analyze_btn = QPushButton("📊 Анализировать все")
        analyze_btn.setToolTip("Запустить анализ всех файлов")
        
        refresh_btn.clicked.connect(self.refresh_files)
        analyze_btn.clicked.connect(self.analyze_all_files)
        
        control_layout.addWidget(refresh_btn)
        control_layout.addWidget(analyze_btn)
        layout.addLayout(control_layout)
        
        # Область с прокруткой для сетки
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        self.grid_layout = QGridLayout(scroll_widget)
        self.grid_layout.setSpacing(15)
        self.grid_layout.setAlignment(Qt.AlignTop)
        
        self.create_file_cards()
        
        scroll_area.setWidget(scroll_widget)
        scroll_area.setWidgetResizable(True)
        layout.addWidget(scroll_area)

    def create_file_cards(self):
        """Создание карточек файлов в сетке"""
        # Очищаем существующие карточки
        for i in reversed(range(self.grid_layout.count())): 
            widget = self.grid_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
                
        # Создаем новые карточки
        for i, file_info in enumerate(self.files):
            card = self.create_file_card(file_info)
            row = i // 2
            col = i % 2
            self.grid_layout.addWidget(card, row, col)

    def create_file_card(self, file_info):
        """Создание карточки файла"""
        card = QFrame()
        card.setFrameStyle(QFrame.Box)
        card.setStyleSheet("""
            QFrame {
                background-color: white;
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 15px;
                margin: 5px;
            }
            QFrame:hover {
                background-color: #f8f9fa;
                border: 2px solid #007acc;
            }
        """)
        card.setFixedSize(320, 240)
        
        layout = QVBoxLayout(card)
        layout.setSpacing(8)
        
        # Заголовок с иконкой типа файла
        header_layout = QHBoxLayout()
        
        type_label = QLabel(file_info["type"].split()[0])
        type_label.setStyleSheet("font-size: 24px;")
        
        name_label = QLabel(file_info["name"])
        name_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        name_label.setWordWrap(True)
        name_label.setMaximumHeight(40)
        
        header_layout.addWidget(type_label)
        header_layout.addWidget(name_label)
        header_layout.addStretch()
        
        layout.addLayout(header_layout)
        
        # Миниатюра
        thumb_label = QLabel("🎬")
        thumb_label.setAlignment(Qt.AlignCenter)
        thumb_label.setStyleSheet("font-size: 56px; padding: 12px; background-color: #f0f0f0; border-radius: 6px;")
        thumb_label.setMinimumHeight(100)
        layout.addWidget(thumb_label)
        
        # Информация о файле
        info_layout = QVBoxLayout()
        
        duration_label = QLabel(f"⏱️ {file_info['duration']} • 📏 {file_info['resolution']}")
        duration_label.setStyleSheet("color: #666; font-size: 12px;")
        
        size_label = QLabel(f"💾 {file_info['size']} • 📅 {file_info['date']}")
        size_label.setStyleSheet("color: #666; font-size: 12px;")
        
        info_layout.addWidget(duration_label)
        info_layout.addWidget(size_label)
        layout.addLayout(info_layout)
        
        # Теги
        tags_text = " ".join([f"#{tag}" for tag in file_info["tags"][:3]])
        tags_label = QLabel(tags_text)
        tags_label.setStyleSheet("color: #007acc; font-size: 11px; background-color: #e3f2fd; padding: 2px 6px; border-radius: 3px;")
        tags_label.setWordWrap(True)
        tags_label.setMaximumHeight(30)
        layout.addWidget(tags_label)
        
        # Кнопки действий
        actions_layout = QHBoxLayout()
        
        view_btn = QPushButton("👁️ Просмотр")
        view_btn.setToolTip("Просмотреть файл")
        tag_btn = QPushButton("🏷️ Теги")
        tag_btn.setToolTip("Управление тегами")
        analyze_btn = QPushButton("📊 Анализ")
        analyze_btn.setToolTip("Анализировать файл")
        
        for btn in [view_btn, tag_btn, analyze_btn]:
            btn.setFixedSize(85, 30)
            btn.setStyleSheet("""
                QPushButton {
                    font-size: 11px;
                    padding: 4px;
                    border: 1px solid #ccc;
                    border-radius: 4px;
                    background-color: #f8f9fa;
                }
                QPushButton:hover {
                    background-color: #e9ecef;
                    border-color: #007acc;
                }
            """)
                
        view_btn.clicked.connect(lambda checked, fi=file_info: self.view_file(fi))
        tag_btn.clicked.connect(lambda checked, fi=file_info: self.tag_file(fi))
        analyze_btn.clicked.connect(lambda checked, fi=file_info: self.analyze_file(fi))
        
        actions_layout.addWidget(view_btn)
        actions_layout.addWidget(tag_btn)
        actions_layout.addWidget(analyze_btn)
        actions_layout.addStretch()
        
        layout.addLayout(actions_layout)
        
        # Устанавливаем обработчик клика для выбора файла
        card.mousePressEvent = lambda event, fi=file_info: self.select_file(fi)
        
        return card

    def setup_list_view(self):
        """Настройка представления в виде списка"""
        layout = QVBoxLayout(self.list_tab)
        
        # Таблица файлов
        self.file_table = QTableWidget()
        self.file_table.setColumnCount(6)
        self.file_table.setHorizontalHeaderLabels(["Имя файла", "Тип", "Длительность", "Разрешение", "Размер", "Дата"])
        self.file_table.setToolTip("Табличное представление файлов. Двойной клик для просмотра.")
        
        # Заполняем таблицу
        self.update_file_table()
            
        # Настройка таблицы
        self.file_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.file_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.file_table.doubleClicked.connect(self.on_file_double_click)
        self.file_table.itemSelectionChanged.connect(self.on_table_selection_changed)
        
        layout.addWidget(self.file_table)

    def setup_upload_view(self):
        """Настройка панели загрузки"""
        layout = QVBoxLayout(self.upload_tab)
        
        # Область перетаскивания
        drop_frame = QFrame()
        drop_frame.setFrameStyle(QFrame.Box)
        drop_frame.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border: 2px dashed #dee2e6;
                border-radius: 10px;
            }
            QFrame:hover {
                background-color: #e9ecef;
                border: 2px dashed #007acc;
            }
        """)
        drop_frame.setMinimumHeight(400)
        
        drop_layout = QVBoxLayout(drop_frame)
        drop_layout.setAlignment(Qt.AlignCenter)
        
        # Иконка и текст
        icon_label = QLabel("📤")
        icon_label.setStyleSheet("font-size: 60px;")
        icon_label.setAlignment(Qt.AlignCenter)
        drop_layout.addWidget(icon_label)
        
        text_label = QLabel("Перетащите файлы сюда")
        text_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        text_label.setAlignment(Qt.AlignCenter)
        drop_layout.addWidget(text_label)
        
        subtext_label = QLabel("или")
        subtext_label.setStyleSheet("color: #666;")
        subtext_label.setAlignment(Qt.AlignCenter)
        drop_layout.addWidget(subtext_label)
        
        # Кнопка выбора файлов
        browse_btn = QPushButton("Выбрать файлы на компьютере")
        browse_btn.setToolTip("Выберите медиафайлы для загрузки в систему")
        browse_btn.setStyleSheet("""
            QPushButton {
                background-color: #007acc;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #005a9e;
            }
        """)
        browse_btn.clicked.connect(self.import_files)
        drop_layout.addWidget(browse_btn, 0, Qt.AlignCenter)
        
        layout.addWidget(drop_frame)
    def toggle_toolbar_visibility(self, checked):
        """Переключение видимости панели инструментов"""
        if checked:
            # Скрыть все панели
            self.top_toolbar.setVisible(False)
            self.bottom_toolbar.setVisible(False)
            self.toolbar_hidden_action.setChecked(True)
            self.toolbar_top_action.setEnabled(False)
            self.toolbar_bottom_action.setEnabled(False)
        else:
            # Показать панель в текущем положении
            if self.toolbar_top_action.isChecked():
                self.set_toolbar_position('top')
            else:
                self.set_toolbar_position('bottom')
            self.toolbar_hidden_action.setChecked(False)
            self.toolbar_top_action.setEnabled(True)
            self.toolbar_bottom_action.setEnabled(True)
    def setup_menubar(self):
        """Настройка меню"""
        menubar = self.menuBar()
        
        # Меню Файл
        file_menu = menubar.addMenu('Файл')
        file_menu.addAction('📁 Импорт', self.import_files, "Ctrl+I")
        file_menu.addAction('💾 Экспорт', self.export_data, "Ctrl+E")
        file_menu.addSeparator()
        file_menu.addAction('⚙️ Настройки', self.show_settings, "Ctrl+,")
        file_menu.addSeparator()
        file_menu.addAction('🚪 Выход', self.close, "Ctrl+Q")
        
        # Меню Вид
        view_menu = menubar.addMenu('Вид')
        view_menu.addAction('🖼️ Сетка', lambda: self.change_view('grid'), "F1")
        view_menu.addAction('📋 Таблица', lambda: self.change_view('list'), "F2")
        view_menu.addSeparator()
        
        
        # Подменю для панели инструментов
        toolbar_menu = view_menu.addMenu('🎛️ Панель инструментов')
        
        self.toolbar_top_action = QAction('⬆️ Вверху', self)
        self.toolbar_top_action.setCheckable(True)
        self.toolbar_top_action.triggered.connect(lambda: self.set_toolbar_position('top'))
        
        self.toolbar_bottom_action = QAction('⬇️ Внизу', self)
        self.toolbar_bottom_action.setCheckable(True)
        self.toolbar_bottom_action.triggered.connect(lambda: self.set_toolbar_position('bottom'))
        
        self.toolbar_hidden_action = QAction('👁️ Скрыть', self)
        self.toolbar_hidden_action.setCheckable(True)
        self.toolbar_hidden_action.triggered.connect(self.toggle_toolbar_visibility)
        
        toolbar_menu.addAction(self.toolbar_top_action)
        toolbar_menu.addAction(self.toolbar_bottom_action)
        toolbar_menu.addSeparator()
        toolbar_menu.addAction(self.toolbar_hidden_action)
        
        # Устанавливаем группу для переключателей положения
        self.toolbar_position_group = QActionGroup(self)
        self.toolbar_position_group.addAction(self.toolbar_top_action)
        self.toolbar_position_group.addAction(self.toolbar_bottom_action)
        self.toolbar_top_action.setChecked(True)  # По умолчанию вверху
        
        # Меню Сервис
        service_menu = menubar.addMenu('Сервис')
        service_menu.addAction('🔍 Поиск', self.show_smart_search, "Ctrl+F")
        service_menu.addAction('📊 Аналитика', self.show_analytics, "F5")
        service_menu.addAction('📹 Камеры', self.show_video_stream, "F8")
        
        # Меню Справка
        help_menu = menubar.addMenu('Справка')
        help_menu.addAction('📖 Помощь', self.show_help, "F1")
        help_menu.addAction('ℹ️ О программе', self.about)
    def set_toolbar_position(self, position):
        """Установка положения панели инструментов"""
        if position == 'top':
            self.top_toolbar.setVisible(True)
            self.bottom_toolbar.setVisible(False)
            self.toolbar_top_action.setChecked(True)
            self.toolbar_bottom_action.setChecked(False)
            self.position_switch.setIconText('⬇️')
            self.position_switch.setToolTip("Переместить панель инструментов вниз")
        elif position == 'bottom':
            self.top_toolbar.setVisible(False)
            self.bottom_toolbar.setVisible(True)
            self.toolbar_top_action.setChecked(False)
            self.toolbar_bottom_action.setChecked(True)
            # В нижней панели тоже добавляем переключатель
            if not hasattr(self, 'bottom_position_switch'):
                self.bottom_position_switch = QAction('⬆️', self)
                self.bottom_position_switch.setToolTip("Переместить панель инструментов вверх")
                self.bottom_position_switch.triggered.connect(lambda: self.set_toolbar_position('top'))
                self.bottom_toolbar.addAction(self.bottom_position_switch)
            self.bottom_position_switch.setIconText('⬆️')
            self.bottom_position_switch.setToolTip("Переместить панель инструментов вверх")
    def switch_toolbar_position(self):
        """Переключение положения панели инструментов"""
        if self.top_toolbar.isVisible():
            self.set_toolbar_position('bottom')
        else:
            self.set_toolbar_position('top')
    def setup_toolbars(self):
        """Настройка панелей инструментов (верхней и нижней)"""
        # Верхняя панель инструментов
        self.top_toolbar = QToolBar("Верхняя панель")
        self.top_toolbar.setIconSize(QSize(24, 24))
        self.top_toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.addToolBar(Qt.TopToolBarArea, self.top_toolbar)
        
        # Нижняя панель инструментов (изначально скрыта)
        self.bottom_toolbar = QToolBar("Нижняя панель")
        self.bottom_toolbar.setIconSize(QSize(24, 24))
        self.bottom_toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.bottom_toolbar.setVisible(False)
        self.addToolBar(Qt.BottomToolBarArea, self.bottom_toolbar)
        
        # Кнопки для панелей инструментов с подсказками
        actions = [
            ('📁 Загрузить', "Загрузить медиафайлы в систему (Ctrl+I)", self.import_files),
            ('🔍 Поиск', "Открыть интеллектуальный поиск (Ctrl+F)", self.show_smart_search),
            ('📊 Анализ', "Запустить анализ выбранного файла", self.run_analysis),
            ('🔄 Обновить', "Обновить список файлов (F5)", self.refresh_files),
            ('⚙️ Настройки', "Открыть настройки системы (Ctrl+,)", self.show_settings),
            ('📹 Камеры', "Управление видеопотоком (F8)", self.show_video_stream)
        ]
        
        # Добавляем действия в обе панели
        for text, tooltip, handler in actions:
            # Для верхней панели
            top_action = QAction(text, self)
            top_action.setToolTip(tooltip)
            top_action.triggered.connect(handler)
            self.top_toolbar.addAction(top_action)
            
            # Для нижней панели
            bottom_action = QAction(text, self)
            bottom_action.setToolTip(tooltip)
            bottom_action.triggered.connect(handler)
            self.bottom_toolbar.addAction(bottom_action)
        
        # Добавляем разделитель и переключатель положения
        self.top_toolbar.addSeparator()
        self.bottom_toolbar.addSeparator()
        
        # Переключатель положения панели (только в верхней панели)
        self.position_switch = QAction('⬇️', self)
        self.position_switch.setToolTip("Переместить панель инструментов вниз")
        self.position_switch.triggered.connect(self.switch_toolbar_position)
        self.top_toolbar.addAction(self.position_switch)

    def setup_navigation_panel(self, parent):
        """Настройка левой панели навигации"""
        nav_frame = QFrame()
        nav_frame.setFrameStyle(QFrame.StyledPanel)
        nav_layout = QVBoxLayout(nav_frame)
        
        # Поиск
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("🔍 Поиск...")
        self.search_input.setToolTip("Быстрый поиск по имени файла и тегам")
        self.search_input.textChanged.connect(self.search_files)
        search_layout.addWidget(self.search_input)
        
        nav_layout.addLayout(search_layout)
        
        # Дерево навигации
        self.nav_tree = QTreeWidget()
        self.nav_tree.setHeaderLabel("Медиатека")
        self.nav_tree.setToolTip("Навигация по медиабиблиотеке")
        self.setup_navigation_tree()
        nav_layout.addWidget(self.nav_tree)
        
        # История поиска
        history_group = QGroupBox("📚 История")
        history_layout = QVBoxLayout()
        
        self.history_list = QListWidget()
        self.history_list.setToolTip("Последние поисковые запросы")
        self.history_list.itemDoubleClicked.connect(self.load_search_from_history)
        history_layout.addWidget(self.history_list)
        
        clear_history_btn = QPushButton("🧹 Очистить")
        clear_history_btn.setToolTip("Удалить всю историю поиска")
        clear_history_btn.clicked.connect(self.clear_search_history)
        history_layout.addWidget(clear_history_btn)
        
        history_group.setLayout(history_layout)
        nav_layout.addWidget(history_group)
        
        parent.addWidget(nav_frame)

    def setup_navigation_tree(self):
        """Настройка дерева навигации"""
        # Основные разделы
        sections = {
            "📁 Медиатека": ["📹 Видео", "🖼️ Фото", "🎵 Аудио", "📄 Документы"],
            "⭐ Избранное": [],
            "🕐 Недавние": ["Сегодня", "Вчера", "Неделя"],
            "🗂️ Проекты": ["Проект Alpha", "Проект Beta", "Архив"]
        }
        
        for section, subsections in sections.items():
            section_item = QTreeWidgetItem(self.nav_tree, [section])
            for subsection in subsections:
                QTreeWidgetItem(section_item, [subsection])
                
        self.nav_tree.expandAll()
        self.nav_tree.itemClicked.connect(self.on_nav_item_clicked)

    def setup_details_panel(self, parent):
        """Настройка правой панели деталей"""
        details_frame = QFrame()
        details_frame.setFrameStyle(QFrame.StyledPanel)
        details_layout = QVBoxLayout(details_frame)
        
        # Заголовок
        self.details_title = QLabel("Выберите файл")
        self.details_title.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        self.details_title.setAlignment(Qt.AlignCenter)
        details_layout.addWidget(self.details_title)
        
        # Вкладки деталей
        self.details_tabs = QTabWidget()
        
        # Вкладка метаданных
        metadata_tab = QWidget()
        self.setup_metadata_tab(metadata_tab)
        self.details_tabs.addTab(metadata_tab, "📊 Данные")
        
        # Вкладка анализа
        analysis_tab = QWidget()
        self.setup_analysis_tab(analysis_tab)
        self.details_tabs.addTab(analysis_tab, "🔍 Анализ")
        
        # Вкладка тегов
        tags_tab = QWidget()
        self.setup_tags_tab(tags_tab)
        self.details_tabs.addTab(tags_tab, "🏷️ Теги")
        
        # Вкладка статистики
        stats_tab = QWidget()
        self.setup_stats_tab(stats_tab)
        self.details_tabs.addTab(stats_tab, "📈 Статистика")
        
        details_layout.addWidget(self.details_tabs)
        parent.addWidget(details_frame)

    def setup_metadata_tab(self, parent):
        """Настройка вкладки метаданных"""
        layout = QVBoxLayout(parent)
        
        self.metadata_text = QTextEdit()
        self.metadata_text.setPlainText("Выберите файл для просмотра метаданных")
        self.metadata_text.setReadOnly(True)
        layout.addWidget(self.metadata_text)

    def setup_analysis_tab(self, parent):
        """Настройка вкладки анализа"""
        layout = QVBoxLayout(parent)
        
        self.analysis_text = QTextEdit()
        self.analysis_text.setPlainText("Анализ не выполнен. Выберите файл и запустите анализ.")
        self.analysis_text.setReadOnly(True)
        layout.addWidget(self.analysis_text)
        
        analyze_btn = QPushButton("Запустить анализ")
        analyze_btn.setToolTip("Запустить полный анализ выбранного файла")
        analyze_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        analyze_btn.clicked.connect(self.run_analysis)
        layout.addWidget(analyze_btn)

    def setup_tags_tab(self, parent):
        """Настройка вкладки тегов"""
        layout = QVBoxLayout(parent)
        
        # Автоматические теги
        auto_label = QLabel("Автотеги:")
        auto_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(auto_label)
        
        self.auto_tags_list = QListWidget()
        layout.addWidget(self.auto_tags_list)
            
        # Разделитель
        layout.addSpacing(10)
        
        # Ручное добавление тегов
        manual_label = QLabel("Добавить тег:")
        manual_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(manual_label)
        
        tag_input_layout = QHBoxLayout()
        self.tag_input = QLineEdit()
        self.tag_input.setPlaceholderText("Введите тег...")
        self.tag_input.setToolTip("Введите новый тег для файла")
        tag_input_layout.addWidget(self.tag_input)
        
        add_tag_btn = QPushButton("Добавить")
        add_tag_btn.setToolTip("Добавить тег к выбранному файлу")
        add_tag_btn.clicked.connect(self.add_manual_tag)
        tag_input_layout.addWidget(add_tag_btn)
        
        layout.addLayout(tag_input_layout)
        layout.addStretch()

    def setup_stats_tab(self, parent):
        """Настройка вкладки статистики"""
        layout = QVBoxLayout(parent)
        
        self.stats_text = QTextEdit()
        self.stats_text.setPlainText("Статистика недоступна. Выберите файл.")
        self.stats_text.setReadOnly(True)
        layout.addWidget(self.stats_text)

    def setup_statusbar(self):
        """Настройка статусной строки"""           
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        # Создаем несколько секций в статусной панели
        self.status_system = QLabel("✅ Система готова")
        self.status_files = QLabel("📁 Файлов: 3")
        self.status_storage = QLabel("💾 Свободно: 346 ГБ")
        self.status_camera = QLabel("📹 Камеры: 1")
        
        # Добавляем разделители
        self.status_bar.addWidget(self.status_system)
        self.status_bar.addWidget(self.create_separator())
        self.status_bar.addWidget(self.status_files)
        self.status_bar.addWidget(self.create_separator())
        self.status_bar.addWidget(self.status_storage)
        self.status_bar.addWidget(self.create_separator())
        self.status_bar.addWidget(self.status_camera)
        
        # Добавляем растягивающийся элемент слева от времени
        self.status_bar.addPermanentWidget(QLabel(""), 1)
        
        # Добавляем время в правую часть
        self.status_time = QLabel()
        self.update_time()
        self.status_bar.addPermanentWidget(self.status_time)
        
        # Запускаем таймер для обновления времени
        self.time_timer = QTimer()
        self.time_timer.timeout.connect(self.update_time)
        self.time_timer.start(1000)  # Обновлять каждую секунду
    
    def create_separator(self):
        """Создание разделителя для статусной панели"""
        separator = QLabel("|")
        separator.setStyleSheet("color: #999; margin: 0 5px;")
        return separator

    def update_time(self):
        """Обновление времени в статусной панели"""
        current_time = QDateTime.currentDateTime().toString("dd.MM.yyyy HH:mm:ss")
        self.status_time.setText(f"🕒 {current_time}")
    
    def update_statusbar(self, message=None, files_count=None, storage=None, camera_count=None):
        """Обновление статусной панели"""
        if message:
            self.status_system.setText(message)
        
        if files_count is not None:
            self.status_files.setText(f"📁 Файлов: {files_count}")
        
        if storage:
            self.status_storage.setText(f"💾 {storage}")
        
        if camera_count is not None:
            self.status_camera.setText(f"📹 Камеры: {camera_count}")
    # МЕТОДЫ ФУНКЦИОНАЛЬНОСТИ:

    def select_file(self, file_info):
        """Выбор файла для отображения деталей"""
        self.current_file = file_info
        self.details_title.setText(file_info["name"])
        self.update_file_details()

    def update_file_details(self):
        """Обновление деталей выбранного файла"""
        if not self.current_file:
            return
            
        # Обновляем метаданные
        metadata_text = f"""📹 Тип: {self.current_file["type"]}
💾 Размер: {self.current_file["size"]}
⏱️ Длительность: {self.current_file["duration"]}
🎞️ Разрешение: {self.current_file["resolution"]}
🔊 Кодек: {self.current_file.get("codec", "N/A")}
📏 Битрейт: {self.current_file.get("bitrate", "N/A")}
🎬 FPS: {self.current_file.get("fps", "N/A")}
📅 Дата: {self.current_file["date"]}

📍 Путь: {self.current_file.get("path", "N/A")}"""
        self.metadata_text.setPlainText(metadata_text)
        
        # Обновляем теги
        self.auto_tags_list.clear()
        for tag in self.current_file["tags"]:
            self.auto_tags_list.addItem(f"• {tag}")
            
        # Обновляем статистику
        stats_text = f"""📊 Статистика файла:

Общая информация:
• Размер: {self.current_file["size"]}
• Длительность: {self.current_file["duration"]}
• Разрешение: {self.current_file["resolution"]}
• Битрейт: {self.current_file.get("bitrate", "N/A")}

Анализ контента:
• Сцен: {len(self.current_file["tags"])}
• Тегов: {len(self.current_file["tags"])}
• Статус: {'✅ Выполнен' if self.current_file.get("analyzed", False) else '❌ Не выполнен'}

Системная информация:
• Дата загрузки: {self.current_file["date"]}
• Последний анализ: {'2024-01-15' if self.current_file.get("analyzed", False) else 'Не выполнен'}"""
        self.stats_text.setPlainText(stats_text)

    def import_files(self):
        """Импорт файлов"""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Выберите медиафайлы",
            "",
            "Все медиафайлы (*.mp4 *.avi *.mov *.mkv *.jpg *.png *.mp3 *.wav);;"
            "Видео файлы (*.mp4 *.avi *.mov *.mkv);;"
            "Изображения (*.jpg *.png *.jpeg *.bmp);;"
            "Аудио файлы (*.mp3 *.wav *.flac *.aac);;"
            "Все файлы (*.*)"
        )
        
        if files:
            # Показываем прогресс загрузки
            progress = QProgressDialog("Загрузка файлов...", "Отмена", 0, len(files), self)
            progress.setWindowTitle("Загрузка файлов")
            progress.setWindowModality(Qt.WindowModal)
            
            for i, file_path in enumerate(files):
                progress.setValue(i)
                progress.setLabelText(f"Загрузка: {os.path.basename(file_path)}")
                QApplication.processEvents()
                
                if progress.wasCanceled():
                    break
                    
                # Имитация обработки файла
                import time
                time.sleep(0.5)
                
            progress.setValue(len(files))
            # Обновляем статусную панель
            self.update_statusbar(
                "✅ Файлы загружены", 
                files_count=len(self.files) + len(files)
            )
            QMessageBox.information(
                self,
                "Загрузка файлов",
                f"Загружено файлов: {len(files)}\n\n"
                "Файлы успешно загружены в систему и готовы к анализу."
            )

    def export_data(self):
        """Экспорт данных"""
        QMessageBox.information(self, "Экспорт", "Функция экспорта данных")

    def search_files(self):
        """Поиск файлов"""
        query = self.search_input.text()
        if query:
            # Сохраняем в историю
            if query not in self.search_history:
                self.search_history.append(query)
                self.history_list.addItem(query)

    def load_search_from_history(self, item):
        """Загрузка поиска из истории"""
        self.search_input.setText(item.text())

    def clear_search_history(self):
        """Очистка истории поиска"""
        reply = QMessageBox.question(self, "Очистка истории", 
                                   "Вы уверены, что хотите очистить историю поиска?")
        if reply == QMessageBox.Yes:
            self.search_history.clear()
            self.history_list.clear()

    def on_nav_item_clicked(self, item, column):
        """Обработка клика по элементу навигации"""
        text = item.text(0)
        if text in ["📹 Видео", "🖼️ Фото", "🎵 Аудио"]:
            QMessageBox.information(self, "Навигация", f"Показаны файлы: {text}")

    def change_view(self, view_type):
        """Изменение режима просмотра"""
        if view_type == 'grid':
            self.central_tabs.setCurrentIndex(0)
        else:
            self.central_tabs.setCurrentIndex(1)

    def toggle_toolbar(self):
        """Переключение панели инструментов"""
        toolbar = self.findChild(QToolBar)
        if toolbar.isVisible():
            toolbar.hide()
        else:
            toolbar.show()

    def show_smart_search(self):
        """Показать интеллектуальный поиск"""
        search_dialog = SmartSearchDialog(self)
        search_dialog.exec_()

    def show_video_stream(self):
        """Показать панель видеопотока"""
        self.central_tabs.setCurrentIndex(3)
        # Обновляем статус камер
        try:
            camera_count = len(self.video_stream_tab.multi_camera.cameras) if hasattr(self, 'video_stream_tab') else 1
            self.update_statusbar(camera_count=camera_count)
        except:
            self.update_statusbar()

    def show_analytics(self):
        """Показать аналитику"""
        QMessageBox.information(
            self,
            "Аналитика системы",
            "Комплексная аналитика системы\n\n"
            "• Статистика использования хранилища\n"
            "• Анализ активности пользователей\n"
            "• Эффективность поисковых запросов\n"
            "• Качество распознавания контента\n"
            "• Производительность системы"
        )

    def show_settings(self):
        """Показать настройки"""
        settings_dialog = SettingsDialog(self)
        settings_dialog.exec_()

    def refresh_files(self):
        """Обновить список файлов"""
        self.create_file_cards()
        self.update_file_table()
        self.update_statusbar("🔄 Список обновлен", files_count=len(self.files))
        QMessageBox.information(self, "Обновление", "Список файлов обновлен")

    def analyze_all_files(self):
        """Анализировать все файлов"""
        progress = QProgressDialog("Анализ файлов...", "Отмена", 0, len(self.files), self)
        progress.setWindowTitle("Анализ всех файлов")
        progress.setWindowModality(Qt.WindowModal)
        
        for i, file_info in enumerate(self.files):
            progress.setValue(i)
            progress.setLabelText(f"Анализ: {file_info['name']}")
            QApplication.processEvents()
            
            if progress.wasCanceled():
                break
                
            # Имитация анализа
            import time
            time.sleep(1)
            
        progress.setValue(len(self.files))
        QMessageBox.information(self, "Анализ завершен", "Все файлы успешно проанализированы")

    def view_file(self, file_info):
        """Просмотр файла"""
        self.select_file(file_info)
        QMessageBox.information(
            self,
            "Просмотр файла",
            f"Просмотр: {file_info['name']}\n\n"
            "В реальной системе откроется видеоплеер с:\n"
            "• Управлением воспроизведением\n• Ключевыми кадрами\n"
            "• Транскрибацией\n• Объектами в реальном времени\n"
            "• Семантическим поиском по содержанию"
        )

    def tag_file(self, file_info):
        """Тегирование файла"""
        self.select_file(file_info)
        QMessageBox.information(
            self,
            "Управление тегами",
            f"Файл: {file_info['name']}\n\n"
            "Система тегирования позволяет:\n"
            "• Добавлять/удалять теги\n• Создавать категории\n"
            "• Группировать по проектам\n• Экспорт тегов\n"
            "• Автоматическое тегирование"
        )

    def analyze_file(self, file_info):
        """Анализ файла"""
        self.select_file(file_info)
        QMessageBox.information(
            self,
            "Анализ файла",
            f"Запуск анализа: {file_info['name']}\n\n"
            "Будет выполнено:\n"
            "• Детекция сцен и объектов\n• Транскрибация аудио\n"
            "• Генерация эмбеддингов\n• Автотегирование\n"
            "• Семантическое индексирование\n• Анализ качества"
        )

    def run_analysis(self):
        """Запуск анализа"""
        if not self.current_file:
            QMessageBox.warning(self, "Ошибка", "Пожалуйста, выберите файл для анализа")
            return
            
        progress_dialog = QProgressDialog("Выполняется анализ...", "Отмена", 0, 100, self)
        progress_dialog.setWindowTitle("Анализ файла")
        progress_dialog.setWindowModality(Qt.WindowModal)
        
        # Имитация прогресса
        for i in range(101):
            progress_dialog.setValue(i)
            progress_dialog.setLabelText(f"Анализ {self.current_file['name']}... {i}%")
            QApplication.processEvents()
            if progress_dialog.wasCanceled():
                break
            import time
            time.sleep(0.03)
                
        progress_dialog.setValue(100)
        
        # Обновляем информацию об анализе
        self.current_file["analyzed"] = True
        self.analysis_text.setPlainText(f"""Статус анализа: ✅ Выполнен

Результаты анализа файла {self.current_file['name']}:

• Ключевые кадры: 12
• Распознанные объекты: 8
• Транскрибация аудио: 95%
• Семантические теги: {len(self.current_file['tags'])}
• Векторные эмбеддинги: сгенерированы
• Статистика сцен: 6 сцен

Анализ выполнен успешно. Все данные доступны для поиска.""")

        QMessageBox.information(
            self,
            "Анализ завершен",
            "Анализ файла выполнен!\n\nДоступны результаты:\n"
            "• 6 ключевых кадров\n• 12 распознанных объектов\n"
            "• Полная транскрибация\n• 8 автоматических тегов\n"
            "• Векторные представления"
        )

    def add_manual_tag(self):
        """Добавление тега вручную"""
        if not self.current_file:
            QMessageBox.warning(self, "Ошибка", "Пожалуйста, выберите файл")
            return
            
        tag = self.tag_input.text().strip()
        if tag:
            if tag not in self.current_file["tags"]:
                self.current_file["tags"].append(tag)
                self.auto_tags_list.addItem(f"• {tag}")
                self.tag_input.clear()
                QMessageBox.information(self, "Тег добавлен", f"Тег '{tag}' успешно добавлен")
            else:
                QMessageBox.warning(self, "Ошибка", "Этот тег уже существует")

    def on_file_double_click(self, index):
        """Обработка двойного клика по файлу"""
        row = index.row()
        if row < len(self.files):
            file_info = self.files[row]
            self.view_file(file_info)

    def on_table_selection_changed(self):
        """Обработка изменения выделения в таблице"""
        selected_items = self.file_table.selectedItems()
        if selected_items:
            row = selected_items[0].row()
            if row < len(self.files):
                self.select_file(self.files[row])

    def show_help(self):
        """Показать справку"""
        QMessageBox.information(
            self,
            "Помощь",
            "MediaFlow Desktop - Руководство\n\n"
            "Основные функции:\n"
            "• Загрузка и хранение медиафайлов\n"
            "• Автоматический анализ контента\n"
            "• Интеллектуальный поиск\n"
            "• Управление метаданными и тегами\n"
            "• Управление видеопотоком\n"
            "• Статистика и аналитика\n\n"
            "Горячие клавиши:\n"
            "• Ctrl+I - Импорт файлов\n"
            "• Ctrl+F - Поиск\n"
            "• F1-F2 - Переключение вида\n"
            "• F8 - Видеопоток\n\n"
            "Версия 2.0"
        )

    def about(self):
        """О программе"""
        QMessageBox.about(
            self,
            "О программе",
            "MediaFlow Desktop\n\n"
            "Интеллектуальная система хранения и обработки медиаданных\n\n"
            "Версия 2.0\n"
            "© 2024 Все права защищены\n\n"
            "Новые возможности:\n"
            "• Улучшенный интерфейс\n"
            "• Управление видеопотоком\n"
            "• Система настроек\n"
            "• История поиска\n"
            "• Контекстные подсказки"
        )

    def update_file_table(self):
        """Обновление таблицы файлов"""
        self.file_table.setRowCount(len(self.files))
        for row, file_info in enumerate(self.files):
            self.file_table.setItem(row, 0, QTableWidgetItem(file_info["name"]))
            self.file_table.setItem(row, 1, QTableWidgetItem(file_info["type"]))
            self.file_table.setItem(row, 2, QTableWidgetItem(file_info["duration"]))
            self.file_table.setItem(row, 3, QTableWidgetItem(file_info["resolution"]))
            self.file_table.setItem(row, 4, QTableWidgetItem(file_info["size"]))
            self.file_table.setItem(row, 5, QTableWidgetItem(file_info["date"]))

   