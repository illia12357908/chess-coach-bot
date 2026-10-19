// Chess watcher for Cloudflare Workers (free plan).
// Runs every minute (Cron Trigger "* * * * *"). If you finished a chess.com game in the last
// ~100 seconds, it starts the "Chess report bot" workflow on GitHub, which analyses the game
// and sends the report to Telegram.
//
// Variables (Worker -> Settings -> Variables and Secrets):
//   CHESSCOM_USERNAME  (text)    your chess.com username
//   GITHUB_REPO        (text)    illia12357908/chess-coach-bot
//   GITHUB_TOKEN       (secret)  fine-grained GitHub token, only "Actions: Read and write" on that repo

const WINDOW_SECONDS = 100;

async function latestGame(user) {
  const opts = { headers: { "User-Agent": `chess-watcher (chess.com user ${user})` } };
  const base = `https://api.chess.com/pub/player/${user.toLowerCase()}`;
  const archRes = await fetch(`${base}/games/archives`, opts);
  if (!archRes.ok) throw new Error(`chess.com archives: HTTP ${archRes.status}`);
  const arch = await archRes.json();
  const last = (arch.archives || []).slice(-1)[0];
  if (!last) return null;
  const monthRes = await fetch(last, opts);
  if (!monthRes.ok) throw new Error(`chess.com month: HTTP ${monthRes.status}`);
  const games = ((await monthRes.json()).games || []).filter((g) => g.rules === "chess" && g.end_time);
  if (!games.length) return null;
  return games.reduce((a, b) => (b.end_time > a.end_time ? b : a));
}

async function check(env) {
  const g = await latestGame(env.CHESSCOM_USERNAME);
  const age = g ? Math.round(Date.now() / 1000 - g.end_time) : null;
  return { url: g ? g.url : null, age_seconds: age, fresh: age !== null && age >= 0 && age <= WINDOW_SECONDS };
}

async function dispatch(env) {
  const r = await fetch(`https://api.github.com/repos/${env.GITHUB_REPO}/actions/workflows/chess-bot.yml/dispatches`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "chess-watcher",
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ ref: "main", inputs: { listen_minutes: "0" } }),
  });
  if (r.status !== 204) throw new Error(`GitHub dispatch failed: HTTP ${r.status} ${await r.text()}`);
}

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(
      (async () => {
        try {
          const res = await check(env);
          if (res.fresh) {
            await dispatch(env);
            console.log("Started GitHub workflow for", res.url);
          }
        } catch (e) {
          console.log("watcher error:", String(e));
        }
      })()
    );
  },
  // Opening the Worker URL in a browser is a safe self-test: it only reads chess.com and never starts anything.
  async fetch(request, env) {
    try {
      const res = await check(env);
      const config = { user: !!env.CHESSCOM_USERNAME, repo: !!env.GITHUB_REPO, token: !!env.GITHUB_TOKEN };
      return Response.json({ ok: true, config, latest_game: res });
    } catch (e) {
      return Response.json({ ok: false, error: String(e) }, { status: 500 });
    }
  },
};
