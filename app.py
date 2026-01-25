import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import graphviz
import json
import os
# --- 追加ライブラリ ---
import gspread
from google.oauth2.service_account import Credentials

# ==========================================
# 1. 設定・データ定義
# ==========================================
st.set_page_config(page_title="パテントカップ大会アプリ", layout="wide")

# パスワード管理
try:
    ADMIN_PASS = st.secrets["ADMIN_PASS"]
    VIEW_PASS = st.secrets["VIEW_PASS"]
    RESET_PASS = st.secrets["RESET_PASS"]
except (FileNotFoundError, KeyError):
    st.error("⛔ セキュリティエラー: パスワード設定が見つかりません。")
    st.stop()

# ★【修正】CSS設定（アイコン隠しのみ。タブ固定やサイドバー操作は削除）
st.markdown("""
    <style>
    /* 右上のツールバーを消す */
    [data-testid="stToolbar"] {
        display: none !important;
    }
    /* Deployボタンを消す */
    .stAppDeployButton {
        display: none !important;
    }
    /* フッターを消す */
    footer {
        display: none !important;
    }
    /* ヘッダーの装飾を消す */
    [data-testid="stDecoration"] {
        display: none !important;
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
# 2. 関数定義 (Google Sheets 対応版)
# ==========================================

def get_google_sheet():
    """Googleスプレッドシートに接続する関数"""
    try:
        # SecretsからJSONキーの文字列を取得して辞書に変換
        key_dict = json.loads(st.secrets["GCP_JSON_KEY"])
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(key_dict, scopes=scopes)
        client = gspread.authorize(creds)
        
        # シートを開く
        sheet_name = st.secrets["SPREADSHEET_NAME"]
        return client.open(sheet_name).sheet1
    except Exception as e:
        st.error(f"スプレッドシート接続エラー: {e}")
        return None

# 修正前
# def load_data_from_json():

# 修正後（@st.cache_data をつける）
@st.cache_data(ttl=30)  # ← 追加！このデータは30秒間キャッシュされます
def load_data_from_json():
    """Googleスプレッドシート(A1セル)からデータを読み込む"""
    try:
        sheet = get_google_sheet()
        # ... (中身はそのまま) ...
        if sheet:
            # A1セルの値を取得
            data_str = sheet.cell(1, 1).value
            if data_str:
                return json.loads(data_str)
    except Exception as e:
        # まだデータがない場合などはここに来るので無視してOK
        pass
    return None

def save_data_to_json():
    """現在のステートをGoogleスプレッドシート(A1セル)に保存する"""
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
    
    try:
        sheet = get_google_sheet()
        if sheet:
            json_str = json.dumps(data, ensure_ascii=False)
            sheet.update_cell(1, 1, json_str)
            
            # ★ここに追加！ 保存したらキャッシュを削除して、次回は必ず読み込み直すようにする
            load_data_from_json.clear()
            
            st.toast("✅ データをクラウドに保存しました")
    except Exception as e:
        st.error(f"保存エラー: {e}")

# ==========================================
# ★追加：競合を防ぐための「単一試合更新」関数
# ==========================================
def save_specific_match(match_key, new_result_dict, is_tournament=False):
    """
    クラウド上の最新データを取得し、特定の1試合の結果だけを書き換えて保存する。
    これにより、他人の入力を消してしまう事故を防ぐ。
    """
    try:
        sheet = get_google_sheet()
        if sheet:
            # 1. クラウドにある「正真正銘の最新データ」を取りに行く
            current_val = sheet.cell(1, 1).value
            if not current_val:
                st.error("データの読み込みに失敗しました")
                return
            
            # 2. JSONを復元
            data = json.loads(current_val)
            
            # 3. 指定された試合だけを書き換える（他は触らない！）
            if is_tournament:
                data['tourn_results'][match_key] = new_result_dict
            else:
                data['results'][match_key] = new_result_dict
            
            # 4. 書き戻す
            json_str = json.dumps(data, ensure_ascii=False)
            sheet.update_cell(1, 1, json_str)
            
            # 5. 自分の手元のデータも最新に合わせる
            if is_tournament:
                st.session_state.tourn_results = data['tourn_results']
            else:
                st.session_state.results = data['results']
            
            # 6. キャッシュをクリア
            load_data_from_json.clear()
            
            st.toast(f"✅ 試合 {match_key} の結果を保存しました")
            
    except Exception as e:
        st.error(f"保存エラー（再試行してください）: {e}")

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
                    # --- 修正前 ---
# st.session_state.tourn_results[match_id] = {'s1': v1, 's2': v2, 'pk1': pk_v1, 'pk2': pk_v2}
# save_data_to_json() 
# st.session_state.editing_match_id = None; st.rerun()

# --- 修正後 ---
save_specific_match(match_id, {'s1': v1, 's2': v2, 'pk1': pk_v1, 'pk2': pk_v2}, is_tournament=True)
st.session_state.editing_match_id = None
st.rerun()
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

# --- メイン画面上部の管理者設定（サイドバー廃止） ---
if check_password():
    is_admin = (st.session_state.auth_status == "admin")
    
    # ★【修正】管理者なら、メイン画面の最上部に設定パネルを表示
    if is_admin:
        with st.expander("⚙️ 管理者設定 (設定・リセット)", expanded=False):
            # 1. タイトル
            st.markdown("##### タイトル設定")
            if not st.session_state.edit_mode_title:
                st.info(st.session_state.app_title)
                if st.button("編集", key="btn_ti"): st.session_state.edit_mode_title=True; st.rerun()
            else:
                nt = st.text_input("タイトル", st.session_state.app_title)
                if st.button("保存", key="sv_ti"): 
                    st.session_state.app_title=nt; save_data_to_json(); st.session_state.edit_mode_title=False; st.rerun()
            
            st.markdown("---")
            
            # 2. コート数
            st.markdown("##### コート数設定")
            if not st.session_state.edit_mode_court:
                st.info(f"現在: {st.session_state.court_mode}")
                if st.button("編集", key="btn_ct"): st.session_state.edit_mode_court=True; st.rerun()
            else:
                nc = st.radio("選択", ["4面", "3面"], index=0 if st.session_state.court_mode=="4面" else 1)
                if st.button("保存", key="sv_ct"): 
                    st.session_state.court_mode=nc; save_data_to_json(); st.session_state.edit_mode_court=False; st.rerun()
            
            st.markdown("---")
            
            # 3. 時間・スケジュール
            st.markdown("##### 時間・スケジュール設定")
            if not st.session_state.edit_mode_settings:
                st.write(f"開始 {st.session_state.start_time_hour}:{st.session_state.start_time_minute:02d}")
                if st.button("編集", key="btn_tm"): st.session_state.edit_mode_settings=True; st.rerun()
            else:
                c1, c2, c3 = st.columns(3)
                nh = c1.number_input("開始(時)", 0, 23, st.session_state.start_time_hour)
                nm = c2.number_input("開始(分)", 0, 59, st.session_state.start_time_minute)
                n_ld = c3.number_input("リーグ時間(分)", 1, 30, st.session_state.league_duration)
                n_iv = c1.number_input("インターバル(分)", 0, 60, st.session_state.interval_duration)
                n_td = c2.number_input("トーナメント時間(分)", 1, 30, st.session_state.tourn_duration)
                if st.button("保存", key="sv_tm"):
                    st.session_state.start_time_hour = nh; st.session_state.start_time_minute = nm
                    st.session_state.league_duration = n_ld; st.session_state.interval_duration = n_iv
                    st.session_state.tourn_duration = n_td
                    save_data_to_json(); st.session_state.edit_mode_settings = False; st.rerun()
            
            st.markdown("---")
            
            # 4. チーム名
            st.markdown("##### チーム名設定")
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

            # 5. データの完全初期化
            st.markdown("---")
            st.error("【危険】データの完全初期化")
            st.caption("全ての試合結果と設定を削除し、初期状態に戻します。元に戻すことはできません。")
            confirm_pass = st.text_input("実行するにはリセット用パスワードを入力", type="password", key="reset_pass")
            if st.button("初期化を実行する", type="primary"):
                if confirm_pass == RESET_PASS:
                    if os.path.exists(DATA_FILE):
                        os.remove(DATA_FILE)
                    st.session_state.clear()
                    st.query_params.clear()
                    st.rerun()
                else:
                    st.error("パスワードが違います")

        # ログアウトボタン（管理者用）
        if st.button("ログアウト", key="admin_logout"):
            st.session_state.auth_status = None
            st.query_params.clear()
            st.rerun()
            
    else:
        # 閲覧者用のログアウトボタン（画面右上あたりに配置したいが、シンプルにタイトル下に配置）
        if st.button("ログアウト", key="viewer_logout"):
            st.session_state.auth_status = None
            st.query_params.clear()
            st.rerun()

    # === メインコンテンツ ===
    st.title(f"⚽ {st.session_state.app_title}")
    
    # タブの表示
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
                                    # --- 修正前 ---
# st.session_state.results[match_key] = {'s1': v1, 's2': v2}
# save_data_to_json() 
# st.session_state.editing_match_id = None; st.rerun()

# --- 修正後 ---
save_specific_match(match_key, {'s1': v1, 's2': v2}, is_tournament=False)
st.session_state.editing_match_id = None
st.rerun()
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
