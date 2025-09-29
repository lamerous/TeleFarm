import os
import re
import sys
import json
import random
import shutil
import winreg
import requests
import platform
import webbrowser
import subprocess
from time import sleep
from pyrogram import Client
from bs4 import BeautifulSoup

from PyQt5 import QtWidgets, uic
from PyQt5.QtCore import Qt, QEventLoop, pyqtSignal
from PyQt5.QtWidgets import QMessageBox, QButtonGroup, QCheckBox
from PyQt5.QtGui import QFont, QPalette, QColor

class MyWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi('mainwindow.ui', self)

        self.button_group = QButtonGroup(self)
        self.button_group.buttonClicked.connect(lambda btn: 
        self.statusBar().showMessage(f"Selected: {btn.text()}"))
        self.container.setLayout(self.check_layout)
        self.check_layout.setAlignment(Qt.AlignTop)
        self.scroll.setWidget(self.container)

        self.update_scroll_area()
        
    def on_addAccount_btn_pressed(self):
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:142.0) Gecko/20100101 Firefox/142.0',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'X-Requested-With': 'XMLHttpRequest',
        }

        proxies = self.load_proxies()
        proxy = self.get_random_proxy(proxies)
        proxy = {
            'https': 'socks4://37.18.73.60:5566',
            'http': 'socks4://37.18.73.60:5566'
        }
        print(proxy)

        # response = requests.get("https://ifconfig.me/ip", headers=headers, timeout=10)
        # print(response.text)
        try:
            response = requests.get("https://ifconfig.me/ip", headers=headers, proxies=proxy, timeout=10)
            print(response.text)
        except:
            print("Error checking proxy IP adress")

        phone = self.PHONE_edit.text()
        login = self.LOGIN_edit.text()

        data = {
            'phone': phone
        }

        if all([phone.strip(), login.strip()]) and self.parse_phone(phone):
            #try:
                QMessageBox.information(self, "Всё ок", "Мы создали новый телеграмм клиент. Требуется вход.")

                current_dir = os.getcwd()
                telegram_dir = os.path.join(current_dir, "Telegram")
                # Путь для копии
                new_dir = os.path.join(current_dir, f"{login}Telegram")

                try:
                    # Копируем папку Telegram
                    new_path = shutil.copytree(telegram_dir, new_dir)
                    
                    # Переименовываем exe файл внутри скопированной папки
                    old_exe_path = os.path.join(new_path, "Telegram.exe")
                    new_exe_path = os.path.join(new_path, f"{login}Telegram.exe")
                    
                    if os.path.exists(old_exe_path):
                        os.rename(old_exe_path, new_exe_path)
                        # Запускаем переименованный exe
                        process = subprocess.Popen([new_exe_path])
                    else:
                        print(f"Файл Telegram.exe не найден в {new_path}")

                except FileExistsError:
                    print(f"Папка {new_dir} уже существует")
                except FileNotFoundError:
                    print(f"Исходная папка Telegram не найдена в {current_dir}")
                except Exception as e:
                    print(f"Ошибка: {e}")

                QMessageBox.information(self, "Всё ок", "Дождитесь загрузки телеграмма, войдите, после, нажмите кнопку Ok")

                #response = requests.post("https://my.telegram.org/auth/send_password", data=f"phone=%2B{phone}", headers=headers, proxies=proxy)
                response = requests.post("https://my.telegram.org/auth/send_password", data=f"phone=%2B{phone}", headers=headers)
                print(f"Код ответа: {response.status_code}")
                print(f"Ответ: {response.text}")

                if "Sorry, too many tries" in response.text:
                    QMessageBox.critical(self, "Ошибка", "Слишком много попыток, попробуйте позже")
                else:
                    text, ok = QtWidgets.QInputDialog.getText(
                        self,
                        "Введите код",
                        "Мы отправили код подтверждения вам в телеграмм",
                        QtWidgets.QLineEdit.Normal,
                        ""
                    )

                    try:
                        random_hash = response.text['random_hash']
                        print("1 works")
                    except:
                        #random_hash = response.text.random_hash
                        data = json.loads(response.text)
                        random_hash = data["random_hash"]
                        print("2 works")

                    print(random_hash)

                    data = {
                        'phone': phone,
                        'random_hash': random_hash,
                        'password': text
                    }

                    #reponse = requests.post("https://my.telegram.org/auth/login", data=data, headers=headers, proxies=proxy)
                    response = requests.post("https://my.telegram.org/auth/login", data=data, headers=headers)

                    print(response.text, type(response.text))
    
                    try:
                        print(response.cookies)
                    except:
                        ...

                    print(response.text, "true", response.text == "true")

                    if response.text == "true":
                        stel_token = response.cookies.get("stel_token")
                        print(stel_token)
                        cookies = {
                            "stel_token": stel_token
                        }
                        #response = requests.get("https://my.telegram.org/apps", proxies=proxy)
                        response = requests.get("https://my.telegram.org/apps", cookies=cookies)
                        parse_result = self.parse_telegram_api(response.text)
                    else:
                        QMessageBox.critical(self, "Ошибка", "Не удалось выполнить вход")

                    api_id = parse_result['api_id']
                    api_hash = parse_result['api_hash']
                    print(api_id, api_hash)

                    self.save_credentials(login, api_id, api_hash)

                    client = Client(
                        name=login, 
                        api_id=api_id, 
                        api_hash=api_hash, 
                        phone_number=phone,
                        app_version="Telegram Desktop 6.1.3 x64",
                        device_model=platform.uname().system,
                        system_version=platform.uname().version
                    )
                
                client.connect()
                client.initialize()
                phone_hash = client.send_code(phone)
                print(phone_hash)
                #try:
                text, ok = QtWidgets.QInputDialog.getText(
                    self,
                    "Введите код",
                    "Мы отправили код подтверждения Вам в телеграмм",
                    QtWidgets.QLineEdit.Normal,
                    ""
                )
                client.sign_in(phone, phone_hash.phone_code_hash, text)

                QMessageBox.information(self, "Всё ок", "Аккаунт добавлен")

                self.update_scroll_area()
                #except:
                    #QMessageBox.critical(self, "Ошибка", "Ошибка аутентификации")

            #except Exception as e:
                #QMessageBox.critical(self, "Ошибка", f"Не удалось создать клиент:\n{str(e)}")
        else:
            QMessageBox.warning(self, "Предупреждение", "Введите коректные значения.")

    def on_start_btn_pressed(self):
        post_link = self.post_link_edit.text()

        clients = []
        client_names = []
        for i in range(self.check_layout.count()):
            widget = self.check_layout.itemAt(i).widget()
            if isinstance(widget, QCheckBox) and widget.isChecked():
                session_name = widget.text()
                filename = session_name + '.session'
                
                credentials = self.load_credentials(session_name)
                if credentials:
                    client = Client(
                        session_name,
                        api_id=credentials['api_id'],
                        api_hash=credentials['api_hash']
                    )
                    clients.append(client)
                    client_names.append(session_name)
                else:
                    print(f"Не найдены credentials для сессии: {session_name}")
                    QMessageBox.warning(self, "Ошибка", f"Не найдены данные для аккаунта {session_name}")
        
        print("Выбранные session файлы:", clients)

        username, message_id = self.parse_post_link(post_link)
        if not username or not message_id:
            QMessageBox.warning(self, "Предупреждение", "Неверный формат ссылки")
            return

        for ind, client in enumerate(clients):
            with client:
                try:
                    message = client.get_messages(username, message_ids=message_id)
                    
                    if message is None:
                        QMessageBox.warning(self, "Предупреждение", "Пост не найден")
                        return
                    
                    if message and message.text:
                        print(f"Сообщение получено: {message.text[:100]}...")
                    else:
                        print("Сообщение не содержит текста или равно None")
                    
                    if not hasattr(message, 'reply_markup') or message.reply_markup is None:
                        print("В сообщении нет кнопок")
                        QMessageBox.warning(self, "Предупреждение", "В сообщении нет кнопок")
                        return
                        
                    print(f"Найдены кнопки: {len(message.reply_markup.inline_keyboard)} строк(и)")
                    
                    button_found = False
                    for i, row in enumerate(message.reply_markup.inline_keyboard):
                        for j, button in enumerate(row):
                            print(f"Кнопка [{i},{j}]: {button.text}")
                            if "участ" in button.text.lower():
                                try:
                                    result = message.click(button.text)
                                    print(f"Успешно нажата кнопка: {button.text}")
                                    print(f"Результат: {result}")
                                    button_found = True
                                    # webbrowser.open(result)
                                    deeplink = self.convert_to_deeplink(result)
                                    print(deeplink)
                                    self.edit_regfile(client_names[ind])
                                    os.system(f"start {deeplink}")
                                    break
                                except Exception as click_error:
                                    print(f"Ошибка при нажатии кнопки: {click_error}")
                                    QMessageBox.warning(self, "Предупреждение", "Ошибка при нажатии кнопки")
                            if button_found:
                                break
                        if button_found:
                            break
                    
                    if not button_found:
                        print("Кнопка 'Участвовать' не найдена среди:")
                        QMessageBox.warning(self, "Предупреждение", "Кнопка 'Участвовать' не найдена")
                        for i, row in enumerate(message.reply_markup.inline_keyboard):
                            for j, button in enumerate(row):
                                print(f"  - {button.text}")
                        
                        try:
                            print("Пробуем нажать первую кнопку...")
                            result = message.click(0)
                            print(f"Нажата первая кнопка. Результат: {result}")
                        except Exception as e:
                            print(f"Ошибка при нажатии первой кнопки: {e}")
                    
                except Exception as e:
                    print(f"Общая ошибка: {e}")
                    QMessageBox.warning(self, "Предупреждение", f"Общая ошибка: {e}")
                    import traceback
                    traceback.print_exc()

    def set_checkbox_values(self, value):
        for i in range(self.check_layout.count()):
            widget = self.check_layout.itemAt(i).widget()
            if isinstance(widget, QCheckBox):
                widget.setChecked(value)

    def on_selectAll_btn_pressed(self):
        self.set_checkbox_values(True)

    def on_clearAll_btn_pressed(self):
        self.set_checkbox_values(False)

    def on_reload_btn_pressed(self):
        self.update_scroll_area()

    def save_credentials(self, session_name, api_id, api_hash):
        credentials_file = f"{session_name}_credentials.json"
        with open(credentials_file, 'w', encoding='utf-8') as f:
            json.dump({
                'api_id': api_id,
                'api_hash': api_hash
            }, f, ensure_ascii=False, indent=2)

    def load_credentials(self, session_name):
        credentials_file = f"{session_name}_credentials.json"
        if os.path.exists(credentials_file):
            try:
                with open(credentials_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Ошибка загрузки credentials для {session_name}: {e}")
        return None

    def convert_to_deeplink(self, url):
        if not url.startswith('https://t.me/'):
            raise ValueError("URL должен начинаться с https://t.me/")
        
        # Извлекаем путь после t.me/
        path = url[13:]
        
        # Разбираем URL на компоненты
        domain, rest = path.split('/', 1)
        appname, query_str = rest.split('?', 1)
        
        # Формируем базовый deeplink
        deeplink = f"tg://resolve?domain={domain}^&appname={appname}"
        
        # Добавляем остальные параметры с экранированием
        params = query_str.split('&')
        for param in params:
            if param:  # Пропускаем пустые параметры
                deeplink += f"^&{param}"
        
        return deeplink

    def edit_regfile(self, login):
        current_dir = os.getcwd()
        exe_path = os.path.join(current_dir, f"{login}Telegram", f"{login}Telegram.exe")

        command_key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, f"Software\\Classes\\tg\\shell\\open\\command")
        winreg.SetValue(command_key, "", winreg.REG_SZ, f'"{exe_path}" -- "%1"')
        winreg.CloseKey(command_key)

        command_key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, f"Software\\Classes\\tdesktop.tg\\shell\\open\\command")
        winreg.SetValue(command_key, "", winreg.REG_SZ, f'"{exe_path}" -- "%1"')
        winreg.CloseKey(command_key)

    def update_scroll_area(self):
        for i in reversed(range(self.check_layout.count())):
            self.check_layout.itemAt(i).widget().setParent(None)
            
        for file in os.listdir('.'):
            if file.endswith('.session') and len(file) != 8:
                name = os.path.splitext(file)[0]
                checkbox = QCheckBox(name)
                checkbox.setMinimumHeight(20)
                checkbox.setMaximumHeight(20)
                self.check_layout.addWidget(checkbox)

    def parse_telegram_api(self, html_content):
        soup = BeautifulSoup(html_content, 'html.parser')
        spans = soup.find_all('span', class_='uneditable-input')
        
        return {
            'api_id': spans[0].find('strong').text if len(spans) > 0 else None,
            'api_hash': spans[1].text if len(spans) > 1 else None
        }

    def parse_phone(self, number):
        pattern = r'^\+\d{9,15}$'
        return bool(re.match(pattern, number))

    def parse_post_link(self, link):
        pattern = r"https?://t\.me/([^/]+)/(\d+)"
        match = re.match(pattern, link)
        if match:
            return match.group(1), int(match.group(2))
        return None, None

    def load_proxies(self):
        """Загружает прокси из файла"""
        proxies = []
        try:
            if os.path.exists('proxies.txt'):
                with open('proxies.txt', 'r') as f:
                    proxies = [line.strip() for line in f if line.strip() and ':' in line]
            print(f"Загружено {len(proxies)} прокси")
        except Exception as e:
            print(f"Ошибка загрузки прокси: {e}")
        return proxies
    
    def get_random_proxy(self, proxies):
        """Возвращает случайный прокси"""
        if not proxies:
            return None
            
        proxy_str = random.choice(proxies)
        parts = proxy_str.split(':')
        
        if len(parts) == 4:
            ip, port, login, password = parts
            return {
                'http': f'http://{login}:{password}@{ip}:{port}',
                'https': f'https://{login}:{password}@{ip}:{port}'
            }
        elif len(parts) == 2:
            ip, port = parts
            return {
                'http': f'http://{ip}:{port}',
                'https': f'https://{ip}:{port}'
            }
        return None

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = MyWindow()
    window.show()
    sys.exit(app.exec_())Key(command_key)