import numpy as np

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
    
    # 0 actions -> raw=0 -> score ~60
    mid_point = -5 
    steepness = 0.08
    passing_scores = 100 / (1 + np.exp(-steepness * (summary['Passing_Raw'] - mid_point)))
    summary['Passing_Score'] = passing_scores.round(0).astype(int)
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
    
    # 0 actions -> raw=0 -> score ~60
    mid_point = -2.2
    steepness = 0.18
    shooting_scores = 100 / (1 + np.exp(-steepness * (summary['Shooting_Raw'] - mid_point)))
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
    
    # 0 actions -> raw=0 -> score ~60
    mid_point = -4
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
    
    # 0 actions -> raw=0 -> score ~60
    mid_point = -2
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
    
    # 0 actions -> raw=0 -> score ~60
    mid_point = -2.7
    steepness = 0.15
    defending_scores = 100 / (1 + np.exp(-steepness * (summary['Defending_Raw'] - mid_point)))
    summary['Defending_Score'] = defending_scores.round(0).astype(int)
    return summary


def calculate_advanced_scores(summary, pass_summary):
    # FST (First Touch)
    fst_numerator = summary['Pass_Success_Count'] + summary['Breakthrough_Success']
    fst_denominator = fst_numerator + summary['Pass_Fail_Count'] + summary['Miss_Count']
    summary['FST_Raw'] = (fst_numerator / fst_denominator).fillna(0) * 100
    
    # Default 60 if no actions
    fst_scores = 100 / (1 + np.exp(-0.15 * (summary['FST_Raw'] - 80)))
    summary['FST_Score'] = np.where(fst_denominator == 0, 60, fst_scores)

    # OFF (Off The Ball)
    summary['OFF_Raw'] = (summary['Received_Assist'] * 3) + (summary['Received_Key_Pass'] * 1.5) + \
                         summary['SOT_Count'] + summary['Goal_Count'] - (summary['Offside_Count'] * 2)
    # 0 actions -> raw=0 -> score ~60
    summary['OFF_Score'] = 100 / (1 + np.exp(-0.25 * (summary['OFF_Raw'] - (-1.6))))

    # DEC (Decision)
    dec_numerator = summary['FT_Pass_Success'] + summary['FT_Breakthrough_Success']
    dec_denominator = dec_numerator + summary['FT_Pass_Fail'] + summary['FT_Miss'] + summary['FT_Offside']
    summary['DEC_Raw'] = (dec_numerator / dec_denominator).fillna(0) * 100
    
    # Default 60 if no actions
    dec_scores = 100 / (1 + np.exp(-0.15 * (summary['DEC_Raw'] - 80)))
    summary['DEC_Score'] = np.where(dec_denominator == 0, 60, dec_scores)
    
    score_cols = [col for col in summary.columns if '_Score' in col]
    summary[score_cols] = summary[score_cols].round(0).astype(int)
    
    return summary
