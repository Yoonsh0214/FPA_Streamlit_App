import pandas as pd
import numpy as np
from stats_utils import is_in_final_third, is_in_penalty_area, is_progressive_pass

def create_player_summary(df_analyzed):
    all_players = df_analyzed['Player'].unique()
    
    # 필수 컬럼 정의 (0으로 초기화할 대상)
    ACTION_CODES = {'ss': 'Pass', 's': 'Pass', 'cc': 'Cross', 'c': 'Cross'}
    pass_actions = list(set(ACTION_CODES.values()))
    ALL_DIRECTIONS = ['forward', 'left', 'right', 'backward']
    ALL_DISTANCES = ['short', 'middle', 'long']
    
    required_cols = [
        'Total_Pass', 'Success_Pass', 'Key_Pass', 'Assist', 'Fail_Pass', 'Pass_Success_Rate',
        'Progressive_Pass_Success', 'Final_Third_Pass_Success', 'PA_Pass_Success',
        'Own_Half_Pass_Score', 'Own_Half_Pass_Fail'
    ] + ALL_DIRECTIONS + ALL_DISTANCES

    # 기본 프레임 생성
    summary = pd.DataFrame(index=all_players)
    for col in required_cols:
        summary[col] = 0.0 if 'Rate' in col else 0

    if 'Tags' not in df_analyzed.columns: df_analyzed['Tags'] = ''
    df_pass = df_analyzed[df_analyzed['Action'].isin(pass_actions)].copy()
    
    if df_pass.empty:
        return summary

    # 실제 데이터 집계
    agg_summary = df_pass.groupby('Player').agg(
        Total_Pass=('Action', 'count'),
        Success_Pass=('Tags', lambda x: x.str.contains('Success').sum()),
        Key_Pass=('Tags', lambda x: x.str.contains('Key').sum()),
        Assist=('Tags', lambda x: x.str.contains('Assist').sum())
    )
    summary.update(agg_summary)
    
    summary['Fail_Pass'] = summary['Total_Pass'] - summary['Success_Pass']
    # 0으로 나누기 방지
    summary['Pass_Success_Rate'] = np.where(
        summary['Total_Pass'] > 0,
        (summary['Success_Pass'] / summary['Total_Pass'] * 100),
        0
    )
    summary['Pass_Success_Rate'] = summary['Pass_Success_Rate'].round(2)

    pivot_direction = pd.pivot_table(df_pass, values='Action', index='Player', columns='Pass_Direction', aggfunc='count').fillna(0)
    pivot_distance = pd.pivot_table(df_pass, values='Action', index='Player', columns='Pass_Distance', aggfunc='count').fillna(0)
    
    summary.update(pivot_direction)
    summary.update(pivot_distance)

    df_pass_success = df_pass[df_pass['Tags'].str.contains('Success')]
    if not df_pass_success.empty:
        summary['Progressive_Pass_Success'] = df_pass_success[is_progressive_pass(df_pass_success['StartX_adj'], df_pass_success['EndX_adj'])].groupby('Player')['Action'].count().reindex(all_players).fillna(0)
        summary['Final_Third_Pass_Success'] = df_pass_success[is_in_final_third(df_pass_success['StartX_adj'])].groupby('Player')['Action'].count().reindex(all_players).fillna(0)
        summary['PA_Pass_Success'] = df_pass_success[is_in_penalty_area(df_pass_success['EndX_adj'], df_pass_success['EndY_adj'])].groupby('Player')['Action'].count().reindex(all_players).fillna(0)
        
        # BLD Score Logic: Own Half Passes
        df_own_half = df_pass_success[df_pass_success['StartX_adj'] <= 52.5].copy()
        if not df_own_half.empty:
            df_own_half['x_gain'] = df_own_half['EndX_adj'] - df_own_half['StartX_adj']
            # Base Score 0.5 + Bonus (x_gain * 0.1 if x_gain >= 5)
            df_own_half['Score'] = 0.5 + np.where(df_own_half['x_gain'] >= 5, df_own_half['x_gain'] * 0.1, 0)
            summary['Own_Half_Pass_Score'] = df_own_half.groupby('Player')['Score'].sum().reindex(all_players).fillna(0)

    # BLD Fail Logic
    df_pass_fail_own = df_pass[(~df_pass['Tags'].str.contains('Success')) & (df_pass['StartX_adj'] <= 52.5)]
    summary['Own_Half_Pass_Fail'] = df_pass_fail_own.groupby('Player')['Action'].count().reindex(all_players).fillna(0)

    # 정수형 변환 (Rate 제외)
    int_cols = [col for col in required_cols if 'Rate' not in col]
    summary[int_cols] = summary[int_cols].astype(int)
        
    return summary.sort_values(by='Total_Pass', ascending=False)


def create_shooter_summary(df_with_xg):
    all_players = df_with_xg['Player'].unique()
    
    required_cols = [
        'Total_Shots', 'Shots_On_Target', 'Goals', 'Total_xG',
        'Headed_Goals', 'Outbox_Goals', 'Counter_Attack_Goals',
        'Catch_Count', 'Total_SOT_xG_Conceded', 'Goals_Conceded'
    ]
    summary = pd.DataFrame(index=all_players)
    for col in required_cols: summary[col] = 0.0

    ACTION_CODES = {'ddd': 'Goal', 'dd': 'Shot On Target', 'd': 'Shot', 'db': 'Blocked Shot'}
    shot_actions = list(ACTION_CODES.values())
    
    df_shots = df_with_xg[df_with_xg['Action'].isin(shot_actions)].copy()
    if df_shots.empty: return summary
    
    if 'Tags' not in df_shots.columns: df_shots['Tags'] = ''
    df_shots['Tags'] = df_shots['Tags'].fillna('')

    agg_summary = df_shots.groupby('Player').agg(
        Total_Shots=('Action', 'count'),
        Shots_On_Target=('Action', lambda x: x.isin(['Shot On Target', 'Goal']).sum()),
        Goals=('Action', lambda x: (x == 'Goal').sum()),
        Total_xG=('xG', 'sum')
    )
    summary.update(agg_summary)

    df_goals = df_shots[df_shots['Action'] == 'Goal']
    if not df_goals.empty:
        summary['Headed_Goals'] = df_goals[df_goals['Tags'].str.contains('Header')].groupby('Player')['Action'].count().reindex(all_players).fillna(0)
        summary['Outbox_Goals'] = df_goals[df_goals['Tags'].str.contains('Out-box')].groupby('Player')['Action'].count().reindex(all_players).fillna(0)
        summary['Counter_Attack_Goals'] = df_goals[df_goals['Tags'].str.contains('Counter Attack')].groupby('Player')['Action'].count().reindex(all_players).fillna(0)

    # SAV Score Logic: Goalkeeper Stats
    # Catching
    df_catch = df_with_xg[df_with_xg['Action'] == 'Catching']
    summary['Catch_Count'] = df_catch.groupby('Player')['Action'].count().reindex(all_players).fillna(0)

    # Team Conceded Stats (Assign Opponent's SOT xG and Goals to Player based on Player's Team)
    # 1. Calculate Team-level SOT xG and Goals
    team_stats = df_with_xg.groupby('TeamID').agg(
        Team_SOT_xG=('xG', lambda x: x[df_with_xg['Action'].isin(['Goal', 'Shot On Target'])].sum()),
        Team_Goals=('Action', lambda x: (x == 'Goal').sum())
    ).to_dict('index')

    # 2. Assign to players (Opponent stats)
    player_teams = df_with_xg[['Player', 'TeamID']].drop_duplicates().set_index('Player')['TeamID']
    all_team_ids = set(df_with_xg['TeamID'].unique())
    
    for player in all_players:
        if player in player_teams:
            my_team = player_teams[player]
            # Assuming 2 teams, opponent is the one not my_team
            opponent_teams = [tid for tid in all_team_ids if tid != my_team]
            if opponent_teams:
                # If multiple opponents (rare), sum them? Usually 1 vs 1.
                opp_team = opponent_teams[0] 
                stats = team_stats.get(opp_team, {'Team_SOT_xG': 0, 'Team_Goals': 0})
                summary.at[player, 'Total_SOT_xG_Conceded'] = stats['Team_SOT_xG']
                summary.at[player, 'Goals_Conceded'] = stats['Team_Goals']
    
    int_cols = ['Total_Shots', 'Shots_On_Target', 'Goals', 'Headed_Goals', 'Outbox_Goals', 'Counter_Attack_Goals']
    summary[int_cols] = summary[int_cols].astype(int)

    return summary.sort_values(by='Goals', ascending=False)


def create_cross_summary(df_analyzed):
    all_players = df_analyzed['Player'].unique()
    
    required_cols = ['Total_Crosses', 'Successful_Crosses', 'Cross_Accuracy', 'Central_PA_Cross_Success']
    summary = pd.DataFrame(index=all_players)
    for col in required_cols: summary[col] = 0.0

    if 'Tags' not in df_analyzed.columns: df_analyzed['Tags'] = ''
    df_cross = df_analyzed[df_analyzed['Action'] == 'Cross'].copy()
    
    if df_cross.empty: return summary

    agg_summary = df_cross.groupby('Player').agg(
        Total_Crosses=('Action', 'count'),
        Successful_Crosses=('Tags', lambda x: x.str.contains('Success').sum())
    )
    summary.update(agg_summary)

    summary['Cross_Accuracy'] = np.where(
        summary['Total_Crosses'] > 0,
        (summary['Successful_Crosses'] / summary['Total_Crosses'] * 100),
        0
    )
    summary['Cross_Accuracy'] = summary['Cross_Accuracy'].round(2)
    
    df_cross_success = df_cross[df_cross['Tags'].str.contains('Success')]
    if not df_cross_success.empty:
        central_crosses = df_cross_success[is_in_penalty_area(df_cross_success['EndX_adj'], df_cross_success['EndY_adj']) & (df_cross_success['EndY_adj'] > 21.1) & (df_cross_success['EndY_adj'] < 46.9)]
        summary['Central_PA_Cross_Success'] = central_crosses.groupby('Player')['Action'].count().reindex(all_players).fillna(0)

    summary[['Total_Crosses', 'Successful_Crosses', 'Central_PA_Cross_Success']] = summary[['Total_Crosses', 'Successful_Crosses', 'Central_PA_Cross_Success']].astype(int)

    return summary

def create_advanced_summary(df_analyzed):
    all_players = df_analyzed['Player'].unique()
    
    required_cols = [
        'Pass_Success_Count', 'Breakthrough_Success', 'Pass_Fail_Count', 'Miss_Count',
        'FT_Pass_Success', 'FT_Breakthrough_Success', 'FT_Pass_Fail', 'FT_Miss', 'FT_Offside',
        'Tackle_Count', 'Duel_Win_Count', 'Intercept_Count', 'Acquisition_Count', 'Foul_Count', 'Duel_Lose_Count',
        'Total_Tackles', 'Successful_Tackles', 'Final_Third_Tackle_Success', 'PA_Foul_Tackles',
        'Clear_Count', 'Cutout_Count', 'Block_Count',
        'Total_Aerial_Duels', 'Aerial_Duels_Won',
        'Received_Assist', 'Received_Key_Pass', 'SOT_Count', 'Goal_Count', 'Offside_Count',
        'Dribble_Attempt', 'Cross_Success', 'Be_Fouled',
        'Valid_Dribble_Distance', 'Dribble_Fail_Count', 'Sprint_Count', 'Total_Sprint_Distance',
        'Header_SOT', 'Header_Clear', 'Aerial_Duels_Lost'
    ]
    summary = pd.DataFrame(index=all_players)
    for col in required_cols: summary[col] = 0

    if 'Tags' not in df_analyzed.columns: df_analyzed['Tags'] = ''
    df_analyzed['Tags'] = df_analyzed['Tags'].fillna('')

    # Helper function to safe update
    def safe_update(series, col_name):
        if not series.empty:
            summary[col_name] = series.reindex(all_players).fillna(0)

    df_pass_succ = df_analyzed[df_analyzed['Action'].isin(['Pass', 'Cross']) & df_analyzed['Tags'].str.contains('Success')]
    df_break_succ = df_analyzed[(df_analyzed['Action'] == 'Breakthrough') & df_analyzed['Tags'].str.contains('Success')]
    df_pass_fail = df_analyzed[df_analyzed['Action'].isin(['Pass', 'Cross']) & ~df_analyzed['Tags'].str.contains('Success')]
    df_miss = df_analyzed[df_analyzed['Action'] == 'Miss']
    
    safe_update(df_pass_succ.groupby('Player')['Action'].count(), 'Pass_Success_Count')
    safe_update(df_break_succ.groupby('Player')['Action'].count(), 'Breakthrough_Success')
    safe_update(df_pass_fail.groupby('Player')['Action'].count(), 'Pass_Fail_Count')
    safe_update(df_miss.groupby('Player')['Action'].count(), 'Miss_Count')

    df_final_third = df_analyzed[is_in_final_third(df_analyzed['StartX_adj'])]
    if not df_final_third.empty:
        df_ft_pass_succ = df_final_third[df_final_third['Action'].isin(['Pass', 'Cross']) & df_final_third['Tags'].str.contains('Success')]
        df_ft_break_succ = df_final_third[(df_final_third['Action'] == 'Breakthrough') & df_final_third['Tags'].str.contains('Success')]
        df_ft_pass_fail = df_final_third[df_final_third['Action'].isin(['Pass', 'Cross']) & ~df_final_third['Tags'].str.contains('Success')]
        df_ft_miss = df_final_third[df_final_third['Action'] == 'Miss']
        df_ft_offside = df_final_third[df_final_third['Action'] == 'Offside']

        safe_update(df_ft_pass_succ.groupby('Player')['Action'].count(), 'FT_Pass_Success')
        safe_update(df_ft_break_succ.groupby('Player')['Action'].count(), 'FT_Breakthrough_Success')
        safe_update(df_ft_pass_fail.groupby('Player')['Action'].count(), 'FT_Pass_Fail')
        safe_update(df_ft_miss.groupby('Player')['Action'].count(), 'FT_Miss')
        safe_update(df_ft_offside.groupby('Player')['Action'].count(), 'FT_Offside')

    df_tackle = df_analyzed[df_analyzed['Action'] == 'Tackle']
    df_duel_win = df_analyzed[(df_analyzed['Action'] == 'Duel') & df_analyzed['Tags'].str.contains('Success')]
    df_intercept = df_analyzed[df_analyzed['Action'] == 'Intercept']
    df_acquisition = df_analyzed[df_analyzed['Action'] == 'Acquisition']
    df_foul = df_analyzed[df_analyzed['Action'] == 'Foul']
    df_duel_lose = df_analyzed[(df_analyzed['Action'] == 'Duel') & ~df_analyzed['Tags'].str.contains('Success')]

    safe_update(df_tackle.groupby('Player')['Action'].count(), 'Tackle_Count')
    safe_update(df_duel_win.groupby('Player')['Action'].count(), 'Duel_Win_Count')
    safe_update(df_intercept.groupby('Player')['Action'].count(), 'Intercept_Count')
    safe_update(df_acquisition.groupby('Player')['Action'].count(), 'Acquisition_Count')
    safe_update(df_foul.groupby('Player')['Action'].count(), 'Foul_Count')
    safe_update(df_duel_lose.groupby('Player')['Action'].count(), 'Duel_Lose_Count')

    safe_update(df_tackle.groupby('Player')['Action'].count(), 'Total_Tackles')
    safe_update(df_tackle[df_tackle['Tags'].str.contains('Success')].groupby('Player')['Action'].count(), 'Successful_Tackles')
    
    df_tackle_success = df_tackle[df_tackle['Tags'].str.contains('Success')]
    if not df_tackle_success.empty:
        safe_update(df_tackle_success[is_in_final_third(df_tackle_success['StartX_adj'])].groupby('Player')['Action'].count(), 'Final_Third_Tackle_Success')
    
    df_tackle_fail_foul = df_analyzed[(df_analyzed['Action'] == 'Foul') & (df_analyzed['Tags'].str.contains('In-box'))]
    safe_update(df_tackle_fail_foul.groupby('Player')['Action'].count(), 'PA_Foul_Tackles')

    df_clear = df_analyzed[df_analyzed['Action'] == 'Clear']
    df_cutout = df_analyzed[df_analyzed['Action'] == 'Cutout']
    df_block = df_analyzed[df_analyzed['Action'] == 'Block']
    safe_update(df_clear.groupby('Player')['Action'].count(), 'Clear_Count')
    safe_update(df_cutout.groupby('Player')['Action'].count(), 'Cutout_Count')
    safe_update(df_block.groupby('Player')['Action'].count(), 'Block_Count')

    df_aerial = df_analyzed[(df_analyzed['Action'] == 'Duel') & (df_analyzed['Tags'].str.contains('Aerial'))].copy()
    safe_update(df_aerial.groupby('Player')['Action'].count(), 'Total_Aerial_Duels')
    safe_update(df_aerial[df_aerial['Tags'].str.contains('Success')].groupby('Player')['Action'].count(), 'Aerial_Duels_Won')

    shot_actions = ['Goal', 'Shot On Target', 'Shot', 'Blocked Shot']
    df_shots = df_analyzed[df_analyzed['Action'].isin(shot_actions)]
    df_offside = df_analyzed[df_analyzed['Action'] == 'Offside']
    
    safe_update(df_shots[df_shots['Tags'].str.contains('Assist')].groupby('Player')['Action'].count(), 'Received_Assist')
    safe_update(df_shots[df_shots['Tags'].str.contains('Key Pass')].groupby('Player')['Action'].count(), 'Received_Key_Pass')
    safe_update(df_shots[df_shots['Action'].isin(['Goal', 'Shot On Target'])].groupby('Player')['Action'].count(), 'SOT_Count')
    safe_update(df_shots[df_shots['Action'] == 'Goal'].groupby('Player')['Action'].count(), 'Goal_Count')
    safe_update(df_offside.groupby('Player')['Action'].count(), 'Offside_Count')
    
    df_dribble = df_analyzed[df_analyzed['Action'] == 'Dribble']
    df_cross_succ = df_analyzed[(df_analyzed['Action'] == 'Cross') & df_analyzed['Tags'].str.contains('Success')]
    df_fouled = df_analyzed[df_analyzed['Action'] == 'Be Fouled']

    safe_update(df_dribble.groupby('Player')['Action'].count(), 'Dribble_Attempt')
    safe_update(df_cross_succ.groupby('Player')['Action'].count(), 'Cross_Success')
    safe_update(df_fouled.groupby('Player')['Action'].count(), 'Be_Fouled')
    
    # DRV Score Logic
    # Valid Dribble Distance: Dribble with dist >= 5m
    df_valid_dribble = df_dribble[df_dribble['Distance'] >= 5]
    safe_update(df_valid_dribble.groupby('Player')['Distance'].sum(), 'Valid_Dribble_Distance')
    
    # Dribble Fail: Dribble not Success or Miss
    # Assuming 'Dribble' actions without Success tag are failed, plus 'Miss' (which is already counted)
    # However, 'Miss' is a separate action. Dribble action usually implies attempting to dribble.
    # If app.py adds 'Fail' to Dribble, we should count that.
    df_dribble_fail = df_dribble[~df_dribble['Tags'].str.contains('Success')]
    # Use existing Miss_Count + Dribble_Fail_Count
    safe_update(df_dribble_fail.groupby('Player')['Action'].count(), 'Dribble_Fail_Count')

    # Sprint Logic
    df_sprint = df_analyzed[df_analyzed['Action'] == 'Sprint']
    safe_update(df_sprint.groupby('Player')['Action'].count(), 'Sprint_Count')
    safe_update(df_sprint.groupby('Player')['Distance'].sum(), 'Total_Sprint_Distance')

    # HED Additional Logic
    df_header = df_analyzed[df_analyzed['Tags'].str.contains('Header')]
    safe_update(df_header[df_header['Action'].isin(['Shot On Target', 'Goal'])].groupby('Player')['Action'].count(), 'Header_SOT')
    safe_update(df_header[df_header['Action'] == 'Clear'].groupby('Player')['Action'].count(), 'Header_Clear')
    
    df_aerial_lost = df_analyzed[(df_analyzed['Action'] == 'Duel') & (df_analyzed['Tags'].str.contains('Aerial')) & (~df_analyzed['Tags'].str.contains('Success'))]
    safe_update(df_aerial_lost.groupby('Player')['Action'].count(), 'Aerial_Duels_Lost')

    return summary.fillna(0).astype(int)
