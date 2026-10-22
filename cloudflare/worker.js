// Chess watcher for Cloudflare Workers (free plan).
// Runs every minute (Cron Trigger "* * * * *"). If your latest chess.com game has not been reported yet
// (checked against data/state.json in your repo) and no bot run is already queued or running, it starts the
// "Chess report bot" workflow on GitHub, which analyses the game and sends the report to Telegram.
//
// Variables (Worker -> Settings -> Variables and Secrets):
//   CHESSCOM_USERNAME  (text)    your chess.com username
//   GITHUB_REPO        (text)    illia12357908/chess-coach-bot
//   GITHUB_TOKEN       (secret)  fine-grained GitHub token, only "Actions: Read and write" on that repo
// Chat with the coach (optional, needs the four below):
//   TELEGRAM_BOT_TOKEN (secret)  your bot token
//   TELEGRAM_CHAT_ID   (text)    your chat id (only this chat is answered)
//   ANTHROPIC_API_KEY  (secret)  key from console.anthropic.com
//   TG_WEBHOOK_SECRET  (secret)  any random string; Telegram sends it back so only Telegram can call the worker
//   ANTHROPIC_MODEL    (text, optional) default claude-sonnet-5-5

const MAX_AGE_SECONDS = 6 * 3600; // never react to games older than this (avoids replaying history)

async function latestGame(user) {
  const opts = { headers: { "User-Agent": `chess-watcher (chess.com user ${user})`, "Cache-Control": "no-cache" } };
  const bust = () => `?_=${Date.now()}`;
  const base = `https://api.chess.com/pub/player/${user.toLowerCase()}`;
  const archRes = await fetch(`${base}/games/archives${bust()}`, opts);
  if (!archRes.ok) throw new Error(`chess.com archives: HTTP ${archRes.status}`);
  const arch = await archRes.json();
  const last = (arch.archives || []).slice(-1)[0];
  if (!last) return null;
  const monthRes = await fetch(last + bust(), opts);
  if (!monthRes.ok) throw new Error(`chess.com month: HTTP ${monthRes.status}`);
  const games = ((await monthRes.json()).games || []).filter((g) => g.rules === "chess" && g.end_time);
  if (!games.length) return null;
  return games.reduce((a, b) => (b.end_time > a.end_time ? b : a));
}

const GH = (env, path, init = {}) =>
  fetch(`https://api.github.com/repos/${env.GITHUB_REPO}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${env.GITHUB_TOKEN}`,
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "chess-watcher",
      "Content-Type": "application/json",
    },
  });

// Is a bot or live run already queued / running? Then it will pick the new game up itself.
async function botBusy(env) {
  const r = await GH(env, "/actions/runs?per_page=20");
  if (!r.ok) throw new Error(`GitHub runs: HTTP ${r.status}`);
  const runs = (await r.json()).workflow_runs || [];
  return runs.some((x) => x.status !== "completed" && ["Chess report bot", "Chess live mode"].includes(x.name));
}

// Has the bot already reported this game? (the bot keeps data/state.json in the repo, which is public)
async function alreadySeen(env, url) {
  const r = await fetch(`https://raw.githubusercontent.com/${env.GITHUB_REPO}/main/data/state.json?_=${Date.now()}`, {
    headers: { "Cache-Control": "no-cache" },
  });
  if (!r.ok) return false;
  const st = await r.json();
  return Object.prototype.hasOwnProperty.call(st.seen || {}, url);
}

// Decide what to do. Returns {action, ...details}.
async function check(env) {
  const g = await latestGame(env.CHESSCOM_USERNAME);
  if (!g) return { action: "none", reason: "no games" };
  const age = Math.round(Date.now() / 1000 - g.end_time);
  const info = { url: g.url, age_seconds: age };
  if (age > MAX_AGE_SECONDS) return { action: "none", reason: "latest game is old", ...info };
  if (await alreadySeen(env, g.url)) return { action: "none", reason: "already reported", ...info };
  if (await botBusy(env)) return { action: "none", reason: "bot already running or queued", ...info };
  return { action: "dispatch", reason: "new game", ...info };
}

async function dispatch(env) {
  const r = await GH(env, "/actions/workflows/chess-bot.yml/dispatches", {
    method: "POST",
    body: JSON.stringify({ ref: "main", inputs: { listen_minutes: "0" } }),
  });
  if (r.status !== 204) throw new Error(`GitHub dispatch failed: HTTP ${r.status} ${await r.text()}`);
}


// ---------------------------------------------------------------- chat with the coach

const LICHESS_THEMES = "fork pin skewer discoveredAttack hangingPiece trappedPiece backRankMate mateIn1 mateIn2 mateIn3 " +
  "endgame rookEndgame pawnEndgame bishopEndgame knightEndgame queenEndgame deflection attraction sacrifice defensiveMove " +
  "advantage crushing opening middlegame quietMove zugzwang promotion exposedKing interference clearance";

function systemPrompt(env, context) {
  return `You are the personal chess coach of ${env.CHESSCOM_USERNAME}, talking in a Telegram chat. You coach like a good human trainer, not like a generic assistant.

STYLE
- Answer in the language the player writes in (usually Russian). Plain text only, no markdown, no tables. Usually under 150 words; go longer only when the player asks for a full explanation.
- Be direct and specific: name the game, the move number and the move. Say what happened, why it happened, and what to do about it. Praise only what the data really shows.
- Give ONE main lesson and ONE concrete drill per answer, not a list of ten tips. Ask at most one clarifying question, and only if you truly need it.

HOW TO COACH
- Find the pattern before the symptom: look across games for the repeated cause (hanging pieces, missed tactics, collapses after a good opening, time trouble in bullet/blitz, one weak opening). Separate tactical oversights from strategic or opening problems and treat them differently.
- Match advice to the level (see ratings): at this level the biggest gains come from blunder checks, not losing won positions, simple solid openings and clock use, not from deep theory.
- Opening advice: choose lines that fit the colour, the openings already in the data and the mistakes found. Give 6-10 moves, the main plan in one sentence and the typical trap or mistake to avoid.

HONESTY (very important)
- The Stockfish evaluations and the "better" moves in the data are the ground truth. Never call a move good or bad against them. Evaluations are in pawns from White's point of view.
- You cannot calculate chess reliably in your head. Do not invent variations, tactics or positions. If you want to explain why a move is bad and the data only says what the engine prefers, say "Stockfish prefers X" and give the idea only if it is simple and certain (for example a piece is left hanging).
- To see the moves of a game, call the get_game tool (game 1 is the latest). Use it whenever the player asks about a particular game or move, or before explaining a mistake. If the player asks about something not in the data, say so.

LICHESS LINKS (use exactly these forms; never invent other URLs, puzzle ids or study ids)
- Puzzles by theme: https://lichess.org/training/<theme>, theme is one of: ${LICHESS_THEMES}. Daily puzzle: https://lichess.org/training/daily
- Opening line on an analysis board: https://lichess.org/analysis/pgn/<moves in SAN joined by underscores>, for example https://lichess.org/analysis/pgn/e4_c5_Nf3_d6_d4_cxd4_Nxd4_Nf6_Nc3_a6. Only give move sequences you are sure are correct theory. The player can open the Explorer tab on that page to see how others play the line.
- Map weaknesses to 2-4 puzzle themes when asked for puzzles.

PLAYER DATA (accuracy is win-probability based; blunder >=20% win-chance loss, mistake >=10%, inaccuracy >=5%; "key" lists the worst moves)
${context}`;
}

function compactGame(g) {
  const fb = g.first_bad ? ` first_bad=${g.first_bad.move_no}.${g.first_bad.san}(best ${g.first_bad.best})` : "";
  const tags = g.tags && Object.keys(g.tags).length ? ` tags=${JSON.stringify(g.tags)}` : "";
  const pa = g.phase_acc ? ` phase_acc=${JSON.stringify(g.phase_acc)}` : "";
  const km = (g.key_moments || []).slice(0, 4)
    .map((m) => `${m.move_no}${m.color === "b" ? "..." : "."}${m.san}:${m.cls}`).join(",");
  return `${new Date(g.end_time * 1000).toISOString().slice(0, 10)} ${g.time_class} ${g.color} ${g.outcome} vs ${g.opp_rating} ` +
    `| ${g.opening} | acc ${g.accuracy} (opp ${g.opp_accuracy}) | B${g.blunders} M${g.mistakes} I${g.inaccuracies}` +
    `${g.blown_win ? " blown_win" : ""}${g.early_error ? " early_error" : ""}${fb}${tags}${pa}${km ? " key=" + km : ""}`;
}

async function playerContext(env) {
  const r = await fetch(`https://raw.githubusercontent.com/${env.GITHUB_REPO}/main/data/state.json?_=${Date.now()}`, {
    headers: { "Cache-Control": "no-cache" },
  });
  if (!r.ok) return "(no analysed games available yet)";
  const st = await r.json();
  const games = Object.values(st.games || {}).sort((a, b) => b.end_time - a.end_time).slice(0, 30);
  if (!games.length) return "(no analysed games available yet)";
  const rated = games.filter((g) => g.accuracy != null);
  const avg = rated.length ? (rated.reduce((s, g) => s + Number(g.accuracy), 0) / rated.length).toFixed(1) : "?";
  const tagTotals = {};
  for (const g of games) for (const [k, v] of Object.entries(g.tags || {})) tagTotals[k] = (tagTotals[k] || 0) + v;
  const wins = games.filter((g) => g.outcome === "win").length;
  const head = `Games: ${games.length} (newest first), wins ${wins}, average accuracy ${avg}. Error tags over all games: ${JSON.stringify(tagTotals)}.\n`;
  return head + games.map((g, i) => `#${i + 1}${i === 0 ? " (latest)" : ""}: ${compactGame(g)}`).join("\n");
}

async function tg(env, method, body) {
  const r = await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/${method}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return r.json().catch(() => ({}));
}

const TOOLS = [{
  name: "get_game",
  description: "Full move list of one analysed game with Stockfish evaluation after every move (pawns, White's view), marks (?? blunder, ? mistake, ?! inaccuracy, !! brilliant) and the better move for errors. game_number 1 = latest game, 2 = the one before, and so on (same numbers as in the player data).",
  input_schema: { type: "object", properties: { game_number: { type: "integer", minimum: 1, maximum: 30 } }, required: ["game_number"] },
}];

async function loadGames(env) {
  const r = await fetch(`https://raw.githubusercontent.com/${env.GITHUB_REPO}/main/data/state.json?_=${Date.now()}`, { headers: { "Cache-Control": "no-cache" } });
  if (!r.ok) return [];
  const st = await r.json();
  return Object.values(st.games || {}).sort((a, b) => b.end_time - a.end_time).slice(0, 30);
}

async function runTool(env, name, input) {
  if (name !== "get_game") return "unknown tool";
  const g = (await loadGames(env))[(input.game_number || 1) - 1];
  if (!g) return "no such game";
  if (!g.review) return "The full move list of this game is not stored (only the 60 most recent games have it). Use the summary line from the player data.";
  return `${g.color === "white" ? "Player had White" : "Player had Black"}, ${g.outcome}, opening ${g.opening}. Moves:\n${g.review}`;
}

async function askCoach(env, question, replyTo) {
  const context = await playerContext(env);
  const content = replyTo ? `(In reply to this earlier message of yours: """${replyTo.slice(0, 1500)}""")\n\n${question}` : question;
  const messages = [{ role: "user", content }];
  for (let step = 0; step < 5; step++) {
    const r = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: { "x-api-key": env.ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json" },
      body: JSON.stringify({
        model: env.ANTHROPIC_MODEL || "claude-sonnet-5-5",
        max_tokens: 1000,
        system: systemPrompt(env, context),
        tools: TOOLS,
        messages,
      }),
    });
    if (!r.ok) throw new Error(`Anthropic HTTP ${r.status}: ${(await r.text()).slice(0, 300)}`);
    const j = await r.json();
    if (j.stop_reason !== "tool_use") {
      return (j.content || []).map((b) => b.text || "").join("").trim() || "(empty answer)";
    }
    messages.push({ role: "assistant", content: j.content });
    const results = [];
    for (const b of j.content.filter((x) => x.type === "tool_use")) {
      let out;
      try { out = await runTool(env, b.name, b.input || {}); } catch (e) { out = "tool error: " + String(e); }
      results.push({ type: "tool_result", tool_use_id: b.id, content: String(out).slice(0, 12000) });
    }
    messages.push({ role: "user", content: results });
  }
  return "Не удалось собрать ответ, попробуй переформулировать вопрос.";
}

// Buttons and /commands need Stockfish, so they go to the GitHub workflow "Chess action".
async function forwardToBot(env, update) {
  const slim = {};
  if (update.callback_query) {
    const cq = update.callback_query, m = cq.message || {};
    slim.callback_query = { id: cq.id, data: cq.data, message: { message_id: m.message_id, text: (m.text || "").slice(0, 200), chat: { id: m.chat && m.chat.id } } };
  } else {
    slim.message = { text: update.message.text, chat: { id: update.message.chat.id } };
  }
  slim.update_id = update.update_id;
  const r = await GH(env, "/actions/workflows/chess-action.yml/dispatches", {
    method: "POST",
    body: JSON.stringify({ ref: "main", inputs: { update: JSON.stringify(slim) } }),
  });
  if (r.status !== 204) throw new Error(`GitHub dispatch failed: HTTP ${r.status} ${await r.text()}`);
}

async function handleUpdate(env, update) {
  const chatOf = update.callback_query ? (update.callback_query.message || {}).chat : (update.message || {}).chat;
  if (!chatOf || String(chatOf.id) !== String(env.TELEGRAM_CHAT_ID).trim()) return; // only the owner
  try {
    if (update.callback_query) {
      await tg(env, "answerCallbackQuery", { callback_query_id: update.callback_query.id });
      await forwardToBot(env, update);
      return;
    }
    const m = update.message;
    const text = (m.text || "").trim();
    if (!text) return;
    if (text.startsWith("/")) {
      await tg(env, "sendChatAction", { chat_id: chatOf.id, action: "typing" });
      await forwardToBot(env, update);
      return;
    }
    if (!env.ANTHROPIC_API_KEY) {
      await tg(env, "sendMessage", { chat_id: chatOf.id, text: "Chat is not set up yet: add ANTHROPIC_API_KEY to the Cloudflare Worker." });
      return;
    }
    await tg(env, "sendChatAction", { chat_id: chatOf.id, action: "typing" });
    const answer = await askCoach(env, text, m.reply_to_message && m.reply_to_message.text);
    await tg(env, "sendMessage", { chat_id: chatOf.id, text: answer.slice(0, 3900), disable_web_page_preview: true });
  } catch (e) {
    console.log("chat error:", String(e));
    await tg(env, "sendMessage", { chat_id: chatOf.id, text: "Не получилось ответить: " + String(e).slice(0, 300) });
  }
}

async function setupWebhook(env, origin, off) {
  if (off) return tg(env, "deleteWebhook", {});
  return tg(env, "setWebhook", {
    url: `${origin}/telegram`,
    secret_token: env.TG_WEBHOOK_SECRET,
    allowed_updates: ["message", "callback_query"],
    drop_pending_updates: false,
  });
}

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(
      (async () => {
        try {
          const res = await check(env);
          console.log("tick:", JSON.stringify(res));
          if (res.action === "dispatch") {
            await dispatch(env);
            console.log("Started GitHub workflow for", res.url);
          }
        } catch (e) {
          console.log("watcher error:", String(e));
        }
      })()
    );
  },
  // Opening the Worker URL shows what the next tick would do (starts nothing).
  // ?dispatch=1 starts the GitHub workflow once and shows GitHub's answer (token test).
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    try {
      if (url.pathname === "/telegram" && request.method === "POST") {
        if (!env.TG_WEBHOOK_SECRET || request.headers.get("X-Telegram-Bot-Api-Secret-Token") !== env.TG_WEBHOOK_SECRET) {
          return new Response("forbidden", { status: 403 });
        }
        const update = await request.json();
        ctx.waitUntil(handleUpdate(env, update)); // answer Telegram at once, work in the background
        return new Response("ok");
      }
      if (url.pathname === "/setup") {
        const res = await setupWebhook(env, url.origin, url.searchParams.get("off") === "1");
        return Response.json({ ok: !!res.ok, telegram: res });
      }
    } catch (e) {
      return Response.json({ ok: false, error: String(e) }, { status: 500 });
    }
    try {
      if (new URL(request.url).searchParams.get("dispatch") === "1") {
        try { await dispatch(env); return Response.json({ ok: true, dispatched: true }); }
        catch (e) { return Response.json({ ok: false, error: String(e) }, { status: 500 }); }
      }
      const res = await check(env);
      const config = { user: !!env.CHESSCOM_USERNAME, repo: !!env.GITHUB_REPO, token: !!env.GITHUB_TOKEN,
        chat: !!(env.TELEGRAM_BOT_TOKEN && env.TELEGRAM_CHAT_ID && env.ANTHROPIC_API_KEY && env.TG_WEBHOOK_SECRET) };
      return Response.json({ ok: true, version: "v6-coach", config, decision: res });
    } catch (e) {
      return Response.json({ ok: false, error: String(e) }, { status: 500 });
    }
  },
};
