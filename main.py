import os
import re
import sys
import json
import random
import shutil
# import winreg
import requests
import platform
import webbrowser
import subprocess
from time import sleep
from pathlib import Path
from urllib.parse import urlparse
from typing import Optional, Dict, Tuple, List
from dataclasses import dataclass

from pyrogram import Client
from bs4 import BeautifulSoup
import ctypes
from ctypes import wintypes

from PyQt5 import QtWidgets, uic
from PyQt5.QtCore import Qt, QEventLoop, pyqtSignal, QThread, pyqtSlot
from PyQt5.QtWidgets import QMessageBox, QButtonGroup, QCheckBox, QInputDialog
from PyQt5.QtGui import QFont, QPalette, QColor

@dataclass
class Credentials:
    api_id: str
    api_hash: str


@dataclass
class ProxyConfig:
    http: str
    https: str

class TelegramWorker(QThread):
    finished_signal = pyqtSignal(bool, str)
    progress_signal = pyqtSignal(str)
    
    def __init__(self, session_name: str, post_link: str, credentials: Credentials):
        super().__init__()
        self.session_name = session_name
        self.post_link = post_link
        self.credentials = credentials
    
    def run(self):
        try:
            self.progress_signal.emit(f"Запуск сессии {self.session_name}")
            
            with Client(
                self.session_name,
                api_id=self.credentials.api_id,
                api_hash=self.credentials.api_hash
            ) as client:
                username, message_id = self.parse_post_link(self.post_link)
                if not username or not message_id:
                    self.finished_signal.emit(False, "Неверный формат ссылки")
                    return
                
                message = client.get_messages(username, message_ids=message_id)
                if not message:
                    self.finished_signal.emit(False, "Пост не найден")
                    return
                
                result = self.process_message(message)
                if result:
                    self.finished_signal.emit(True, f"Успешно: {self.session_name}")
                else:
                    self.finished_signal.emit(False, f"Не удалось обработать: {self.session_name}")
                    
        except Exception as e:
            self.finished_signal.emit(False, f"Ошибка в {self.session_name}: {str(e)}")
    
    def process_message(self, message) -> bool:
        if not hasattr(message, 'reply_markup') or not message.reply_markup:
            return False
        
        for row in message.reply_markup.inline_keyboard:
            for button in row:
                if "участ" in button.text.lower():
                    try:
                        result = message.click(button.text)
                        deeplink = self.convert_to_deeplink(result)
                        self.edit_registry(self.session_name)
                        os.system(f"start {deeplink}")
                        return True
                    except Exception:
                        continue
        return False
    
    def parse_post_link(self, link: str) -> Tuple[Optional[str], Optional[int]]:
        pattern = r"https?://t\.me/([^/]+)/(\d+)"
        match = re.match(pattern, link)
        return (match.group(1), int(match.group(2))) if match else (None, None) 

    def convert_to_deeplink(self, url: str) -> str:
        if not url.startswith('https://t.me/'):
            raise ValueError("URL должен начинаться с https://t.me/")
        
        path = url[13:]
        parts = path.split('?', 1)
        domain_appname = parts[0]
        query = parts[1] if len(parts) > 1 else ""
        
        deeplink = f"tg://resolve?domain={domain_appname.replace('/', '^&appname=')}"
        
        if query:
            deeplink += f"^&{query.replace('&', '^&')}"
        
        return deeplink
    
    def edit_registry(self, login: str):
        current_dir = Path.cwd()
        exe_path = current_dir / f"{login}Telegram" / f"{login}Telegram.exe"
        
        if not exe_path.exists():
            return
        
        commands = [
            f"Software\\Classes\\tg\\shell\\open\\command",
            f"Software\\Classes\\tdesktop.tg\\shell\\open\\command"
        ]
        
        for cmd_key in commands:
            try:
                key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, cmd_key)
                winreg.SetValue(key, "", winreg.REG_SZ, f'"{exe_path}" -- "%1"')
                winreg.CloseKey(key)
            except Exception:
                continue
        
        ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x1000, None, None)


class ProxyManager:
    def __init__(self):
        self.proxies = self.load_proxies()
    
    def load_proxies(self) -> List[str]:
        proxies = []
        try:
            proxy_file = Path('proxies.txt')
            if proxy_file.exists():
                with open(proxy_file, 'r', encoding='utf-8') as f:
                    proxies = [line.strip() for line in f if line.strip() and ':' in line]
        except Exception as e:
            print(f"Ошибка загрузки прокси: {e}")
        return proxies
    
    def get_random_proxy(self) -> Optional[ProxyConfig]:
        if not self.proxies:
            return None
            
        proxy_str = random.choice(self.proxies)
        parts = proxy_str.split(':')
        
        if len(parts) == 4:
            ip, port, login, password = parts
            return ProxyConfig(
                http=f'http://{login}:{password}@{ip}:{port}',
                https=f'https://{login}:{password}@{ip}:{port}'
            )
        elif len(parts) == 2:
            ip, port = parts
            return ProxyConfig(
                http=f'http://{ip}:{port}',
                https=f'https://{ip}:{port}'
            )
        return None
    
    def test_proxy(self, proxy: ProxyConfig) -> bool:
        try:
            response = requests.get(
                "https://ifconfig.me/ip", 
                proxies=proxy.__dict__,
                timeout=10
            )
            return response.status_code == 200
        except:
            return False


class MyWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi('mainwindow.ui', self)
        
        self.proxy_manager = ProxyManager()
        self.workers = []
        
        self.setup_ui()
        self.connect_signals()
        self.update_scroll_area()
    
    def setup_ui(self):
        """Настройка интерфейса"""
        self.button_group = QButtonGroup(self)
        self.button_group.buttonClicked.connect(
            lambda btn: self.statusBar().showMessage(f"Selected: {btn.text()}")
        )
        self.container.setLayout(self.check_layout)
        self.check_layout.setAlignment(Qt.AlignTop)
        self.scroll.setWidget(self.container)
    
    def connect_signals(self):
        """Подключение сигналов"""
        self.addAccount_btn.pressed.connect(self.on_add_account)
        self.start_btn.pressed.connect(self.on_start)
        self.selectAll_btn.pressed.connect(self.on_select_all)
        self.clearAll_btn.pressed.connect(self.on_clear_all)
        self.reload_btn.pressed.connect(self.update_scroll_area)
    
    def validate_phone(self, phone: str) -> bool:
        """Проверка формата номера телефона"""
        pattern = r'^\+\d{9,15}$'
        return bool(re.match(pattern, phone))
    
    def validate_inputs(self, phone: str, login: str) -> bool:
        """Проверка введенных данных"""
        return all([phone.strip(), login.strip()]) and self.validate_phone(phone)
    
    @pyqtSlot()
    def on_add_account(self):
        """Добавление нового аккаунта"""
        phone = self.PHONE_edit.text().strip()
        login = self.LOGIN_edit.text().strip()
        
        if not self.validate_inputs(phone, login):
            QMessageBox.warning(self, "Предупреждение", "Введите корректные значения.")
            return
        
        try:
            self.create_telegram_client(phone, login)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось создать клиент:\n{str(e)}")
    
    def create_telegram_client(self, phone: str, login: str):
        """Создание Telegram клиента"""
        # Тестирование прокси
        proxy = self.proxy_manager.get_random_proxy()
        if proxy and self.proxy_manager.test_proxy(proxy):
            print(f"Используется прокси: {proxy}")
        else:
            proxy = None
            print("Используется прямое соединение")
        
        # Создание копии Telegram
        telegram_dir = Path("Telegram")
        new_dir = Path(f"{login}Telegram")
        
        if not telegram_dir.exists():
            QMessageBox.critical(self, "Ошибка", "Папка Telegram не найдена")
            return
        
        try:
            if new_dir.exists():
                shutil.rmtree(new_dir)
            
            shutil.copytree(telegram_dir, new_dir)
            self.rename_and_launch_exe(new_dir, login)
            
            QMessageBox.information(self, "Информация", 
                                  "Дождитесь загрузки Telegram, войдите, после нажмите OK")
            
            # Получение API credentials
            credentials = self.get_telegram_credentials(phone, proxy)
            if credentials:
                self.save_credentials(login, credentials)
                self.authenticate_client(login, phone, credentials)
                self.update_scroll_area()
                
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка создания клиента: {str(e)}")
    
    def rename_and_launch_exe(self, directory: Path, login: str):
        """Переименование и запуск EXE файла"""
        old_exe_path = directory / "Telegram.exe"
        new_exe_path = directory / f"{login}Telegram.exe"
        
        if old_exe_path.exists():
            old_exe_path.rename(new_exe_path)
            subprocess.Popen([new_exe_path])
        else:
            raise FileNotFoundError("Telegram.exe не найден")
    
    def get_telegram_credentials(self, phone: str, proxy: Optional[ProxyConfig]) -> Optional[Credentials]:
        """Получение учетных данных API от Telegram"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest',
        }
        
        proxies = proxy.__dict__ if proxy else None
        
        try:
            # Отправка запроса на код
            response = requests.post(
                "https://my.telegram.org/auth/send_password",
                data=f"phone=%2B{phone}",
                headers=headers,
                proxies=proxies,
                timeout=30
            )
            
            if "Sorry, too many tries" in response.text:
                QMessageBox.critical(self, "Ошибка", "Слишком много попыток, попробуйте позже")
                return None
            
            data = json.loads(response.text)
            random_hash = data["random_hash"]
            
            # Ввод кода подтверждения
            code, ok = QInputDialog.getText(
                self, "Введите код", "Код подтверждения отправлен в Telegram:"
            )
            
            if not ok or not code:
                return None
            
            # Авторизация
            auth_data = {
                'phone': phone,
                'random_hash': random_hash,
                'password': code
            }
            
            response = requests.post(
                "https://my.telegram.org/auth/login",
                data=auth_data,
                headers=headers,
                proxies=proxies,
                timeout=30
            )
            
            if response.text == "true":
                return self.extract_api_credentials(response.cookies, proxies)
            else:
                QMessageBox.critical(self, "Ошибка", "Не удалось выполнить вход")
                return None
                
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Ошибка получения credentials: {str(e)}")
            return None
    
    def extract_api_credentials(self, cookies, proxies: Optional[Dict]) -> Optional[Credentials]:
        """Извлечение API credentials из страницы приложений"""
        try:
            response = requests.get(
                "https://my.telegram.org/apps",
                cookies=cookies,
                proxies=proxies,
                timeout=30
            )
            
            soup = BeautifulSoup(response.text, 'html.parser')
            spans = soup.find_all('span', class_='uneditable-input')
            
            if len(spans) >= 2:
                return Credentials(
                    api_id=spans[0].find('strong').text,
                    api_hash=spans[1].text
                )
        except Exception as e:
            print(f"Ошибка извлечения credentials: {e}")
        
        return None
    
    def authenticate_client(self, login: str, phone: str, credentials: Credentials):
        """Аутентификация клиента Pyrogram"""
        try:
            client = Client(
                name=login,
                api_id=credentials.api_id,
                api_hash=credentials.api_hash,
                phone_number=phone,
                app_version="Telegram Desktop 6.1.3 x64",
                device_model=platform.uname().system,
                system_version=platform.uname().version
            )
            
            client.connect()
            phone_code_hash = client.send_code(phone).phone_code_hash
            
            code, ok = QInputDialog.getText(
                self, "Введите код", "Код подтверждения отправлен в Telegram:"
            )
            
            if ok and code:
                client.sign_in(phone, phone_code_hash, code)
                QMessageBox.information(self, "Успех", "Аккаунт добавлен")
            else:
                QMessageBox.warning(self, "Предупреждение", "Аутентификация отменена")
                
        except Exception as e:
            raise Exception(f"Ошибка аутентификации: {str(e)}")
    
    @pyqtSlot()
    def on_start(self):
        """Запуск процесса участия в розыгрышах"""
        post_link = self.post_link_edit.text().strip()
        
        if not post_link:
            QMessageBox.warning(self, "Предупреждение", "Введите ссылку на пост")
            return
        
        selected_sessions = self.get_selected_sessions()
        if not selected_sessions:
            QMessageBox.warning(self, "Предупреждение", "Выберите хотя бы один аккаунт")
            return
        
        self.start_workers(selected_sessions, post_link)
    
    def get_selected_sessions(self) -> List[Tuple[str, Credentials]]:
        """Получение выбранных сессий"""
        sessions = []
        for i in range(self.check_layout.count()):
            widget = self.check_layout.itemAt(i).widget()
            if isinstance(widget, QCheckBox) and widget.isChecked():
                session_name = widget.text()
                credentials = self.load_credentials(session_name)
                if credentials:
                    sessions.append((session_name, credentials))
                else:
                    QMessageBox.warning(self, "Ошибка", 
                                      f"Не найдены данные для аккаунта {session_name}")
        return sessions
    
    def start_workers(self, sessions: List[Tuple[str, Credentials]], post_link: str):
        """Запуск worker'ов для обработки"""
        self.workers.clear()
        
        for session_name, credentials in sessions:
            worker = TelegramWorker(session_name, post_link, credentials)
            worker.finished_signal.connect(self.on_worker_finished)
            worker.progress_signal.connect(self.on_worker_progress)
            self.workers.append(worker)
            worker.start()
    
    @pyqtSlot(bool, str)
    def on_worker_finished(self, success: bool, message: str):
        """Обработка завершения worker'а"""
        if success:
            self.statusBar().showMessage(message, 5000)
        else:
            QMessageBox.warning(self, "Ошибка", message)
    
    @pyqtSlot(str)
    def on_worker_progress(self, message: str):
        """Обновление прогресса"""
        self.statusBar().showMessage(message, 3000)
    
    @pyqtSlot()
    def on_select_all(self):
        """Выбрать все аккаунты"""
        self.set_checkboxes_state(True)
    
    @pyqtSlot()
    def on_clear_all(self):
        """Снять выделение со всех аккаунтов"""
        self.set_checkboxes_state(False)
    
    def set_checkboxes_state(self, state: bool):
        """Установка состояния всех чекбоксов"""
        for i in range(self.check_layout.count()):
            widget = self.check_layout.itemAt(i).widget()
            if isinstance(widget, QCheckBox):
                widget.setChecked(state)
    
    def save_credentials(self, session_name: str, credentials: Credentials):
        """Сохранение учетных данных"""
        credentials_file = Path(f"{session_name}_credentials.json")
        with open(credentials_file, 'w', encoding='utf-8') as f:
            json.dump(credentials.__dict__, f, ensure_ascii=False, indent=2)
    
    def load_credentials(self, session_name: str) -> Optional[Credentials]:
        """Загрузка учетных данных"""
        credentials_file = Path(f"{session_name}_credentials.json")
        if credentials_file.exists():
            try:
                with open(credentials_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return Credentials(**data)
            except Exception as e:
                print(f"Ошибка загрузки credentials: {e}")
        return None
    
    def update_scroll_area(self):
        """Обновление списка аккаунтов"""
        # Очистка текущего списка
        for i in reversed(range(self.check_layout.count())):
            widget = self.check_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        
        # Добавление аккаунтов
        for file in Path.cwd().glob('*.session'):
            if len(file.stem) != 7:  # Исключаем стандартные session файлы
                checkbox = QCheckBox(file.stem)
                checkbox.setFixedHeight(25)
                self.check_layout.addWidget(checkbox)

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MyWindow()
    window.show()
    sys.exit(app.exec_())