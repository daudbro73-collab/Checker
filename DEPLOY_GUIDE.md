# Руководство по развертыванию (Deployment Guide)

## 1. Аренда Сервера (VPS) и Домена

### Шаг А: Покупка сервера
Вам нужен любой VPS с **Ubuntu 22.04**.
**Где брать:**
- **Hetzner** (Cloud CPX11) — ~5€ (Лучший выбор цена/качество)
- **Aeza** (Москва/Европа) — принимает карты РФ, быстрая поддержка.
- **DigitalOcean** — классика ($6/мес).

**Что выбрать при создании:**
- **OS**: Ubuntu 22.04 LTS (Обязательно!)
- **Location**: Любая (Финляндия/Германия для Hetzner).

После покупки вам на почту придет IP-адрес и пароль (root).

### Шаг Б: Покупка Домена
Купите домен (например, `aml-guardian.io`) на Namecheap, Reg.ru или GoDaddy.
Сразу зайдите в настройки DNS и создайте **A-запись**:
- **Type**: A
- **Host**: @ (или пустое поле)
- **Value**: IP-адрес вашего нового сервера (например, `45.132.x.x`)

---

## 2. Подготовка Сервера

Откройте терминал на Mac и подключитесь к новому серверу:
```bash
ssh root@ВАШ_IP
# Введите пароль из письма (при вводе его не видно)
```

Обновите систему и установите Docker (просто скопируйте все сразу):
```bash
apt update && apt upgrade -y
apt install docker.io docker-compose -y
```

---

## 3. Загрузка проекта (С вашего Mac)

**НЕ закрывайте** терминал с сервером.
Откройте **НОВОЕ окно терминала** на вашем Mac (`Cmd + T`).

Перейдите в папку с архивом (где лежит `aml_deploy.tar.gz`):
```bash
cd /Users/rustamberheev/Desktop/AML
```

Отправьте файл на сервер:
```bash
# Если сервер по паролю (Aeza/Hetzner):
scp aml_deploy.tar.gz root@ВАШ_IP:~/

# Если сервер по ключу (AWS/Oracle):
scp -i /путь/к/ключу.pem aml_deploy.tar.gz ubuntu@ВАШ_IP:~/
```

---

## 4. Запуск!

Вернитесь в окно терминала, где вы подключены к серверу.

Распакуйте и запустите:
```bash
tar -xzf aml_deploy.tar.gz
cd .
docker-compose up -d --build
```

Всё! Сайт работает по адресу `http://ВАШ_IP:8000`.

---

## 5. Подключение Домена и HTTPS (Зеленый замочек)

Чтобы сайт открывался по домену (`https://your-domain.com`):

1. Установите Nginx:
```bash
apt install nginx certbot python3-certbot-nginx -y
```

2. Создайте конфиг (замените `your-domain.com` на ваш домен):
```bash
nano /etc/nginx/sites-available/aml
```

Вставьте этот текст:
```nginx
server {
    server_name your-domain.com www.your-domain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```
*(Нажмите `Ctrl+X`, затем `Y`, затем `Enter` для сохранения)*

3. Включите сайт:
```bash
ln -s /etc/nginx/sites-available/aml /etc/nginx/sites-enabled/
rm /etc/nginx/sites-enabled/default
systemctl restart nginx
```

4. Получите сертификат (SSL):
```bash
certbot --nginx -d your-domain.com
```

**Поздравляю! Ваш AML-сервис доступен всему миру! 🚀**

