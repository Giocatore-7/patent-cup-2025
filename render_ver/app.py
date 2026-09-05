import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import json
import time
import html
from sqlalchemy import text

# ==========================================
# 1. 設定・データ定義
# ==========================================
st.set_page_config(page_title="パテントカップ大会アプリ", layout="wide")

try:
    ADMIN_PASS = st.secrets["ADMIN_PASS"]
    VIEW_PASS = st.secrets["VIEW_PASS"]
    RESET_PASS = st.secrets["RESET_PASS"]
except (FileNotFoundError, KeyError):
    st.error("⛔ セキュリティエラー: パスワード設定が見つかりません。")
    st.stop()

# ★入力者モード用パスワード。未設定でもアプリは落ちない（入力者モードが無効になるだけ）。
try:
    INPUT_PASS = st.secrets["INPUT_PASS"]
except (FileNotFoundError, KeyError):
    INPUT_PASS = None

# CSS設定（スマホでタブ4つが収まるように圧縮）
st.markdown("""
    <style>
    [data-testid="stToolbar"] { display: none !important; }
    .stAppDeployButton { display: none !important; }
    footer { display: none !important; }
    [data-testid="stDecoration"] { display: none !important; }

    .stTabs [data-baseweb="tab-list"] {
        gap: 4px !important;
        overflow-x: visible !important;
        flex-wrap: nowrap !important;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 6px 8px !important;
        font-size: 13px !important;
        white-space: nowrap !important;
        min-width: 0 !important;
    }
    .stTabs [data-baseweb="tab-list"] > button[aria-label] { display: none !important; }

    @media (max-width: 520px) {
        .stTabs [data-baseweb="tab-list"] { gap: 1px !important; }
        .stTabs [data-baseweb="tab"] {
            padding: 5px 3px !important;
            font-size: 11px !important;
        }
        .block-container { padding-left: 0.6rem !important; padding-right: 0.6rem !important; }
    }
    </style>
""", unsafe_allow_html=True)

DEFAULT_TEAMS_REGULAR = {chr(65 + i): f"チーム{chr(65+i)}" for i in range(12)}
DEFAULT_TEAMS_MIX = {chr(65 + i): f"MIXチーム{chr(65+i)}" for i in range(12)}

SCHEDULE_TEMPLATE_4COURT = [
    [("A", "E"), ("B", "F"), ("A", "E"), ("B", "F")],
    [("C", "G"), ("D", "H"), ("C", "G"), ("D", "H")],
    [("I", "J"), ("K", "L"), ("I", "J"), ("K", "L")],
    [("A", "B"), ("C", "D"), ("A", "B"), ("C", "D")],
    [("E", "F"), ("G", "H"), ("E", "F"), ("G", "H")],
    [("A", "I"), ("B", "J"), ("A", "I"), ("B", "J")],
    [("C", "K"), ("D", "L"), ("C", "K"), ("D", "L")],
    [("E", "I"), ("F", "J"), ("E", "I"), ("F", "J")],
    [("G", "K"), ("H", "L"), ("G", "K"), ("H", "L")]
]
SCHEDULE_TEMPLATE_3COURT = [
    {"id": 1, "matches": [("reg", "A", "E"), ("reg", "B", "F"), ("mix", "A", "E")]},
    {"id": 2, "matches": [("reg", "C", "G"), ("mix", "B", "F"), ("mix", "C", "G")]},
    {"id": 3, "matches": [("reg", "I", "J"), ("reg", "D", "H"), ("mix", "D", "H")]},
    {"id": 4, "matches": [("reg", "K", "L"), ("mix", "I", "J"), ("mix", "K", "L")]},
    {"id": 5, "matches": [("reg", "A", "B"), ("reg", "C", "D"), ("mix", "A", "B")]},
    {"id": 6, "matches": [("reg", "E", "F"), ("mix", "C", "D"), ("mix", "E", "F")]},
    {"id": 7, "matches": [("reg", "G", "H"), ("reg", "A", "I"), ("mix", "G", "H")]},
    {"id": 8, "matches": [("reg", "B", "J"), ("mix", "A", "I"), ("mix", "B", "J")]},
    {"id": 9, "matches": [("reg", "C", "K"), ("reg", "D", "L"), ("mix", "C", "K")]},
    {"id": 10, "matches": [("reg", "E", "I"), ("mix", "D", "L"), ("mix", "E", "I")]},
    {"id": 11, "matches": [("reg", "F", "J"), ("reg", "G", "K"), ("mix", "F", "J")]},
    {"id": 12, "matches": [("reg", "H", "L"), ("mix", "G", "K"), ("mix", "H", "L")]},
]

TOURN_SCHED_4COURT = [
    {"cup_display": "パテントクラシカルカップ", "games": [
        {"league": "reg", "cup": "Classical", "round": "SF1", "court": "A"},
        {"league": "reg", "cup": "Classical", "round": "SF2", "court": "B"},
        {"league": "mix", "cup": "Classical", "round": "SF1", "court": "C"},
        {"league": "mix", "cup": "Classical", "round": "SF2", "court": "D"},
    ]},
    {"cup_display": "パテントエリートカップ", "games": [
        {"league": "reg", "cup": "Elite", "round": "SF1", "court": "A"},
        {"league": "reg", "cup": "Elite", "round": "SF2", "court": "B"},
        {"league": "mix", "cup": "Elite", "round": "SF1", "court": "C"},
        {"league": "mix", "cup": "Elite", "round": "SF2", "court": "D"},
    ]},
    {"cup_display": "パテントチャンピオンズカップ", "games": [
        {"league": "reg", "cup": "Champions", "round": "SF1", "court": "A"},
        {"league": "reg", "cup": "Champions", "round": "SF2", "court": "B"},
        {"league": "mix", "cup": "Champions", "round": "SF1", "court": "C"},
        {"league": "mix", "cup": "Champions", "round": "SF2", "court": "D"},
    ]},
    {"cup_display": "パテントクラシカルカップ(決勝)", "games": [
        {"league": "reg", "cup": "Classical", "round": "Final", "court": "A"},
        {"league": "reg", "cup": "Classical", "round": "3rd", "court": "B"},
        {"league": "mix", "cup": "Classical", "round": "Final", "court": "C"},
        {"league": "mix", "cup": "Classical", "round": "3rd", "court": "D"},
    ]},
    {"cup_display": "パテントエリートカップ(決勝)", "games": [
        {"league": "reg", "cup": "Elite", "round": "Final", "court": "A"},
        {"league": "reg", "cup": "Elite", "round": "3rd", "court": "B"},
        {"league": "mix", "cup": "Elite", "round": "Final", "court": "C"},
        {"league": "mix", "cup": "Elite", "round": "3rd", "court": "D"},
    ]},
    {"cup_display": "パテントチャンピオンズカップ(決勝)", "games": [
        {"league": "reg", "cup": "Champions", "round": "Final", "court": "A"},
        {"league": "reg", "cup": "Champions", "round": "3rd", "court": "B"},
        {"league": "mix", "cup": "Champions", "round": "Final", "court": "C"},
        {"league": "mix", "cup": "Champions", "round": "3rd", "court": "D"},
    ]},
]
TOURN_SCHED_3COURT = [
    {"cup_display": "クラシカルSF", "games": [
        {"league": "reg", "cup": "Classical", "round": "SF1", "court": "A"},
        {"league": "reg", "cup": "Classical", "round": "SF2", "court": "B"},
        {"league": "mix", "cup": "Classical", "round": "SF1", "court": "C"},
    ]},
    {"cup_display": "クラシカル/エリートSF", "games": [
        {"league": "mix", "cup": "Classical", "round": "SF2", "court": "A"},
        {"league": "reg", "cup": "Elite", "round": "SF1", "court": "B"},
        {"league": "reg", "cup": "Elite", "round": "SF2", "court": "C"},
    ]},
    {"cup_display": "エリート/チャンピオンズSF", "games": [
        {"league": "mix", "cup": "Elite", "round": "SF1", "court": "A"},
        {"league": "mix", "cup": "Elite", "round": "SF2", "court": "B"},
        {"league": "reg", "cup": "Champions", "round": "SF1", "court": "C"},
    ]},
    {"cup_display": "チャンピオンズSF", "games": [
        {"league": "reg", "cup": "Champions", "round": "SF2", "court": "A"},
        {"league": "mix", "cup": "Champions", "round": "SF1", "court": "B"},
        {"league": "mix", "cup": "Champions", "round": "SF2", "court": "C"},
    ]},
    {"cup_display": "クラシカル決勝", "games": [
        {"league": "reg", "cup": "Classical", "round": "Final", "court": "A"},
        {"league": "reg", "cup": "Classical", "round": "3rd", "court": "B"},
        {"league": "mix", "cup": "Classical", "round": "Final", "court": "C"},
    ]},
    {"cup_display": "エリート決勝", "games": [
        {"league": "mix", "cup": "Classical", "round": "3rd", "court": "A"},
        {"league": "reg", "cup": "Elite", "round": "Final", "court": "B"},
        {"league": "reg", "cup": "Elite", "round": "3rd", "court": "C"},
    ]},
    {"cup_display": "エリート/チャンピオンズ決勝", "games": [
        {"league": "mix", "cup": "Elite", "round": "Final", "court": "A"},
        {"league": "mix", "cup": "Elite", "round": "3rd", "court": "B"},
        {"league": "reg", "cup": "Champions", "round": "Final", "court": "C"},
    ]},
    {"cup_display": "チャンピオンズ決勝", "games": [
        {"league": "reg", "cup": "Champions", "round": "3rd", "court": "A"},
        {"league": "mix", "cup": "Champions", "round": "Final", "court": "B"},
        {"league": "mix", "cup": "Champions", "round": "3rd", "court": "C"},
    ]},
]

CUP_LABEL_JA = {
    "Champions": "パテントチャンピオンズカップ",
    "Elite": "パテントエリートカップ",
    "Classical": "パテントクラシカルカップ",
}

SETTING_KEYS = [
    'app_title', 'teams_reg', 'teams_mix', 'court_mode',
    'start_time_hour', 'start_time_minute',
    'league_duration', 'tourn_duration', 'interval_duration',
]


# ==========================================
# 2. データ層（PostgreSQL）
# ==========================================
def _default_state():
    return {
        'app_title': "パテントカップ2025",
        'teams_reg': DEFAULT_TEAMS_REGULAR.copy(),
        'teams_mix': DEFAULT_TEAMS_MIX.copy(),
        'results': {},
        'tourn_results': {},
        'court_mode': "4面",
        'start_time_hour': 13,
        'start_time_minute': 15,
        'league_duration': 7,
        'tourn_duration': 10,
        'interval_duration': 15,
    }


def get_conn():
    return st.connection("postgresql", type="sql")


@st.cache_resource
def init_db():
    conn = get_conn()
    with conn.session as s:
        s.execute(text("""
            CREATE TABLE IF NOT EXISTS patent_cup_logs (
                id SERIAL PRIMARY KEY,
                log_type VARCHAR(50),
                log_data JSONB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))
        s.commit()
    return True


def _as_dict(v):
    return json.loads(v) if isinstance(v, str) else v


def _replay(rows):
    """init行が無くても match行を取りこぼさない"""
    data = _default_state()
    for log_type, log_data in rows:
        d = _as_dict(log_data)
        if d is None:
            continue
        if log_type == 'init':
            merged = _default_state()
            merged.update(d)
            merged.setdefault('results', {})
            merged.setdefault('tourn_results', {})
            data = merged
        elif log_type == 'match':
            key, val, is_tourn = d.get('k'), d.get('v'), d.get('t')
            if not key:
                continue
            bucket = data['tourn_results'] if is_tourn else data['results']
            bucket[key] = val
    return data


@st.cache_data(ttl=5, show_spinner=False)
def load_state():
    """毎回DBから最新状態を読む（全セッション共有キャッシュ・5秒）"""
    conn = get_conn()
    df = conn.query(
        "SELECT log_type, log_data FROM patent_cup_logs ORDER BY id ASC", ttl=0)
    rows = [(r['log_type'], r['log_data']) for _, r in df.iterrows()]
    return _replay(rows)


def save_match(match_key, result_dict, is_tournament=False):
    try:
        payload = {'k': match_key, 'v': result_dict, 't': bool(is_tournament)}
        conn = get_conn()
        with conn.session as s:
            s.execute(
                text("INSERT INTO patent_cup_logs (log_type, log_data) "
                     "VALUES (:type, CAST(:data AS JSONB));"),
                {"type": "match", "data": json.dumps(payload, ensure_ascii=False)}
            )
            s.commit()
        load_state.clear()
        st.toast("✅ 試合結果を記録しました")
        return True
    except Exception as e:
        st.error(f"保存エラー: {e}")
        return False


def save_settings(changes):
    """テーブルをロックし、DBの最新を読み直してから設定だけ差し替える"""
    try:
        conn = get_conn()
        with conn.session as s:
            s.execute(text("LOCK TABLE patent_cup_logs IN EXCLUSIVE MODE;"))
            rows = s.execute(
                text("SELECT log_type, log_data FROM patent_cup_logs ORDER BY id ASC")
            ).fetchall()
            latest = _replay([(r[0], r[1]) for r in rows])
            for k, v in changes.items():
                if k in SETTING_KEYS:
                    latest[k] = v
            s.execute(text("DELETE FROM patent_cup_logs;"))
            s.execute(
                text("INSERT INTO patent_cup_logs (log_type, log_data) "
                     "VALUES ('init', CAST(:data AS JSONB));"),
                {"data": json.dumps(latest, ensure_ascii=False)}
            )
            s.commit()
        load_state.clear()
        st.toast("✅ 設定を保存しました（試合結果は保持されています）")
        return True
    except Exception as e:
        st.error(f"保存エラー: {e}")
        return False


def reset_all():
    try:
        conn = get_conn()
        with conn.session as s:
            s.execute(text("LOCK TABLE patent_cup_logs IN EXCLUSIVE MODE;"))
            s.execute(text("DELETE FROM patent_cup_logs;"))
            s.execute(
                text("INSERT INTO patent_cup_logs (log_type, log_data) "
                     "VALUES ('init', CAST(:data AS JSONB));"),
                {"data": json.dumps(_default_state(), ensure_ascii=False)}
            )
            s.commit()
        load_state.clear()
        return True
    except Exception as e:
        st.error(f"初期化エラー: {e}")
        return False


# ==========================================
# 3. ロジック
# ==========================================
def valid_league_keys(court_mode):
    keys = set()
    if court_mode == "4面":
        for i, slot in enumerate(SCHEDULE_TEMPLATE_4COURT):
            for j, (h, a) in enumerate(slot):
                lt = "reg" if j < 2 else "mix"
                keys.add(f"{lt}_{i}_{h}_{a}")
    else:
        for i, slot in enumerate(SCHEDULE_TEMPLATE_3COURT):
            for lt, h, a in slot["matches"]:
                keys.add(f"{lt}_{i}_{h}_{a}")
    return keys


def calculate_standings(state, league_type):
    teams_map = state['teams_reg'] if league_type == "reg" else state['teams_mix']
    allowed = valid_league_keys(state['court_mode'])
    rows = []
    for code, name in teams_map.items():
        st_ = {"チーム名": name, "勝点": 0, "試合数": 0, "勝": 0, "引": 0, "負": 0,
               "得点": 0, "失点": 0, "得失差": 0, "SortIndex": ord(code) - 65}
        for key, res in state['results'].items():
            if key not in allowed or not key.startswith(f"{league_type}_"):
                continue
            parts = key.split("_")
            if len(parts) < 4:
                continue
            home_code, away_code = parts[2], parts[3]
            if res is None or res.get('s1') is None or res.get('s2') is None:
                continue
            s1, s2 = res['s1'], res['s2']
            if code == home_code:
                mine, theirs = s1, s2
            elif code == away_code:
                mine, theirs = s2, s1
            else:
                continue
            st_["試合数"] += 1
            st_["得点"] += mine
            st_["失点"] += theirs
            st_["得失差"] += mine - theirs
            if mine > theirs:
                st_["勝点"] += 3
                st_["勝"] += 1
            elif mine == theirs:
                st_["勝点"] += 1
                st_["引"] += 1
            else:
                st_["負"] += 1
        rows.append(st_)
    df = pd.DataFrame(rows).sort_values(
        by=["勝点", "得失差", "得点", "SortIndex"], ascending=[False, False, False, True])
    df = df.drop(columns=["SortIndex"])
    df.insert(0, "順位", range(1, len(df) + 1))
    return df


def league_progress(state, league_type):
    allowed = {k for k in valid_league_keys(state['court_mode'])
               if k.startswith(f"{league_type}_")}
    done = sum(1 for k in allowed
               if state['results'].get(k) and state['results'][k].get('s1') is not None)
    return done, len(allowed)


def get_cup_ranks(cup_name):
    return {"Champions": 0, "Elite": 4, "Classical": 8}.get(cup_name, 0)


def match_result(state, match_id):
    res = state['tourn_results'].get(
        match_id, {'s1': None, 's2': None, 'pk1': None, 'pk2': None})
    s1, s2 = res.get('s1'), res.get('s2')
    winner = None
    if s1 is not None and s2 is not None:
        if s1 > s2:
            winner = "left"
        elif s2 > s1:
            winner = "right"
        else:
            pk1, pk2 = res.get('pk1'), res.get('pk2')
            if pk1 is not None and pk2 is not None:
                if pk1 > pk2:
                    winner = "left"
                elif pk2 > pk1:
                    winner = "right"
    return res, winner


def cup_teams(state, league, cup):
    ranks = calculate_standings(state, league)["チーム名"].tolist()
    if len(ranks) < 12:
        return None
    i = get_cup_ranks(cup)
    return ranks[i], ranks[i + 1], ranks[i + 2], ranks[i + 3]


def resolve_slot(state, league, cup, slot):
    teams = cup_teams(state, league, cup)
    if teams is None:
        return None
    t1, t2, t3, t4 = teams
    if slot == "SF1":
        return t1
    if slot == "SF1_Opp":
        return t4
    if slot == "SF2":
        return t2
    if slot == "SF2_Opp":
        return t3
    _, w1 = match_result(state, f"{league}_{cup}_SF1")
    _, w2 = match_result(state, f"{league}_{cup}_SF2")
    win1 = t1 if w1 == "left" else (t4 if w1 == "right" else None)
    lose1 = t4 if w1 == "left" else (t1 if w1 == "right" else None)
    win2 = t2 if w2 == "left" else (t3 if w2 == "right" else None)
    lose2 = t3 if w2 == "left" else (t2 if w2 == "right" else None)
    return {"Final": win1, "Final_Opp": win2,
            "3rd": lose1, "3rd_Opp": lose2}.get(slot)


def schedule_times(state):
    base = datetime(2025, 1, 1, state['start_time_hour'], state['start_time_minute'])
    n_slots = 9 if state['court_mode'] == "4面" else 12
    league_end = base + timedelta(minutes=n_slots * state['league_duration'])
    tourn_start = league_end + timedelta(minutes=state['interval_duration'])
    return base, league_end, tourn_start


# ==========================================
# 4. トーナメント表（SVG）
# ==========================================
RED, GRAY = "#d32f2f", "#b0b0b0"


def _score_labels(res):
    if not res or res.get('s1') is None or res.get('s2') is None:
        return "", ""
    s1, s2 = res['s1'], res['s2']
    pk1, pk2 = res.get('pk1'), res.get('pk2')
    if s1 == s2 and pk1 is not None and pk2 is not None:
        return f"{s1}({pk1})", f"{s2}({pk2})"
    return str(s1), str(s2)


def _text_w(s, fs):
    """全角=1.0em、半角=0.55em で概算"""
    return sum(fs * (0.55 if ord(c) < 0x2E80 else 1.0) for c in s)


def _fit_lines(name, avail, max_fs=12, min_fs=7.5):
    """★チーム名が枠に必ず収まるよう、フォント縮小→2行折り返しの順で調整する"""
    name = str(name or "")
    if not name:
        return [""], max_fs

    def two_lines(fs):
        cut = 0
        for i in range(1, len(name) + 1):
            if _text_w(name[:i], fs) <= avail:
                cut = i
            else:
                break
        if cut and _text_w(name[cut:], fs) <= avail:
            return [name[:cut], name[cut:]]
        return None

    # 1) まずは大きめのフォントで1行
    for fs in (max_fs, 11, 10):
        if _text_w(name, fs) <= avail:
            return [name], fs
    # 2) 入らなければ「小さい1行」より「読める2行」を優先する
    for fs in (11, 10, 9, 8):
        lines = two_lines(fs)
        if lines:
            return lines, fs
    # 3) それでも駄目なら小さい1行
    for fs in (9, 8, min_fs):
        if _text_w(name, fs) <= avail:
            return [name], fs
    # 4) 最終手段
    lines = two_lines(min_fs)
    if lines:
        return lines, min_fs
    half = max(1, len(name) // 2)
    return [name[:half], name[half:]], min_fs


def _lines_svg(x, cy, lines, fs, weight, anchor="start", fill="#1a1a1a"):
    lh = fs * 1.18
    if len(lines) == 1:
        ys = [cy + fs * 0.36]
    else:
        ys = [cy - lh / 2 + fs * 0.36, cy + lh / 2 + fs * 0.36]
    out = []
    for ln, y in zip(lines, ys):
        out.append(f'<text x="{x}" y="{y:.1f}" font-size="{fs}" font-weight="{weight}" '
                   f'text-anchor="{anchor}" fill="{fill}">{html.escape(ln)}</text>')
    return "".join(out)


def _box(x, y, w, h, name, score, rank=None, win=False, fill="#ffffff"):
    stroke = RED if win else "#8a8a8a"
    sw = 2 if win else 1
    weight = "600" if win else "400"
    pad_l = 7
    rank_w = 20 if rank is not None else 0
    score_w = 32 if score else 0
    avail = w - pad_l - rank_w - score_w - 6
    lines, fs = _fit_lines(name, avail)
    cy = y + h / 2
    parts = [f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="5" '
             f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>']
    if rank is not None:
        parts.append(f'<text x="{x+pad_l}" y="{cy+4}" font-size="10" '
                     f'fill="#777">{rank}位</text>')
    parts.append(_lines_svg(x + pad_l + rank_w, cy, lines, fs, weight))
    if score:
        parts.append(f'<text x="{x+w-7}" y="{cy+4.5}" font-size="13" font-weight="700" '
                     f'text-anchor="end" fill="#1a1a1a">{html.escape(score)}</text>')
    return "".join(parts)


def _seg(x1, y1, x2, y2, red):
    c = RED if red else GRAY
    sw = 2.2 if red else 1
    return (f'<path d="M{x1} {y1} L{x2} {y2}" stroke="{c}" stroke-width="{sw}" '
            f'fill="none" stroke-linecap="round"/>')


def _link(x_from, x_to, y1, y2, win):
    """
    ★勝者の経路を「枠 → 横 → 縦 → 横 → 次の枠」まで途切れず赤くする。
    縦線を中点で2分割し、勝者側の半分だけを赤くするのがポイント。
    """
    xm = (x_from + x_to) / 2
    ym = (y1 + y2) / 2
    top, bot = (win == "top"), (win == "bottom")
    return "".join([
        _seg(x_from, y1, xm, y1, top),
        _seg(x_from, y2, xm, y2, bot),
        _seg(xm, y1, xm, ym, top),
        _seg(xm, ym, xm, y2, bot),
        _seg(xm, ym, x_to, ym, bool(win)),
    ])


X1, W1 = 4, 158
X2, W2 = 174, 138
X3, W3 = 326, 110
BH = 34
SVG_W, SVG_H = 444, 320


def bracket_svg(state, league, cup):
    teams = cup_teams(state, league, cup)
    if teams is None:
        return None
    t1, t2, t3, t4 = teams
    i = get_cup_ranks(cup)

    sf1, w_sf1 = match_result(state, f"{league}_{cup}_SF1")
    sf2, w_sf2 = match_result(state, f"{league}_{cup}_SF2")
    fin, w_fin = match_result(state, f"{league}_{cup}_Final")
    trd, w_trd = match_result(state, f"{league}_{cup}_3rd")

    a1, a2 = _score_labels(sf1)
    b1, b2 = _score_labels(sf2)
    f1, f2 = _score_labels(fin)
    d1, d2 = _score_labels(trd)

    fin_l = t1 if w_sf1 == "left" else (t4 if w_sf1 == "right" else "SF1勝者")
    fin_r = t2 if w_sf2 == "left" else (t3 if w_sf2 == "right" else "SF2勝者")
    trd_l = t4 if w_sf1 == "left" else (t1 if w_sf1 == "right" else "SF1敗者")
    trd_r = t3 if w_sf2 == "left" else (t2 if w_sf2 == "right" else "SF2敗者")
    champ = fin_l if w_fin == "left" else (fin_r if w_fin == "right" else "優勝")
    third = trd_l if w_trd == "left" else (trd_r if w_trd == "right" else "3位")

    bg = "#FFF4F8" if league == "mix" else "#EFF6FF"
    p = [f'<svg viewBox="0 0 {SVG_W} {SVG_H}" xmlns="http://www.w3.org/2000/svg" '
         f'role="img" style="width:100%;max-width:560px;height:auto;display:block">',
         f'<rect x="0" y="0" width="{SVG_W}" height="{SVG_H}" rx="8" fill="{bg}"/>',
         f'<text x="{X1+4}" y="14" font-size="11" font-weight="700" fill="#555">準決勝</text>',
         f'<text x="{X2+4}" y="14" font-size="11" font-weight="700" fill="#555">決勝</text>']

    ya1, ya2 = 22, 64
    yb1, yb2 = 140, 182
    yf1, yf2, ych = 43, 161, 99

    p.append(_link(X1 + W1, X2, ya1 + BH / 2, ya2 + BH / 2,
                   "top" if w_sf1 == "left" else ("bottom" if w_sf1 == "right" else None)))
    p.append(_link(X1 + W1, X2, yb1 + BH / 2, yb2 + BH / 2,
                   "top" if w_sf2 == "left" else ("bottom" if w_sf2 == "right" else None)))
    p.append(_link(X2 + W2, X3, yf1 + BH / 2, yf2 + BH / 2,
                   "top" if w_fin == "left" else ("bottom" if w_fin == "right" else None)))

    p.append(_box(X1, ya1, W1, BH, t1, a1, i + 1, w_sf1 == "left"))
    p.append(_box(X1, ya2, W1, BH, t4, a2, i + 4, w_sf1 == "right"))
    p.append(_box(X1, yb1, W1, BH, t2, b1, i + 2, w_sf2 == "left"))
    p.append(_box(X1, yb2, W1, BH, t3, b2, i + 3, w_sf2 == "right"))
    p.append(_box(X2, yf1, W2, BH, fin_l, f1, None, w_fin == "left"))
    p.append(_box(X2, yf2, W2, BH, fin_r, f2, None, w_fin == "right"))
    p.append(_box(X3, ych, W3, BH + 6, champ, "", None, w_fin is not None, "#FFD86B"))

    yd1, yd2, yth = 236, 278, 257
    p.append(f'<text x="{X1+4}" y="228" font-size="11" font-weight="700" '
             f'fill="#555">3位決定戦</text>')
    p.append(_link(X1 + W1, X2, yd1 + BH / 2, yd2 + BH / 2,
                   "top" if w_trd == "left" else ("bottom" if w_trd == "right" else None)))
    p.append(_box(X1, yd1, W1, BH, trd_l, d1, None, w_trd == "left", "#F7FAFF"))
    p.append(_box(X1, yd2, W1, BH, trd_r, d2, None, w_trd == "right", "#F7FAFF"))
    p.append(_box(X2, yth, W2, BH, third, "", None, w_trd is not None, "#FFF6C2"))

    p.append('</svg>')
    return "".join(p)


def render_bracket(state, league, cup):
    label = CUP_LABEL_JA[cup] + ("MIX" if league == "mix" else "")
    icon = "🟧" if league == "mix" else "🟦"
    st.markdown(f"##### {icon} {label}")
    svg = bracket_svg(state, league, cup)
    if svg is None:
        st.caption("順位確定後に表示されます")
    else:
        st.markdown(svg, unsafe_allow_html=True)


# ==========================================
# 5. 認証（管理者 / 入力者 / 閲覧者）
# ==========================================
ROLE_LABEL = {"admin": "管理者", "input": "入力者", "view": "閲覧者"}


def init_session():
    init_db()
    ss = st.session_state
    ss.setdefault('auth_status', None)
    ss.setdefault('edit_mode_title', False)
    ss.setdefault('edit_mode_court', False)
    ss.setdefault('edit_mode_settings', False)
    ss.setdefault('edit_mode_teams', False)
    ss.setdefault('editing_match_id', None)
    # 閲覧者だけURLに残す（管理者・入力者はURL共有で権限が漏れるため載せない）
    if ss.auth_status is None and st.query_params.get("role") == "player":
        ss.auth_status = "view"


def check_password():
    ss = st.session_state
    if ss.auth_status is not None:
        return True
    st.markdown("## 🔐 ログイン")
    st.caption("閲覧用パスワードは一度入力すると次回から自動で表示されます。"
               "管理者・入力者は毎回入力が必要です。")
    password = st.text_input("パスワードを入力", type="password")
    if st.button("ログイン"):
        if password == ADMIN_PASS:
            ss.auth_status = "admin"
            st.query_params.clear()
            st.rerun()
        elif INPUT_PASS and password == INPUT_PASS:
            ss.auth_status = "input"
            st.query_params.clear()
            st.rerun()
        elif password == VIEW_PASS:
            ss.auth_status = "view"
            st.query_params["role"] = "player"
            st.rerun()
        else:
            st.error("パスワードが違います")
    return False


# ==========================================
# 6. 画面
# ==========================================
def admin_panel(state):
    ss = st.session_state
    with st.expander("⚙️ 管理者設定 (設定・リセット)", expanded=False):
        if INPUT_PASS is None:
            st.warning("入力者モードのパスワード（INPUT_PASS）が未設定です。"
                       "Secrets に追加すると入力者モードが使えます。")
        st.caption("※ 設定を保存しても、入力済みの試合結果は消えません。")

        st.markdown("##### タイトル設定")
        if not ss.edit_mode_title:
            st.info(state['app_title'])
            if st.button("編集", key="btn_ti"):
                ss.edit_mode_title = True
                st.rerun()
        else:
            nt = st.text_input("タイトル", state['app_title'])
            c1, c2 = st.columns(2)
            if c1.button("保存", key="sv_ti", type="primary"):
                if save_settings({'app_title': nt}):
                    ss.edit_mode_title = False
                    st.rerun()
            if c2.button("取消", key="cn_ti"):
                ss.edit_mode_title = False
                st.rerun()

        st.markdown("---")
        st.markdown("##### コート数設定")
        if not ss.edit_mode_court:
            st.info(f"現在: {state['court_mode']}")
            if st.button("編集", key="btn_ct"):
                ss.edit_mode_court = True
                st.rerun()
        else:
            st.warning("コート数を変えると試合の組み合わせが変わります。"
                       "入力済みの結果は集計対象から外れます。開始後は変更しないでください。")
            nc = st.radio("選択", ["4面", "3面"],
                          index=0 if state['court_mode'] == "4面" else 1)
            c1, c2 = st.columns(2)
            if c1.button("保存", key="sv_ct", type="primary"):
                if save_settings({'court_mode': nc}):
                    ss.edit_mode_court = False
                    st.rerun()
            if c2.button("取消", key="cn_ct"):
                ss.edit_mode_court = False
                st.rerun()

        st.markdown("---")
        st.markdown("##### 時間・スケジュール設定")
        if not ss.edit_mode_settings:
            st.write(f"開始 {state['start_time_hour']}:{state['start_time_minute']:02d}")
            if st.button("編集", key="btn_tm"):
                ss.edit_mode_settings = True
                st.rerun()
        else:
            c1, c2, c3 = st.columns(3)
            nh = c1.number_input("開始(時)", 0, 23, state['start_time_hour'])
            nm = c2.number_input("開始(分)", 0, 59, state['start_time_minute'])
            n_ld = c3.number_input("リーグ時間(分)", 1, 30, state['league_duration'])
            n_iv = c1.number_input("インターバル(分)", 0, 60, state['interval_duration'])
            n_td = c2.number_input("トーナメント時間(分)", 1, 30, state['tourn_duration'])
            b1, b2 = st.columns(2)
            if b1.button("保存", key="sv_tm", type="primary"):
                ok = save_settings({
                    'start_time_hour': int(nh), 'start_time_minute': int(nm),
                    'league_duration': int(n_ld), 'interval_duration': int(n_iv),
                    'tourn_duration': int(n_td)})
                if ok:
                    ss.edit_mode_settings = False
                    st.rerun()
            if b2.button("取消", key="cn_tm"):
                ss.edit_mode_settings = False
                st.rerun()

        st.markdown("---")
        st.markdown("##### チーム名設定")
        if not ss.edit_mode_teams:
            if st.button("編集", key="btn_te"):
                ss.buf_reg = dict(state['teams_reg'])
                ss.buf_mix = dict(state['teams_mix'])
                ss.edit_mode_teams = True
                st.rerun()
        else:
            if 'buf_reg' not in ss:
                ss.buf_reg = dict(state['teams_reg'])
            if 'buf_mix' not in ss:
                ss.buf_mix = dict(state['teams_mix'])
            with st.form("team_form"):
                t1, t2 = st.tabs(["ガチ", "MIX"])
                with t1:
                    for c in "ABCDEFGHIJKL":
                        ss.buf_reg[c] = st.text_input(
                            f"ガチ {c}", ss.buf_reg.get(c, ""), key=f"tr_{c}")
                with t2:
                    for c in "ABCDEFGHIJKL":
                        ss.buf_mix[c] = st.text_input(
                            f"MIX {c}", ss.buf_mix.get(c, ""), key=f"tm_{c}")
                submitted = st.form_submit_button("保存する", type="primary")
            if submitted:
                if save_settings({'teams_reg': dict(ss.buf_reg),
                                  'teams_mix': dict(ss.buf_mix)}):
                    ss.edit_mode_teams = False
                    st.rerun()
            if st.button("取消", key="cn_te"):
                ss.edit_mode_teams = False
                st.rerun()

        st.markdown("---")
        st.error("【危険】データの完全初期化")
        st.caption("全ての試合結果・チーム名・設定を初期状態に戻します。")
        confirm_pass = st.text_input("実行するにはリセット用パスワードを入力",
                                     type="password", key="reset_pass")
        if st.button("初期化を実行する", type="primary"):
            if confirm_pass == RESET_PASS:
                if reset_all():
                    st.toast("✅ 全データを初期化しました")
                    time.sleep(1.5)
                    st.rerun()
            else:
                st.error("パスワードが違います")


def league_tab(state, can_edit):
    base, _, _ = schedule_times(state)
    ss = st.session_state
    slots = []
    if state['court_mode'] == "4面":
        for i, slot in enumerate(SCHEDULE_TEMPLATE_4COURT):
            slots.append({
                "time": base + timedelta(minutes=i * state['league_duration']),
                "games": [
                    {"type": "reg", "c": "A", "p": slot[0]},
                    {"type": "reg", "c": "B", "p": slot[1]},
                    {"type": "mix", "c": "C", "p": slot[2]},
                    {"type": "mix", "c": "D", "p": slot[3]},
                ]})
    else:
        for i, slot in enumerate(SCHEDULE_TEMPLATE_3COURT):
            games = []
            for idx, (lt, h, a) in enumerate(slot["matches"]):
                games.append({"type": lt, "c": ["A", "B", "C"][idx], "p": (h, a)})
            slots.append({
                "time": base + timedelta(minutes=i * state['league_duration']),
                "games": games})

    for i, slot in enumerate(slots):
        st.markdown(f"#### 第{i+1}試合帯 ({slot['time'].strftime('%H:%M')})")
        cols = st.columns(len(slot['games']))
        for idx, game in enumerate(slot['games']):
            l_type, court = game['type'], game['c']
            home, away = game['p']
            match_key = f"{l_type}_{i}_{home}_{away}"
            teams = state['teams_reg'] if l_type == "reg" else state['teams_mix']
            home_name = teams.get(home, home)
            away_name = teams.get(away, away)
            with cols[idx]:
                color = "#FFF0F5" if l_type == "mix" else "#E6F3FF"
                label = f"{court}コート ({'MIX' if l_type == 'mix' else 'ガチ'})"
                with st.container(border=True):
                    st.markdown(
                        f'<div style="background-color:{color};padding:8px;'
                        f'border-radius:5px;margin-bottom:10px;font-weight:bold;">'
                        f'{label}</div>', unsafe_allow_html=True)
                    st.write(f"**{home_name}** vs **{away_name}**")
                    res = state['results'].get(match_key) or {'s1': None, 's2': None}
                    if not can_edit:
                        st.write(f"### {res['s1']} - {res['s2']}"
                                 if res.get('s1') is not None else "ー")
                        continue
                    if ss.editing_match_id == match_key:
                        c1, c2 = st.columns(2)
                        v1 = c1.number_input("左", min_value=0, value=res.get('s1') or 0,
                                             key=f"{match_key}_1",
                                             label_visibility="collapsed")
                        v2 = c2.number_input("右", min_value=0, value=res.get('s2') or 0,
                                             key=f"{match_key}_2",
                                             label_visibility="collapsed")
                        b1, b2 = st.columns(2)
                        if b1.button("確定", key=f"sv_{match_key}", type="primary"):
                            if save_match(match_key, {'s1': int(v1), 's2': int(v2)}, False):
                                ss.editing_match_id = None
                                st.rerun()
                        if b2.button("中止", key=f"cn_{match_key}"):
                            ss.editing_match_id = None
                            st.rerun()
                    elif res.get('s1') is not None:
                        st.markdown(f"### {res['s1']} - {res['s2']}")
                        if st.button("修正", key=f"ed_{match_key}"):
                            ss.editing_match_id = match_key
                            st.rerun()
                    else:
                        if st.button("入力", key=f"in_{match_key}"):
                            ss.editing_match_id = match_key
                            st.rerun()
        st.divider()


def tourn_card(state, game, can_edit):
    ss = st.session_state
    league, cup, rnd, court = game['league'], game['cup'], game['round'], game['court']
    m_id = f"{league}_{cup}_{rnd}"
    left = resolve_slot(state, league, cup, rnd)
    right = resolve_slot(state, league, cup, f"{rnd}_Opp")
    res, _ = match_result(state, m_id)

    color = "#FFF0F5" if league == "mix" else "#E6F3FF"
    label = CUP_LABEL_JA[cup] + ("MIX" if league == "mix" else "")
    rnd_ja = {"SF1": "準決勝1", "SF2": "準決勝2", "Final": "決勝", "3rd": "3位決定戦"}[rnd]

    with st.container(border=True):
        st.markdown(
            f'<div style="background-color:{color};padding:8px;border-radius:5px;'
            f'margin-bottom:10px;font-weight:bold;font-size:13px;">'
            f'{label}<br>{rnd_ja} @ {court}コート</div>', unsafe_allow_html=True)
        st.write(f"**{left or 'Wait'}** vs **{right or 'Wait'}**")

        def show_score():
            txt = f"{res['s1']}-{res['s2']}"
            if res['s1'] == res['s2']:
                txt += f" (PK {res.get('pk1')}-{res.get('pk2')})"
            st.markdown(f"### {txt}")

        if not can_edit:
            if res.get('s1') is not None:
                show_score()
            else:
                st.write("ー")
            return

        if ss.editing_match_id == m_id:
            c1, c2 = st.columns(2)
            v1 = c1.number_input("左", min_value=0, value=res.get('s1') or 0,
                                 key=f"{m_id}_s1", label_visibility="collapsed")
            v2 = c2.number_input("右", min_value=0, value=res.get('s2') or 0,
                                 key=f"{m_id}_s2", label_visibility="collapsed")
            pk1 = pk2 = None
            if v1 == v2:
                st.caption("PK戦のスコア（引き分けのため必須・同点にはできません）")
                p1, p2 = st.columns(2)
                pk1 = p1.number_input("PK左", min_value=0, value=res.get('pk1') or 0,
                                      key=f"{m_id}_pk1")
                pk2 = p2.number_input("PK右", min_value=0, value=res.get('pk2') or 0,
                                      key=f"{m_id}_pk2")
            b1, b2 = st.columns(2)
            if b1.button("保存", key=f"sv_{m_id}", type="primary"):
                if v1 == v2 and pk1 == pk2:
                    st.error("PKのスコアが同点です。勝者が決まらないため保存できません。")
                else:
                    payload = {'s1': int(v1), 's2': int(v2),
                               'pk1': None if pk1 is None else int(pk1),
                               'pk2': None if pk2 is None else int(pk2)}
                    if save_match(m_id, payload, True):
                        ss.editing_match_id = None
                        st.rerun()
            if b2.button("取消", key=f"cn_{m_id}"):
                ss.editing_match_id = None
                st.rerun()
        elif res.get('s1') is not None:
            show_score()
            if st.button("修正", key=f"ed_{m_id}"):
                ss.editing_match_id = m_id
                st.rerun()
        elif left and right:
            if st.button("入力", key=f"in_{m_id}"):
                ss.editing_match_id = m_id
                st.rerun()
        else:
            st.caption("対戦待ち（前のラウンドの結果待ち）")


# ==========================================
# 7. メイン
# ==========================================
init_session()

if check_password():
    role = st.session_state.auth_status
    is_admin = (role == "admin")
    can_edit = role in ("admin", "input")          # ★入力者もスコア編集可
    state = load_state()

    head_l, head_r = st.columns([4, 1])
    with head_l:
        st.title(f"⚽ {state['app_title']}")
        st.caption(f"ログイン中: {ROLE_LABEL.get(role, '')}")
    with head_r:
        if st.button("🔄 更新", use_container_width=True):
            load_state.clear()
            st.rerun()
        if st.button("ログアウト", use_container_width=True):
            st.session_state.clear()
            st.query_params.clear()
            st.rerun()

    if is_admin:
        admin_panel(state)
        state = load_state()

    reg_done, reg_total = league_progress(state, "reg")
    mix_done, mix_total = league_progress(state, "mix")
    league_complete = (reg_done == reg_total and mix_done == mix_total)

    # ★タブは全員4つ（閲覧者も見られる。ただし編集はできない）
    tab1, tab2, tab3, tab4 = st.tabs(
        ["📊 順位表", "📝 リーグ戦", "🏆 決勝戦", "🌲 対戦表"])

    with tab1:
        if league_complete:
            st.success(f"リーグ戦 入力完了（ガチ {reg_done}/{reg_total}・"
                       f"MIX {mix_done}/{mix_total}）順位が確定しました。")
        else:
            st.info(f"リーグ戦 入力状況 … ガチ {reg_done}/{reg_total}・"
                    f"MIX {mix_done}/{mix_total}")
        df_reg = calculate_standings(state, "reg")
        df_mix = calculate_standings(state, "mix")
        cfg = {"チーム名": st.column_config.TextColumn("チーム名", width="medium")}
        st.subheader("🟦 ガチリーグ")
        st.dataframe(
            df_reg.style.background_gradient(subset=['勝点'], cmap='Blues')
                  .format(precision=0),
            hide_index=True, column_config=cfg, use_container_width=True)
        st.subheader("🟧 MIXリーグ")
        st.dataframe(
            df_mix.style.background_gradient(subset=['勝点'], cmap='Oranges')
                  .format(precision=0),
            hide_index=True, column_config=cfg, use_container_width=True)

    with tab2:
        if not can_edit:
            st.caption("閲覧モードです（編集はできません）")
        league_tab(state, can_edit)

    with tab3:
        _, league_end, tourn_start = schedule_times(state)
        st.info(f"🏆 トーナメント開始: {tourn_start.strftime('%H:%M')} "
                f"(リーグ終了 {league_end.strftime('%H:%M')} + "
                f"{state['interval_duration']}分後)")
        if not can_edit:
            st.caption("閲覧モードです（編集はできません）")
        elif not league_complete:
            st.warning(
                f"⚠️ リーグ戦がまだ全部入力されていません"
                f"（ガチ {reg_done}/{reg_total}・MIX {mix_done}/{mix_total}）。"
                "順位が未確定のため、この画面の組み合わせは変わる可能性があります。")
        sched = (TOURN_SCHED_4COURT if state['court_mode'] == "4面"
                 else TOURN_SCHED_3COURT)
        for idx_slot, slot in enumerate(sched):
            t_str = (tourn_start + timedelta(
                minutes=idx_slot * state['tourn_duration'])).strftime('%H:%M')
            st.markdown(f"#### ⏰ {t_str} - {slot['cup_display']}")
            cols = st.columns(len(slot['games']))
            for idx_game, game in enumerate(slot['games']):
                with cols[idx_game]:
                    tourn_card(state, game, can_edit)
            st.divider()

    with tab4:
        st.header("決勝トーナメント表")
        if not league_complete:
            st.caption("※ リーグ戦の全結果が入力されると順位が確定します。")
        st.markdown("### 🟦 ガチリーグ")
        for cup in ("Champions", "Elite", "Classical"):
            render_bracket(state, "reg", cup)
        st.markdown("### 🟧 MIXリーグ")
        for cup in ("Champions", "Elite", "Classical"):
            render_bracket(state, "mix", cup)
