import pandas as pd
import numpy as np

# 모듈별 기능 분리
from stats_utils import FIELD_W, FIELD_H, convert_time_to_seconds, is_in_final_third, is_in_penalty_area, is_progressive_pass
from summaries import create_player_summary, create_shooter_summary, create_cross_summary, create_advanced_summary
from scoring import calculate_passing_score, calculate_shooting_score, calculate_cross_score, calculate_dribbling_score, calculate_defending_score, calculate_advanced_scores

def analyze_pass_data(df):
    """
    경기 이벤트 데이터프레임을 분석하여 보정 좌표, 패스 거리, 패스 방향을 추가합니다.
    """
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


def add_xg_to_data(df):
    """
    새로운 xG 공식을 적용하여 슈팅 데이터에 xG 값을 추가합니다.
    xG = 1 / (1 + exp(0.2 * dist - 2.0 * angle - 1.2 * is_pa + 1.5 * is_head + 0.8 * is_weak - 0.6))
    
    - dist: 골문까지의 거리
    - angle: 슈팅 각도 (골문과 이루는 각도)
    - is_pa: 페널티 박스 내 여부 (1: 안, 0: 밖) - Tags의 'In-box'로 판단
    - is_head: 헤딩 여부 (1: 헤딩, 0: 아님) - Tags의 'Header'로 판단
    - is_weak: 약발 여부 (1: 약발, 0: 아님) - Tags의 'Weak Foot'로 판단
    """
    shot_action_codes = {'ddd': 'Goal', 'dd': 'Shot On Target', 'd': 'Shot', 'db': 'Blocked Shot'}
    shot_actions = list(shot_action_codes.values())
    df_shots = df[df['Action'].isin(shot_actions)].copy()
    if df_shots.empty:
        df['xG'] = np.nan
        return df

    # 골문 좌표 (오른쪽 골대 중앙)
    goal_x, goal_y = 105, 34
    goal_post_left = 30.34  # 골문 왼쪽 포스트 y좌표
    goal_post_right = 37.66  # 골문 오른쪽 포스트 y좌표
    
    # 거리 계산
    distance = np.sqrt((goal_x - df_shots['StartX_adj'])**2 + (goal_y - df_shots['StartY_adj'])**2)
    
    # 슈팅 각도 계산 (골문과 이루는 각도, 라디안 단위)
    # 슈팅 위치에서 양쪽 골포스트까지의 벡터를 이용해 각도 계산
    dx_left = goal_x - df_shots['StartX_adj']
    dy_left = goal_post_left - df_shots['StartY_adj']
    dx_right = goal_x - df_shots['StartX_adj']
    dy_right = goal_post_right - df_shots['StartY_adj']
    
    # 두 벡터 사이의 각도 계산
    angle_left = np.arctan2(dy_left, dx_left)
    angle_right = np.arctan2(dy_right, dx_right)
    angle = np.abs(angle_left - angle_right)  # 라디안 단위
    
    # Tags 컬럼에서 정보 추출
    df_shots['Tags'] = df_shots['Tags'].astype(str).fillna('')
    
    # is_pa: 페널티 박스 내 여부 (In-box = 1, Out-box = 0)
    is_pa = df_shots['Tags'].str.contains('In-box', case=False, na=False).astype(int)
    
    # is_head: 헤딩 여부 (Header = 1)
    is_head = df_shots['Tags'].str.contains('Header', case=False, na=False).astype(int)
    
    # is_weak: 약발 여부 (Weak Foot = 1)
    is_weak = df_shots['Tags'].str.contains('Weak Foot', case=False, na=False).astype(int)
    
    # xG 계산
    # xG = 1 / (1 + exp(0.2 * dist - 2.0 * angle - 1.2 * is_pa + 1.5 * is_head + 0.8 * is_weak - 0.6))
    exponent = 0.2 * distance - 2.0 * angle - 1.2 * is_pa + 1.5 * is_head + 0.8 * is_weak - 0.6
    xg_values = 1 / (1 + np.exp(exponent))
    
    df_shots['xG'] = xg_values
    
    df = pd.merge(df, df_shots[['No', 'xG']], on='No', how='left')
    return df


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

def perform_full_analysis(df):
    """
    전체 분석 파이프라인을 실행합니다.
    1. 시간 변환
    2. 키패스/어시스트 태깅
    3. 패스/공간 분석
    4. xG 계산
    """
    df_with_seconds = convert_time_to_seconds(df.copy())
    df_tagged = auto_tag_key_pass_and_assist(df_with_seconds)
    df_analyzed = analyze_pass_data(df_tagged)
    df_analyzed_with_xg = add_xg_to_data(df_analyzed)
    return df_analyzed_with_xg
