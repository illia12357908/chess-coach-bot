#!/usr/bin/env python3
"""
Chess.com -> Telegram game report bot.

- Polls chess.com for your newly finished games
- Analyses them locally with Stockfish
- Sends a Telegram report: accuracy, key mistakes, what went well, and theory to study
- Weekly digest + on-demand commands (/latest, /week, /month, /check)

Run:  python bot.py            (long-running loop)
      python bot.py --once     (check once and exit, for cron)
      python bot.py --test-pgn game.pgn --user YourName   (print a report locally)
      python bot.py --get-chat-id                         (find your Telegram chat id)
"""
import argparse
import html
import io
import json
import logging
import math
import os
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import chess
import chess.engine
import chess.pgn
import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

log = logging.getLogger("chessbot")

# --------------------------------------------------------------------------- config


class Config:
    def __init__(self, require_telegram=True):
        self.username = os.environ.get("CHESSCOM_USERNAME", "").strip()
        self.tg_token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        self.tg_chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
        self.stockfish = os.environ.get("STOCKFISH_PATH", "stockfish")
        self.depth = int(os.environ.get("ENGINE_DEPTH", "14"))
        self.move_time = float(os.environ.get("ENGINE_MOVE_TIME", "0.6"))  # max sec/position
        self.threads = int(os.environ.get("ENGINE_THREADS", "2"))
        self.hash_mb = int(os.environ.get("ENGINE_HASH_MB", "128"))
        self.poll_minutes = float(os.environ.get("POLL_MINUTES", "10"))
        self.backfill = int(os.environ.get("INITIAL_BACKFILL", "3"))
        self.data_dir = Path(os.environ.get("DATA_DIR", "data"))
        self.digest_day = os.environ.get("WEEKLY_DIGEST_DAY", "sun").lower()[:3]  # or "off"
        self.digest_hour = int(os.environ.get("WEEKLY_DIGEST_HOUR", "18"))
        self.tz = os.environ.get("TIMEZONE", "UTC")
        self.anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        self.anthropic_model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5")
        if not self.username:
            sys.exit("Set CHESSCOM_USERNAME")
        if require_telegram and not (self.tg_token and self.tg_chat):
            sys.exit("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID (see README)")


# --------------------------------------------------------------------------- state


class State:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.data = {"seen": {}, "games": {}, "tg_offset": 0, "last_digest": ""}
        if path.exists():
            try:
                self.data.update(json.loads(path.read_text()))
            except Exception:
                log.exception("Could not read state, starting fresh")

    def save(self):
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=1))
        tmp.replace(self.path)


# --------------------------------------------------------------------------- chess.com


def cc_get(url, username):
    r = requests.get(
        url,
        headers={"User-Agent": f"chess-report-bot (chess.com user: {username})"},
        timeout=30,
    )
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


def fetch_recent_games(username, months=2):
    base = f"https://api.chess.com/pub/player/{username.lower()}"
    arch = cc_get(f"{base}/games/archives", username)
    if not arch:
        raise RuntimeError(f"chess.com user '{username}' not found")
    games = []
    for url in arch["archives"][-months:]:
        data = cc_get(url, username) or {}
        for g in data.get("games", []):
            if g.get("rules") == "chess" and g.get("pgn") and g.get("url"):
                games.append(g)
    games.sort(key=lambda g: g.get("end_time", 0))
    return games


def fetch_games_limit(username, n=50):
    """Last n standard-chess games (looks back through monthly archives as needed)."""
    base = f"https://api.chess.com/pub/player/{username.lower()}"
    arch = cc_get(f"{base}/games/archives", username)
    if not arch:
        raise RuntimeError(f"chess.com user '{username}' not found")
    games = []
    for url in reversed(arch["archives"]):
        data = cc_get(url, username) or {}
        games += [g for g in data.get("games", [])
                  if g.get("rules") == "chess" and g.get("pgn") and g.get("url")]
        if len(games) >= n:
            break
    games.sort(key=lambda g: g.get("end_time", 0))
    return games[-n:]


# --------------------------------------------------------------------------- analysis

VALUES = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}
NAMES = {chess.PAWN: "pawn", chess.KNIGHT: "knight", chess.BISHOP: "bishop",
         chess.ROOK: "rook", chess.QUEEN: "queen"}
DRAWS = {"agreed", "repetition", "stalemate", "insufficient", "50move", "timevsinsufficient"}


def win_pct(cp):
    cp = max(-1000, min(1000, cp))
    return 50 + 50 * (2 / (1 + math.exp(-0.00368208 * cp)) - 1)


def move_accuracy(loss_wp):
    return max(0.0, min(100.0, 103.1668 * math.exp(-0.04354 * loss_wp) - 3.1668))


def classify(loss_wp):
    if loss_wp >= 20:
        return "blunder"
    if loss_wp >= 10:
        return "mistake"
    if loss_wp >= 5:
        return "inaccuracy"
    return "ok"


def non_pawn_material(board):
    return sum(VALUES[p.piece_type] for p in board.piece_map().values()
               if p.piece_type in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN))


def phase_of(board):
    if non_pawn_material(board) <= 26:
        return "endgame"
    if board.fullmove_number <= 10:
        return "opening"
    return "middlegame"


def endgame_type(board):
    kinds = {p.piece_type for p in board.piece_map().values()
             if p.piece_type not in (chess.PAWN, chess.KING)}
    if not kinds:
        return "king and pawn"
    if kinds == {chess.ROOK}:
        return "rook"
    if kinds == {chess.QUEEN}:
        return "queen"
    if kinds <= {chess.KNIGHT, chess.BISHOP}:
        return "minor-piece"
    if kinds <= {chess.ROOK, chess.KNIGHT, chess.BISHOP}:
        return "rook and minor-piece"
    return "mixed"


def captured_value(board, move):
    if board.is_en_passant(move):
        return 1
    p = board.piece_at(move.to_square)
    return VALUES.get(p.piece_type, 0) if p else 0


def captured_name(board, move):
    if board.is_en_passant(move):
        return "pawn"
    p = board.piece_at(move.to_square)
    return NAMES.get(p.piece_type, "piece") if p else "piece"


def opening_from_headers(h):
    url = h.get("ECOUrl", "")
    name = ""
    if url:
        slug = url.rstrip("/").split("/")[-1]
        toks = []
        for t in slug.split("-"):
            if re.match(r"^\d+\.", t):
                break
            toks.append(t)
        name = " ".join(toks)
    if not name:
        name = h.get("Opening") or h.get("ECO") or "Unknown opening"
    return name, url


def eval_str(cp):
    if abs(cp) >= 9000:
        return "mate"
    return f"{cp / 100:+.1f}"


def analyse_position(engine, board, limit):
    if board.is_checkmate():
        cp = -10000 if board.turn == chess.WHITE else 10000
        return {"cp": cp, "mate": 0, "best": None}
    if board.is_game_over(claim_draw=False):
        return {"cp": 0, "mate": None, "best": None}
    info = engine.analyse(board, limit)
    s = info["score"].white()
    pv = info.get("pv") or []
    return {"cp": s.score(mate_score=10000), "mate": s.mate(), "best": pv[0] if pv else None}


def analyse_game(pgn_text, username, engine, limit, extra=None):
    extra = extra or {}
    game = chess.pgn.read_game(io.StringIO(pgn_text))
    if game is None:
        raise ValueError("Could not parse PGN")
    h = game.headers
    uname = username.lower()
    if h.get("White", "").lower() == uname:
        color = chess.WHITE
    elif h.get("Black", "").lower() == uname:
        color = chess.BLACK
    else:
        raise ValueError(f"{username} not found in game headers")

    nodes = list(game.mainline())
    boards = [game.board()]
    for n in nodes:
        b = boards[-1].copy()
        b.push(n.move)
        boards.append(b)

    evals = [analyse_position(engine, b, limit) for b in boards]

    tc = h.get("TimeControl", "")
    base = None
    m = re.match(r"^(\d+)(\+\d+)?$", tc)
    if m:
        base = int(m.group(1))

    recs = []
    for i, node in enumerate(nodes):
        b = boards[i]
        mover = b.turn
        sign = 1 if mover == chess.WHITE else -1
        cp_b, cp_a = evals[i]["cp"] * sign, evals[i + 1]["cp"] * sign
        best = evals[i]["best"]
        loss = 0.0 if (best is not None and node.move == best) else max(0.0, win_pct(cp_b) - win_pct(cp_a))
        # no "mistakes" once the game is already totally decided either way
        if win_pct(cp_b) > 97 or win_pct(cp_b) < 3:
            loss = min(loss, 4.0)
        cls = classify(loss)
        san = b.san(node.move)
        r = {
            "ply": i, "color": mover, "san": san, "move_no": b.fullmove_number,
            "cp_before": cp_b, "cp_after": cp_a, "loss": loss, "acc": move_accuracy(loss),
            "cls": cls, "phase": phase_of(b), "tags": [],
            "best_san": b.san(best) if best and best != node.move else None,
            "best_is_best": best == node.move,
        }
        clk = node.clock()
        r["time_pressure"] = bool(base and clk is not None and clk <= max(10, 0.1 * base))

        if mover == color and cls in ("mistake", "blunder"):
            tags = []
            mate_b = evals[i]["mate"]
            if mate_b is not None and mate_b != 0 and (mate_b > 0) == (mover == chess.WHITE) and not r["best_is_best"]:
                tags.append("missed mate")
            mate_a = evals[i + 1]["mate"]
            if mate_a is not None and mate_a != 0 and (mate_a > 0) != (mover == chess.WHITE):
                tags.append("allowed mate")
            if best is not None and not r["best_is_best"]:
                my_cap = captured_value(b, node.move)
                best_cap = captured_value(b, best)
                if best_cap >= 3 and best_cap - my_cap >= 3:
                    tags.append("missed material")
            reply = evals[i + 1]["best"]
            if reply is not None:
                opp_cap = captured_value(boards[i + 1], reply)
                if opp_cap >= 3 and opp_cap - captured_value(b, node.move) >= 2:
                    tags.append(f"hung {captured_name(boards[i + 1], reply)}")
            if not tags and best is not None and loss >= 20 and (b.is_capture(best) or b.gives_check(best)):
                tags.append("missed tactic")
            r["tags"] = tags
            if r["phase"] == "endgame":
                r["endgame_type"] = endgame_type(b)
        recs.append(r)

    mine = [r for r in recs if r["color"] == color]
    theirs = [r for r in recs if r["color"] != color]

    def avg(rs):
        return sum(x["acc"] for x in rs) / len(rs) if rs else None

    phase_acc = {}
    for ph in ("opening", "middlegame", "endgame"):
        v = avg([r for r in mine if r["phase"] == ph])
        if v is not None:
            phase_acc[ph] = round(v, 1)

    res = h.get("Result", "*")
    if res == "1/2-1/2":
        outcome = "draw"
    elif (res == "1-0" and color == chess.WHITE) or (res == "0-1" and color == chess.BLACK):
        outcome = "win"
    elif res in ("1-0", "0-1"):
        outcome = "loss"
    else:
        outcome = "draw"

    opening, opening_url = opening_from_headers(h)
    my_elo = h.get("WhiteElo" if color == chess.WHITE else "BlackElo", "?")
    opp_elo = h.get("BlackElo" if color == chess.WHITE else "WhiteElo", "?")
    opp = h.get("Black" if color == chess.WHITE else "White", "?")

    max_wp = max((win_pct(r["cp_before"]) for r in mine), default=50)
    min_wp = min((win_pct(r["cp_before"]) for r in mine), default=50)
    blown_win = outcome != "win" and max_wp >= 85
    saved_loss = outcome != "loss" and min_wp <= 15
    first_bad = next((r for r in mine if r["cls"] in ("mistake", "blunder")), None)
    early_error = bool(first_bad and first_bad["phase"] == "opening")

    top = sorted([r for r in mine if r["cls"] in ("mistake", "blunder")],
                 key=lambda r: -r["loss"])[:3]
    top.sort(key=lambda r: r["ply"])

    eg_types = [r["endgame_type"] for r in mine
                if r["cls"] in ("mistake", "blunder") and r.get("endgame_type")]

    tags = Counter()
    for r in mine:
        for t in r["tags"]:
            tags[t] += 1

    return {
        "url": extra.get("url") or h.get("Link", ""),
        "end_time": extra.get("end_time") or int(time.time()),
        "time_class": extra.get("time_class", ""),
        "time_control": tc,
        "color": "white" if color == chess.WHITE else "black",
        "opp": opp, "opp_rating": opp_elo, "my_rating": my_elo,
        "outcome": outcome, "termination": h.get("Termination", ""),
        "opening": opening, "opening_url": opening_url,
        "accuracy": round(avg(mine) or 0, 1),
        "opp_accuracy": round(avg(theirs) or 0, 1),
        "blunders": sum(r["cls"] == "blunder" for r in mine),
        "mistakes": sum(r["cls"] == "mistake" for r in mine),
        "inaccuracies": sum(r["cls"] == "inaccuracy" for r in mine),
        "best_moves": sum(r["best_is_best"] for r in mine),
        "moves": len(mine),
        "phase_acc": phase_acc,
        "max_wp": round(max_wp, 1), "blown_win": blown_win, "saved_loss": saved_loss,
        "early_error": early_error,
        "first_bad": ({"move_no": first_bad["move_no"], "san": first_bad["san"],
                       "best": first_bad["best_san"]} if first_bad else None),
        "endgame_errors": eg_types,
        "time_trouble_errors": sum(1 for r in mine if r["cls"] in ("mistake", "blunder") and r["time_pressure"]),
        "tags": dict(tags),
        "key_moments": [{
            "move_no": r["move_no"], "color": "w" if r["color"] == chess.WHITE else "b",
            "san": r["san"], "cls": r["cls"], "best": r["best_san"], "tags": r["tags"],
            "before": r["cp_before"], "after": r["cp_after"], "phase": r["phase"],
        } for r in top],
    }


# --------------------------------------------------------------------------- advice

TAG_ADVICE = {
    "hung": ("Blunder check", "Before every move ask: what does their last move threaten, and is the piece I'm moving still safe? "
             "Drill: <a href=\"https://lichess.org/training/hangingPiece\">Hanging piece puzzles</a>."),
    "missed mate": ("Mating patterns", "You had a forced mate and missed it. Drill: "
                    "<a href=\"https://lichess.org/training/mateIn2\">Mate in 2</a> and "
                    "<a href=\"https://lichess.org/training/mateIn3\">Mate in 3</a> puzzles."),
    "allowed mate": ("King safety", "Your move allowed a forced mate. Check opponent checks/captures near your king every move. Drill: "
                     "<a href=\"https://lichess.org/training/defensiveMove\">Defensive move puzzles</a>."),
    "missed material": ("Forcing-move scan", "You skipped a way to win material. Scan checks, captures, threats (in that order) each move. Drill: "
                        "<a href=\"https://lichess.org/training/fork\">Forks</a>, "
                        "<a href=\"https://lichess.org/training/pin\">pins</a>, "
                        "<a href=\"https://lichess.org/training/skewer\">skewers</a>."),
    "missed tactic": ("Tactical vision", "A strong forcing move was available. Daily mixed tactics help: "
                      "<a href=\"https://lichess.org/training\">Lichess puzzles</a>."),
}

ENDGAME_ADVICE = {
    "king and pawn": "King & pawn endings: opposition, key squares, outside passed pawn, triangulation.",
    "rook": "Rook endings: Lucena, Philidor, rook behind passed pawns, cutting off the king.",
    "queen": "Queen endings: perpetual check, passed-pawn races, king safety.",
    "minor-piece": "Minor-piece endings: good vs bad bishop, opposite-coloured bishops, knight vs bishop.",
    "rook and minor-piece": "Rook + minor piece endings: piece activity, rook vs two minors, and when to trade.",
    "mixed": "General endgame technique: activate the king, create passed pawns, trade when ahead.",
}


def tag_key(t):
    return "hung" if t.startswith("hung") else t


def game_advice(s):
    """Returns list of HTML bullet strings."""
    out = []
    if s["early_error"] and s["first_bad"]:
        fb = s["first_bad"]
        op = html.escape(s["opening"])
        link = f"<a href=\"{html.escape(s['opening_url'], quote=True)}\">{op}</a>" if s["opening_url"] else op
        best = f" (engine preferred {html.escape(fb['best'])})" if fb["best"] else ""
        out.append(f"<b>Opening theory:</b> you went wrong early in the {link} at move {fb['move_no']} "
                   f"with {html.escape(fb['san'])}{best}. Review the main lines and the typical plans of this opening.")
    seen = set()
    for t in s["tags"]:
        k = tag_key(t)
        if k in seen:
            continue
        seen.add(k)
        title, text = TAG_ADVICE[k]
        out.append(f"<b>{title}:</b> {text}")
    if s["endgame_errors"]:
        t = Counter(s["endgame_errors"]).most_common(1)[0][0]
        out.append(f"<b>Endgame ({t}):</b> {ENDGAME_ADVICE[t]} "
                   "<a href=\"https://lichess.org/practice\">Lichess Practice</a> has interactive lessons.")
    if s["blown_win"]:
        out.append(f"<b>Converting advantages:</b> you were clearly winning (~{s['max_wp']:.0f}% win chance) but didn't win. "
                   "When ahead: trade pieces, remove counterplay, and double-check every move for tactics.")
    if s["time_trouble_errors"]:
        out.append(f"<b>Clock management:</b> {s['time_trouble_errors']} of your errors came in time trouble. "
                   "Spend less time in the opening (play familiar lines) so you keep time for critical moments.")
    return out


def game_positives(s):
    out = []
    if s["blunders"] == 0:
        out.append("No blunders")
    if s["accuracy"] >= 85:
        out.append(f"High accuracy ({s['accuracy']})")
    pa = s["phase_acc"]
    if pa.get("opening", 0) >= 90 and not s["early_error"]:
        out.append("Solid opening phase")
    if pa.get("endgame", 0) >= 85:
        out.append("Clean endgame technique")
    if s["saved_loss"]:
        out.append("Fought back from a bad position")
    if s["outcome"] == "win" and s["accuracy"] >= s["opp_accuracy"] + 5:
        out.append("Outplayed the opponent")
    if s["moves"] and s["best_moves"] / s["moves"] >= 0.5:
        out.append(f"{s['best_moves']}/{s['moves']} moves matched the engine's top choice")
    return out


# --------------------------------------------------------------------------- formatting

ICON = {"win": "✅ Win", "loss": "❌ Loss", "draw": "🤝 Draw"}
CLS_LABEL = {"blunder": "blunder ??", "mistake": "mistake ?"}


def esc(x):
    return html.escape(str(x))


def format_report(s):
    side = "White" if s["color"] == "white" else "Black"
    tclass = (s["time_class"] or "").capitalize()
    lines = [f"♟ <b>{ICON[s['outcome']]}</b> vs <b>{esc(s['opp'])}</b> ({esc(s['opp_rating'])})",
             f"{esc(tclass)} {esc(s['time_control'])} · {side} · your rating {esc(s['my_rating'])}"]
    if s["termination"]:
        lines.append(f"<i>{esc(s['termination'])}</i>")
    op = esc(s["opening"])
    lines.append("Opening: " + (f"<a href=\"{esc(s['opening_url'])}\">{op}</a>" if s["opening_url"] else op))
    lines.append("")
    lines.append(f"🎯 Accuracy: <b>{s['accuracy']}</b> (opponent {s['opp_accuracy']})")
    lines.append(f"🔴 Blunders {s['blunders']} · 🟠 Mistakes {s['mistakes']} · 🟡 Inaccuracies {s['inaccuracies']}")
    if s["phase_acc"]:
        pretty = " · ".join(f"{k.capitalize()} {v}" for k, v in s["phase_acc"].items())
        lines.append(f"📊 By phase: {pretty}")

    pos = game_positives(s)
    if pos:
        lines += ["", "👍 <b>What went well</b>"] + [f"• {esc(p)}" for p in pos]

    if s["key_moments"]:
        lines += ["", "⚠️ <b>Key moments</b>"]
        for k in s["key_moments"]:
            num = f"{k['move_no']}." if k["color"] == "w" else f"{k['move_no']}..."
            extra = ""
            if k["tags"]:
                extra = " · " + ", ".join(k["tags"])
            best = f", best was <b>{esc(k['best'])}</b>" if k["best"] else ""
            lines.append(f"• {num} <b>{esc(k['san'])}</b> ({CLS_LABEL[k['cls']]}){best}{esc(extra)} "
                         f"[{eval_str(k['before'])} → {eval_str(k['after'])}]")

    adv = game_advice(s)
    if adv:
        lines += ["", "📚 <b>What to study</b>"] + [f"• {a}" for a in adv]
    if s["url"]:
        lines += ["", f"<a href=\"{esc(s['url'])}\">Open game on chess.com</a>"]
    return "\n".join(lines)


def digest_data(state, days, username):
    cutoff = time.time() - days * 86400
    gs = [g for g in state.data["games"].values() if g["end_time"] >= cutoff]
    gs.sort(key=lambda g: g["end_time"])
    return gs


def format_digest(gs, days):
    if not gs:
        return f"No analysed games in the last {days} days."
    w = sum(g["outcome"] == "win" for g in gs)
    d = sum(g["outcome"] == "draw" for g in gs)
    l = sum(g["outcome"] == "loss" for g in gs)
    acc = sum(g["accuracy"] for g in gs) / len(gs)
    lines = [f"📈 <b>Last {days} days — {len(gs)} games</b>",
             f"Record: {w}W / {d}D / {l}L · avg accuracy <b>{acc:.1f}</b>",
             f"Blunders per game: {sum(g['blunders'] for g in gs) / len(gs):.1f} · "
             f"mistakes per game: {sum(g['mistakes'] for g in gs) / len(gs):.1f}"]

    ph = defaultdict(list)
    for g in gs:
        for k, v in g["phase_acc"].items():
            ph[k].append(v)
    if ph:
        pa = {k: sum(v) / len(v) for k, v in ph.items()}
        lines.append("By phase: " + " · ".join(f"{k.capitalize()} {v:.1f}" for k, v in pa.items()))
        weakest = min(pa, key=pa.get)
        lines.append(f"Weakest phase: <b>{weakest}</b>")

    by_class = defaultdict(list)
    for g in gs:
        try:
            by_class[g["time_class"] or "?"].append(int(g["my_rating"]))
        except (ValueError, TypeError):
            pass
    ratings = [f"{k}: {v[0]} → {v[-1]} ({v[-1] - v[0]:+d})" for k, v in by_class.items() if len(v) >= 1]
    if ratings:
        lines.append("Rating: " + " · ".join(ratings))

    ops = defaultdict(lambda: {"n": 0, "loss": 0, "acc": 0.0, "url": ""})
    for g in gs:
        o = ops[(g["color"], g["opening"])]
        o["n"] += 1
        o["loss"] += g["outcome"] == "loss"
        o["acc"] += g["accuracy"]
        o["url"] = g["opening_url"]
    problem = sorted(((k, v) for k, v in ops.items() if v["loss"] > 0),
                     key=lambda kv: (-kv[1]["loss"], kv[1]["acc"] / kv[1]["n"]))[:3]
    if problem:
        lines += ["", "🚧 <b>Openings costing you games</b>"]
        for (color, name), v in problem:
            nm = esc(name)
            link = f"<a href=\"{esc(v['url'])}\">{nm}</a>" if v["url"] else nm
            lines.append(f"• {link} as {color}: {v['loss']} loss(es) in {v['n']} game(s)")

    tags = Counter()
    for g in gs:
        for t, n in g["tags"].items():
            tags[tag_key(t)] += n
    early = sum(g["early_error"] for g in gs)
    blown = sum(g["blown_win"] for g in gs)
    eg = Counter(t for g in gs for t in g["endgame_errors"])
    tt = sum(g["time_trouble_errors"] for g in gs)

    study = []
    if tags:
        for k, n in tags.most_common(2):
            title, text = TAG_ADVICE[k]
            study.append(f"<b>{title}</b> ({n}× in errors): {text}")
    if early >= 2 or (early and len(gs) <= 4):
        study.append(f"<b>Opening prep:</b> you made an early error in {early} game(s). "
                     "Pick one opening per colour and learn the first 8–10 moves and their plans properly.")
    if eg:
        t = eg.most_common(1)[0][0]
        study.append(f"<b>Endgames ({t}):</b> {ENDGAME_ADVICE[t]}")
    if blown:
        study.append(f"<b>Converting wins:</b> {blown} game(s) where you were clearly winning but didn't win.")
    if tt:
        study.append(f"<b>Clock:</b> {tt} errors came in time trouble, consider a safer time-control or faster opening play.")
    if study:
        lines += ["", "📚 <b>Study plan</b>"] + [f"• {x}" for x in study]
    return "\n".join(lines)


# --------------------------------------------------------------------------- optional LLM coach


def llm_coach(cfg, gs, days):
    """Optional: short personalised coaching note from Claude. Needs ANTHROPIC_API_KEY."""
    if not cfg.anthropic_key or not gs:
        return ""
    compact = [{k: g[k] for k in ("outcome", "opening", "color", "accuracy", "blunders", "mistakes",
                                  "phase_acc", "tags", "endgame_errors", "blown_win", "early_error", "time_class")}
               for g in gs[-30:]]
    prompt = (f"You are a chess coach. Here are my last {days} days of chess.com games analysed by Stockfish "
              f"(JSON): {json.dumps(compact)}\n\nWrite a concise coaching note (max 150 words, plain text, no markdown): "
              "my 2 biggest recurring weaknesses, one concrete training plan for the next week "
              "with specific theory topics (named openings, endgames, tactical themes).")
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": cfg.anthropic_key, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": cfg.anthropic_model, "max_tokens": 500,
                  "messages": [{"role": "user", "content": prompt}]},
            timeout=60)
        r.raise_for_status()
        return "".join(b.get("text", "") for b in r.json()["content"])
    except Exception:
        log.exception("LLM coach failed")
        return ""


# --------------------------------------------------------------------------- telegram


def tg_api(cfg, method, **params):
    r = requests.post(f"https://api.telegram.org/bot{cfg.tg_token}/{method}", json=params, timeout=60)
    r.raise_for_status()
    return r.json()


def tg_send(cfg, text, chat_id=None, markup=None):
    chat_id = chat_id or cfg.tg_chat
    chunks, cur = [], ""
    for line in text.split("\n"):
        if len(cur) + len(line) + 1 > 3800:
            chunks.append(cur)
            cur = ""
        cur += line + "\n"
    if cur.strip():
        chunks.append(cur)
    for i, c in enumerate(chunks):
        params = dict(chat_id=chat_id, text=c.strip(), parse_mode="HTML", disable_web_page_preview=True)
        if markup and i == len(chunks) - 1:
            params["reply_markup"] = markup
        tg_api(cfg, "sendMessage", **params)


# --------------------------------------------------------------------------- pipeline


class Analyzer:
    def __init__(self, cfg):
        self.cfg = cfg

    def __enter__(self):
        self.engine = chess.engine.SimpleEngine.popen_uci(self.cfg.stockfish)
        try:
            self.engine.configure({"Threads": self.cfg.threads, "Hash": self.cfg.hash_mb})
        except Exception:
            pass
        self.limit = chess.engine.Limit(depth=self.cfg.depth, time=self.cfg.move_time)
        return self

    def __exit__(self, *a):
        self.engine.quit()

    def game(self, g):
        extra = {"url": g["url"], "end_time": g.get("end_time"), "time_class": g.get("time_class", "")}
        return analyse_game(g["pgn"], self.cfg.username, self.engine, self.limit, extra)


def process_games(cfg, state, games):
    if not games:
        return
    with Analyzer(cfg) as an:
        for g in games:
            try:
                s = an.game(g)
            except Exception:
                log.exception("Failed analysing %s", g.get("url"))
                continue
            state.data["games"][g["url"]] = s
            state.data["seen"][g["url"]] = g.get("end_time", 0)
            tg_send(cfg, format_report(s))
            state.save()
            log.info("Reported %s", g["url"])


def check_new_games(cfg, state):
    games = fetch_recent_games(cfg.username)
    seen = state.data["seen"]
    if not seen and not state.data["games"]:
        # first run: only report the latest N games, mark everything else as seen
        old = games[:-cfg.backfill] if cfg.backfill > 0 else games
        for g in old:
            seen[g["url"]] = g.get("end_time", 0)
        state.save()
    new = [g for g in games if g["url"] not in seen]
    if new:
        log.info("%d new game(s)", len(new))
    process_games(cfg, state, new)
    # keep seen dict from growing forever
    cutoff = time.time() - 90 * 86400
    state.data["seen"] = {u: t for u, t in seen.items() if t >= cutoff}
    state.save()


def send_digest(cfg, state, days, chat_id=None):
    gs = digest_data(state, days, cfg.username)
    text = format_digest(gs, days)
    note = llm_coach(cfg, gs, days)
    if note:
        text += "\n\n🧠 <b>Coach's note</b>\n" + esc(note)
    tg_send(cfg, text, chat_id)


def digest_due(cfg, state):
    if cfg.digest_day == "off":
        return False, ""
    try:
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo(cfg.tz))
    except Exception:
        now = datetime.now(timezone.utc)
    wk = now.strftime("%G-W%V")
    due = (now.strftime("%a").lower()[:3] == cfg.digest_day and now.hour >= cfg.digest_hour
           and state.data.get("last_digest") != wk)
    return due, wk


def maybe_weekly_digest(cfg, state):
    due, wk = digest_due(cfg, state)
    if due:
        send_digest(cfg, state, 7)
        state.data["last_digest"] = wk
        state.save()


def probe(cfg, state):
    """Cheap check (no Stockfish): is there anything to do? Sets GitHub output work=true/false."""
    work = False
    games = fetch_recent_games(cfg.username)
    if not state.data["seen"] and not state.data["games"]:
        work = True  # first run
    elif any(g["url"] not in state.data["seen"] for g in games):
        work = True
    if not work:
        res = tg_api(cfg, "getUpdates", offset=state.data["tg_offset"], timeout=0,
                     allowed_updates=["message", "callback_query"])
        work = bool(res.get("result"))
    if not work:
        work = digest_due(cfg, state)[0]
    out = os.environ.get("GITHUB_OUTPUT")
    line = f"work={'true' if work else 'false'}"
    if out:
        with open(out, "a") as f:
            f.write(line + "\n")
    print(line)


MENU_TEXT = "♟ <b>Chess coach</b>\nWhat do you want to do?"
CMD = {"/start": "menu", "/menu": "menu", "/help": "menu", "/latest": "latest",
       "/games": "p:0", "/week": "week", "/month": "month", "/check": "check"}
BOT_COMMANDS = [("menu", "Show buttons"), ("latest", "Analyse my latest game"),
                ("games", "Pick from my last 50 games"), ("week", "Stats for 7 days"),
                ("month", "Stats for 30 days"), ("check", "Look for new games now")]
PAGE = 8
OUT_ICON = {"win": "✅", "loss": "❌", "draw": "🤝"}


def main_menu():
    return {"inline_keyboard": [
        [{"text": "🔍 Latest game", "callback_data": "latest"},
         {"text": "📋 Last 50 games", "callback_data": "p:0"}],
        [{"text": "📈 Week", "callback_data": "week"},
         {"text": "📆 Month", "callback_data": "month"}],
        [{"text": "🔄 Check new games", "callback_data": "check"}]]}


def game_id(g):
    return g["url"].rstrip("/").split("/")[-1]


def user_outcome(g, username):
    white_is_me = g["white"]["username"].lower() == username.lower()
    me, opp = (g["white"], g["black"]) if white_is_me else (g["black"], g["white"])
    code = me.get("result", "")
    return ("win" if code == "win" else "draw" if code in DRAWS else "loss"), opp


def games_page(cfg, state, page):
    games = list(reversed(fetch_games_limit(cfg.username, 50)))  # newest first
    pages = max(1, math.ceil(len(games) / PAGE))
    page = max(0, min(page, pages - 1))
    rows = []
    for g in games[page * PAGE:(page + 1) * PAGE]:
        o, opp = user_outcome(g, cfg.username)
        d = datetime.fromtimestamp(g.get("end_time", 0), timezone.utc).strftime("%d %b")
        done = "✔ " if g["url"] in state.data["games"] else ""
        label = f"{done}{OUT_ICON[o]} vs {opp.get('username', '?')} ({opp.get('rating', '?')}) · {g.get('time_class', '')} · {d}"
        rows.append([{"text": label[:60], "callback_data": "g:" + game_id(g)}])
    nav = []
    if page > 0:
        nav.append({"text": "⬅ Newer", "callback_data": f"p:{page - 1}"})
    if page < pages - 1:
        nav.append({"text": "Older ➡", "callback_data": f"p:{page + 1}"})
    if nav:
        rows.append(nav)
    rows.append([{"text": "🏠 Menu", "callback_data": "menu"}])
    return f"📋 Pick a game to analyse (page {page + 1}/{pages}, ✔ = already analysed):", {"inline_keyboard": rows}


def analyse_and_send(cfg, state, g, chat=None):
    cached = state.data["games"].get(g["url"])
    if cached:
        s = cached
    else:
        tg_send(cfg, "⏳ Analysing the game…", chat)
        with Analyzer(cfg) as an:
            s = an.game(g)
        state.data["games"][g["url"]] = s
        state.data["seen"][g["url"]] = g.get("end_time", 0)
    tg_send(cfg, format_report(s), chat, markup=main_menu())


def do_action(cfg, state, data, chat, msg_id=None, msg_text=""):
    if data in ("menu", "start"):
        tg_send(cfg, MENU_TEXT, chat, markup=main_menu())
    elif data == "week":
        send_digest(cfg, state, 7, chat)
    elif data == "month":
        send_digest(cfg, state, 30, chat)
    elif data == "check":
        tg_send(cfg, "🔄 Checking chess.com…", chat)
        before = len(state.data["games"])
        check_new_games(cfg, state)
        if len(state.data["games"]) == before:
            tg_send(cfg, "No new games.", chat, markup=main_menu())
    elif data == "latest":
        games = fetch_recent_games(cfg.username)
        if games:
            analyse_and_send(cfg, state, games[-1], chat)
        else:
            tg_send(cfg, "No games found.", chat)
    elif data.startswith("p:"):
        text, markup = games_page(cfg, state, int(data[2:]))
        if msg_id and msg_text.startswith("📋"):
            tg_api(cfg, "editMessageText", chat_id=chat, message_id=msg_id, text=text, reply_markup=markup)
        else:
            tg_send(cfg, text, chat, markup=markup)
    elif data.startswith("g:"):
        gid = data[2:]
        g = next((x for x in fetch_games_limit(cfg.username, 50) if game_id(x) == gid), None)
        if g:
            analyse_and_send(cfg, state, g, chat)
        else:
            tg_send(cfg, "Game not found (too old?).", chat)


def handle_updates(cfg, state, timeout):
    res = tg_api(cfg, "getUpdates", offset=state.data["tg_offset"], timeout=timeout,
                 allowed_updates=["message", "callback_query"])
    for u in res.get("result", []):
        state.data["tg_offset"] = u["update_id"] + 1
        action, msg_id, msg_text = None, None, ""
        if "callback_query" in u:
            cq = u["callback_query"]
            msg = cq.get("message") or {}
            chat = str(msg.get("chat", {}).get("id", ""))
            if chat != cfg.tg_chat:
                continue
            try:
                tg_api(cfg, "answerCallbackQuery", callback_query_id=cq["id"])
            except Exception:
                pass  # old button presses can no longer be acknowledged
            action, msg_id, msg_text = cq.get("data", ""), msg.get("message_id"), msg.get("text", "")
        else:
            msg = u.get("message") or {}
            chat = str(msg.get("chat", {}).get("id", ""))
            if chat != cfg.tg_chat:
                continue
            words = (msg.get("text") or "").strip().lower().split()
            if words and words[0].startswith("/"):
                action = CMD.get(words[0].split("@")[0])
        if not action:
            continue
        try:
            do_action(cfg, state, action, chat, msg_id, msg_text)
        except Exception:
            log.exception("Action %s failed", action)
            tg_send(cfg, "Something went wrong, check the logs.")
        state.save()
    state.save()


def run_listen(cfg, state, minutes):
    """Stay online for a few minutes so button presses are answered instantly."""
    tg_send(cfg, f"🟢 Session open for {minutes:g} min. Tap a button:", markup=main_menu())
    deadline = time.time() + minutes * 60
    while time.time() < deadline:
        left = int(deadline - time.time())
        if left < 3:
            break
        try:
            handle_updates(cfg, state, timeout=min(25, left))
        except requests.RequestException as e:
            log.warning("Network error: %s", e)
            time.sleep(5)
    tg_send(cfg, "⚪ Session closed. Start it again from GitHub (Actions → Run workflow) or wait for the next automatic check.")


def run_loop(cfg, state, deadline=None):
    """Poll chess.com every POLL_MINUTES and answer Telegram buttons. Runs forever, or until `deadline`."""
    log.info("Bot started for chess.com user %s", cfg.username)
    last_check = 0.0
    while deadline is None or time.time() < deadline:
        try:
            if time.time() - last_check >= cfg.poll_minutes * 60:
                last_check = time.time()
                check_new_games(cfg, state)
                maybe_weekly_digest(cfg, state)
            wait = 25 if deadline is None else max(0, min(25, int(deadline - time.time())))
            handle_updates(cfg, state, timeout=wait)
        except requests.RequestException as e:
            log.warning("Network error: %s", e)
            time.sleep(15)
        except Exception:
            log.exception("Loop error")
            time.sleep(30)


def run_watch(cfg, state, minutes):
    """Live session: new games are reported ~30-60 s after they finish."""
    cfg.poll_minutes = float(os.environ.get("WATCH_POLL_SECONDS", "30")) / 60
    tg_send(cfg, f"👀 <b>Live mode on for {minutes:g} min.</b> Every game you finish will be analysed automatically.",
            markup=main_menu())
    run_loop(cfg, state, deadline=time.time() + minutes * 60)
    state.save()
    tg_send(cfg, "⚪ Live mode finished. Start it again from GitHub (Actions → Chess live mode → Run workflow).")


# --------------------------------------------------------------------------- cli


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="check for new games once and exit")
    ap.add_argument("--test-pgn", help="analyse a local PGN file and print the report")
    ap.add_argument("--user", help="username inside the PGN (for --test-pgn)")
    ap.add_argument("--get-chat-id", action="store_true")
    ap.add_argument("--probe", action="store_true", help="cheap check: print work=true/false for CI")
    ap.add_argument("--watch", type=float, default=0,
                    help="live mode: poll chess.com every ~30 s for N minutes, then exit")
    ap.add_argument("--listen", type=float, default=0,
                    help="after the check, stay online N minutes answering button presses")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.get_chat_id:
        token = os.environ.get("TELEGRAM_BOT_TOKEN") or sys.exit("Set TELEGRAM_BOT_TOKEN")
        r = requests.get(f"https://api.telegram.org/bot{token}/getUpdates", timeout=30).json()
        ids = {(m["message"]["chat"]["id"], m["message"]["chat"].get("first_name", ""))
               for m in r.get("result", []) if "message" in m}
        print(ids or "No messages yet: send /start to your bot first, then rerun.")
        return

    if args.test_pgn:
        os.environ.setdefault("CHESSCOM_USERNAME", args.user or "")
        cfg = Config(require_telegram=False)
        if args.user:
            cfg.username = args.user
        pgn = Path(args.test_pgn).read_text()
        with Analyzer(cfg) as an:
            s = analyse_game(pgn, cfg.username, an.engine, an.limit)
        txt = format_report(s)
        print(re.sub(r"<[^>]+>", "", html.unescape(txt)))
        return

    cfg = Config()
    state = State(cfg.data_dir / "state.json")
    if args.probe:
        probe(cfg, state)
        return
    try:
        tg_api(cfg, "setMyCommands", commands=[{"command": c, "description": d} for c, d in BOT_COMMANDS])
    except Exception:
        log.warning("Could not register bot commands")
    if args.watch > 0:
        run_watch(cfg, state, args.watch)
        return
    if args.once:
        try:
            handle_updates(cfg, state, timeout=0)  # answer any /commands sent since last run
        except Exception:
            log.exception("Could not process Telegram commands")
        check_new_games(cfg, state)
        maybe_weekly_digest(cfg, state)
        state.save()
        if args.listen > 0:
            run_listen(cfg, state, args.listen)
            state.save()
    else:
        run_loop(cfg, state)


if __name__ == "__main__":
    main()
