import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mplsoccer import Pitch
import base64
import io
import pandas as pd
import numpy as np
import re
from flask import Flask, request, jsonify, render_template, send_file
import analysis  # analysis.py 파일이 같은 폴더에 있어야 합니다.

app = Flask(__name__, static_url_path='/static')

# --- [1. 기존 상수 및 설정 (태깅 시스템용)] ---
ACTION_CODES = { 'ddd': 'Goal', 'dd': 'Shot On Target', 'd': 'Shot', 'db': 'Blocked Shot', 'zz': 'Assist', 'z': 'Key Pass', 'cc': 'Cross', 'c': 'Cross', 'ss': 'Pass', 's': 'Pass', 'ee': 'Breakthrough', 'rr': 'Dribble', 'gp': 'Gain', 'm': 'Miss', 'aa': 'Tackle', 'q': 'Intercept', 'qq': 'Acquisition', 'w': 'Clear', 'ww': 'Cutout', 'qw': 'Block', 'v': 'Catching', 'vv': 'Punching', 'bb': 'Duel', 'b': 'Duel', 'f': 'Foul', 'ff': 'Be Fouled', 'o': 'Offside' }
TAG_CODES = { 'k': 'Key', 'a': 'Assist', 'h': 'Header', 'r': 'Aerial', 'w': 'Suffered', 'n': 'In-box', 'u': 'Out-box', 'p': 'Progressive', 'c': 'Counter Attack', 'sw': 'Switch', 'wf': 'Weak Foot', 'ft': 'First Time' }
TWO_DOT_ACTION_CODES = {'s', 'c', 'r', 'e'}

def parse_logs_to_dataframe(logs, match_id, teamid_h, teamid_a):
    parsed_logs = []
    for log in logs:
        log_dict = {}
        parts = log.split(' | ')
        # (기존 파싱 로직 유지)
        if len(parts) < 6: continue
        log_dict['Half'] = parts[0]; log_dict['Team'] = parts[1]; log_dict['Direction'] = parts[2]; log_dict['Time'] = parts[3]
        pos_match = re.search(r'Pos\((.+?), (.+?)\)', parts[4])
        if pos_match: log_dict['StartX'], log_dict['StartY'] = pos_match.groups()
        action_part = parts[5]
        action_match = re.match(r'(\d+) (.+?)(?: to (\d+))?$', action_part)
        if action_match:
            log_dict['Player'], log_dict['Action'], log_dict['Receiver'] = action_match.groups()
            log_dict['Receiver'] = log_dict['Receiver'] if log_dict['Receiver'] else ''
        log_dict['EndX'], log_dict['EndY'], log_dict['Tags'] = '', '', ''
        for part in parts[6:]:
            if 'Pos' in part:
                end_pos_match = re.search(r'Pos\((.+?), (.+?)\)', part)
                if end_pos_match: log_dict['EndX'], log_dict['EndY'] = end_pos_match.groups()
            elif 'Tags' in part: log_dict['Tags'] = part.replace('Tags: ', '')
        parsed_logs.append(log_dict)
    
    if not parsed_logs: return pd.DataFrame()

    columns = ["No", "MatchID", "TeamID", "Half", "Team", "Direction", "Time", "Player", "Receiver", "Action", "StartX", "StartY", "EndX", "EndY", "Tags"]
    df = pd.DataFrame(parsed_logs)
    # 컬럼 채우기 (No, MatchID 등)
    df['No'] = range(1, len(df) + 1)
    df['MatchID'] = match_id
    df['TeamID'] = df['Team'].apply(lambda x: teamid_h if str(x).strip().lower() == 'home' else teamid_a)
    return df.reindex(columns=columns)

# --- [2. 시각화 헬퍼 함수 (새로 추가된 기능)] ---
def fig_to_base64(fig):
    img = io.BytesIO()
    fig.savefig(img, format='png', bbox_inches='tight', pad_inches=0.1)
    img.seek(0)
    return base64.b64encode(img.getvalue()).decode('utf-8')

def draw_pass_map_flask(df, p_id):
    pitch = Pitch(pitch_type='custom', pitch_length=105, pitch_width=68, pitch_color='grass', line_color='white', stripe=True)
    fig, ax = pitch.draw(figsize=(10, 8))
    
    cols = ['StartX', 'StartY', 'EndX', 'EndY']
    for c in cols:
        if c in df.columns: df[c] = pd.to_numeric(df[c], errors='coerce')
    
    plot_df = df[(df['Player'].astype(str) == str(p_id)) & (df['Action'].str.contains('Pass', case=False, na=False))].dropna(subset=cols)
    
    if plot_df.empty:
        ax.text(52.5, 34, "No Pass Data", ha='center', va='center', fontsize=20, color='white')
    else:
        for _, row in plot_df.iterrows():
            color = '#0dff00' if 'Success' in str(row.get('Tags', '')) else 'red'
            pitch.arrows(row['StartX'], row['StartY'], row['EndX'], row['EndY'], color=color, ax=ax, width=2, zorder=2)
    
    ax.set_title(f"Player {p_id} | Pass Map", fontsize=20, fontweight='bold', pad=15)
    base64_img = fig_to_base64(fig)
    plt.close(fig)
    return base64_img

def draw_heatmap_flask(df, p_id):
    pitch = Pitch(pitch_type='custom', pitch_length=105, pitch_width=68, pitch_color='grass', line_color='white')
    fig, ax = pitch.draw(figsize=(10, 8))
    
    if 'StartX' in df.columns and 'StartY' in df.columns:
        df['StartX'] = pd.to_numeric(df['StartX'], errors='coerce')
        df['StartY'] = pd.to_numeric(df['StartY'], errors='coerce')
        plot_df = df[df['Player'].astype(str) == str(p_id)].dropna(subset=['StartX', 'StartY'])
        
        if not plot_df.empty:
            pitch.kdeplot(x=plot_df['StartX'], y=plot_df['StartY'], ax=ax, fill=True, levels=100, thresh=0.05, cmap='hot', alpha=0.6)
        else:
            ax.text(52.5, 34, "No Data", ha='center', va='center', fontsize=20, color='black')
            
    ax.set_title(f"Player {p_id} | Heatmap", fontsize=20, fontweight='bold', pad=15)
    base64_img = fig_to_base64(fig)
    plt.close(fig)
    return base64_img

# --- [3. 라우트 정의] ---

@app.route('/')
def index():
    return render_template('index.html')

# [기존 기능 복구] 태깅 로그 생성
@app.route('/generate_log', methods=['POST'])
def generate_log():
    data = request.get_json()
    stat_input = data.get('stat_input', '').lower()
    dots = data.get('dots', [])
    half, team, direction, timeline = data.get('half'), data.get('team'), data.get('direction'), data.get('timeline')

    try:
        parts = stat_input.split('.', 1)
        base_action_part = parts[0]
        tag_codes = parts[1].split('.') if len(parts) > 1 else []

        match = re.match(r"(\d+)([a-z]+)(\d*)", base_action_part)
        if not match: raise ValueError("형식 오류")

        player_from, action_code_raw, player_to = match.groups()
        player_to = player_to if player_to else ''
        
        base_action_code = action_code_raw[0]
        action_name = ACTION_CODES.get(action_code_raw) or ACTION_CODES.get(base_action_code)
        if not action_name: raise ValueError("알 수 없는 코드")

        tags_list = [TAG_CODES[tc] for tc in tag_codes if tc in TAG_CODES]
        
        # 태그 자동 추가 로직 (성공/실패 등)
        if action_code_raw not in ['t', 'm', 'q', 'p', 'l', 'qq', 'bl', 'o', 'd', 'db']:
             if len(action_code_raw) > 1 and action_code_raw[0] == action_code_raw[1]: tags_list.append('Success')
             else: tags_list.append('Fail')
        elif action_code_raw in ['dd', 'ddd']: tags_list.append('Success')
        elif action_code_raw in ['d', 'db']: tags_list.append('Fail')

        requires_two_dots = base_action_code in TWO_DOT_ACTION_CODES or player_to
        if requires_two_dots:
            if len(dots) < 2: raise ValueError("좌표 부족")
            start_pos, end_pos = dots[-2], dots[-1]
            start_x, start_y = float(start_pos['meter_x']), float(start_pos['meter_y'])
            end_x, end_y = float(end_pos['meter_x']), float(end_pos['meter_y'])
            
            # Progressive 로직 (간소화하여 호출)
            is_left = direction == 'left'
            sx_adj = 105 - start_x if is_left else start_x
            ex_adj = 105 - end_x if is_left else end_x
            if analysis.is_progressive_pass(sx_adj, ex_adj): 
                if 'Progressive' not in tags_list: tags_list.append('Progressive')

            action_str = f"{player_from} {action_name}"
            if player_to: action_str += f" to {player_to}"
            log_text = f"{half} | {team} | {direction} | {timeline} | Pos({start_x}, {start_y}) | {action_str} | Pos({end_x}, {end_y})"
        else:
            start_pos = dots[-1]
            start_x, start_y = float(start_pos['meter_x']), float(start_pos['meter_y'])
            log_text = f"{half} | {team} | {direction} | {timeline} | Pos({start_x}, {start_y}) | {player_from} {action_name}"

        # In-box/Out-box
        if analysis.is_in_penalty_area(start_x, start_y):
            if 'In-box' not in tags_list: tags_list.append('In-box')
        elif action_name in ['Goal', 'Shot On Target', 'Shot']:
             if 'Out-box' not in tags_list: tags_list.append('Out-box')

        if tags_list: log_text += f" | Tags: {', '.join(sorted(list(set(tags_list))))}"
        
        coord_str = f"Pos({start_x}, {start_y})"
        log_data = {"Time": timeline, "Team": team, "Player": player_from, "Action": action_name, "Coord": coord_str}
        return jsonify({"log_text": log_text, "log_data": log_data})

    except Exception as e:
        return jsonify({"error": str(e)}), 400

# [기존 기능 복구] 엑셀 내보내기 (export)
@app.route('/export', methods=['POST'])
def export_data():
    data = request.get_json()
    logs = data.get('logs', [])
    match_id = data.get('match_id', '')
    teamid_h = data.get('teamid_h', '')
    teamid_a = data.get('teamid_a', '')
    if not logs: return jsonify({"error": "로그 없음"}), 400

    try:
        df = parse_logs_to_dataframe(logs, match_id, teamid_h, teamid_a)
        
        # 분석 파이프라인
        df_with_seconds = analysis.convert_time_to_seconds(df.copy())
        df_tagged = analysis.auto_tag_key_pass_and_assist(df_with_seconds)
        df_analyzed = analysis.analyze_pass_data(df_tagged)
        df_analyzed_with_xg = analysis.add_xg_to_data(df_analyzed)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_analyzed_with_xg.to_excel(writer, sheet_name='Data', index=False)
            # (나머지 분석 요약 시트들도 필요시 여기에 추가)
            analysis.create_player_summary(df_analyzed_with_xg).to_excel(writer, sheet_name='Pass_Summary')

        output.seek(0)
        return send_file(output, as_attachment=True, download_name='live_analyzed.xlsx', mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# [신규 기능] 1. 선수 목록 가져오기
@app.route('/get_player_list', methods=['POST'])
def get_player_list():
    if 'file' not in request.files: return jsonify({"error": "파일 없음"}), 400
    file = request.files['file']
    try:
        df = pd.read_excel(file, sheet_name=0)
        if 'Player' not in df.columns: return jsonify({"error": "Player 컬럼 없음"}), 400
        players = sorted(df['Player'].dropna().astype(str).unique(), key=lambda x: float(x) if x.replace('.','',1).isdigit() else 999)
        return jsonify({"players": players})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# [신규 기능] 2. 분석 및 시각화 (엑셀 다운로드 제거됨)
@app.route('/upload_analyze_visualize', methods=['POST'])
def upload_analyze_visualize():
    if 'file' not in request.files: return jsonify({"error": "파일 없음"}), 400
    file = request.files['file']
    player_id = request.form.get('player_id', '')

    try:
        df = pd.read_excel(file, sheet_name=0)
        
        # 시각화 이미지만 생성
        pass_map = draw_pass_map_flask(df.copy(), player_id)
        heatmap = draw_heatmap_flask(df.copy(), player_id)
        
        # 엑셀 데이터는 반환하지 않음 (요청사항 반영)
        return jsonify({
            "pass_map": pass_map,
            "heatmap": heatmap
        })

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)