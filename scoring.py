import numpy as np
import pandas as pd

def sigmoid_score(raw, mid, steepness):
    score = 100 / (1 + np.exp(-steepness * (raw - mid)))
    return score

def calculate_passing_score(summary, advanced_summary):
    if summary.empty: return summary
    
    summary = summary.drop(columns=['Pass_Fail_Count'], errors='ignore')
    summary = summary.join(advanced_summary[['Pass_Fail_Count']], how='left').fillna(0)

    raw_score = (summary['Pass_Success_Rate'] * 0.8) + \
                (summary['Progressive_Pass_Success'] * 1.5) + \
                (summary['Key_Pass'] * 2.5) + \
                (summary['Assist'] * 5) + \
                (summary['PA_Pass_Success'] * 3) - \
                (summary['Pass_Fail_Count'] * 0.5)
    
    summary['Passing_Raw'] = raw_score
    # 0 actions -> raw=0 -> score 50
    # mid_point = 0
    summary['Passing_Score'] = sigmoid_score(summary['Passing_Raw'], 0, 0.08).round(0).astype(int)
    return summary

def calculate_buildup_score(summary):
    # BLD Score (Build-Up)
    if summary.empty: return summary
    
    # Needs Own_Half_Pass_Score and Own_Half_Pass_Fail from summaries.py/create_player_summary
    if 'Own_Half_Pass_Score' not in summary.columns: summary['Own_Half_Pass_Score'] = 0
    if 'Own_Half_Pass_Fail' not in summary.columns: summary['Own_Half_Pass_Fail'] = 0

    raw_score = summary['Own_Half_Pass_Score'] - (summary['Own_Half_Pass_Fail'] * 2)
    summary['BLD_Raw'] = raw_score
    # 0 actions -> raw=0 -> score 50
    summary['BLD_Score'] = sigmoid_score(summary['BLD_Raw'], 0, 0.15).round(0).astype(int)
    return summary

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
    # 0 actions -> raw=0 -> score 50
    summary['Shooting_Score'] = sigmoid_score(summary['Shooting_Raw'], 0, 0.18).round(0).astype(int)
    return summary

def calculate_save_score(summary):
    # SAV Score (Save) - derived from df_shooter_summary containing GK stats
    if summary.empty: return summary
    
    required_cols = ['Total_SOT_xG_Conceded', 'Goals_Conceded', 'Catch_Count']
    for col in required_cols:
        if col not in summary.columns: summary[col] = 0
        
    total_xg = summary['Total_SOT_xG_Conceded']
    goals = summary['Goals_Conceded']
    saved_xg = total_xg - goals # Approximation
    
    raw_score = ((total_xg - goals) * 10) + (saved_xg * 10) + (summary['Catch_Count'] * 2)
    
    summary['SAV_Raw'] = raw_score
    # 0 actions -> raw=0 -> score 50
    summary['SAV_Score'] = sigmoid_score(summary['SAV_Raw'], 0, 0.1).round(0).astype(int)
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
    # 0 actions -> raw=0 -> score 50
    summary['Cross_Score'] = sigmoid_score(summary['Raw_Cross_Score'], 0, 0.1).round(0).astype(int)
    return summary

def calculate_dribbling_score(summary):
    # Dribbling Score (Old Formula: Success/Fail based)
    if summary.empty: return summary

    failed_dribble = summary['Dribble_Attempt'] - summary['Breakthrough_Success']
    raw_score = (summary['Breakthrough_Success'] * 3) - \
                (failed_dribble + summary['Miss_Count']) * 1 + \
                (summary['Be_Fouled'] * 0.8)

    summary['Dribbling_Raw'] = raw_score
    # 0 actions -> raw=0 -> score 50
    summary['Dribbling_Score'] = sigmoid_score(summary['Dribbling_Raw'], 0, 0.2).round(0).astype(int)
    return summary

def calculate_drive_score(summary):
    # DRV Score (Drive: Distance based)
    if summary.empty: return summary
    
    # Needs Valid_Dribble_Distance and Dribble_Fail_Count from advanced_summary
    if 'Valid_Dribble_Distance' not in summary.columns: summary['Valid_Dribble_Distance'] = 0
    if 'Dribble_Fail_Count' not in summary.columns: summary['Dribble_Fail_Count'] = 0

    raw = (summary['Valid_Dribble_Distance'] * 0.15) - (summary['Dribble_Fail_Count'] * 2)
    
    summary['DRV_Raw'] = raw
    # 0 actions -> raw=0 -> score 50
    summary['DRV_Score'] = sigmoid_score(summary['DRV_Raw'], 0, 0.12).round(0).astype(int)
    return summary

def calculate_tackling_score(summary):
    # TAC Score (Renamed from Defending)
    if summary.empty: return summary

    required_cols = ['Successful_Tackles', 'Total_Tackles', 'Intercept_Count', 'Block_Count', 'Clear_Count', 'Aerial_Duels_Won', 'Total_Aerial_Duels', 'Duel_Win_Count']
    for col in required_cols:
        if col not in summary.columns: summary[col] = 0

    failed_tackles = summary['Total_Tackles'] - summary['Successful_Tackles']
    failed_aerials = summary['Total_Aerial_Duels'] - summary['Aerial_Duels_Won']

    raw_score = (summary['Successful_Tackles'] * 2) - (failed_tackles * 1) + \
                (summary['Intercept_Count'] * 1.5) + \
                (summary['Block_Count'] * 1.2) + \
                (summary['Clear_Count'] * 1) + \
                (summary['Aerial_Duels_Won'] * 1.5) - (failed_aerials * 0.5) + \
                (summary['Duel_Win_Count'] * 0.5)
    
    summary['TAC_Raw'] = raw_score
    # 0 actions -> raw=0 -> score 50
    summary['TAC_Score'] = sigmoid_score(summary['TAC_Raw'], 0, 0.15).round(0).astype(int)
    return summary

def calculate_header_score(summary):
    # HED Score (Header)
    if summary.empty: return summary
    
    required_cols = ['Header_SOT', 'Header_Clear', 'Aerial_Duels_Won', 'Aerial_Duels_Lost', 'Goal_Count'] 
    # Goal_Count needs to be checked for Header tag? No, summary usually has HED_Goals. 
    # But advanced_summary might not have Header_Goals clearly unless I added it.
    # summaries.py added Header_SOT (includes Goals) and Header_Clear.
    # We need Header_Goal specifically for bonus.
    # `summary` passed here is usually advanced_summary? Or combined?
    # I should pass combined or ensure cols exist.
    # summaries.py -> create_advanced_summary added 'Header_SOT'. 
    # It did NOT add 'Header_Goal' specifically there.
    # But `create_shooter_summary` has `Headed_Goals`.
    # I'll rely on `Header_SOT` (which includes goals) * 3 + `Headed_Goals` * 2 -> Total 5 for goal.
    # But current inputs are likely `advanced_summary`. `Headed_Goals` is in `shooter_summary`.
    # I will assume `Headed_Goals` is passed in `summary` (requires join in app.py).
    
    if 'Headed_Goals' not in summary.columns: summary['Headed_Goals'] = 0
    if 'Header_SOT' not in summary.columns: summary['Header_SOT'] = 0
    if 'Header_Clear' not in summary.columns: summary['Header_Clear'] = 0
    if 'Aerial_Duels_Won' not in summary.columns: summary['Aerial_Duels_Won'] = 0
    if 'Aerial_Duels_Lost' not in summary.columns: summary['Aerial_Duels_Lost'] = 0
    
    raw = (summary['Header_SOT'] * 3) + (summary['Headed_Goals'] * 2) + \
          (summary['Aerial_Duels_Won'] * 2) + (summary['Header_Clear'] * 1) - \
          (summary['Aerial_Duels_Lost'] * 1.5)
          
    summary['HED_Raw'] = raw
    # 0 actions -> raw=0 -> score 50
    summary['HED_Score'] = sigmoid_score(summary['HED_Raw'], 0, 0.2).round(0).astype(int)
    return summary

def calculate_pace_score(summary):
    # PAC Score (Pace / Sprint)
    if summary.empty: return summary
    
    if 'Total_Sprint_Distance' not in summary.columns: summary['Total_Sprint_Distance'] = 0
    if 'Sprint_Count' not in summary.columns: summary['Sprint_Count'] = 0
    
    # Formula (Proposed): Distance * 0.1 + Count * 1
    raw = (summary['Total_Sprint_Distance'] * 0.1) + (summary['Sprint_Count'] * 1)
    
    summary['PAC_Raw'] = raw
    # 0 actions -> raw=0 -> score 50
    summary['PAC_Score'] = sigmoid_score(summary['PAC_Raw'], 0, 0.1).round(0).astype(int)
    return summary

def calculate_advanced_scores(summary, pass_summary):
    # FST, OFF, DEC logic (keeping existing)
    fst_num = summary['Pass_Success_Count'] + summary['Breakthrough_Success']
    fst_denom = fst_num + summary['Pass_Fail_Count'] + summary['Miss_Count']
    summary['FST_Raw'] = (fst_num / fst_denom).fillna(0) * 100
    
    # Default 50 if no actions
    fst_scores = sigmoid_score(summary['FST_Raw'], 80, 0.15)
    summary['FST_Score'] = np.where(fst_denom == 0, 50, fst_scores).astype(int)

    summary['OFF_Raw'] = (summary['Received_Assist'] * 3) + (summary['Received_Key_Pass'] * 1.5) + \
                         summary['SOT_Count'] + summary['Goal_Count'] - (summary['Offside_Count'] * 2)
    # 0 actions -> raw=0 -> score 50
    summary['OFF_Score'] = sigmoid_score(summary['OFF_Raw'], 0, 0.25).round(0).astype(int)

    dec_num = summary['FT_Pass_Success'] + summary['FT_Breakthrough_Success']
    dec_denom = dec_num + summary['FT_Pass_Fail'] + summary['FT_Miss'] + summary['FT_Offside']
    summary['DEC_Raw'] = (dec_num / dec_denom).fillna(0) * 100
    
    # Default 50 if no actions
    dec_scores = sigmoid_score(summary['DEC_Raw'], 80, 0.15)
    summary['DEC_Score'] = np.where(dec_denom == 0, 50, dec_scores).astype(int)
    
    return summary
