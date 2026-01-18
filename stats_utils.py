

# --- 상수 ---
FIELD_W = 105
FIELD_H = 68

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
            return 0
        return 0

    if 'Time' in df.columns:
        df['Time(s)'] = df['Time'].apply(time_to_seconds)
    return df

def is_in_final_third(x):
    return x >= 70

def is_in_penalty_area(x, y):
    return (x > 88.5) & (y > 13.84) & (y < 54.16)

def is_progressive_pass(start_x, end_x):
    return end_x - start_x >= 10
