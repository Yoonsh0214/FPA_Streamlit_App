import streamlit as st
import pandas as pd
import analysis
import io
import re
from PIL import Image
from streamlit_drawable_canvas import st_canvas

# --- 초기 설정 ---
st.set_page_config(page_title="FPA Live Analyzer", layout="wide")

# --- 세션 상태 초기화 ---
if 'logs' not in st.session_state:
    st.session_state.logs = []
if 'dots' not in st.session_state:
    st.session_state.dots = []

# --- 상수 및 헬퍼 함수 (기존 ui.py에서 가져옴) ---
FIELD_WIDTH = 105
FIELD_HEIGHT = 68
ACTION_CODES = {
    'ddd': 'Goal', 'dd': 'Shot On Target', 'd': 'Shot', 'db': 'Blocked Shot',
    'zz': 'Assist', 'z': 'Key Pass', 'cc': 'Cross', 'c': 'Cross',
    'ss': 'Pass', 's': 'Pass', 'ee': 'Breakthrough', 'rr': 'Dribble',
    'gp': 'Gain', 'm': 'Miss', 'aa': 'Tackle', 'q': 'Intercept',
    'qq': 'Acquisition', 'w': 'Clear', 'ww': 'Cutout', 'qw': 'Block',
    'v': 'Catching', 'vv': 'Punching', 'bb': 'Duel', 'b': 'Duel',
    'f': 'Foul', 'ff': 'Be Fouled', 'o': 'Offside'
}
TAG_CODES = {
    'k': 'Key', 'a': 'Assist', 'h': 'Header', 'r': 'Aerial',
    'w': 'Suffered', 'n': 'In-box', 'u': 'Out-box',
    'p': 'Progressive', 'c': 'Counter Attack', 'sw': 'Switch',
    'wf': 'Weak Foot', 'ft': 'First Time'
}
TWO_DOT_ACTION_CODES = {'s', 'c', 'r', 'e'}

def parse_logs_to_dataframe(logs, match_id, teamid_h, teamid_a):
    parsed_logs = []
    for log in logs:
        log_dict = {}
        parts = log.split(' | ')
        log_dict['Half'] = parts[0]
        log_dict['Team'] = parts[1]
        log_dict['Direction'] = parts[2]
        log_dict['Time'] = parts[3]
        pos_match = re.search(r'Pos\((.+?), (.+?)\)', parts[4])
        if pos_match:
            log_dict['StartX'] = pos_match.group(1)
            log_dict['StartY'] = pos_match.group(2)
        action_part = parts[5]
        action_match = re.match(r'(\d+) (.+?)(?: to (\d+))?$', action_part)
        if action_match:
            log_dict['Player'] = action_match.group(1)
            log_dict['Action'] = action_match.group(2)
            log_dict['Receiver'] = action_match.group(3) if action_match.group(3) else ''
        log_dict['EndX'], log_dict['EndY'], log_dict['Tags'] = '', '', ''
        for part in parts[6:]:
            if 'Pos' in part:
                end_pos_match = re.search(r'Pos\((.+?), (.+?)\)', part)
                if end_pos_match:
                    log_dict['EndX'] = end_pos_match.group(1)
                    log_dict['EndY'] = end_pos_match.group(2)
            elif 'Tags' in part:
                log_dict['Tags'] = part.replace('Tags: ', '')
        parsed_logs.append(log_dict)
    for idx, log in enumerate(parsed_logs, start=1):
        log["No"] = idx
        log["MatchID"] = match_id
        team_val = str(log.get("Team", "")).strip().lower()
        log["TeamID"] = teamid_h if team_val == "home" else teamid_a
    columns = ["No", "MatchID", "TeamID", "Half", "Team", "Direction", "Time", "Player", "Receiver", "Action", "StartX", "StartY", "EndX", "EndY", "Tags"]
    return pd.DataFrame(parsed_logs).reindex(columns=columns)

# --- UI 탭 구성 ---
tab1, tab2 = st.tabs(["⚽ 실시간 입력 (Live Input)", "📄 기존 파일 분석 (File Analysis)"])

# --- 탭 1: 실시간 입력 ---
with tab1:
    col1, col2 = st.columns([0.4, 0.6])

    with col1:
        st.header("입력 컨트롤")
        
        # 경기 정보
        with st.expander("경기 정보 입력", expanded=True):
            match_id = st.text_input("Match ID")
            teamid_h = st.text_input("Home Team ID")
            teamid_a = st.text_input("Away Team ID")
            half = st.radio("Half", ["1st", "2nd"], horizontal=True)
            team = st.radio("Team", ["home", "away"], horizontal=True)
            direction = st.radio("Direction", ["right", "left"], horizontal=True)

        # 시간 및 스탯 입력
        timeline = st.text_input("Timeline (MM:SS)", "00:00")
        stat_input = st.text_input("스탯 코드 입력 (예: 10ss8.k)")
        
        submit_button = st.button("스탯 기록")
        
        st.info(f"현재 클릭된 좌표: {st.session_state.dots}")

        # 로그 관리
        st.subheader("기록된 로그")
        log_display = st.text_area("Logs", "\n".join(st.session_state.logs), height=300)
        
        col1a, col1b = st.columns(2)
        with col1a:
            if st.button("마지막 로그 삭제"):
                if st.session_state.logs:
                    st.session_state.logs.pop()
                    st.rerun()
        with col1b:
            if st.button("모든 로그 삭제"):
                st.session_state.logs = []
                st.session_state.dots = []
                st.rerun()

        # 데이터 분석 및 다운로드
        st.subheader("분석 및 저장")
        if st.button("현재 로그 분석 및 Excel로 내보내기"):
            if not st.session_state.logs:
                st.warning("분석할 로그가 없습니다.")
            else:
                with st.spinner("데이터를 분석 중입니다..."):
                    df = parse_logs_to_dataframe(st.session_state.logs, match_id, teamid_h, teamid_a)
                    
                    # 분석 파이프라인
                    df_with_seconds = analysis.convert_time_to_seconds(df.copy())
                    df_tagged = analysis.auto_tag_key_pass_and_assist(df_with_seconds)
                    df_analyzed = analysis.analyze_pass_data(df_tagged)
                    df_analyzed_with_xg = analysis.add_xg_to_data(df_analyzed)

                    # 엑셀 파일 생성
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
                        if not shooter_summary.empty:
                            shooting_scores = analysis.calculate_shooting_score(shooter_summary.copy())
                            final_stats_df = final_stats_df.join(shooting_scores[['Shooting_Score']], how='left')
                        if not cross_summary.empty:
                            cross_scores = analysis.calculate_cross_score(cross_summary.copy())
                            final_stats_df = final_stats_df.join(cross_scores[['Cross_Score']], how='left')
                        if not advanced_summary.empty:
                            passing_scores = analysis.calculate_passing_score(pass_summary.copy(), advanced_summary.copy())
                            dribbling_scores = analysis.calculate_dribbling_score(advanced_summary.copy())
                            defending_scores = analysis.calculate_defending_score(advanced_summary.copy())
                            final_stats_df = final_stats_df.join(passing_scores[['Passing_Score']], how='left')
                            final_stats_df = final_stats_df.join(dribbling_scores[['Dribbling_Score']], how='left')
                            final_stats_df = final_stats_df.join(defending_scores[['Defending_Score']], how='left')
                            remaining_advanced_scores = analysis.calculate_advanced_scores(advanced_summary.copy(), pass_summary.copy())
                            score_cols_to_join = [col for col in remaining_advanced_scores.columns if '_Score' in col]
                            if score_cols_to_join:
                                final_stats_df = final_stats_df.join(remaining_advanced_scores[score_cols_to_join], how='left')
                        
                        if not final_stats_df.empty:
                            final_stats_df = final_stats_df.fillna(0).astype(int)
                            final_stats_df.index.name = 'Player'
                            final_stats_df.to_excel(writer, sheet_name='Final_Stats')
                    
                    st.session_state.final_excel = output.getvalue()

                if 'final_excel' in st.session_state:
                    st.download_button(
                        label="📥 분석 결과 다운로드 (.xlsx)",
                        data=st.session_state.final_excel,
                        file_name="live_analyzed_data.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )


    with col2:
        st.header("축구장")
        try:
            bg_image = Image.open("static/assets/football_field.png")
            canvas_result = st_canvas(
                fill_color="rgba(255, 165, 0, 0.3)",
                stroke_width=2,
                stroke_color="#FF7740",
                background_image=bg_image,
                update_streamlit=True,
                height=450,
                width=700,
                drawing_mode="point",
                key="canvas",
            )
            if canvas_result.json_data is not None and canvas_result.json_data["objects"]:
                new_dot = canvas_result.json_data["objects"][-1]
                x, y = new_dot["left"], new_dot["top"]
                
                # Prevent duplicate coordinates
                if (x, y) not in [(d['x'], d['y']) for d in st.session_state.dots]:
                    meter_x = round(x * FIELD_WIDTH / 700, 2)
                    meter_y = round((450 - y) * FIELD_HEIGHT / 450, 2)
                    st.session_state.dots.append({'x': x, 'y': y, 'meter_x': meter_x, 'meter_y': meter_y})
                    st.rerun()

        except FileNotFoundError:
            st.error("축구장 이미지를 찾을 수 없습니다. 'static/assets/football_field.png' 경로에 파일이 있는지 확인하세요.")

    # 스탯 기록 버튼 로직
    if submit_button:
        if not stat_input:
            st.warning("스탯 코드를 입력해주세요.")
        elif not st.session_state.dots:
            st.warning("좌표를 먼저 클릭해주세요.")
        else:
            # 스탯 생성 로직 (ui.py의 submit_stat 함수 간소화 버전)
            try:
                parts = stat_input.lower().split('.', 1)
                base_action_part = parts[0]
                tag_codes = parts[1].split('.') if len(parts) > 1 else []
                match = re.match(r"(\d+)([a-z]+)(\d*)", base_action_part)
                if not match: raise ValueError("기본 입력 형식 오류")

                player_from, action_code_raw, player_to = match.groups()
                base_action_code = action_code_raw[0]
                
                action_name = ACTION_CODES.get(action_code_raw) or ACTION_CODES.get(base_action_code)
                if not action_name: raise ValueError("알 수 없는 액션 코드")

                tags_list = [TAG_CODES[tc] for tc in tag_codes if tc in TAG_CODES]

                requires_two_dots = base_action_code in TWO_DOT_ACTION_CODES or player_to
                
                if requires_two_dots:
                    if len(st.session_state.dots) < 2: raise ValueError("좌표 2개가 필요합니다.")
                    start_pos = st.session_state.dots[-2]
                    end_pos = st.session_state.dots[-1]
                    action_str = f"{player_from} {action_name}"
                    if player_to: action_str += f" to {player_to}"
                    log_text = f"{half} | {team} | {direction} | {timeline} | Pos({start_pos['meter_x']}, {start_pos['meter_y']}) | {action_str} | Pos({end_pos['meter_x']}, {end_pos['meter_y']})"
                else:
                    start_pos = st.session_state.dots[-1]
                    log_text = f"{half} | {team} | {direction} | {timeline} | Pos({start_pos['meter_x']}, {start_pos['meter_y']}) | {player_from} {action_name}"

                if tags_list: log_text += f" | Tags: {', '.join(tags_list)}"
                
                st.session_state.logs.append(log_text)
                st.session_state.dots = []
                st.rerun()

            except Exception as e:
                st.error(f"스탯 생성 오류: {e}")


# --- 탭 2: 기존 파일 분석 ---
with tab2:
    st.header("📄 기존 파일 분석")
    st.write("이전에 작업했던 Excel 파일을 업로드하여 한번에 분석할 수 있습니다.")
    
    uploaded_file_analysis = st.file_uploader("분석할 Excel 파일(.xlsx)을 업로드하세요", type=['xlsx'], key="file_uploader_analysis")

    if uploaded_file_analysis is not None:
        try:
            with st.spinner('데이터를 분석하는 중입니다...'):
                df = pd.read_excel(uploaded_file_analysis, sheet_name='Data')
                
                df_with_seconds = analysis.convert_time_to_seconds(df.copy())
                df_tagged = analysis.auto_tag_key_pass_and_assist(df_with_seconds)
                df_analyzed = analysis.analyze_pass_data(df_tagged)
                df_analyzed_with_xg = analysis.add_xg_to_data(df_analyzed)

                output_analysis = io.BytesIO()
                with pd.ExcelWriter(output_analysis, engine='openpyxl') as writer:
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
                    if not shooter_summary.empty:
                        shooting_scores = analysis.calculate_shooting_score(shooter_summary.copy())
                        final_stats_df = final_stats_df.join(shooting_scores[['Shooting_Score']], how='left')
                    if not cross_summary.empty:
                        cross_scores = analysis.calculate_cross_score(cross_summary.copy())
                        final_stats_df = final_stats_df.join(cross_scores[['Cross_Score']], how='left')
                    if not advanced_summary.empty:
                        passing_scores = analysis.calculate_passing_score(pass_summary.copy(), advanced_summary.copy())
                        dribbling_scores = analysis.calculate_dribbling_score(advanced_summary.copy())
                        defending_scores = analysis.calculate_defending_score(advanced_summary.copy())
                        final_stats_df = final_stats_df.join(passing_scores[['Passing_Score']], how='left')
                        final_stats_df = final_stats_df.join(dribbling_scores[['Dribbling_Score']], how='left')
                        final_stats_df = final_stats_df.join(defending_scores[['Defending_Score']], how='left')
                        remaining_advanced_scores = analysis.calculate_advanced_scores(advanced_summary.copy(), pass_summary.copy())
                        score_cols_to_join = [col for col in remaining_advanced_scores.columns if '_Score' in col]
                        if score_cols_to_join:
                            final_stats_df = final_stats_df.join(remaining_advanced_scores[score_cols_to_join], how='left')
                    
                    if not final_stats_df.empty:
                        final_stats_df = final_stats_df.fillna(0).astype(int)
                        final_stats_df.index.name = 'Player'
                        final_stats_df.to_excel(writer, sheet_name='Final_Stats')
            
            st.success('✅ 분석이 완료되었습니다!')
            st.download_button(
                label="📥 분석 결과 다운로드 (.xlsx)",
                data=output_analysis,
                file_name="analyzed_data.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        except Exception as e:
            st.error(f"파일 분석 중 오류 발생: {e}")
