# Запуск и настройка

Три контейнера. `vharvest` читает шары Keenetic и пишет карточки в Postgres. `web` показывает каталог в локальной сети. Ollama стоит на компьютере, не в Compose: контейнеру нужен GPU этой машины.

Сайт не проксирует видео. Пути для плеера описаны в [README.md](../README.md).

## Запуск

Docker Desktop должен быть запущен. Ollama на этом компьютере слушает `0.0.0.0:11434`.

```powershell
docker compose up -d --build
```

Сайт: `http://<IP-этого-ПК>:8080`

Первый запуск сам начинает скан, если база пустая, есть карточки в статусе `pending` или у уверенных карточек ещё не спрошен Кинопоиск. Потом скан идёт каждую ночь в 03:00 по Москве. Повтор с этого компьютера:

```powershell
$token = ((Get-Content .env | Where-Object { $_ -like 'SCAN_TOKEN=*' }) -split '=', 2)[1]
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8080/api/scan -Headers @{ Authorization = "Bearer $token" }
```

Пока идёт разбор, шапка сайта показывает файл и счётчик. Повторный запуск не стартует второй проход.

Номер карточки виден в каталоге и на странице фильма: кнопка «Карточка N» копирует его. Сброс очищает эти карточки и собирает их заново, без обхода шар. Пока идёт скан или другой сброс, команда отвечает отказом.

Та же форма открывается в браузере: `http://<IP-этого-ПК>:8080/service`. Пароль — `SCAN_TOKEN`. Сайт держит его только в этой вкладке и не записывает на сервер.

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8080/api/movies/reset -Headers @{ Authorization = "Bearer $token" } -ContentType "application/json" -Body '{"ids":[1,2]}'
```

За один сброс — не больше 100 номеров.

## Что лежит в `.env`

Рабочий файл не коммитится. Образец полей — `.env.example`.

- `TMDB_API_KEY`, `KP_API_KEY` — карточка, постер, жанры, актёры и рейтинг Кинопоиска.
- `SMB_LOGIN`, `SMB_PASSWORD` — чтение шар. Пароль без запятой: запятая ломает параметры монтирования.
- `KEENETIC_IP` — адрес `Keenetic-1601`, с него монтируются `ADATA SC610` и `KINGSTON`.
- `SMB_HOST` — имя хоста в путях `\\хост\шара` и `smb://`. По умолчанию `Keenetic-1601`.
- `SCAN_TOKEN` — пароль команд скана и сброса.
- `SCAN_CRON` — расписание ночного скана, по умолчанию `0 3 * * *`, часовой пояс Москва.
- `OLLAMA_MODEL` — модель, которая вытаскивает название из имени файла. Адрес Ollama для контейнера задан в `docker-compose.yml`: `http://host.docker.internal:11434`.
- `MIN_FILE_BYTES` — файлы меньше этого размера пропускаются. По умолчанию 50 МБ.
- `WEB_PORT` — порт сайта на компьютере, по умолчанию `8080`.

Служебные папки торрент-клиента (`blocklists`, `resume`, `torrents`, `watch`) и скрытые каталоги пропускаются. Файлы меньше `MIN_FILE_BYTES` тоже. Папка `download` сканируется вместе с остальными, включая вложенные каталоги. Берутся `mkv`, `mp4`, `avi`, `mov`, `m4v`, `wmv` и `ts`. Звуковые дорожки `.ac3` рядом с фильмом в каталог не попадают. Файлы `sample` и короткие имена с `trailer` пропускаются.

Если шара не смонтировалась, смотрите `docker compose logs vharvest` и сообщение `docker compose up`. После смены пароля SMB пересоздайте только тома шар:

```powershell
docker compose down
docker volume rm video_catalog_adata video_catalog_kingston
docker compose up -d
```

`docker compose down -v` удалит ещё и базу с постерами.

## Проверки кода

Зависимости службы — `vharvest/requirements.txt`. Из каталога `vharvest`:

```powershell
python -m unittest discover -s tests
```

Тесты не ходят в шары, Postgres и внешние API.
