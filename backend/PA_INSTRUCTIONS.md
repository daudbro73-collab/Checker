# Как развернуть AML Guard на PythonAnywhere

## Шаг 1: Регистрация и файлы
1.  Зарегистрируйтесь на [PythonAnywhere](https://www.pythonanywhere.com/) (Beginner account - бесплатно).
2.  Перейдите во вкладку **Files**.
3.  Загрузите файл `aml_deploy.zip` (он лежит в папке `backend` на вашем компьютере).
4.  Откройте **Bash Console** (кнопка `$ Bash` сверху справа).
5.  Распакуйте архив командой:
    ```bash
    unzip aml_deploy.zip
    ```

## Шаг 2: Установка зависимостей
В той же консоли выполните команды:
```bash
# Создаем виртуальное окружение
python3 -m venv venv

# Активируем его
source venv/bin/activate

# Обновляем pip
pip install --upgrade pip

# Устанавливаем библиотеки
pip install -r requirements_full.txt
```

## Шаг 3: Настройка Web App
1.  Перейдите во вкладку **Web**.
2.  Нажмите **Add a new web app**.
3.  Нажмите **Next**, выберите **Manual configuration** (это важно!), выберите **Python 3.10** (или ту версию, для которой создали venv, обычно 3.10 по умолчанию).
4.  После создания, в разделе **Code**:
    *   **Source code:** `/home/ВАШ_НИК/`
    *   **Working directory:** `/home/ВАШ_НИК/`
5.  В разделе **Virtualenv**:
    *   Укажите путь: `/home/ВАШ_НИК/venv` (ВАШ_НИК - это ваш логин на PythonAnywhere).
6.  В разделе **WSGI configuration file**:
    *   Нажмите на ссылку (файлик).
    *   Удалите ВСЁ содержимое этого файла.
    *   Вставьте этот код:

```python
import sys
import os

# Путь к проекту
path = '/home/ВАШ_НИК'  # <-- ЗАМЕНИТЕ ВАШ_НИК НА СВОЙ ЛОГИН
if path not in sys.path:
    sys.path.append(path)

from wsgi import application
```
    *   Нажмите **Save**.

## Шаг 4: Запуск
1.  Вернитесь во вкладку **Web**.
2.  Нажмите зеленую кнопку **Reload <ваш-сайт>**.
3.  Откройте ссылку вашего сайта (например, `rustamberheev.pythonanywhere.com`). Если увидите `{ "message": "AML Guard API" }` или ошибку 404 (но от FastAPI) — значит сервер работает!

## Шаг 5: Обновление бота
1.  Вернитесь в **Files**.
2.  Откройте файл `bot.py`.
3.  Найдите строку `WEBAPP_URL = "..."`.
4.  Замените ссылку на ваш новый сайт: `https://ВАШ_НИК.pythonanywhere.com/webapp`.
5.  Сохраните (`Save`).
6.  Запустите бота. Для этого откройте **Bash Console** и напишите:
    ```bash
    source venv/bin/activate
    python bot.py
    ```
    *Важно: На бесплатном тарифе консоль может закрыться через некоторое время. Для теста это ок, но для постоянной работы лучше использовать "Always-on task" (платно) или запускать вручную раз в день.*
