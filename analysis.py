import pandas as pd
import numpy as np


def convert_time_to_seconds(df):
    """
    'Time' 컬럼(MM:SS 또는 HH:MM:SS 형식)을 초 단위 'Time(s)' 컬럼으로 변환합니다.
    """
    def time_to_seconds(time_str):
        try:
            parts = str(time_str).split(':')
            if len(parts) == 2:
                m, s = map(int, parts)
                return m * 60 + s
            elif len(parts) == 3:
                h, m, s = map(int, parts)
                return h * 3600 + m * 60 + s
        except (ValueError, TypeError):
            return 0  # 변환 실패 시 0으로 처리
        return 0

    if 'Time' in df.columns:
        df['Time(s)'] = df['Time'].apply(time_to_seconds)
    return df


def analyze_pass_data(df):
    """
    경기 이벤트 데이터프레임을 분석하여 보정 좌표, 패스 거리, 패스 방향을 추가합니다.
    """
    # --- 0. 사전 준비 ---
    FIELD_W = 105
    FIELD_H = 68
    coord_cols = ['StartX', 'StartY', 'EndX', 'EndY']
    for col in coord_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    if not all(col in df.columns for col in coord_cols + ['Direction']):
        return df

    # --- 1. 보정 좌표 산출 ---
    is_left_direction = df['Direction'].str.lower() == 'left'
    df['StartX_adj'] = np.where(is_left_direction, FIELD_W - df['StartX'], df['StartX'])
    df['StartY_adj'] = np.where(is_left_direction, FIELD_H - df['StartY'], df['StartY'])
    df['EndX_adj'] = np.where(is_left_direction, FIELD_W - df['EndX'], df['EndX'])
    df['EndY_adj'] = np.where(is_left_direction, FIELD_H - df['EndY'], df['EndY'])

    # --- 2. 패스 거리 분류 ---
    distance = np.sqrt(
        (df['EndX_adj'] - df['StartX_adj']) ** 2 + (df['EndY_adj'] - df['StartY_adj']) ** 2
    )
    df['Distance'] = distance
    conditions_dist = [distance < 20, (distance >= 20) & (distance < 40), distance >= 40]
    choices_dist = ['short', 'middle', 'long']
    df['Pass_Distance'] = np.select(conditions_dist, choices_dist, default=None)

    # --- 3. 패스 방향 분류 ---
    dx = df['EndX_adj'] - df['StartX_adj']
    dy = df['EndY_adj'] - df['StartY_adj']
    angle = np.degrees(np.arctan2(dy, dx))
    df['Angle'] = (angle + 360) % 360
    conditions_dir = [
        (df['Angle'] >= 315) | (df['Angle'] < 45),
        (df['Angle'] >= 45) & (df['Angle'] < 135),
        (df['Angle'] >= 135) & (df['Angle'] < 225),
        (df['Angle'] >= 225) & (df['Angle'] < 315)
    ]
    choices_dir = ['forward', 'left', 'backward', 'right']
    df['Pass_Direction'] = np.select(conditions_dir, choices_dir, default=None)

    return df

# --- 공간 분석 헬퍼 함수 ---
def is_in_final_third(x):
    return x >= 70

def is_in_penalty_area(x, y):
    return (x > 88.5) & (y > 13.84) & (y < 54.16)

def is_progressive_pass(start_x, end_x):
    return end_x - start_x >= 10

# --- 요약(Summary) 함수 업데이트 ---

def create_player_summary(df_analyzed):
    all_players = df_analyzed['Player'].unique()
    
    ACTION_CODES = {'ss': 'Pass', 's': 'Pass', 'cc': 'Cross', 'c': 'Cross'}
    pass_actions = list(set(ACTION_CODES.values()))
    
    if 'Tags' not in df_analyzed.columns: df_analyzed['Tags'] = ''
    df_pass = df_analyzed[df_analyzed['Action'].isin(pass_actions)].copy()
    if df_pass.empty: return pd.DataFrame(index=all_players).fillna(0)

    summary = df_pass.groupby('Player').agg(
        Total_Pass=('Action', 'count'),
        Success_Pass=('Tags', lambda x: x.str.contains('Success').sum()),
        Key_Pass=('Tags', lambda x: x.str.contains('Key').sum()),
        Assist=('Tags', lambda x: x.str.contains('Assist').sum())
    )
    summary = summary.reindex(all_players).fillna(0)
    summary['Fail_Pass'] = summary['Total_Pass'] - summary['Success_Pass']
    summary['Pass_Success_Rate'] = (summary['Success_Pass'] / summary['Total_Pass'] * 100).fillna(0).round(2)

    pivot_direction = pd.pivot_table(df_pass, values='Action', index='Player', columns='Pass_Direction', aggfunc='count').reindex(all_players).fillna(0)
    pivot_distance = pd.pivot_table(df_pass, values='Action', index='Player', columns='Pass_Distance', aggfunc='count').reindex(all_players).fillna(0)
    summary = summary.join(pivot_direction, how='left').join(pivot_distance, how='left').fillna(0)

    df_pass_success = df_pass[df_pass['Tags'].str.contains('Success')]
    
    summary['Progressive_Pass_Success'] = df_pass_success[is_progressive_pass(df_pass_success['StartX_adj'], df_pass_success['EndX_adj'])].groupby('Player')['Action'].count().reindex(all_players).fillna(0)
    summary['Final_Third_Pass_Success'] = df_pass_success[is_in_final_third(df_pass_success['StartX_adj'])].groupby('Player')['Action'].count().reindex(all_players).fillna(0)
    summary['PA_Pass_Success'] = df_pass_success[is_in_penalty_area(df_pass_success['EndX_adj'], df_pass_success['EndY_adj'])].groupby('Player')['Action'].count().reindex(all_players).fillna(0)

    ALL_DIRECTIONS = ['forward', 'left', 'right', 'backward']
    ALL_DISTANCES = ['short', 'middle', 'long']
    for col in ALL_DIRECTIONS + ALL_DISTANCES:
        if col not in summary.columns: summary[col] = 0
    
    int_cols = ['Total_Pass', 'Success_Pass', 'Fail_Pass', 'Key_Pass', 'Assist'] + ALL_DIRECTIONS + ALL_DISTANCES
    for col in int_cols:
        if col in summary.columns: summary[col] = summary[col].astype(int)
        
    return summary.sort_values(by='Total_Pass', ascending=False)


def create_shooter_summary(df_with_xg):
    all_players = df_with_xg['Player'].unique()
    
    ACTION_CODES = {'ddd': 'Goal', 'dd': 'Shot On Target', 'd': 'Shot', 'db': 'Blocked Shot'}
    shot_actions = list(ACTION_CODES.values())
    
    df_shots = df_with_xg[df_with_xg['Action'].isin(shot_actions)].copy()
    if df_shots.empty: return pd.DataFrame(index=all_players).fillna(0)
    if 'Tags' not in df_shots.columns: df_shots['Tags'] = ''
    df_shots['Tags'] = df_shots['Tags'].fillna('')

    summary = df_shots.groupby('Player').agg(
        Total_Shots=('Action', 'count'),
        Shots_On_Target=('Action', lambda x: x.isin(['Shot On Target', 'Goal']).sum()),
        Goals=('Action', lambda x: (x == 'Goal').sum()),
        Total_xG=('xG', 'sum')
    ).reindex(all_players).fillna(0)

    df_goals = df_shots[df_shots['Action'] == 'Goal']
    summary['Headed_Goals'] = df_goals[df_goals['Tags'].str.contains('Header')].groupby('Player')['Action'].count().reindex(all_players).fillna(0)
    summary['Outbox_Goals'] = df_goals[df_goals['Tags'].str.contains('Out-box')].groupby('Player')['Action'].count().reindex(all_players).fillna(0)
    summary['Counter_Attack_Goals'] = df_goals[df_goals['Tags'].str.contains('Counter Attack')].groupby('Player')['Action'].count().reindex(all_players).fillna(0)
    
    return summary.sort_values(by='Goals', ascending=False)


def create_cross_summary(df_analyzed):
    all_players = df_analyzed['Player'].unique()
    if 'Tags' not in df_analyzed.columns: df_analyzed['Tags'] = ''
    df_cross = df_analyzed[df_analyzed['Action'] == 'Cross'].copy()
    if df_cross.empty: return pd.DataFrame(index=all_players).fillna(0)

    summary = df_cross.groupby('Player').agg(
        Total_Crosses=('Action', 'count'),
        Successful_Crosses=('Tags', lambda x: x.str.contains('Success').sum())
    ).reindex(all_players).fillna(0)
    summary['Cross_Accuracy'] = (summary['Successful_Crosses'] / summary['Total_Crosses'] * 100).fillna(0).round(2)
    
    df_cross_success = df_cross[df_cross['Tags'].str.contains('Success')]
    central_crosses = df_cross_success[is_in_penalty_area(df_cross_success['EndX_adj'], df_cross_success['EndY_adj']) & (df_cross_success['EndY_adj'] > 21.1) & (df_cross_success['EndY_adj'] < 46.9)]
    summary['Central_PA_Cross_Success'] = central_crosses.groupby('Player')['Action'].count().reindex(all_players).fillna(0)

    return summary

def create_advanced_summary(df_analyzed):
    all_players = df_analyzed['Player'].unique()
    summary = pd.DataFrame(index=all_players)
    if 'Tags' not in df_analyzed.columns: df_analyzed['Tags'] = ''
    df_analyzed['Tags'] = df_analyzed['Tags'].fillna('')

    df_pass_succ = df_analyzed[df_analyzed['Action'].isin(['Pass', 'Cross']) & df_analyzed['Tags'].str.contains('Success')]
    df_break_succ = df_analyzed[(df_analyzed['Action'] == 'Breakthrough') & df_analyzed['Tags'].str.contains('Success')]
    df_pass_fail = df_analyzed[df_analyzed['Action'].isin(['Pass', 'Cross']) & ~df_analyzed['Tags'].str.contains('Success')]
    df_miss = df_analyzed[df_analyzed['Action'] == 'Miss']
    
    summary['Pass_Success_Count'] = df_pass_succ.groupby('Player')['Action'].count()
    summary['Breakthrough_Success'] = df_break_succ.groupby('Player')['Action'].count()
    summary['Pass_Fail_Count'] = df_pass_fail.groupby('Player')['Action'].count()
    summary['Miss_Count'] = df_miss.groupby('Player')['Action'].count()

    df_final_third = df_analyzed[is_in_final_third(df_analyzed['StartX_adj'])]
    df_ft_pass_succ = df_final_third[df_final_third['Action'].isin(['Pass', 'Cross']) & df_final_third['Tags'].str.contains('Success')]
    df_ft_break_succ = df_final_third[(df_final_third['Action'] == 'Breakthrough') & df_final_third['Tags'].str.contains('Success')]
    df_ft_pass_fail = df_final_third[df_final_third['Action'].isin(['Pass', 'Cross']) & ~df_final_third['Tags'].str.contains('Success')]
    df_ft_miss = df_final_third[df_final_third['Action'] == 'Miss']
    df_ft_offside = df_final_third[df_final_third['Action'] == 'Offside']

    summary['FT_Pass_Success'] = df_ft_pass_succ.groupby('Player')['Action'].count()
    summary['FT_Breakthrough_Success'] = df_ft_break_succ.groupby('Player')['Action'].count()
    summary['FT_Pass_Fail'] = df_ft_pass_fail.groupby('Player')['Action'].count()
    summary['FT_Miss'] = df_ft_miss.groupby('Player')['Action'].count()
    summary['FT_Offside'] = df_ft_offside.groupby('Player')['Action'].count()

    df_tackle = df_analyzed[df_analyzed['Action'] == 'Tackle']
    df_duel_win = df_analyzed[(df_analyzed['Action'] == 'Duel') & df_analyzed['Tags'].str.contains('Success')]
    df_intercept = df_analyzed[df_analyzed['Action'] == 'Intercept']
    df_acquisition = df_analyzed[df_analyzed['Action'] == 'Acquisition']
    df_foul = df_analyzed[df_analyzed['Action'] == 'Foul']
    df_duel_lose = df_analyzed[(df_analyzed['Action'] == 'Duel') & ~df_analyzed['Tags'].str.contains('Success')]

    summary['Tackle_Count'] = df_tackle.groupby('Player')['Action'].count()
    summary['Duel_Win_Count'] = df_duel_win.groupby('Player')['Action'].count()
    summary['Intercept_Count'] = df_intercept.groupby('Player')['Action'].count()
    summary['Acquisition_Count'] = df_acquisition.groupby('Player')['Action'].count()
    summary['Foul_Count'] = df_foul.groupby('Player')['Action'].count()
    summary['Duel_Lose_Count'] = df_duel_lose.groupby('Player')['Action'].count()

    summary['Total_Tackles'] = df_tackle.groupby('Player')['Action'].count()
    summary['Successful_Tackles'] = df_tackle[df_tackle['Tags'].str.contains('Success')].groupby('Player')['Action'].count()
    df_tackle_success = df_tackle[df_tackle['Tags'].str.contains('Success')]
    summary['Final_Third_Tackle_Success'] = df_tackle_success[is_in_final_third(df_tackle_success['StartX_adj'])].groupby('Player')['Action'].count()
    df_tackle_fail_foul = df_analyzed[(df_analyzed['Action'] == 'Foul') & (df_analyzed['Tags'].str.contains('In-box'))]
    summary['PA_Foul_Tackles'] = df_tackle_fail_foul.groupby('Player')['Action'].count()

    df_clear = df_analyzed[df_analyzed['Action'] == 'Clear']
    df_cutout = df_analyzed[df_analyzed['Action'] == 'Cutout']
    df_block = df_analyzed[df_analyzed['Action'] == 'Block']
    summary['Clear_Count'] = df_clear.groupby('Player')['Action'].count()
    summary['Cutout_Count'] = df_cutout.groupby('Player')['Action'].count()
    summary['Block_Count'] = df_block.groupby('Player')['Action'].count()

    df_aerial = df_analyzed[(df_analyzed['Action'] == 'Duel') & (df_analyzed['Tags'].str.contains('Aerial'))].copy()
    summary['Total_Aerial_Duels'] = df_aerial.groupby('Player')['Action'].count()
    summary['Aerial_Duels_Won'] = df_aerial[df_aerial['Tags'].str.contains('Success')].groupby('Player')['Action'].count()

    shot_actions = ['Goal', 'Shot On Target', 'Shot', 'Blocked Shot']
    df_shots = df_analyzed[df_analyzed['Action'].isin(shot_actions)]
    df_offside = df_analyzed[df_analyzed['Action'] == 'Offside']
    
    summary['Received_Assist'] = df_shots[df_shots['Tags'].str.contains('Assist')].groupby('Player')['Action'].count()
    summary['Received_Key_Pass'] = df_shots[df_shots['Tags'].str.contains('Key Pass')].groupby('Player')['Action'].count()
    summary['SOT_Count'] = df_shots[df_shots['Action'].isin(['Goal', 'Shot On Target'])].groupby('Player')['Action'].count()
    summary['Goal_Count'] = df_shots[df_shots['Action'] == 'Goal'].groupby('Player')['Action'].count()
    summary['Offside_Count'] = df_offside.groupby('Player')['Action'].count()
    
    df_dribble = df_analyzed[df_analyzed['Action'] == 'Dribble']
    df_cross_succ = df_analyzed[(df_analyzed['Action'] == 'Cross') & df_analyzed['Tags'].str.contains('Success')]
    df_fouled = df_analyzed[df_analyzed['Action'] == 'Be Fouled']

    summary['Dribble_Attempt'] = df_dribble.groupby('Player')['Action'].count()
    summary['Cross_Success'] = df_cross_succ.groupby('Player')['Action'].count()
    summary['Be_Fouled'] = df_fouled.groupby('Player')['Action'].count()

    return summary.fillna(0)

# --- 점수(Score) 계산 함수 업데이트 ---

def calculate_passing_score(summary, advanced_summary):
    if summary.empty: return summary
    
    summary = summary.join(advanced_summary[['Pass_Fail_Count']], how='left').fillna(0)

    raw_score = (summary['Pass_Success_Rate'] * 0.8) + \
                (summary['Progressive_Pass_Success'] * 1.5) + \
                (summary['Key_Pass'] * 2.5) + \
                (summary['Assist'] * 5) + \
                (summary['PA_Pass_Success'] * 3) - \
                (summary['Pass_Fail_Count'] * 0.5)
    
    summary['Passing_Raw'] = raw_score
    
    mid_point = 50
    steepness = 0.08
    passing_scores = 100 / (1 + np.exp(-steepness * (summary['Passing_Raw'] - mid_point)))
    summary['Passing_Score'] = passing_scores.round(0).astype(int)
    return summary


def add_xg_to_data(df):
    shot_action_codes = {'ddd': 'Goal', 'dd': 'Shot On Target', 'd': 'Shot', 'db': 'Blocked Shot'}
    shot_actions = list(shot_action_codes.values())
    df_shots = df[df['Action'].isin(shot_actions)].copy()
    if df_shots.empty:
        df['xG'] = np.nan
        return df

    goal_x, goal_y = 105, 34
    distance = np.sqrt((goal_x - df_shots['StartX_adj'])**2 + (goal_y - df_shots['StartY_adj'])**2)
    
    xg_values = 1 / (1 + np.exp(0.14 * distance - 2.5))
    df_shots['xG'] = xg_values
    
    df = pd.merge(df, df_shots[['No', 'xG']], on='No', how='left')
    return df


def calculate_shooting_score(df_shooter_summary):
    summary = df_shooter_summary.copy()
    if summary.empty: return summary

    required_cols = ['Goals', 'Total_xG', 'Headed_Goals', 'Outbox_Goals']
    for col in required_cols:
        if col not in summary.columns: summary[col] = 0

    raw_score = ((summary['Goals'] - summary['Total_xG']) * 10) + \
                (summary['Total_xG'] * 15) + \
                (summary['Headed_Goals'] * 5) + \
                (summary['Outbox_Goals'] * 3)
    
    summary['Shooting_Raw'] = raw_score
    
    mid_point = 10
    steepness = 0.18
    shooting_scores = 100 / (1 + np.exp(-steepness * (summary['Raw_Shooting_Score'] - mid_point)))
    summary['Shooting_Score'] = shooting_scores.round(0).astype(int)
    return summary


def calculate_cross_score(df_cross_summary):
    summary = df_cross_summary.copy()
    if summary.empty: return summary

    required_cols = ['Cross_Accuracy', 'Successful_Crosses', 'Central_PA_Cross_Success']
    for col in required_cols:
        if col not in summary.columns: summary[col] = 0

    base_score = (summary['Cross_Accuracy'] * 0.7) + (np.log1p(summary['Successful_Crosses']) * 3)
    bonus_score = summary['Central_PA_Cross_Success'] * 2.5
    
    summary['Raw_Cross_Score'] = base_score + bonus_score
    
    mid_point = 42
    steepness = 0.1
    cross_scores = 100 / (1 + np.exp(-steepness * (summary['Raw_Cross_Score'] - mid_point)))
    summary['Cross_Score'] = cross_scores.round(0).astype(int)
    return summary


def calculate_dribbling_score(summary):
    if summary.empty: return summary

    failed_dribble = summary['Dribble_Attempt'] - summary['Breakthrough_Success']
    raw_score = (summary['Breakthrough_Success'] * 3) - \
                (failed_dribble + summary['Miss_Count']) * 1 + \
                (summary['Be_Fouled'] * 0.8)

    summary['Dribbling_Raw'] = raw_score
    
    mid_point = 5
    steepness = 0.2
    dribbling_scores = 100 / (1 + np.exp(-steepness * (summary['Dribbling_Raw'] - mid_point)))
    summary['Dribbling_Score'] = dribbling_scores.round(0).astype(int)
    return summary


def calculate_defending_score(summary):
    if summary.empty: return summary

    failed_tackles = summary['Total_Tackles'] - summary['Successful_Tackles']
    failed_aerials = summary['Total_Aerial_Duels'] - summary['Aerial_Duels_Won']

    raw_score = (summary['Successful_Tackles'] * 2) - (failed_tackles * 1) + \
                (summary['Intercept_Count'] * 1.5) + \
                (summary['Block_Count'] * 1.2) + \
                (summary['Clear_Count'] * 1) + \
                (summary['Aerial_Duels_Won'] * 1.5) - (failed_aerials * 0.5) + \
                (summary['Duel_Win_Count'] * 0.5)
    
    summary['Defending_Raw'] = raw_score
    
    mid_point = 15
    steepness = 0.15
    defending_scores = 100 / (1 + np.exp(-steepness * (summary['Defending_Raw'] - mid_point)))
    summary['Defending_Score'] = defending_scores.round(0).astype(int)
    return summary


def auto_tag_key_pass_and_assist(df):
    df_sorted = df.sort_values(by='No').reset_index(drop=True)
    
    df_sorted['Tags'] = df_sorted['Tags'].astype(str).fillna('')

    shot_action_codes = {'ddd': 'Goal', 'dd': 'Shot On Target', 'd': 'Shot', 'db': 'Blocked Shot'}
    shot_actions = list(shot_action_codes.values())
    pass_action_codes = {'ss': 'Pass', 's': 'Pass', 'cc': 'Cross', 'c': 'Cross'}
    pass_actions = list(set(pass_action_codes.values()))

    for i in range(1, len(df_sorted)):
        current_event = df_sorted.loc[i]
        prev_event = df_sorted.loc[i-1]

        if current_event['Action'] in shot_actions and \
           prev_event['Action'] in pass_actions and \
           'Success' in prev_event['Tags']:
            
            if prev_event['TeamID'] == current_event['TeamID'] and \
               prev_event['Player'] != current_event['Player']:
                
                if current_event['Action'] == 'Goal':
                    if 'Assist' not in prev_event['Tags']:
                        df_sorted.loc[i-1, 'Tags'] = (prev_event['Tags'] + ', Assist').lstrip(', ')
                
                else:
                    if 'Key Pass' not in prev_event['Tags'] and 'Assist' not in prev_event['Tags']:
                         df_sorted.loc[i-1, 'Tags'] = (prev_event['Tags'] + ', Key Pass').lstrip(', ')

    return df_sorted


def create_tableau_pass_data(df):
    FIELD_W = 105
    FIELD_H = 68
    coord_cols = ['StartX', 'StartY', 'EndX', 'EndY']
    for col in coord_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce')

    df_origin = df.copy()
    df_origin['table'] = 'origin'
    df_apply = df.copy()
    df_apply[['StartX', 'StartY', 'EndX', 'EndY']] = df_apply[['EndX', 'EndY', 'StartX', 'StartY']]
    df_apply['table'] = 'apply'

    combined_df = pd.concat([df_origin, df_apply], ignore_index=True)
    combined_df['Pont Size'] = np.where(combined_df['table'] == 'origin', 1, 5)

    is_left = combined_df['Direction'].str.lower() == 'left'
    combined_df['StartX_adj'] = np.where(is_left, FIELD_W - combined_df['StartX'], combined_df['StartX'])
    combined_df['StartY_adj'] = np.where(is_left, FIELD_H - combined_df['StartY'], combined_df['StartY'])
    combined_df['EndX_adj'] = np.where(is_left, FIELD_W - combined_df['EndX'], combined_df['EndX'])
    combined_df['EndY_adj'] = np.where(is_left, FIELD_H - combined_df['EndY'], combined_df['EndY'])

    return combined_df

def calculate_advanced_scores(summary, pass_summary):
    # FST (First Touch)
    fst_numerator = summary['Pass_Success_Count'] + summary['Breakthrough_Success']
    fst_denominator = fst_numerator + summary['Pass_Fail_Count'] + summary['Miss_Count']
    summary['FST_Raw'] = (fst_numerator / fst_denominator).fillna(0) * 100
    summary['FST_Score'] = 100 / (1 + np.exp(-0.15 * (summary['FST_Raw'] - 80)))

    # OFF (Off The Ball)
    summary['OFF_Raw'] = (summary['Received_Assist'] * 3) + (summary['Received_Key_Pass'] * 1.5) + \
                         summary['SOT_Count'] + summary['Goal_Count'] - (summary['Offside_Count'] * 2)
    summary['OFF_Score'] = 100 / (1 + np.exp(-0.25 * (summary['OFF_Raw'] - 6)))

    # DEC (Decision)
    dec_numerator = summary['FT_Pass_Success'] + summary['FT_Breakthrough_Success']
    dec_denominator = dec_numerator + summary['FT_Pass_Fail'] + summary['FT_Miss'] + summary['FT_Offside']
    summary['DEC_Raw'] = (dec_numerator / dec_denominator).fillna(0) * 100
    summary['DEC_Score'] = 100 / (1 + np.exp(-0.15 * (summary['DEC_Raw'] - 80)))
    
    score_cols = [col for col in summary.columns if '_Score' in col]
    summary[score_cols] = summary[score_cols].round(0).astype(int)
    
    return summary
