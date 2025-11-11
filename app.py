import streamlit as st
import pandas as pd
import analysis
import io

st.set_page_config(page_title="FPA Data Analyzer", layout="centered")

st.title("📊 FPA 데이터 분석 웹 애플리케이션")

st.write("""
이 앱은 FPA 데이터가 포함된 Excel 파일을 분석합니다.
'Data' 시트가 포함된 `.xlsx` 파일을 업로드하면, 분석된 통계가 포함된 새로운 Excel 파일을 다운로드할 수 있습니다.
""")

uploaded_file = st.file_uploader("여기에 Excel 파일(.xlsx)을 업로드하세요", type=['xlsx'])

if uploaded_file is not None:
    try:
        with st.spinner('데이터를 분석하는 중입니다... 잠시만 기다려주세요.'):
            df = pd.read_excel(uploaded_file, sheet_name='Data')

            # --- analysis.py의 전체 분석 파이프라인 실행 ---
            df_with_seconds = analysis.convert_time_to_seconds(df.copy())
            df_tagged = analysis.auto_tag_key_pass_and_assist(df_with_seconds)
            df_analyzed = analysis.analyze_pass_data(df_tagged)
            df_analyzed_with_xg = analysis.add_xg_to_data(df_analyzed)

            # 메모리 내에서 엑셀 파일 생성
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
            
            output.seek(0)
        
        st.success('✅ 분석이 완료되었습니다! 아래 버튼을 눌러 결과를 다운로드하세요.')
        
        st.download_button(
            label="📥 분석 결과 다운로드 (.xlsx)",
            data=output,
            file_name="analyzed_data.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error(f"오류가 발생했습니다: {e}")
        st.warning("Excel 파일에 'Data'라는 이름의 시트가 포함되어 있는지 확인해주세요.")
