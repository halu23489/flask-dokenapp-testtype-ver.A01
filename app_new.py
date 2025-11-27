# app.py
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import pandas as pd
from io import BytesIO

app = Flask(__name__)
app.secret_key = 'your_super_secret_key_z_system_proto_0'

APP_CONFIG = {
    'app_name': 'ITショクチョー！',
    'app_title': 'Ζシステムシリーズ：歩掛マスタープロトタイプ0',
    'app_subtitle': '現場に携わる技術者のための',
    'nav': {
        'home': {'name': '🏠 ホーム', 'url': 'index'},
        'record': {'name': '📝 日々の作業記録', 'url': 'daily_record'},
        'stopwatch': {'name': '⏱ サイクルタイム計測', 'url': 'stopwatch'},
        'others': {
            'name': '📊 その他機能（予定）',
            'children': [
                {'id': 'comparison_tool', 'name': '効率比較ツール', 'url': 'comparison_tool'},
                {'id': 'calc_a', 'name': '出来形計算（仮）', 'url': 'index'},
                {'id': 'report_b', 'name': '報告書作成（仮）', 'url': 'index'},
            ]
        }
    }
}

app.jinja_env.globals.update(zip=zip, enumerate=enumerate, len=len)

def safe_url_for(endpoint):
    try:
        return url_for(endpoint)
    except Exception:
        return url_for('index')

@app.context_processor
def inject_global_config():
    return {
        'app_name': APP_CONFIG['app_name'],
        'app_title': APP_CONFIG['app_title'],
        'app_subtitle': APP_CONFIG['app_subtitle'],
        'nav': APP_CONFIG['nav'],
        'safe_url_for': safe_url_for,
    }

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        session['project_data'] = {
            'site_name': request.form.get('site_name', ''),
            'task_name': request.form.get('task_name', ''),
            'tool_list': request.form.get('tool_list', ''),
            'cycle_steps': request.form.getlist('step[]'),
            'cycle_checks': request.form.getlist('check[]')
        }
        return redirect(url_for('daily_record'))
    project_data = session.get('project_data', {})
    return render_template('index.html', page_title='ホーム', current_app='home', project_data=project_data)

@app.route('/workmaster_basic', methods=['GET', 'POST'])
def workmaster_basic():
    if request.method == 'POST':
        session['workmaster_basic'] = {
            'site_name': request.form.get('site_name', ''),
            'task_name': request.form.get('task_name', ''),
            'period': request.form.get('period', ''),
            'contractor': request.form.get('contractor', ''),
            'machines': request.form.get('machines', ''),
        }
        return redirect(url_for('workmaster_detail'))
    data = session.get('workmaster_basic', {})
    return render_template('workmaster_basic.html', page_title='歩掛マスター：基本情報入力', current_app='workmaster_basic', data=data)

@app.route('/workmaster_detail', methods=['GET', 'POST'])
def workmaster_detail():
    if request.method == 'POST':
        session['workmaster_detail'] = {
            'material_name': request.form.getlist('material_name[]'),
            'material_qty': request.form.getlist('material_qty[]'),
            'heavy_machine': request.form.get('heavy_machine', ''),
            'person_count': request.form.get('person_count', ''),
            'work_unit': request.form.get('work_unit', ''),
            'work_cycle': request.form.get('work_cycle', ''),
            'cycle_options': request.form.get('cycle_options', ''),
        }
        return redirect(url_for('workmaster_daily'))
    data = session.get('workmaster_detail', {})
    return render_template('workmaster_detail.html', page_title='歩掛マスター：詳細内容入力', current_app='workmaster_detail', data=data)

@app.route('/daily_record', methods=['GET', 'POST'])
def daily_record():
    project_data = session.get('project_data')
    if not project_data or not project_data.get('site_name'):
        return redirect(url_for('index'))
    daily_records = session.get('daily_records', [])
    if request.method == 'POST':
        record = {
            'date': request.form.get('record_date'),
            'personnel': request.form.get('personnel'),
            'machinery': request.form.get('machinery'),
            'work_time': request.form.get('work_time'),
            'work_content': request.form.get('work_content'),
            'progress_unit': request.form.get('progress_unit'),
            'progress_value': request.form.get('progress_value'),
            'progress_total': request.form.get('progress_total'),
            'weather': request.form.get('weather'),
            'remarks': request.form.get('remarks'),
        }
        daily_records.append(record)
        session['daily_records'] = daily_records
        return redirect(url_for('daily_record'))
    recent_records = daily_records[::-1]
    return render_template('daily_record.html', page_title='日々の作業記録', current_app='record', project_data=project_data, recent_records=recent_records)

@app.route('/export_excel')
def export_excel():
    daily_records = session.get('daily_records', [])
    project_data = session.get('project_data', {})
    if not daily_records:
        return redirect(url_for('daily_record'))
    df = pd.DataFrame(daily_records)
    site_info = pd.Series({
        '現場名': project_data.get('site_name', 'N/A'),
        '作業名': project_data.get('task_name', 'N/A'),
        '道具': project_data.get('tool_list', 'N/A'),
        '作業サイクル': ", ".join([f"{s} ({c})" for s, c in zip(project_data.get('cycle_steps', []), project_data.get('cycle_checks', []))]),
    })
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='日々の記録', index=False)
        site_df = pd.DataFrame(site_info).T
        site_df.to_excel(writer, sheet_name='現場設定', index=False)
    output.seek(0)
    return render_template('daily_record.html', page_title='日々の作業記録', current_app='record', project_data=project_data, recent_records=daily_records[::-1], export_message="✅ Excelデータのエクスポート処理が完了しました（ダミー）。")

@app.route('/stopwatch', methods=['GET', 'POST'])
def stopwatch():
    project_data = session.get('project_data')
    if not project_data or not project_data.get('cycle_steps'):
        return redirect(url_for('index'))
    cycle_records = session.get('cycle_records', [])
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add_record':
            new_record = {
                'step': request.form.get('step_name'),
                'time': request.form.get('time_duration')
            }
            cycle_records.append(new_record)
            session['cycle_records'] = cycle_records
            return "Record added successfully", 200
        elif action == 'clear_records':
            session.pop('cycle_records', None)
            return redirect(url_for('stopwatch'))
    recent_records = cycle_records[::-1]
    return render_template('stopwatch.html', page_title='サイクルタイム計測', current_app='stopwatch', project_data=project_data, recent_records=recent_records)

@app.route('/comparison_tool')
def comparison_tool():
    return render_template('comparison_tool.html', page_title='効率比較ツール', current_app='comparison_tool')

if __name__ == '__main__':
    app.run(debug=True)
