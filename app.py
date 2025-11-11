import os
import io
from flask import Flask, request, send_file, render_template, jsonify
import pandas as pd
import analysis

app = Flask(__name__)

@app.route('/')
def index():
    """
    메인 페이지를 렌더링합니다.
    """
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process_file():
    """
    업로드된 엑셀 파일을 받아 분석하고, 결과 엑셀 파일을 반환합니다.
    """
    if 'file' not in request.files:
        return "No file part", 400
    
    file = request.files['file']
    
    if file.filename == '':
        return "No selected file", 400

    if file and file.filename.endswith('.xlsx'):
        try:
            df = pd.read_excel(file, sheet_name='Data')

            # --- 기존 analysis.py의 분석 파이프라인 실행 ---
            df_with_seconds = analysis.convert_time_to_seconds(df.copy())
            df_tagged = analysis.auto_tag_key_pass_and_assist(df_with_seconds)
            df_analyzed = analysis.analyze_pass_data(df_tagged)
            df_analyzed_with_xg = analysis.add_xg_to_data(df_analyzed)

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
            
            return send_file(
                output,
                as_attachment=True,
                download_name='analyzed_data.xlsx',
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )

        except Exception as e:
            return f"An error occurred: {str(e)}", 500
    
    return "Invalid file type", 400

if __name__ == '__main__':
    app.run(debug=True)
