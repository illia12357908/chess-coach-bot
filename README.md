# Chess Coach Bot

Free, fully automatic chess.com → Telegram coach. A few seconds after you finish a game you get:

- a **report** in Telegram: result, accuracy, blunders / mistakes / inaccuracies, key moments, what went well, what theory to study
- an **interactive review** (button under the report): board, move list, evaluation graph, move quality marks
  (best ★ / excellent / good / inaccuracy / mistake / blunder), better-move arrows, sound, and a
  *Next key moment* tour with a text explanation of each turning point
- **weekly digest** and menu buttons (latest game, pick from last 50, week, month)
- optional AI coach note in the digest (Anthropic API key, about 1.5 US cents per digest)

Everything runs on **GitHub Actions** (free for public repos) with Stockfish. Nothing to host, nothing running on your phone.
Русская инструкция: [README.ru.md](README.ru.md)

## Set it up (about 10 minutes, once)

1. **Fork** this repository (button at the top right). Keep it public: Actions minutes are unlimited for public repos.
2. **Telegram bot:** in Telegram open **@BotFather** → `/newbot` → copy the token (looks like `123456789:AAH...`, copy all of it, digits included).
   Open your new bot and press **Start**. Then open `https://api.telegram.org/bot<TOKEN>/getUpdates` in a browser
   (replace `<TOKEN>`, no `<>`) and copy the number after `"chat":{"id":` — that is your chat id.
3. In your fork: **Settings → Secrets and variables → Actions → New repository secret**, add:
   - `CHESSCOM_USERNAME` — your chess.com name
   - `TELEGRAM_BOT_TOKEN` — the token from BotFather
   - `TELEGRAM_CHAT_ID` — the number from step 2
   - `ANTHROPIC_API_KEY` — optional (AI note in the weekly digest)
   - optional *variable* (Variables tab) `TIMEZONE`, for example `Europe/Berlin` (default `Europe/Madrid`)
4. **Settings → Actions → General → Workflow permissions → Read and write permissions → Save.**
5. **Actions** tab → enable workflows, open **Chess report bot** → **Run workflow**. The Telegram menu and your last 3 games arrive.
6. **Settings → Pages → Deploy from a branch → `main` → `/docs` → Save.** This makes the interactive review open as a link.
   (Without it the bot still works and sends the review as an .html file, which you must open in Chrome/Safari.)

Done. The bot checks chess.com every ~5 minutes. After a game it starts a live session that checks every 30 seconds and shuts itself off after 25 idle minutes.

## Instant reports (optional, recommended)
GitHub's own schedule is slow (5–15 minutes). The free **Cloudflare Worker** in `cloudflare/worker.js` checks chess.com every minute and starts the bot as soon as a game ends.
1. Cloudflare dashboard → Workers → Create → paste `cloudflare/worker.js`.
2. Variables: `CHESSCOM_USERNAME`, `GITHUB_REPO` (`yourname/chess-coach-bot`), secret `GITHUB_TOKEN` (fine-grained token, only *Actions: Read and write* on this repo).
3. Triggers → Cron → `* * * * *`.

## Notes
- Accuracy uses a formula close to chess.com's, so numbers are similar but not identical. Move marks: best = engine's top move, excellent < 2% winning-chance loss, good < 5%, inaccuracy ≥ 5%, mistake ≥ 10%, blunder ≥ 20%.
- Piece art is the free *cburnett* set (the same style Lichess uses). Chess.com's own pieces and sounds are proprietary and are not copied; sounds are synthesised in the browser.
- Review links hold the game data after the `#`, so nothing about your games is stored on a server. Very long games (about 55+ moves) don't fit into a Telegram button and come as an .html file instead.
- Changing the review page: edit `viewer.py`, then run `python viewer.py --write-static docs/index.html` and commit.
- Run locally: `pip install -r requirements.txt`, install Stockfish, copy `.env.example` to `.env`, `python bot.py`.

License: MIT (see LICENSE for third-party notes).
