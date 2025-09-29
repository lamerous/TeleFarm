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
from PyQt5.QtCore import Qt, QEventLoop, pyqtSignal, QThread, pyqtSlot
from PyQt5.QtWidgets import QMessageBox, QButtonGroup, QCheckBox
from PyQt5.QtGui import QFont, QPalette, QColor

class TelegramWorker(QThread):
    finished_signal = pyqtSignal(bool, str)
    progress_signal = pyqtSignal(str)

    def process_message(self, message):
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

    def parse_post_link(self, link):
        pattern = r"https?://t\.me/([^/]+)/(\d+)"
        match = re.match(pattern, link)
        if match:
            return match.group(1), int(match.group(2))
        return None, None

    def convert_to_deeplink(self, url):
        if not url.startswith('https://t.me/'):
            raise ValueError("URL должен начинаться с https://t.me/")
        
        path = url[13:]
        
        domain, rest = path.split('/', 1)
        appname, query_str = rest.split('?', 1)
        
        deeplink = f"tg://resolve?domain={domain}^&appname={appname}"
        
        params = query_str.split('&')
        for param in params:
            if param:
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