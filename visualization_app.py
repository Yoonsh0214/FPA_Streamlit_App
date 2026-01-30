import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from mplsoccer import Pitch
import numpy as np

# [1] 페이지 레이아웃 설정
st.set_page_config(page_title="Pro Football Analytics", layout="wide")

# [2] 사이드바 설정
st.sidebar.title("🛠️ Analysis Control")
uploaded_file = st.sidebar.file_uploader("Step 1: Upload Game Data File", type=['xlsx'])

# --- [이름 관리용 헬퍼 함수] ---
def get_name(p_id):
    # 세션 상태에 저장된 맵핑 정보를 가져옴 (없으면 ID 반환)
    mapping = st.session_state.get('player_map', {})
    return mapping.get(str(p_id), str(p_id))

# --- [시각화 함수 정의] ---

def draw_pass_map(df, p_id):
    pitch = Pitch(pitch_type='custom', pitch_length=105, pitch_width=68, pitch_color='grass', line_color='white', stripe=True)
    fig, ax = pitch.draw(figsize=(10, 8))
    
    # 데이터 필터링
    plot_df = df[(df['Player_Str'] == p_id) & (df['Action'].str.contains('Pass', case=False))]
    plot_df = plot_df.dropna(subset=['StartX_adj', 'StartY_adj', 'EndX_adj', 'EndY_adj'])
    
    for _, row in plot_df.iterrows():
        color = '#0dff00' if 'Success' in row['Tags'] else 'red'
        pitch.arrows(row['StartX_adj'], row['StartY_adj'], row['EndX_adj'], row['EndY_adj'], 
                     color=color, ax=ax, width=2, zorder=2)
    
    # [수정] 입력된 이름 사용
    display_name = get_name(p_id)
    title_text = f"{display_name} (No. {p_id}) | Pass Map"
    ax.set_title(title_text, fontsize=16, loc='center', pad=15, color='black', fontweight='bold')
    return fig

def draw_heatmap(df, p_id):
    pitch = Pitch(pitch_type='custom', pitch_length=105, pitch_width=68, pitch_color='grass', line_color='white')
    fig, ax = pitch.draw(figsize=(10, 8))
    
    plot_df = df[df['Player_Str'] == p_id].dropna(subset=['StartX_adj', 'StartY_adj'])
    
    if not plot_df.empty:
        pitch.kdeplot(x=plot_df['StartX_adj'], y=plot_df['StartY_adj'], ax=ax, fill=True, levels=100, thresh=0.05, cmap='hot', alpha=0.6)
    
    # [수정] 입력된 이름 사용
    display_name = get_name(p_id)
    title_text = f"{display_name} (No. {p_id}) | Heatmap"
    ax.set_title(title_text, fontsize=16, loc='center', pad=15, color='black', fontweight='bold')
    return fig

def draw_network(df, thresh):
    df_copy = df.copy()
    pass_df = df_copy[(df_copy['Action'].str.contains('Pass', case=False)) & 
                      (df_copy['Tags'].str.contains('Success', case=False))].dropna(subset=['Player', 'Receiver'])
    
    pass_df['Player'] = pass_df['Player'].astype(str).str.replace('.0', '', regex=False)
    pass_df['Receiver'] = pass_df['Receiver'].astype(str).str.replace('.0', '', regex=False)

    player_ids = pd.concat([pass_df['Player'], pass_df['Receiver']]).unique()
    scatter_df = pd.DataFrame()
    
    for i, p_id in enumerate(player_ids):
        p_pos = pass_df[pass_df["Player"] == p_id][["StartX_adj", "StartY_adj"]].rename(columns={"StartX_adj":"x","StartY_adj":"y"})
        r_pos = pass_df[pass_df["Receiver"] == p_id][["EndX_adj", "EndY_adj"]].rename(columns={"EndX_adj":"x","EndY_adj":"y"})
        all_pos = pd.concat([p_pos, r_pos])
        
        if not all_pos.empty:
            scatter_df.at[i, "player_id"] = p_id
            scatter_df.at[i, "x"] = all_pos.x.mean()
            scatter_df.at[i, "y"] = all_pos.y.mean()
            scatter_df.at[i, "count"] = len(pass_df[pass_df["Player"] == p_id])

    pass_df["pair"] = pass_df.apply(lambda x: "_".join(sorted([x["Player"], x["Receiver"]])), axis=1)
    lines_df = pass_df.groupby("pair").size().reset_index(name="count")
    lines_df = lines_df[lines_df['count'] >= thresh] 

    pitch = Pitch(pitch_type='custom', pitch_length=105, pitch_width=68, pitch_color='#224422', line_color='white')
    fig, ax = pitch.draw(figsize=(10, 8))
    
    if not lines_df.empty:
        max_lw = lines_df['count'].max()
        for _, row in lines_df.iterrows():
            p1_id, p2_id = row["pair"].split("_")
            pos1 = scatter_df[scatter_df["player_id"] == p1_id]
            pos2 = scatter_df[scatter_df["player_id"] == p2_id]
            
            if not pos1.empty and not pos2.empty:
                width = (row["count"] / max_lw * 10) + 1
                pitch.lines(pos1.x.iloc[0], pos1.y.iloc[0], pos2.x.iloc[0], pos2.y.iloc[0], 
                            lw=width, color='#0dff00', alpha=0.7, ax=ax, zorder=2)

    if not scatter_df.empty:
        pitch.scatter(scatter_df.x, scatter_df.y, s=scatter_df['count']*20+150, color='#1a78cf', edgecolors='white', ax=ax, zorder=3)
        for _, row in scatter_df.iterrows():
            # [수정] 노드 위에 입력된 이름 표시
            p_id_clean = str(int(float(row.player_id)))
            display_name = get_name(p_id_clean)
            pitch.annotate(display_name, xy=(row.x, row.y), c='white', va='center', ha='center', weight='bold', ax=ax, fontsize=10)

    title_text = f"Team Passing Network | Min. Passes: {thresh}"
    ax.set_title(title_text, fontsize=16, loc='center', pad=15, color='black', fontweight='bold')
    return fig

# --- [메인 로직] ---

if uploaded_file:
    df = pd.read_excel(uploaded_file)
    st.sidebar.success("Data Loaded!")

    # 데이터 전처리
    df['Player_Str'] = df['Player'].astype(str).str.replace('.0', '', regex=False).str.strip()
    df['Action'] = df['Action'].astype(str).str.strip()
    df['Tags'] = df['Tags'].fillna('None').astype(str).str.strip()

    # 선수 ID 목록 추출
    unique_players = df['Player_Str'].unique()
    def sort_key(val):
        try: return float(val)
        except ValueError: return float('inf')
    players_sorted = sorted(unique_players, key=sort_key)

    # ---------------------------------------------------------
    # [추가됨] 사이드바: 선수 이름 편집기 (Excel 스타일)
    # ---------------------------------------------------------
    st.sidebar.markdown("### 📝 Player Name Editor")
    st.sidebar.caption("ID 옆에 이름을 입력하세요.")

    # 편집기 초기 데이터 생성 (처음에는 ID=Name)
    if 'editor_df' not in st.session_state:
        st.session_state['editor_df'] = pd.DataFrame({
            'ID': players_sorted,
            'Name': players_sorted # 기본값은 ID와 동일
        })

    # 데이터 에디터 표시 (사용자가 수정 가능)
    edited_df = st.sidebar.data_editor(
        st.session_state['editor_df'],
        hide_index=True,
        column_config={
            "ID": st.column_config.TextColumn("No.", disabled=True), # ID는 수정 불가
            "Name": st.column_config.TextColumn("Player Name", required=True)
        },
        key="data_editor",
        num_rows="fixed" 
    )

    # 수정된 데이터를 딕셔너리로 변환하여 세션에 저장 (그래프 함수들이 갖다 쓰도록)
    player_map = dict(zip(edited_df['ID'], edited_df['Name']))
    st.session_state['player_map'] = player_map
    # ---------------------------------------------------------

    # 선수 선택 (이름 표시됨)
    selected_player = st.sidebar.selectbox(
        "Step 2: Select Player", 
        players_sorted, 
        format_func=lambda x: f"{get_name(x)} (No.{x})"
    )

    # 상단 통계 지표
    p_passes = df[(df['Player_Str'] == selected_player) & (df['Action'].str.contains('Pass', case=False))]
    total_p = len(p_passes)
    success_p = len(p_passes[p_passes['Tags'].str.contains('Success', case=False)])
    accuracy = (success_p / total_p * 100) if total_p > 0 else 0

    st.write(f"## 📊 Summary: {get_name(selected_player)}")
    m1, m2, m3 = st.columns(3)
    m1.metric("Total Passes", f"{total_p} 회")
    m2.metric("Successful Passes", f"{success_p} 회")
    m3.metric("Pass Accuracy", f"{accuracy:.1f} %")
    st.divider()

    # 탭 구성
    tab1, tab2, tab3 = st.tabs(["🎯 Pass Map", "🔥 Heatmap", "🕸️ Passing Network"])

    with tab1:
        if total_p > 0:
            st.pyplot(draw_pass_map(df, selected_player))
        else:
            st.warning("이 선수의 패스 데이터가 없습니다.")

    with tab2:
        st.pyplot(draw_heatmap(df, selected_player))

    with tab3:
        st.write("#### Network Sensitivity")
        thresh = st.slider("Minimum passes for connection", 1, 10, 2)
        st.pyplot(draw_network(df, thresh))

else:
    st.title("⚽ Football Data Analysis Hub")
    st.info("Please upload your Excel data file from the sidebar.")