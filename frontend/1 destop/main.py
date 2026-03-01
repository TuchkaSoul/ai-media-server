import sys
import os
import configparser
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt

# Добавляем путь к текущей директории для импорта модулей
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from login_dialog import LoginDialog
from main_window import ModernMediaFlowDesktop

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    
    # Показываем окно входа
    login_dialog = LoginDialog()
    if login_dialog.exec_() == LoginDialog.Accepted:
        window = ModernMediaFlowDesktop()
        window.show()
        sys.exit(app.exec_())
    else:
        sys.exit()