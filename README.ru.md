## 🌐 Языки
- 🇬🇧 [English](README.md)
- 🇷🇺 [Русский](README.ru.md)

## ✈️ Описание
<div align="center">
  <img src="images/present-image.jpg">
</div>

<div align="center">
  Телеграм ферма аккаунтов для выполнения действий на них
</div>

## ❗ДИСКЛЕЙМЕР
Все действия не должны выполняться на оффициальных серверах телеграмм, т.к. это противоречит условиям использования

## 🚀 Быстрый старт
1. **🔐 Удалите облачный пароль**
    -  <p align="left"><img src="images/quickstart-cloudpass.png"></p>

2. **🔑 Зарегистрируйте свой Telegram API ID**   
    -  Перейдите [my.telegram.org/auth](my.telegram.org/auth) <br><div align="left"><img src="images/quickstart-authpage.png" width="400"></div>
    -  Войдите в свой телеграмм аккаунт<br><div align="left"><img src="images/quickstart-login.png" width="400"></div>
    -  Перейдите в API development tools <br><div align="left"><img src="images/quickstart-apidevtools.png" width="400"></div>
    -  Заполните поля уникальными значениями <br><div align="left"><img src="images/quickstart-fillfields.png" width="400"></div>
    
## ⚙️ Запуск из исходного кода
1. Установите Telegram Portable
    - Установите [Telegram Portable](https://desktop.telegram.org/) с оффициального сайта Telegram и поместите папку Telegram в корневую папку проекта.
2. Установите виртуальное python окружение и перейдите в него
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Установите pip зависимости
   ```bash
   pip install -r requirements.txt
   ```
4. Запустите
   ```bash
   python3 main.py
   ```  

## 🧪 Скриншоты приложения
<div align="left"><img src="images/app-screenshot.png" width="400"></div>

## ❗Решение проблем

###  ❌ Ошибка: 
`Failed building wheel for tgcrypto`
###  ✅ Решение:
Установите TgCrypto-pyrofork
```bash
pip install TgCrypto-pyrofork
```

## 📄 License
Проект находится под лицензией [GPLv3 license](LICENSE).

## Resourses
Иконка приложения от Pixel perfect
