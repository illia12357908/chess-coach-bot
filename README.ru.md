# Chess Coach Bot — инструкция по-русски

Бесплатный бот: после каждой партии на chess.com присылает в Telegram разбор (точность, ошибки, ключевые моменты, что учить)
и кнопку с интерактивным разбором (доска, оценки ходов, звук, пошаговые объяснения ключевых моментов). Работает на GitHub Actions, ничего хостить не надо.

## Установка (~10 минут, один раз)
1. Нажми **Fork** в правом верхнем углу этого репозитория. Оставь его публичным (так минуты GitHub Actions бесплатные и неограниченные).
2. **Telegram:** открой **@BotFather** → `/newbot` → скопируй токен целиком (вместе с цифрами до двоеточия).
   Открой своего бота и нажми **Start**. Затем открой в браузере `https://api.telegram.org/bot<ТОКЕН>/getUpdates`
   (без скобок `<>`) и найди число после `"chat":{"id":` — это твой chat id.
3. В своём форке: **Settings → Secrets and variables → Actions → New repository secret**:
   `CHESSCOM_USERNAME` (ник на chess.com), `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, по желанию `ANTHROPIC_API_KEY`.
   Часовой пояс: вкладка Variables → `TIMEZONE`, например `Europe/Kyiv`.
4. **Settings → Actions → General → Workflow permissions → Read and write permissions → Save.**
5. Вкладка **Actions** → включи workflows → **Chess report bot** → **Run workflow**. В Telegram придёт меню и последние 3 партии.
6. **Settings → Pages → Deploy from a branch → `main` → `/docs` → Save.** Тогда интерактивный разбор открывается ссылкой.

Дальше всё само. Для разбора через ~минуту после партии подключи бесплатный Cloudflare Worker (см. английский README, раздел *Instant reports*).

## Чат с тренером (по желанию)

Можно писать боту обычным текстом («почему я слил эту партию?», «дай новый дебют», «какие у меня слабые места?», «дай пазлы») — отвечает Claude по данным твоих разобранных партий и даёт ссылки на lichess.

Нужно в Cloudflare Worker (Settings → Variables and Secrets): `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `ANTHROPIC_API_KEY`, `TG_WEBHOOK_SECRET` (любая случайная строка). Затем один раз открыть `https://<твой-worker>.workers.dev/setup` — это подключит вебхук. Кнопки меню и команды `/latest`, `/week` при этом обрабатывает workflow «Chess action». Отключить: `/setup?off=1`.
