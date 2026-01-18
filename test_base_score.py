import pandas as pd
import numpy as np
import scoring

# Create a dummy summary with one player and all zeros
cols = [
    'Pass_Success_Rate', 'Progressive_Pass_Success', 'Key_Pass', 'Assist', 'PA_Pass_Success', 'Pass_Fail_Count', # Passing
    'Goals', 'Total_xG', 'Headed_Goals', 'Outbox_Goals', # Shooting
    'Cross_Accuracy', 'Successful_Crosses', 'Central_PA_Cross_Success', # Cross
    'Dribble_Attempt', 'Breakthrough_Success', 'Miss_Count', 'Be_Fouled', # Dribbling
    'Total_Tackles', 'Successful_Tackles', 'Total_Aerial_Duels', 'Aerial_Duels_Won', 'Intercept_Count', \
    'Block_Count', 'Clear_Count', 'Duel_Win_Count', # Defending
    'Pass_Success_Count', 'Received_Assist', 'Received_Key_Pass', 'SOT_Count', 'Goal_Count', 'Offside_Count', # Advanced
    'FT_Pass_Success', 'FT_Breakthrough_Success', 'FT_Pass_Fail', 'FT_Miss', 'FT_Offside' # DEC
]
# Add all necessary columns initialized to 0
data = {col: [0] for col in cols}
df = pd.DataFrame(data)

# Run scoring functions
print("--- Verification Results (Expected ~60) ---")

# Passing
passed = scoring.calculate_passing_score(df.copy(), df.copy())
print(f"Passing Score: {passed['Passing_Score'].iloc[0]}")

# Shooting
shoot = scoring.calculate_shooting_score(df.copy())
print(f"Shooting Score: {shoot['Shooting_Score'].iloc[0]}")

# Cross
cross = scoring.calculate_cross_score(df.copy())
print(f"Cross Score: {cross['Cross_Score'].iloc[0]}")

# Dribbling
dribble = scoring.calculate_dribbling_score(df.copy())
print(f"Dribbling Score: {dribble['Dribbling_Score'].iloc[0]}")

# Defending
defend = scoring.calculate_defending_score(df.copy())
print(f"Defending Score: {defend['Defending_Score'].iloc[0]}")

# Advanced
adv = scoring.calculate_advanced_scores(df.copy(), df.copy())
print(f"FST Score: {adv['FST_Score'].iloc[0]}")
print(f"OFF Score: {adv['OFF_Score'].iloc[0]}")
print(f"DEC Score: {adv['DEC_Score'].iloc[0]}")
