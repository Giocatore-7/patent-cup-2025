import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import graphviz
import json
import os

# ==========================================
# 1. 設定・データ定義
# ==========================================
st.set_page_config(page_title="パテントカップ大会アプリ", layout="wide")

# ★【修正】コード内からパスワードを完全削除
# Secrets（金庫）から読み込めない場合は、エラーを出してアプリを停止します。
# これにより、GitHub上のコードを見てもパスワードは一切分かりません。
try:
    ADMIN_PASS = st.secrets["ADMIN_PASS"]
    VIEW_PASS = st.secrets["VIEW_PASS"]
    RESET_PASS = st.secrets["RESET_PASS"]
except (FileNotFoundError, KeyError):
    st.error("⛔ セキュリティエラー: パスワード設定が見つかりません。")
    st.info("管理者の方へ: Streamlit Community Cloudの「Settings > Secrets」にて、ADMIN_PASS, VIEW_PASS, RESET_PASS を設定してください。")
    st.stop() # アプリをここで強制停止

# ★ CSS設定（アイコン非表示 ＆ タブ固定）
st.markdown("""
    <style>
    /* 1. 右上のツールバー（GitHubアイコン、点々メニューなど）だけを消す */
    [data-testid="stToolbar"] {
        visibility: hidden !important;
        display: none !important;
    }
    
    /* Deployボタンを消す */
    .stAppDeployButton {
        display: none !important;
    }
    
    /* フッター（Made with Streamlit）を消す */
    footer {
        visibility: hidden;
    }

    /* 2. タブをスクロール追従（Sticky）させる */
    div[data-baseweb="tab-list"] {
        position: sticky;
        top: 3.5rem;
        z-index: 999;
        background-color: white;
        padding-top: 10px;
        padding-bottom: 0px;
        margin-bottom: 10px;
        border-bottom: 1px solid #f0f0f0;
    }
    </style>
""", unsafe_allow_html=True)

DATA_FILE = "patent_cup_data.json" # データを保存するファイル名

# チーム名初期値
DEFAULT_TEAMS_REGULAR = {chr(65+i): f"チーム{chr(65+i)}" for i in range(12)}
DEFAULT_TEAMS_MIX = {chr(65+i): f"MIXチーム{chr(65+i)}" for i in range(12)}

# -------------------------------------------
# スケジュール定義
# -------------------------------------------
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

# ==========================================
# 2. 関数定義
# ==========================================

def load_data_from_json():
    """JSONファイルからデータを読み込む"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return None
    return None

def save_data_to_json():
    """現在のステートをJSONファイルに保存する"""
    data = {
        'app_title': st.session_state.app_title,
        'teams_reg': st.session_state.teams_reg,
        'teams_mix': st.session_state.teams_mix,
        'results': st.session_state.results,
        'tourn_results': st.session_state.tourn_results,
        'court_mode': st.session_state.court_mode,
        'start_time_hour': st.session_state.start_time_hour,
        'start_time_minute': st.session_state.start_time_minute,
        'league_duration': st.session_state.league_duration,
        'tourn_duration': st.session_state.tourn_duration,
        'interval_duration': st.session_state.interval_duration
    }
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def init_session_state():
    if 'initialized' not in st.session_state:
        saved_data = load_data_from_json()
        
        # 変数の初期化
        st.session_state.auth_status = None
        st.session_state.edit_mode_title = False
        st.session_state.edit_mode_court = False
        st.session_state.edit_mode_settings = False
        st.session_state.edit_mode_teams = False
        st.session_state.editing_match_id = None

        if saved_data:
            st.session_state.app_title = saved_data.get('app_title', "パテントカップ2025")
            st.session_state.teams_reg = saved_data.get('teams_reg', DEFAULT_TEAMS_REGULAR.copy())
            st.session_state.teams_mix = saved_data.get('teams_mix', DEFAULT_TEAMS_MIX.copy())
            st.session_state.results = saved_data.get('results', {})
            st.session_state.tourn_results = saved_data.get('tourn_results', {})
            st.session_state.court_mode = saved_data.get('court_mode', "4面")
            st.session_state.start_time_hour = saved_data.get('start_time_hour', 13)
            st.session_state.start_time_minute = saved_data.get('start_time_minute', 15)
            st.session_state.league_duration = saved_data.get('league_duration', 7)
            st.session_state.tourn_duration = saved_data.get('tourn_duration', 10)
            st.session_state.interval_duration = saved_data.get('interval_duration', 15)
        else:
            if 'app_title' not in st.session_state: st.session_state.app_title = "パテントカップ2025"
            if 'teams_reg' not in st.session_state: st.session_state.teams_reg = DEFAULT_TEAMS_REGULAR.copy()
            if 'teams_mix' not in st.session_state: st.session_state.teams_mix = DEFAULT_TEAMS_MIX.copy()
            if 'results' not in st.session_state: st.session_state.results = {} 
            if 'tourn_results' not in st.session_state: st.session_state.tourn_results = {}
            if 'court_mode' not in st.session_state: st.session_state.court_mode = "4面"
            if 'start_time_hour' not in st.session_state: st.session_state.start_time_hour = 13
            if 'start_time_minute' not in st.session_state: st.session_state.start_time_minute = 15
            if 'league_duration' not in st.session_state: st.session_state.league_duration = 7
            if 'tourn_duration' not in st.session_state: st.session_state.tourn_duration = 10
            if 'interval_duration' not in st.session_state: st.session_state.interval_duration = 15
        
        st.session_state.initialized = True

    # URLパラメータによる自動ログイン
    query_params = st.query_params
    if st.session_state.auth_status is None:
        role = query_params.get("role")
        if role == "player":
            st.session_state.auth_status = "view"
        elif role == "admin_secret":
            st.session_state.auth_status = "admin"

def check_password():
    if st.session_state.auth_status is not None:
        return True

    st.markdown("## 🔐 ログイン")
    st.caption("一度ログインすると、次回からは自動で表示されます。")
    password = st.text_input("パスワードを入力", type="password")
    
    if st.button("ログイン"):
        if password == ADMIN_PASS:
            st.session_state.auth_status = "admin"
            st.query_params["role"] = "admin_secret"
            st.rerun()
        elif password == VIEW_PASS:
            st.session_state.auth_status = "view"
            st.query_params["role"] = "player"
            st.rerun()
        else:
            st.error("パスワードが違います")
    return False

def get_team_name(league, code):
    if league == "reg": return st.session_state.teams_reg.get(code, code)
    else: return st.session_state.teams_mix.get(code, code)

def calculate_standings(league_type):
    teams_map = st.session_state.teams_reg if league_type == "reg" else st.session_state.teams_mix
    data = []
    for code, name in teams_map.items():
        stats = {"チーム名": name, "Code": code, "勝点": 0, "試合数": 0, "勝": 0, "引": 0, "負": 0, "得点": 0, "失点": 0, "得失差": 0}
        stats["SortIndex"] = ord(code) - 65
        for key, res in st.session_state.results.items():
            if not key.startswith(f"{league_type}_"): continue
            parts = key.split("_")
            if len(parts) < 4: continue
            home_code, away_code = parts[2], parts[3]
            if res['s1'] is not None and res['s2'] is not None:
                s1, s2 = res['s1'], res['s2']
                if code == home_code:
                    stats["試合数"]+=1; stats["得点"]+=s1; stats["失点"]+=s2; stats["得失差"]+=(s1-s2)
                    if s1>s2: stats["勝点"]+=3; stats["勝"]+=1
                    elif s1==s2: stats["勝点"]+=1; stats["引"]+=1
                    else: stats["負"]+=1
                elif code == away_code:
                    stats["試合数"]+=1; stats["得点"]+=s2; stats["失点"]+=s1; stats["得失差"]+=(s2-s1)
                    if s2>s1: stats["勝点"]+=3; stats["勝"]+=1
                    elif s2==s1: stats["勝点"]+=1; stats["引"]+=1
                    else: stats["負"]+=1
        data.append(stats)
    df = pd.DataFrame(data)
    df = df.sort_values(by=["勝点", "得失差", "得点", "SortIndex"], ascending=[False, False, False, True])
    df.insert(0, "順位", range(1, len(df) + 1))
    return df

# --- トーナメント処理 ---
def get_cup_ranks(cup_name):
    if cup_name == "Champions": return 0
    if cup_name == "Elite": return 4
    if cup_name == "Classical": return 8
    return 0

def get_tourn_match_result(match_id):
    res = st.session_state.tourn_results.get(match_id, {'s1': None, 's2': None, 'pk1': None, 'pk2': None})
    winner, loser = None, None
    s1, s2 = res['s1'], res['s2']
    if s1 is not None and s2 is not None:
        if s1 > s2: winner, loser = "left", "right"
        elif s2 > s1: winner, loser = "right", "left"
        else:
            pk1, pk2 = res.get('pk1'), res.get('pk2')
            if pk1 is not None and pk2 is not None:
                if pk1 > pk2: winner, loser = "left", "right"
                elif pk2 > pk1: winner, loser = "right", "left"
    return res, winner, loser

def resolve_tournament_team(league, cup, round_name, ranks_list, match_id_prefix):
    start_idx = get_cup_ranks(cup)
    if len(ranks_list) < 12: return None
    t1, t4 = ranks_list[start_idx], ranks_list[start_idx+3]
    t2, t3 = ranks_list[start_idx+1], ranks_list[start_idx+2]
    
    if round_name == "SF1": return t1
    if round_name == "SF1_Opp": return t4
    if round_name == "SF2": return t2
    if round_name == "SF2_Opp": return t3

    sf1_id = f"{league}_{cup}_SF1"; sf2_id = f"{league}_{cup}_SF2"
    _, w1, l1 = get_tourn_match_result(sf1_id)
    _, w2, l2 = get_tourn_match_result(sf2_id)
    
    win1 = t1 if w1=="left" else t4 if w1=="right" else None
    lose1 = t1 if w1=="right" else t4 if w1=="left" else None
    win2 = t2 if w2=="left" else t3 if w2=="right" else None
    lose2 = t2 if w2=="right" else t3 if w2=="left" else None

    if round_name == "Final": return win1
    if round_name == "Final_Opp": return win2
    if round_name == "3rd": return lose1
    if round_name == "3rd_Opp": return lose2
    return None

def render_match_card(league_type, title, match_id, team_l, team_r, court, is_admin):
    res, _, _ = get_tourn_match_result(match_id)
    header_color = "#FFF0F5" if league_type == "mix" else "#E6F3FF"
    
    # コート名に「コート」を追加
    header_text = f"{title} @ {court}コート"
    
    with st.container(border=True):
        st.markdown(f"""<div style="background-color: {header_color}; padding: 8px; border-radius: 5px; margin-bottom: 10px; font-weight: bold;">{header_text}</div>""", unsafe_allow_html=True)
        t_l_show = team_l if team_l else "Wait"
        t_r_show = team_r if team_r else "Wait"
        st.write(f"**{t_l_show}** vs **{t_r_show}**")

        if is_admin:
            if st.session_state.editing_match_id == match_id:
                c1, c2 = st.columns(2)
                v1 = c1.number_input("左", value=res['s1'] or 0, key=f"{match_id}_s1", label_visibility="collapsed")
                v2 = c2.number_input("右", value=res['s2'] or 0, key=f"{match_id}_s2", label_visibility="collapsed")
                pk_v1, pk_v2 = None, None
                if v1 == v2:
                    st.caption("PK")
                    cp1, cp2 = st.columns(2)
                    pk_v1 = cp1.number_input("P左", value=res['pk1'] or 0, key=f"{match_id}_pk1")
                    pk_v2 = cp2.number_input("P右", value=res['pk2'] or 0, key=f"{match_id}_pk2")
                b1, b2 = st.columns(2)
                if b1.button("保存", key=f"sv_{match_id}", type="primary"):
                    st.session_state.tourn_results[match_id] = {'s1': v1, 's2': v2, 'pk1': pk_v1, 'pk2': pk_v2}
                    save_data_to_json() 
                    st.session_state.editing_match_id = None; st.rerun()
                if b2.button("取消", key=f"cn_{match_id}"): st.session_state.editing_match_id = None; st.rerun()
            else:
                if res['s1'] is not None:
                    txt = f"{res['s1']}-{res['s2']}"
                    if res['s1'] == res['s2']: txt += f" (PK {res['pk1']}-{res['pk2']})"
                    st.markdown(f"### {txt}")
                    if st.button("修正", key=f"ed_{match_id}"): st.session_state.editing_match_id = match_id; st.rerun()
                else:
                    if team_l and team_r:
                        if st.button("入力", key=f"in_{match_id}"): st.session_state.editing_match_id = match_id; st.rerun()
                    else:
                        st.caption("対戦待ち")
        else:
            if res['s1'] is not None:
                txt = f"{res['s1']}-{res['s2']}"
                if res['s1'] == res['s2']: txt += f" (PK {res['pk1']}-{res['pk2']})"
                st.markdown(f"### {txt}")
            else:
                st.write("ー")

def render_graphviz_bracket(cup_name, team_list, league, league_label):
    st.markdown(f"#### {league_label} {cup_name}")
    if len(team_list) < 12:
        st.caption("順位確定後に表示されます")
        return
    start_idx = get_cup_ranks(cup_name)
    prefix = f"{league}_{cup_name}"
    t1, t2, t3, t4 = team_list[start_idx], team_list[start_idx+1], team_list[start_idx+2], team_list[start_idx+3]
    _, w_sf1, _ = get_tourn_match_result(f"{prefix}_SF1")
    _, w_sf2, _ = get_tourn_match_result(f"{prefix}_SF2")
    _, w_fin, _ = get_tourn_match_result(f"{prefix}_Final")
    _, w_3rd, _ = get_tourn_match_result(f"{prefix}_3rd")
    
    f1_name = t1 if w_sf1 == "left" else t4 if w_sf1 == "right" else "SF1勝者"
    f2_name = t2 if w_sf2 == "left" else t3 if w_sf2 == "right" else "SF2勝者"
    th1_name = t1 if w_sf1 == "right" else t4 if w_sf1 == "left" else "SF1敗者"
    th2_name = t2 if w_sf2 == "right" else t3 if w_sf2 == "left" else "SF2敗者"
    champ_name = f1_name if w_fin == "left" else f2_name if w_fin == "right" else "優勝"
    third_name = th1_name if w_3rd == "left" else th2_name if w_3rd == "right" else "3位"
    bg_color = "#FFF0F5" if league == "mix" else "#E6F3FF"
    third_node_color = "#FFFACD" 
    dot_code = f"""
    digraph G {{
        rankdir=LR; bgcolor="{bg_color}";
        node [shape=box, style="filled,rounded", fillcolor="white", fontname="Sans-Serif", fontsize=10];
        edge [penwidth=1.5];
        subgraph cluster_main {{
            label="本戦"; style=invis;
            node [fillcolor="#E6F3FF"] T1 [label="1位: {t1}"]; T4 [label="4位: {t4}"]; T2 [label="2位: {t2}"]; T3 [label="3位: {t3}"];
            node [fillcolor="#FFF0F5"] F1 [label="{f1_name}"]; F2 [label="{f2_name}"];
            node [fillcolor="#FFD700"] WIN [label="{champ_name}"];
            T1 -> F1 [color="{'red' if w_sf1=='left' else 'black'}", penwidth={'2.5' if w_sf1=='left' else '1'}];
            T4 -> F1 [color="{'red' if w_sf1=='right' else 'black'}", penwidth={'2.5' if w_sf1=='right' else '1'}];
            T2 -> F2 [color="{'red' if w_sf2=='left' else 'black'}", penwidth={'2.5' if w_sf2=='left' else '1'}];
            T3 -> F2 [color="{'red' if w_sf2=='right' else 'black'}", penwidth={'2.5' if w_sf2=='right' else '1'}];
            F1 -> WIN [color="{'red' if w_fin=='left' else 'black'}", penwidth={'2.5' if w_fin=='left' else '1'}];
            F2 -> WIN [color="{'red' if w_fin=='right' else 'black'}", penwidth={'2.5' if w_fin=='right' else '1'}];
        }}
        T3 -> L1 [style=invis, weight=10];
        subgraph cluster_3rd {{
            label="3位決定戦"; style=filled; color="{bg_color}";
            node [fillcolor="#F0F8FF"] L1 [label="{th1_name}"]; L2 [label="{th2_name}"];
            node [fillcolor="{third_node_color}"] THIRD [label="{third_name}"];
            L1 -> THIRD [color="{'red' if w_3rd=='left' else 'black'}", penwidth={'2.5' if w_3rd=='left' else '1'}];
            L2 -> THIRD [color="{'red' if w_3rd=='right' else 'black'}", penwidth={'2.5' if w_3rd=='right' else '1'}];
        }}
    }}
    """
    st.graphviz_chart(dot_code)

# ==========================================
# 4. メイン処理
# ==========================================
init_session_state()

# --- 管理者設定パネル ---
if check_password():
    is_admin = (st.session_state.auth_status == "admin")
    st.sidebar.title("大会設定")
    if is_admin:
        with st.sidebar.expander("⚙️ 管理者メニュー"):
            st.markdown("### タイトル")
            if not st.session_state.edit_mode_title:
                st.info(st.session_state.app_title)
                if st.button("編集", key="btn_ti"): st.session_state.edit_mode_title=True; st.rerun()
            else:
                nt = st.text_input("タイトル", st.session_state.app_title)
                if st.button("保存", key="sv_ti"): 
                    st.session_state.app_title=nt; save_data_to_json(); st.session_state.edit_mode_title=False; st.rerun()
            st.markdown("---")
            st.markdown("### コート数")
            if not st.session_state.edit_mode_court:
                st.info(f"現在: {st.session_state.court_mode}")
                if st.button("編集", key="btn_ct"): st.session_state.edit_mode_court=True; st.rerun()
            else:
                nc = st.radio("選択", ["4面", "3面"], index=0 if st.session_state.court_mode=="4面" else 1)
                if st.button("保存", key="sv_ct"): 
                    st.session_state.court_mode=nc; save_data_to_json(); st.session_state.edit_mode_court=False; st.rerun()
            st.markdown("---")
            st.markdown("### 時間・スケジュール")
            if not st.session_state.edit_mode_settings:
                st.write(f"開始 {st.session_state.start_time_hour}:{st.session_state.start_time_minute:02d}")
                if st.button("編集", key="btn_tm"): st.session_state.edit_mode_settings=True; st.rerun()
            else:
                nh = st.number_input("開始(時)", 0, 23, st.session_state.start_time_hour)
                nm = st.number_input("開始(分)", 0, 59, st.session_state.start_time_minute)
                n_ld = st.number_input("リーグ時間(分)", 1, 30, st.session_state.league_duration)
                n_iv = st.number_input("インターバル(分)", 0, 60, st.session_state.interval_duration)
                n_td = st.number_input("トーナメント時間(分)", 1, 30, st.session_state.tourn_duration)
                if st.button("保存", key="sv_tm"):
                    st.session_state.start_time_hour = nh; st.session_state.start_time_minute = nm
                    st.session_state.league_duration = n_ld; st.session_state.interval_duration = n_iv
                    st.session_state.tourn_duration = n_td
                    save_data_to_json(); st.session_state.edit_mode_settings = False; st.rerun()
            st.markdown("---")
            st.markdown("### チーム名")
            if not st.session_state.edit_mode_teams:
                if st.button("編集", key="btn_te"): st.session_state.edit_mode_teams=True; st.rerun()
            else:
                t1, t2 = st.tabs(["ガチ", "MIX"])
                with t1:
                    with st.form("rt"):
                        for c in "ABCDEFGHIJKL": st.session_state.teams_reg[c] = st.text_input(f"{c}", st.session_state.teams_reg[c])
                        st.form_submit_button("保存")
                with t2:
                    with st.form("mt"):
                        for c in "ABCDEFGHIJKL": st.session_state.teams_mix[c] = st.text_input(f"{c}", st.session_state.teams_mix[c])
                        st.form_submit_button("保存")
                if st.button("編集完了（保存）", key="en_te"): 
                    save_data_to_json(); st.session_state.edit_mode_teams=False; st.rerun()
        
        # ★【追加】完全初期化機能（爆弾削除）
        st.markdown("---")
        with st.expander("データの完全初期化"):
            st.error("【注意】全ての試合結果と設定を削除し、初期状態に戻します。元に戻すことはできません。")
            confirm_pass = st.text_input("実行するにはリセット用パスワードを入力", type="password", key="reset_pass")
            if st.button("初期化を実行する", type="primary"):
                # ここで RESET_PASS と一致するかチェック
                if confirm_pass == RESET_PASS:
                    if os.path.exists(DATA_FILE):
                        os.remove(DATA_FILE)
                    st.session_state.clear()
                    st.query_params.clear()
                    st.rerun()
                else:
                    st.error("パスワードが違います")
    else:
        st.sidebar.info(f"コート: {st.session_state.court_mode}")
            
    if st.sidebar.button("ログアウト"): 
        st.session_state.auth_status = None
        st.query_params.clear() 
        st.rerun()

    # === メイン画面 ===
    st.title(f"⚽ {st.session_state.app_title}")
    tab1, tab2, tab3, tab4 = st.tabs(["📊 順位表", "📝 リーグ戦入力", "🏆 トーナメント入力", "🌲 トーナメント表"])
    
    df_reg = calculate_standings("reg")
    df_mix = calculate_standings("mix")

    # Tab 1: 順位表
    with tab1:
        # カラム設定を追加（チーム名の幅を固定）
        common_cfg = {"チーム名": st.column_config.TextColumn("チーム名", width="medium")}
        
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("🟦 ガチリーグ")
            st.dataframe(
                df_reg.style.background_gradient(subset=['勝点'], cmap='Blues').format(precision=0), 
                hide_index=True, 
                column_config=common_cfg
            )
        with c2:
            st.subheader("🟧 MIXリーグ")
            st.dataframe(
                df_mix.style.background_gradient(subset=['勝点'], cmap='Oranges').format(precision=0), 
                hide_index=True,
                column_config=common_cfg
            )

    # Tab 2: リーグ戦
    with tab2:
        base_time = datetime(2025, 1, 1, st.session_state.start_time_hour, st.session_state.start_time_minute)
        court_mode = st.session_state.court_mode
        matches_to_show = []
        if court_mode == "4面":
            for i, slot in enumerate(SCHEDULE_TEMPLATE_4COURT):
                matches_to_show.append({"time": base_time + timedelta(minutes=i*st.session_state.league_duration), "games": [
                    {"type": "reg", "c": "A", "p": slot[0]}, {"type": "reg", "c": "B", "p": slot[1]},
                    {"type": "mix", "c": "C", "p": slot[2]}, {"type": "mix", "c": "D", "p": slot[3]}
                ]})
            league_end_time = base_time + timedelta(minutes=9*st.session_state.league_duration)
        else:
            for i, slot in enumerate(SCHEDULE_TEMPLATE_3COURT):
                games = []
                for idx, m_info in enumerate(slot["matches"]):
                    games.append({"type": m_info[0], "c": ["A","B","C"][idx], "p": (m_info[1], m_info[2])})
                matches_to_show.append({"time": base_time + timedelta(minutes=i*st.session_state.league_duration), "games": games})
            league_end_time = base_time + timedelta(minutes=12*st.session_state.league_duration)

        for i, slot in enumerate(matches_to_show):
            st.markdown(f"#### 第{i+1}試合帯 ({slot['time'].strftime('%H:%M')})")
            cols = st.columns(len(slot['games']))
            for idx, game in enumerate(slot['games']):
                l_type, court, (home, away) = game['type'], game['c'], game['p']
                match_key = f"{l_type}_{i}_{home}_{away}"
                home_name = get_team_name(l_type, home); away_name = get_team_name(l_type, away)
                
                with cols[idx]:
                    header_color = "#FFF0F5" if l_type == "mix" else "#E6F3FF"
                    # コート名に「コート」を追加
                    header_text = f"{court}コート (MIX)" if l_type == "mix" else f"{court}コート (ガチ)"
                    
                    with st.container(border=True):
                        st.markdown(f"""<div style="background-color: {header_color}; padding: 8px; border-radius: 5px; margin-bottom: 10px; font-weight: bold;">{header_text}</div>""", unsafe_allow_html=True)
                        st.write(f"**{home_name}** vs **{away_name}**")
                        res = st.session_state.results.get(match_key, {'s1': None, 's2': None})
                        if is_admin:
                            if st.session_state.editing_match_id == match_key:
                                c1, c2 = st.columns(2)
                                v1 = c1.number_input("左", value=res['s1'] or 0, key=f"{match_key}_1", label_visibility="collapsed")
                                v2 = c2.number_input("右", value=res['s2'] or 0, key=f"{match_key}_2", label_visibility="collapsed")
                                b1, b2 = st.columns(2)
                                if b1.button("確定", key=f"sv_{match_key}", type="primary"):
                                    st.session_state.results[match_key] = {'s1': v1, 's2': v2}
                                    save_data_to_json() # 保存！
                                    st.session_state.editing_match_id = None; st.rerun()
                                if b2.button("中止", key=f"cn_{match_key}"): st.session_state.editing_match_id = None; st.rerun()
                            else:
                                if res['s1'] is not None:
                                    st.markdown(f"### {res['s1']} - {res['s2']}")
                                    if st.button("修正", key=f"ed_{match_key}"): st.session_state.editing_match_id = match_key; st.rerun()
                                else:
                                    if st.button("入力", key=f"in_{match_key}"): st.session_state.editing_match_id = match_key; st.rerun()
                        else:
                            st.write(f"### {res['s1']} - {res['s2']}" if res['s1'] is not None else "ー")
            st.divider()

    with tab3:
        tourn_start = league_end_time + timedelta(minutes=st.session_state.interval_duration)
        st.info(f"🏆 トーナメント開始: {tourn_start.strftime('%H:%M')} (リーグ終了 {league_end_time.strftime('%H:%M')} + {st.session_state.interval_duration}分後)")
        
        reg_ranks = df_reg["チーム名"].tolist()
        mix_ranks = df_mix["チーム名"].tolist()
        schedule = TOURN_SCHED_4COURT if st.session_state.court_mode == "4面" else TOURN_SCHED_3COURT
        
        for idx_slot, slot in enumerate(schedule):
            t_str = (tourn_start + timedelta(minutes=idx_slot * st.session_state.tourn_duration)).strftime('%H:%M')
            st.markdown(f"#### ⏰ {t_str} - {slot['cup_display']}")
            cols = st.columns(len(slot['games']))
            for idx_game, game in enumerate(slot['games']):
                with cols[idx_game]:
                    m_id = f"{game['league']}_{game['cup']}_{game['round']}"
                    team_list = reg_ranks if game['league']=="reg" else mix_ranks
                    if game['round'].startswith("SF"):
                        t_left = resolve_tournament_team(game['league'], game['cup'], "SF1" if game['round']=="SF1" else "SF2", team_list, "")
                        t_right = resolve_tournament_team(game['league'], game['cup'], "SF1_Opp" if game['round']=="SF1" else "SF2_Opp", team_list, "")
                    else:
                        t_left = resolve_tournament_team(game['league'], game['cup'], game['round'], team_list, "")
                        t_right = resolve_tournament_team(game['league'], game['cup'], f"{game['round']}_Opp", team_list, "")

                    render_match_card(game['league'], f"{game['cup']} {game['round']}", m_id, t_left, t_right, game['court'], is_admin)
            st.divider()

    with tab4:
        st.header("決勝トーナメント表")
        reg_ranks_list = df_reg["チーム名"].tolist()
        mix_ranks_list = df_mix["チーム名"].tolist()

        c1, c2 = st.columns(2)
        with c1:
            st.subheader("🟦 ガチリーグ")
            render_graphviz_bracket("Champions", reg_ranks_list, "reg", "🟦 パテントチャンピオンズカップ")
            render_graphviz_bracket("Elite", reg_ranks_list, "reg", "🟦 パテントエリートカップ")
            render_graphviz_bracket("Classical", reg_ranks_list, "reg", "🟦 パテントクラシカルカップ")
        with c2:
            st.subheader("🟧 MIXリーグ")
            render_graphviz_bracket("Champions", mix_ranks_list, "mix", "🟧 パテントチャンピオンズカップMIX")
            render_graphviz_bracket("Elite", mix_ranks_list, "mix", "🟧 パテントエリートカップMIX")
            render_graphviz_bracket("Classical", mix_ranks_list, "mix", "🟧 パテントクラシカルカップMIX")
