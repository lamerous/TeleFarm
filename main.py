import os
import re
import sys
import json
import time
import random
import shutil
import winreg
import psutil
import asyncio
import requests
import platform
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
from PyQt5.QtCore import Qt, QEventLoop, pyqtSignal, QThread, pyqtSlot, QMetaObject, Q_ARG, QTimer
from PyQt5.QtWidgets import QMessageBox, QButtonGroup, QCheckBox, QInputDialog, QProgressDialog
from PyQt5.QtGui import QFont, QPalette, QColor, QIcon

@dataclass
class Credentials:
    api_id: str
    api_hash: str


@dataclass
class ProxyConfig:
    http: str
    https: str

class TelegramWorker(QThread):
    creation_finished = pyqtSignal(bool, str)
    creation_progress = pyqtSignal(str)
    
    participation_finished = pyqtSignal(bool, str)
    participation_progress = pyqtSignal(str)
    show_message = pyqtSignal(str, str)

    message_confirmed = None

    step_signal = pyqtSignal(int)
    
    def __init__(self, worker_type: str, **kwargs):
        super().__init__()
        self.worker_type = worker_type
        self.kwargs = kwargs
        
        self.verification_code = None
        self.auth_code = None

        self.pyrogram_client = None
    
    def run(self):
        #try:
            if self.worker_type == 'creation':
                self.run_creation()
            elif self.worker_type == 'participation':
                self.run_participation()
        #except Exception as err:
        #    print(err)
        #    self.show_info_message("Ошибка", str({err}))
        #    return

    def run_creation(self):
        try:
            phone = self.kwargs.get('phone')
            login = self.kwargs.get('login')
            proxy_manager = self.kwargs.get('proxy_manager')
            
            self.creation_progress.emit("Начало создания клиента...")
            self.step_signal.emit(10)
            
            # Проверка прокси
            self.creation_progress.emit("Проверка прокси...")
            proxy = proxy_manager.get_random_proxy()
            if proxy and proxy_manager.test_proxy(proxy):
                self.creation_progress.emit("Используется прокси")
            else:
                proxy = None
                self.creation_progress.emit("Прямое соединение")
            self.step_signal.emit(20)
            
            # Создание копии Telegram
            self.creation_progress.emit("Создание копии Telegram...")
            telegram_dir = Path("Telegram")
            new_dir = Path(f"{login}Telegram")
            
            if not telegram_dir.exists():
                self.creation_finished.emit(False, "Папка Telegram не найдена")
                return
            
            self.step_signal.emit(30)
            
            # Копирование и запуск
            if new_dir.exists():
                shutil.rmtree(new_dir)
            
            shutil.copytree(telegram_dir, new_dir)
            self.step_signal.emit(50)
            
            self.creation_progress.emit("Запуск Telegram...")
            self.rename_and_launch_exe(new_dir, login)
            self.step_signal.emit(60)
            
            # Получение API credentials
            self.creation_progress.emit("Получение API credentials...")
            credentials = self.get_telegram_credentials(phone, proxy)
            self.step_signal.emit(80)
        
            if credentials:
                self.creation_progress.emit("Аутентификация...")
                self.authenticate_client(login, phone, credentials)
                self.step_signal.emit(100)
            
                self.creation_finished.emit(True, "Аккаунт успешно добавлен!")
                self.show_info_message("Информация", "Аккаунт успешно добавлен")
            else:
                self.creation_finished.emit(False, "Не удалось получить credentials")
                
        except Exception as e:
            self.creation_finished.emit(False, f"Ошибка создания: {str(e)}")
    
    def rename_and_launch_exe(self, directory: Path, login: str):
        old_exe_path = directory / "Telegram.exe"
        new_exe_path = directory / f"{login}Telegram.exe"
        
        if old_exe_path.exists():
            old_exe_path.rename(new_exe_path)
            subprocess.Popen([new_exe_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.show_info_message("Информация", "Войдите в аккаунт Telegram, затем нажмите Ок")
            
        else:
            raise FileNotFoundError("Telegram.exe не найден")

    def show_info_message(self, title, text):
        self.message_confirmed = False
        self.show_message.emit(title, text)
        max_wait = 86400
        waited = 0
        while not self.message_confirmed and waited < max_wait:
            self.sleep(1)
            waited += 1
            print("Still work")

    def get_telegram_credentials(self, phone: str, proxy: Optional[ProxyConfig]) -> Optional[Credentials]:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest',
        }
        
        proxies = proxy.__dict__ if proxy else None
        
        try:
            # Отправка запроса на код
            self.creation_progress.emit("Отправка запроса кода...")

            response = requests.post(
                "https://my.telegram.org/auth/send_password",
                data=f"phone=%2B{phone}",
                headers=headers,
                proxies=proxies,
                timeout=30
            )

            if "Sorry, too many tries" in response.text:
                self.show_info_message("Информация", "Слишком много попыток, поробуйте позже")
                raise Exception("Слишком много попыток, попробуйте позже")
            
            data = json.loads(response.text)
            random_hash = data["random_hash"]
            
            # Запрашиваем код в основном потоке через сигнал
            self.creation_progress.emit("REQUEST_CODE_INPUT")
            
            max_wait = 300  # Максимум 5 минут ожидания
            waited = 0
            while not self.verification_code and waited < max_wait:
                self.sleep(1)
                waited += 1
            
            if not self.verification_code:
                return None
            
            # Авторизация
            self.creation_progress.emit("Авторизация...")
            auth_data = {
                'phone': phone,
                'random_hash': random_hash,
                'password': self.verification_code
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
                raise Exception("Не удалось выполнить вход")
                
        except Exception as e:
            raise Exception(f"Ошибка получения credentials: {str(e)}")
    
    def extract_api_credentials(self, cookies, proxies: Optional[Dict]) -> Optional[Credentials]:
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
        try:
            try:
                loop = asyncio.get_event_loop_policy().get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

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
            
            self.creation_progress.emit("REQUEST_AUTH_CODE_INPUT")
            
            max_wait = 300
            waited = 0
            while not self.auth_code and waited < max_wait:
                self.sleep(1)
                waited += 1
            
            if not self.auth_code:
                raise Exception("Аутентификация отменена")
            
            client.sign_in(phone, phone_code_hash, self.auth_code)
            client.disconnect()
                
        except Exception as e:
            raise Exception(f"Ошибка аутентификации: {str(e)}")

    def run_participation(self):
        session_name = self.kwargs.get('session_name')
        post_link = self.kwargs.get('post_link')
        credentials = self.kwargs.get('credentials')
                
        self.participation_progress.emit(f"Запуск сессии {session_name}")

        client = None
        try:            
            try:
                loop = asyncio.get_event_loop_policy().get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            client = Client(
                name=session_name,
                api_id=credentials.api_id,
                api_hash=credentials.api_hash,
                app_version="Telegram Desktop 6.1.3 x64",
                device_model=platform.uname().system,
                system_version=platform.uname().version
            )

            client.start()

            username, message_id = self.parse_post_link(post_link)
            if not username or not message_id:
                self.participation_finished.emit(False, "Неверный формат ссылки")
                return
            
            message = client.get_messages(username, message_ids=message_id)
            if not message:
                self.participation_finished.emit(False, "Пост не найден")
                return
            
            self.pyrogram_client = client

            result = self.process_message(message, session_name)
            if result:
                self.participation_finished.emit(True, f"Успешно: {session_name}")
            else:
                self.participation_finished.emit(False, f"Не удалось обработать: {session_name}")

        except Exception as e:
           self.participation_finished.emit(False, f"Не удалось обработать {session_name}, {e}")
        finally:
           if client and not hasattr(self, 'monitor_timer'):
               try:
                   client.stop()
               except Exception as e:
                   print(f"Ошибка при закрытии клиента: {e}")
    
    def process_message(self, message, session_name: str) -> bool:
        if not hasattr(message, 'reply_markup') or not message.reply_markup:
            print("no reply_markup in post")
            return False
        
        for row in message.reply_markup.inline_keyboard:
            for button in row:
                if "участ" in button.text.lower():
                    try:
                        result = message.click(button.text)
                        deeplink = self.convert_to_deeplink(result)
                        self.edit_registry(session_name)

                        # Запускаем через start для правильного открытия deeplink
                        subprocess.Popen(['cmd', '/c', 'start', '', deeplink])
                        
                        # Ждем закрытия Telegram
                        process_name = f"{session_name}Telegram.exe"
                        self.wait_for_process_close(process_name, session_name)
                        
                        return True
                    except Exception as e:
                        print(f"Ошибка при нажатии кнопки: {e}")
                        continue

        print("No buttons in post")
        return False

    def wait_for_process_close(self, process_name: str, session_name: str):
        """Ждем пока процесс Telegram закроется"""
        max_wait = 300  # 5 минут
        check_interval = 2
        
        for _ in range(max_wait // check_interval):
            # Проверяем есть ли процесс с таким именем
            process_found = False
            for proc in psutil.process_iter(['name']):
                if proc.info['name'] and proc.info['name'].lower() == process_name.lower():
                    process_found = True
                    break
            
            if not process_found:
                break  # Процесс закрыт
                
            self.sleep(check_interval)
            self.participation_progress.emit(f"Ожидание закрытия Telegram: {session_name}")
            
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
            "Software\\Classes\\tg\\shell\\open\\command",
            "Software\\Classes\\tdesktop.tg\\shell\\open\\command"
        ]
        
        for cmd_key in commands:
            try:
                key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, cmd_key)
                winreg.SetValue(key, "", winreg.REG_SZ, f'"{exe_path}" -- "%1"')
                winreg.CloseKey(key)
            except Exception as e:
                print(f"Ошибка редактирования реестра: {e}")
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
        self.setWindowIcon(QIcon('icon.ico'))
        self.setWindowTitle("TeleFarm - ферма телеграмм аккаунтов")
        
        self.proxy_manager = ProxyManager()
        self.workers = []
        
        self.setup_ui()
        self.connect_signals()
        self.update_scroll_area()

        self.creation_worker = None

        self.progressBar.hide()

    def setup_ui(self):
        self.button_group = QButtonGroup(self)
        self.button_group.buttonClicked.connect(
            lambda btn: self.statusBar().showMessage(f"Selected: {btn.text()}")
        )
        self.container.setLayout(self.check_layout)
        self.check_layout.setAlignment(Qt.AlignTop)
        self.scroll.setWidget(self.container)
    
    def connect_signals(self):
        self.addAccount_btn.pressed.connect(self.on_add_account)
        self.start_btn.pressed.connect(self.on_start)
        self.selectAll_btn.pressed.connect(self.on_select_all)
        self.clearAll_btn.pressed.connect(self.on_clear_all)
        self.reload_btn.pressed.connect(self.update_scroll_area)
    
    def display_message(self, title, text):
        QMessageBox.information(self, title, text)

        for worker in self.workers:
            if worker.worker_type == 'creation' and worker.isRunning():
                worker.message_confirmed = True

    def validate_phone(self, phone: str) -> bool:
        pattern = r'^\+\d{9,15}$'
        return bool(re.match(pattern, phone))
    
    def validate_inputs(self, phone: str, login: str) -> bool:
        return all([phone.strip(), login.strip()]) and self.validate_phone(phone)

    @pyqtSlot()
    def on_add_account(self):
        phone = self.PHONE_edit.text().strip()
        login = self.LOGIN_edit.text().strip()
        
        if not self.validate_inputs(phone, login):
            QMessageBox.warning(self, "Предупреждение", "Введите корректные значения.")
            return

        self.addAccount_btn.setEnabled(False)
        self.progressBar.show()
        
        worker = TelegramWorker(
            worker_type='creation',
            phone=phone,
            login=login,
            proxy_manager=self.proxy_manager
        )
        worker.creation_finished.connect(self.on_creation_finished)
        worker.creation_progress.connect(self.on_creation_progress)
        worker.show_message.connect(self.display_message)
        worker.step_signal.connect(self.progressBar.setValue)
        
        self.workers.append(worker)
        worker.start()
    
    @pyqtSlot()
    def on_start(self):
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
        workers = []
        for session_name, credentials in sessions:
            worker = TelegramWorker(
                worker_type='participation',
                session_name=session_name,
                post_link=post_link,
                credentials=credentials
            )
            worker.participation_finished.connect(self.on_participation_finished)
            worker.participation_progress.connect(self.on_participation_progress)
            workers.append(worker)
        
        self.run_workers_sequentially(workers, 0)

    def run_workers_sequentially(self, workers: List[TelegramWorker], index: int):
        if index >= len(workers):
            return
        
        worker = workers[index]
        
        def on_current_finished(success: bool, message: str):
            worker.participation_finished.disconnect(on_current_finished)
            
            self.on_participation_finished(success, message)
            
            self.run_workers_sequentially(workers, index + 1)
        
        worker.participation_finished.connect(on_current_finished)
        worker.start()

    @pyqtSlot(bool, str)
    def on_creation_finished(self, success: bool, message: str):
        self.progressBar.hide()
        
        self.addAccount_btn.setEnabled(True)
        
        if success:
            QMessageBox.information(self, "Успех", message)
            self.update_scroll_area()
        else:
            QMessageBox.critical(self, "Ошибка", message)
        
        self.creation_worker = None
        self.workers = []

    @pyqtSlot()
    def on_creation_canceled(self):
        if self.creation_worker and self.creation_worker.isRunning():
            self.creation_worker.terminate()
            self.creation_worker.wait(3000)
        
        self.addAccount_btn.setEnabled(True)
        self.creation_worker = None

    @pyqtSlot(str)
    def on_creation_progress(self, message: str):
        self.progressBar.setFormat(message)

        if message == "REQUEST_CODE_INPUT":
            self.request_verification_code()
        elif message == "REQUEST_AUTH_CODE_INPUT":
            self.request_auth_code()

    @pyqtSlot(bool, str)
    def on_participation_finished(self, success: bool, message: str):
        if success:
            self.statusBar().showMessage(message, 5000)
        else:
            QMessageBox.warning(self, "Ошибка", message)

    @pyqtSlot(str)
    def on_participation_progress(self, message: str):
        self.statusBar().showMessage(message, 3000)
    
    @pyqtSlot(str)
    def on_worker_progress(self, message: str):
        self.statusBar().showMessage(message, 3000)
    
    @pyqtSlot()
    def on_select_all(self):
        self.set_checkboxes_state(True)
    
    @pyqtSlot()
    def on_clear_all(self):
        self.set_checkboxes_state(False)
    
    def set_checkboxes_state(self, state: bool):
        for i in range(self.check_layout.count()):
            widget = self.check_layout.itemAt(i).widget()
            if isinstance(widget, QCheckBox):
                widget.setChecked(state)
    
    def save_credentials(self, session_name: str, credentials: Credentials):
        credentials_file = Path(f"{session_name}_credentials.json")
        with open(credentials_file, 'w', encoding='utf-8') as f:
            json.dump(credentials.__dict__, f, ensure_ascii=False, indent=2)
    
    def load_credentials(self, session_name: str) -> Optional[Credentials]:
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
        # Очистка текущего списка
        for i in reversed(range(self.check_layout.count())):
            widget = self.check_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        
        # Добавление аккаунтов
        for file in Path.cwd().glob('*.session'):
            if len(file.stem) != 7:  # Исключаем стандартные session файлы
                checkbox = QCheckBox(file.stem)
                #checkbox.setFixedHeight(25)
                self.check_layout.addWidget(checkbox)

    def request_verification_code(self):
        """Запрос кода верификации от пользователя"""
        code, ok = QInputDialog.getText(
            self, 
            "Ввод кода верификации", 
            "Введите код верификации, отправленный в Telegram:",
            text=""
        )
        
        if ok and code:
            # Отправляем код в worker
            for worker in self.workers:
                if worker.worker_type == 'creation' and worker.isRunning():
                    worker.verification_code = code.strip()
                    break
        else:
            # Пользователь отменил ввод
            for worker in self.workers:
                if worker.worker_type == 'creation' and worker.isRunning():
                    worker.verification_code = None
                    break

    def request_auth_code(self):
        """Запрос кода аутентификации от пользователя"""
        code, ok = QInputDialog.getText(
            self, 
            "Ввод кода аутентификации", 
            "Введите код аутентификации, отправленный в Telegram:",
            text=""
        )
        
        if ok and code:
            # Отправляем код в worker
            for worker in self.workers:
                if worker.worker_type == 'creation' and worker.isRunning():
                    worker.auth_code = code.strip()
                    break
        else:
            # Пользователь отменил ввод
            for worker in self.workers:
                if worker.worker_type == 'creation' and worker.isRunning():
                    worker.auth_code = None
                    break

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MyWindow()
    window.show()
    sys.exit(app.exec_())