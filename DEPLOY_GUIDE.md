# 🚀 AML Guard — Руководство по развертыванию

## Быстрый чек-лист

- [ ] Купить VPS (Ubuntu 22.04)
- [ ] Купить домен
- [ ] Настроить DNS (A-запись → IP сервера)
- [ ] Загрузить проект на сервер
- [ ] Запустить Docker
- [ ] Настроить Nginx + SSL
- [ ] Запустить Telegram бота

---

## 0. Секреты (.env)

Скопируйте `.env.example` → `.env` и заполните:

- `SECRET_KEY` — новый длинный random
- `BOT_TOKEN` — новый токен от @BotFather (старый в git считать скомпрометированным)
- `WEBAPP_URL` — `https://your-domain.com/webapp`
- `PAYMENT_ADDRESS_TRON` / `PAYMENT_ADDRESS_ETH` / `PAYMENT_ADDRESS_BSC` / `PAYMENT_ADDRESS_SOL`
- `TREASURY_ADDRESS_*` — чистые холодные кошельки для вывода средств
- `DATABASE_URL` / `REDIS_URL` (compose задаёт сам)
- `TRONGRID_API_KEY` (рекомендуется для TronGrid Pro)

## 1. Покупка сервера (VPS)


Нужен VPS с **Ubuntu 22.04 LTS**, минимум **1 CPU / 1 GB RAM**.

| Провайдер | Цена | Плюсы |
|-----------|------|-------|
| **Hetzner** (CPX11) | ~5€/мес | Лучшее цена/качество, ЕС |
| **Aeza** | ~300₽/мес | Принимает карты РФ |
| **DigitalOcean** | $6/мес | Классика, хорошие гайды |

После покупки вы получите **IP-адрес** и **пароль root**.

---

## 2. Покупка домена

Рекомендуемые домены:
- `amlguard.io` / `amlguard.pro` / `aml-check.io`
- Покупайте на **Namecheap**, **Reg.ru** или **GoDaddy**

### Настройка DNS

Зайдите в DNS-панель домена и создайте **A-запись**:

| Type | Host | Value |
|------|------|-------|
| A | @ | `ВАШ_IP_СЕРВЕРА` |
| A | www | `ВАШ_IP_СЕРВЕРА` |

⏰ DNS обновляется за 5-30 минут.

---

## 3. Подготовка сервера

```bash
# Подключаемся к серверу
ssh root@ВАШ_IP

# Обновляем систему + ставим Docker
apt update && apt upgrade -y
apt install docker.io docker-compose nginx certbot python3-certbot-nginx -y
```

---

## 4. Загрузка проекта

**На вашем Mac** (новая вкладка терминала):

```bash
cd /Users/rustamberheev/Desktop/AML

# Загружаем архив на сервер
scp aml_deploy.tar.gz root@ВАШ_IP:~/
```

---

## 5. Запуск!

**На сервере:**

```bash
cd ~
tar -xzf aml_deploy.tar.gz
cp .env.example .env   # заполните секреты
docker-compose up -d --build
```

Сервисы: `aml-backend`, `aml-worker` (OFAC/labels sync), `aml-bot`, `postgres`, `redis`.

Проверка: `curl http://localhost:8000/health`

---

## 6. Настройка домена + HTTPS

### Nginx конфигурация

```bash
nano /etc/nginx/sites-available/aml
```

Вставить (замените `your-domain.com`):

```nginx
server {
    server_name your-domain.com www.your-domain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Увеличенный таймаут для анализа
    proxy_read_timeout 30s;
    proxy_connect_timeout 10s;
}
```

Сохранить: `Ctrl+X` → `Y` → `Enter`

```bash
# Включаем сайт
ln -s /etc/nginx/sites-available/aml /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx

# Получаем SSL-сертификат (бесплатно!)
certbot --nginx -d your-domain.com -d www.your-domain.com
```

✅ **Готово!** Сайт доступен по `https://your-domain.com`

---

## 7. Telegram бот

Бот поднимается сервисом `aml-bot` в compose (нужны `BOT_TOKEN` и `WEBAPP_URL` в `.env`).

Отдельный `docker exec` больше не нужен.

---

## 8. Интеграция с ON Messenger

Просто добавьте ссылку `https://your-domain.com` в мессенджер:
- Кнопка "AML Check" в настройках кошелька
- Баннер в чате при получении крипто-перевода
- Раздел "Безопасность" в профиле

---

## Полезные команды

```bash
# Логи
docker-compose logs -f

# Перезапуск
docker-compose restart

# Обновление (загрузить новый архив и пересобрать)
docker-compose down
docker-compose up -d --build

# Статус
docker ps
```
