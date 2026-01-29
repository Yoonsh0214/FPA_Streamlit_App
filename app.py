import os
import io
import re
import pandas as pd
import numpy as np
from flask import Flask, request, send_file, render_template, jsonify
import analysis
import matplotlib
matplotlib.use('Agg') # Flask 서버 환경에서 GUI 백엔드 사용 방지
import matplotlib.pyplot as plt
from mplsoccer import Pitch
import base64

def fig_to_base64(fig):
    img = io.BytesIO()
    fig.savefig(img, format='png', bbox_inches='tight')
    img.seek(0)
    return base64.b64encode(img.getvalue()).decode('utf-8')

def draw_pass_map_flask(df, p_id):
    # Reference Image Style: Striped Grass
    pitch = Pitch(pitch_type='custom', pitch_length=105, pitch_width=68, 
                  pitch_color='grass', line_color='white', stripe=True)
    fig, ax = pitch.draw(figsize=(10, 7))
    
    # 데이터 타입 통일
    df['Player'] = df['Player'].astype(str).str.replace('.0', '', regex=False)
    p_id = str(p_id).replace('.0', '')

    plot_df = df[(df['Player'] == p_id) & (df['Action'].str.contains('Pass', case=False, na=False))]
    
    req_cols = ['StartX_adj', 'StartY_adj', 'EndX_adj', 'EndY_adj']
    if not all(col in df.columns for col in req_cols):
         return None

    plot_df = plot_df.dropna(subset=req_cols)
    
    # Colors from Reference: Blue (Success), Red (Fail)
    success_color = 'blue'
    fail_color = 'red'
    
    for _, row in plot_df.iterrows():
        tags = str(row['Tags']) if pd.notna(row['Tags']) else ''
        is_success = 'Success' in tags
        
        color = success_color if is_success else fail_color
        linestyle = '-' if is_success else '--' # Dashed for failure
        alpha = 0.8
        
        # 1. 꼬리 (원형) - Rounded Tail: Remove border as requested
        pitch.scatter(row['StartX_adj'], row['StartY_adj'], ax=ax, 
                      color=color, edgecolors='none', s=60, alpha=alpha, zorder=2)
                      
        # 2. 화살표 (Arrow)
        pitch.arrows(row['StartX_adj'], row['StartY_adj'], row['EndX_adj'], row['EndY_adj'], 
                     color=color, ax=ax, width=2, headwidth=3, headlength=3, 
                     linestyle=linestyle, alpha=alpha, zorder=1)
    
    # Remove Title and Legend as requested
    # ax.set_title(f"Player {p_id} | Pass Map", fontsize=20, fontweight='bold', pad=15)
    
    base64_img = fig_to_base64(fig)
    plt.close(fig)
    return base64_img

def draw_heatmap_flask(df, p_id):
    # Match Pass Map Style: Striped Grass
    pitch = Pitch(pitch_type='custom', pitch_length=105, pitch_width=68, 
                  pitch_color='grass', line_color='white', stripe=True)
    fig, ax = pitch.draw(figsize=(10, 7))
    
    # 데이터 타입 통일
    df['Player'] = df['Player'].astype(str).str.replace('.0', '', regex=False)
    p_id = str(p_id).replace('.0', '')

    if 'StartX_adj' in df.columns and 'StartY_adj' in df.columns:
        plot_df = df[df['Player'] == p_id].dropna(subset=['StartX_adj', 'StartY_adj'])
        
        if not plot_df.empty:
            # User Request: "Standard football heatmap colors"
            # YlOrRd (Yellow -> Orange -> Red) is the classic standard.
            pitch.kdeplot(x=plot_df['StartX_adj'], y=plot_df['StartY_adj'], ax=ax, 
                          fill=True, levels=500, thresh=0.01, cmap='YlOrRd', alpha=0.8)
            
            # Label grid just in case? No, user wants clean.
        else:
            ax.text(52.5, 34, "No Data", ha='center', va='center', fontsize=20, color='white')
            
    # Remove Title as requested
    # ax.set_title(f"Player {p_id} | Heatmap", fontsize=20, fontweight='bold', pad=15)
    
    base64_img = fig_to_base64(fig)
    plt.close(fig)
    return base64_img

app = Flask(__name__, static_url_path='/static')

# --- 상수 (기존 ui.py에서 가져옴) ---
ACTION_CODES = { 'ddd': 'Goal', 'dd': 'Shot On Target', 'd': 'Shot', 'db': 'Blocked Shot', 'zz': 'Assist', 'z': 'Key Pass', 'cc': 'Cross', 'c': 'Cross', 'ss': 'Pass', 's': 'Pass', 'ee': 'Breakthrough', 'rr': 'Dribble', 'gp': 'Gain', 'm': 'Miss', 'aa': 'Tackle', 'q': 'Intercept', 'qq': 'Acquisition', 'w': 'Clear', 'ww': 'Cutout', 'qw': 'Block', 'v': 'Catching', 'vv': 'Punching', 'bb': 'Duel', 'b': 'Duel', 'f': 'Foul', 'ff': 'Be Fouled', 'o': 'Offside', 't': 'Touch' }
TAG_CODES = { 'k': 'Key', 'a': 'Assist', 'h': 'Header', 'r': 'Aerial', 'w': 'Suffered', 'n': 'In-box', 'u': 'Out-box', 'p': 'Progressive', 'c': 'Counter Attack', 'sw': 'Switch', 'wf': 'Weak Foot', 'ft': 'First Time' }
TWO_DOT_ACTION_CODES = {'s', 'c', 'r', 'e'}

def parse_logs_to_dataframe(logs, match_id, teamid_h, teamid_a):
    parsed_logs = []
    for log in logs:
        log_dict = {}
        parts = log.split(' | ')
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
    for idx, log in enumerate(parsed_logs, start=1):
        log["No"] = idx; log["MatchID"] = match_id
        team_val = str(log.get("Team", "")).strip().lower()
        log["TeamID"] = teamid_h if team_val == "home" else teamid_a
    columns = ["No", "MatchID", "TeamID", "Half", "Team", "Direction", "Time", "Player", "Receiver", "Action", "StartX", "StartY", "EndX", "EndY", "Tags"]
    return pd.DataFrame(parsed_logs).reindex(columns=columns)

@app.route('/')
def index():
    return render_template('index.html')

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

        # [수정] 숫자만 입력된 경우 'Touch'로 간주
        if base_action_part.isdigit():
            player_from = base_action_part
            action_code_raw = 't'
            player_to = ''
        else:
            match = re.match(r"(\d+)([a-z]+)(\d*)", base_action_part)
            if not match: raise ValueError("기본 입력 형식 오류")

            player_from, action_code_raw, player_to = match.groups()
        player_to = player_to if player_to else ''
        
        base_action_code = action_code_raw[0]
        action_name = ACTION_CODES.get(action_code_raw) or ACTION_CODES.get(base_action_code)
        if not action_name: raise ValueError("알 수 없는 액션 코드")

        tags_list = [TAG_CODES[tc] for tc in tag_codes if tc in TAG_CODES]
        
        # Success/Fail 태그 자동 추가
        if action_code_raw not in ['t', 'm', 'q', 'p', 'l', 'qq', 'bl', 'o', 'd', 'db']:
             if len(action_code_raw) > 1 and action_code_raw[0] == action_code_raw[1]:
                 tags_list.append('Success')
             else:
                 tags_list.append('Fail')
        elif action_code_raw in ['dd', 'ddd']:
            tags_list.append('Success')
        elif action_code_raw in ['d', 'db']:
            tags_list.append('Fail')

        requires_two_dots = base_action_code in TWO_DOT_ACTION_CODES or player_to
        if requires_two_dots:
            if len(dots) < 2: raise ValueError("좌표 2개가 필요합니다.")
            start_pos, end_pos = dots[-2], dots[-1]
            start_x, start_y = float(start_pos['meter_x']), float(start_pos['meter_y'])
            end_x, end_y = float(end_pos['meter_x']), float(end_pos['meter_y'])
            
            # Progressive 태그
            is_left_direction = direction == 'left'
            start_x_adj = 105 - start_x if is_left_direction else start_x
            end_x_adj = 105 - end_x if is_left_direction else end_x
            if analysis.is_progressive_pass(start_x_adj, end_x_adj):
                if 'Progressive' not in tags_list: tags_list.append('Progressive')

            action_str = f"{player_from} {action_name}"
            if player_to: action_str += f" to {player_to}"
            log_text = f"{half} | {team} | {direction} | {timeline} | Pos({start_x}, {start_y}) | {action_str} | Pos({end_x}, {end_y})"
        else: # 좌표 1개
            start_pos = dots[-1]
            start_x, start_y = float(start_pos['meter_x']), float(start_pos['meter_y'])
            log_text = f"{half} | {team} | {direction} | {timeline} | Pos({start_x}, {start_y}) | {player_from} {action_name}"

        # In-box/Out-box 태그
        if analysis.is_in_penalty_area(start_x, start_y):
            if 'In-box' not in tags_list: tags_list.append('In-box')
        elif action_name in ['Goal', 'Shot On Target', 'Shot', 'Blocked Shot']:
             if 'Out-box' not in tags_list: tags_list.append('Out-box')

        if tags_list:
            log_text += f" | Tags: {', '.join(sorted(list(set(tags_list))))}"
        
        # UI 표 출력을 위한 구조화된 데이터 생성
        coord_str = f"Pos({start_x}, {start_y})"
        log_data = {
            "Time": timeline,
            "Team": team,
            "Player": player_from,
            "Action": action_name,
            "Receiver": player_to,
            "Coord": coord_str,
            "Tags": ', '.join(sorted(list(set(tags_list)))) if tags_list else ''
        }

        return jsonify({"log_text": log_text, "log_data": log_data})

    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/export', methods=['POST'])
def export_data():
    data = request.get_json()
    logs = data.get('logs', [])
    match_id = data.get('match_id', '')
    teamid_h = data.get('teamid_h', '')
    teamid_a = data.get('teamid_a', '')

    if not logs:
        return jsonify({"error": "No logs to process"}), 400

    try:
        df = parse_logs_to_dataframe(logs, match_id, teamid_h, teamid_a)
        
        # --- analysis.py의 통합 분석 파이프라인 실행 ---
        df_analyzed_with_xg = analysis.perform_full_analysis(df)

        # --- 메모리 내에서 엑셀 파일 생성 ---
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_analyzed_with_xg.to_excel(writer, sheet_name='Data', index=False)
            analysis.create_tableau_pass_data(df_analyzed_with_xg).to_excel(writer, sheet_name='Tableau_Pass', index=False)
            pass_summary = analysis.create_player_summary(df_analyzed_with_xg)
            shooter_summary = analysis.create_shooter_summary(df_analyzed_with_xg)
            cross_summary = analysis.create_cross_summary(df_analyzed_with_xg)
            advanced_summary = analysis.create_advanced_summary(df_analyzed_with_xg)
            pass_summary.to_excel(writer, sheet_name='Pass_Summary')
            shooter_summary.to_excel(writer, sheet_name='Shooting_Summary')
            cross_summary.to_excel(writer, sheet_name='Cross_Summary')
            advanced_summary.to_excel(writer, sheet_name='Advanced_Summary')
            final_stats_df = pd.DataFrame(index=df_analyzed_with_xg['Player'].unique())
            if not shooter_summary.empty: final_stats_df = final_stats_df.join(analysis.calculate_shooting_score(shooter_summary.copy())[['Shooting_Score']], how='left')
            if not cross_summary.empty: final_stats_df = final_stats_df.join(analysis.calculate_cross_score(cross_summary.copy())[['Cross_Score']], how='left')
            if not advanced_summary.empty:
                final_stats_df = final_stats_df.join(analysis.calculate_passing_score(pass_summary.copy(), advanced_summary.copy())[['Passing_Score']], how='left')
                final_stats_df = final_stats_df.join(analysis.calculate_dribbling_score(advanced_summary.copy())[['Dribbling_Score']], how='left')
                final_stats_df = final_stats_df.join(analysis.calculate_defending_score(advanced_summary.copy())[['Defending_Score']], how='left')
                remaining_advanced_scores = analysis.calculate_advanced_scores(advanced_summary.copy(), pass_summary.copy())
                score_cols_to_join = [col for col in remaining_advanced_scores.columns if '_Score' in col]
                if score_cols_to_join: final_stats_df = final_stats_df.join(remaining_advanced_scores[score_cols_to_join], how='left')
            if not final_stats_df.empty:
                final_stats_df = final_stats_df.fillna(0).astype(int)
                final_stats_df.index.name = 'Player'
                final_stats_df.to_excel(writer, sheet_name='Final_Stats')
        
        output.seek(0)
        
        return send_file(
            output,
            as_attachment=True,
            download_name='live_analyzed_data.xlsx',
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/upload_analyze', methods=['POST'])
def upload_and_analyze():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file and file.filename.endswith('.xlsx'):
        try:
            df = pd.read_excel(file, sheet_name='Data')
            
            # --- analysis.py의 통합 분석 파이프라인 실행 ---
            df_analyzed_with_xg = analysis.perform_full_analysis(df)

            # --- 메모리 내에서 엑셀 파일 생성 ---
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_analyzed_with_xg.to_excel(writer, sheet_name='Data', index=False)
                analysis.create_tableau_pass_data(df_analyzed_with_xg).to_excel(writer, sheet_name='Tableau_Pass', index=False)
                pass_summary = analysis.create_player_summary(df_analyzed_with_xg)
                shooter_summary = analysis.create_shooter_summary(df_analyzed_with_xg)
                cross_summary = analysis.create_cross_summary(df_analyzed_with_xg)
                advanced_summary = analysis.create_advanced_summary(df_analyzed_with_xg)
                pass_summary.to_excel(writer, sheet_name='Pass_Summary')
                shooter_summary.to_excel(writer, sheet_name='Shooting_Summary')
                cross_summary.to_excel(writer, sheet_name='Cross_Summary')
                advanced_summary.to_excel(writer, sheet_name='Advanced_Summary')
                final_stats_df = pd.DataFrame(index=df_analyzed_with_xg['Player'].unique())
                if not shooter_summary.empty: final_stats_df = final_stats_df.join(analysis.calculate_shooting_score(shooter_summary.copy())[['Shooting_Score']], how='left')
                if not cross_summary.empty: final_stats_df = final_stats_df.join(analysis.calculate_cross_score(cross_summary.copy())[['Cross_Score']], how='left')
                if not advanced_summary.empty:
                    final_stats_df = final_stats_df.join(analysis.calculate_passing_score(pass_summary.copy(), advanced_summary.copy())[['Passing_Score']], how='left')
                    final_stats_df = final_stats_df.join(analysis.calculate_dribbling_score(advanced_summary.copy())[['Dribbling_Score']], how='left')
                    final_stats_df = final_stats_df.join(analysis.calculate_defending_score(advanced_summary.copy())[['Defending_Score']], how='left')
                    remaining_advanced_scores = analysis.calculate_advanced_scores(advanced_summary.copy(), pass_summary.copy())
                    score_cols_to_join = [col for col in remaining_advanced_scores.columns if '_Score' in col]
                    if score_cols_to_join: final_stats_df = final_stats_df.join(remaining_advanced_scores[score_cols_to_join], how='left')
                if not final_stats_df.empty:
                    final_stats_df = final_stats_df.fillna(0).astype(int)
                    final_stats_df.index.name = 'Player'
                    final_stats_df.to_excel(writer, sheet_name='Final_Stats')
            
            output.seek(0)
            
            return send_file(
                output,
                as_attachment=True,
                download_name='uploaded_analyzed_data.xlsx',
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )

        except Exception as e:
            return jsonify({"error": str(e)}), 500
    
    return jsonify({"error": "Invalid file type"}), 400


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

# [신규 기능] 2. 분석 및 시각화
@app.route('/upload_analyze_visualize', methods=['POST'])
def upload_analyze_visualize():
    if 'file' not in request.files: return jsonify({"error": "파일 없음"}), 400
    file = request.files['file']
    player_id = request.form.get('player_id', '')

    try:
        df = pd.read_excel(file, sheet_name=0)
        
        # 분석 파이프라인 (필요시)
        required_cols = ['StartX_adj', 'StartY_adj', 'EndX_adj', 'EndY_adj']
        if not all(col in df.columns for col in required_cols):
             df = analysis.perform_full_analysis(df)
        
        # 시각화 이미지만 생성
        pass_map = draw_pass_map_flask(df.copy(), player_id)
        heatmap = draw_heatmap_flask(df.copy(), player_id)
        
        return jsonify({
            "pass_map": pass_map,
            "heatmap": heatmap
        })

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)
