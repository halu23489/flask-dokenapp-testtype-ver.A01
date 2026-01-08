# app.py
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import pandas as pd
from io import BytesIO
from datetime import datetime

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
                {'id': 'workmaster_proto', 'name': '歩掛マスター（プロトタイプ）', 'url': 'workmaster_proto_basic'},
                {'id': 'calc_a', 'name': '出来形計算（仮）', 'url': 'index'},
                {'id': 'report_b', 'name': '報告書作成（仮）', 'url': 'index'},
            ]
        }
    }
}

MASTER_DATA = {
    'work_items': [
        {'id': 'concrete_pour', 'name': '生コン打設'},
        {'id': 'anchor_drill', 'name': 'アンカー削孔'},
        {'id': 'sheet_pile', 'name': '矢板打設'},
        {'id': 'backhoe_excavation', 'name': 'バックホウ掘削'},
        {'id': 'asphalt', 'name': '舗装（アスファルト）'}
    ],
    'machines': [
        {'id': 'bh_02', 'name': '0.2m3バックホウ', 'unit_cost_per_hour': 12000},
        {'id': 'bh_045', 'name': '0.45m3バックホウ', 'unit_cost_per_hour': 18000},
        {'id': 'dump_4t', 'name': '4tダンプ', 'unit_cost_per_hour': 9500},
        {'id': 'crane_25t', 'name': '25tラフター', 'unit_cost_per_hour': 24000},
        {'id': 'vibro', 'name': 'バイブロハンマー', 'unit_cost_per_hour': 15000},
    ],
    'check_items': [
        '足場の手すり高さ確認（1.1m以上）',
        '重機周囲の立入禁止措置',
        'アンカー削孔位置の基準墨確認',
        'コンクリート打設時のスランプ・温度確認',
        '夜間照明・視認性の確保'
    ],
    'personnel_unit_cost_per_hour': 6000,
}

app.jinja_env.globals.update(zip=zip, enumerate=enumerate, len=len, now=datetime.now)


def safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def ensure_project_session():
    project = session.get('project_data')
    if not project:
        project = {
            'site_name': '未設定の現場',
            'task_name': '未設定の作業',
            'planned_quantity': 0.0,
            'planned_unit': '',
            'cycle_steps': [],
            'cycle_checks': [],
            'budget': {'labor': 0, 'machine': 0, 'materials': 0},
            'design_link': '',
            'phase': '施工前',
            'progress_pct': 0.0,
            'actual_cost': 0.0,
        }
        session['project_data'] = project
    else:
        project.setdefault('cycle_steps', [])
        project.setdefault('cycle_checks', [])
        project.setdefault('budget', {'labor': 0, 'machine': 0, 'materials': 0})
        project.setdefault('planned_quantity', 0.0)
        project.setdefault('planned_unit', '')
        project.setdefault('phase', '施工前')
        project.setdefault('progress_pct', 0.0)
        project.setdefault('actual_cost', 0.0)
    return project


def ensure_proto_project_session():
    project = session.get('proto_project_data')
    if not project:
        project = {
            'site_name': '未設定の現場',
            'task_name': '未設定の作業',
            'planned_quantity': 0.0,
            'planned_unit': '',
            'cycle_steps': [],
            'cycle_checks': [],
            'budget': {'labor': 0, 'machine': 0, 'materials': 0},
            'design_link': '',
            'phase': '施工前',
            'progress_pct': 0.0,
            'actual_cost': 0.0,
        }
        session['proto_project_data'] = project
    else:
        project.setdefault('cycle_steps', [])
        project.setdefault('cycle_checks', [])
        project.setdefault('budget', {'labor': 0, 'machine': 0, 'materials': 0})
        project.setdefault('planned_quantity', 0.0)
        project.setdefault('planned_unit', '')
        project.setdefault('phase', '施工前')
        project.setdefault('progress_pct', 0.0)
        project.setdefault('actual_cost', 0.0)
    return project


def calculate_daily_cost(personnel_count, work_time, machinery_list):
    # 機械単価と人件費単価から実費を計算
    personnel_rate = MASTER_DATA['personnel_unit_cost_per_hour']
    cost_personnel = personnel_count * work_time * personnel_rate
    cost_machinery = 0
    for machine_name in machinery_list:
        machine = next((m for m in MASTER_DATA['machines'] if m['name'] == machine_name), None)
        if machine:
            cost_machinery += work_time * machine['unit_cost_per_hour']
    return round(cost_personnel, 0), round(cost_machinery, 0), round(cost_personnel + cost_machinery, 0)


def update_project_from_daily(project_data, daily_records, session_key='project_data'):
    cumulative_qty = sum(rec.get('progress_value_float', 0.0) for rec in daily_records)
    planned_qty = project_data.get('planned_quantity') or (daily_records[-1].get('progress_total_float') if daily_records else 0.0)
    progress_pct = (cumulative_qty / planned_qty * 100) if planned_qty else 0.0
    project_data['planned_quantity'] = planned_qty
    project_data['progress_pct'] = round(min(progress_pct, 100.0), 1)
    project_data['phase'] = '竣工' if project_data['progress_pct'] >= 100 else ('施工中' if cumulative_qty > 0 else '施工前')
    project_data['actual_cost'] = round(sum(rec.get('cost_total', 0.0) for rec in daily_records), 0)
    session[session_key] = project_data

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
        project = ensure_project_session()
        project.update({
            'site_name': request.form.get('site_name', project.get('site_name', '')),
            'task_name': request.form.get('task_name', project.get('task_name', '')),
            'planned_quantity': safe_float(request.form.get('planned_quantity'), project.get('planned_quantity', 0.0)),
            'planned_unit': request.form.get('planned_unit', project.get('planned_unit', '')),
            'design_link': request.form.get('design_link', project.get('design_link', '')),
            'budget': {
                'labor': safe_float(request.form.get('budget_labor'), project.get('budget', {}).get('labor', 0)),
                'machine': safe_float(request.form.get('budget_machine'), project.get('budget', {}).get('machine', 0)),
                'materials': safe_float(request.form.get('budget_materials'), project.get('budget', {}).get('materials', 0)),
            },
            'cycle_steps': request.form.getlist('step[]'),
            'cycle_checks': request.form.getlist('check[]'),
            'tool_list': request.form.get('tool_list', ''),
        })
        session['project_data'] = project
        return redirect(url_for('daily_record'))
    project_data = ensure_project_session()
    return render_template(
        'index.html',
        page_title='ホーム',
        current_app='home',
        project_data=project_data,
        master_data=MASTER_DATA,
    )

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
    project_data = ensure_project_session()
    daily_records = session.get('daily_records', [])
    if request.method == 'POST':
        machinery_list = request.form.getlist('machinery[]')
        work_contents = request.form.getlist('work_content[]')
        progress_value = safe_float(request.form.get('progress_value'))
        progress_total = safe_float(request.form.get('progress_total'), project_data.get('planned_quantity', 0.0))
        personnel = int(safe_float(request.form.get('personnel'), 0))
        work_time = safe_float(request.form.get('work_time'), 0)

        cycle_steps = request.form.getlist('cycle_step[]')
        cycle_counts = request.form.getlist('cycle_count[]')
        cycle_progresses = request.form.getlist('cycle_progress[]')
        cycle_entries = []
        for s, c, p in zip(cycle_steps, cycle_counts, cycle_progresses):
            if not s:
                continue
            entry = {
                'step': s,
                'count': int(safe_float(c, 0)) if c else None,
                'progress_pct': safe_float(p, None) if p else None,
            }
            cycle_entries.append(entry)

        cost_personnel, cost_machinery, cost_total = calculate_daily_cost(personnel, work_time, machinery_list)

        record = {
            'date': request.form.get('record_date'),
            'personnel': personnel,
            'machinery': machinery_list,
            'work_time': work_time,
            'work_content': work_contents,
            'progress_unit': request.form.get('progress_unit'),
            'progress_value': progress_value,
            'progress_total': progress_total,
            'progress_value_float': progress_value,
            'progress_total_float': progress_total,
            'cycle_entries': cycle_entries,
            'weather': request.form.get('weather'),
            'remarks': request.form.get('remarks'),
            'cost_personnel': cost_personnel,
            'cost_machinery': cost_machinery,
            'cost_total': cost_total,
        }
        daily_records.append(record)
        session['daily_records'] = daily_records
        update_project_from_daily(project_data, daily_records)
        return redirect(url_for('daily_record'))

    recent_records = daily_records[::-1]
    return render_template(
        'daily_record.html',
        page_title='日々の作業記録',
        current_app='record',
        project_data=project_data,
        recent_records=recent_records,
        master_data=MASTER_DATA,
    )

@app.route('/export_excel')
def export_excel():
    daily_records = session.get('daily_records', [])
    project_data = session.get('project_data', {})
    if not daily_records:
        return redirect(url_for('daily_record'))
    # リスト型の機械名を文字列化
    flattened = []
    for rec in daily_records:
        rec_copy = rec.copy()
        if isinstance(rec_copy.get('machinery'), list):
            rec_copy['machinery'] = ", ".join(rec_copy['machinery'])
        flattened.append(rec_copy)

    df = pd.DataFrame(flattened)
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


@app.route('/workmaster_proto_basic', methods=['GET', 'POST'])
def workmaster_proto_basic():
    project = ensure_proto_project_session()
    if request.method == 'POST':
        project.update({
            'site_name': request.form.get('site_name', project.get('site_name', '')),
            'task_name': request.form.get('task_name', project.get('task_name', '')),
            'planned_quantity': safe_float(request.form.get('planned_quantity'), project.get('planned_quantity', 0.0)),
            'planned_unit': request.form.get('planned_unit', project.get('planned_unit', '')),
            'design_link': request.form.get('design_link', project.get('design_link', '')),
            'budget': {
                'labor': safe_float(request.form.get('budget_labor'), project.get('budget', {}).get('labor', 0)),
                'machine': safe_float(request.form.get('budget_machine'), project.get('budget', {}).get('machine', 0)),
                'materials': safe_float(request.form.get('budget_materials'), project.get('budget', {}).get('materials', 0)),
            },
            'cycle_steps': request.form.getlist('step[]'),
            'cycle_checks': request.form.getlist('check[]'),
            'tool_list': request.form.get('tool_list', ''),
        })
        session['proto_project_data'] = project
        return redirect(url_for('workmaster_proto_daily'))

    return render_template(
        'workmaster_proto_basic.html',
        page_title='歩掛マスター（プロトタイプ）',
        current_app='workmaster_proto',
        project_data=project,
        master_data=MASTER_DATA,
    )


@app.route('/workmaster_proto_daily', methods=['GET', 'POST'])
def workmaster_proto_daily():
    project_data = ensure_proto_project_session()
    daily_records = session.get('proto_daily_records', [])
    if request.method == 'POST':
        machinery_list = request.form.getlist('machinery[]')
        work_contents = request.form.getlist('work_content[]')
        progress_value = safe_float(request.form.get('progress_value'))
        progress_total = safe_float(request.form.get('progress_total'), project_data.get('planned_quantity', 0.0))
        personnel = int(safe_float(request.form.get('personnel'), 0))
        work_time = safe_float(request.form.get('work_time'), 0)

        cycle_steps = request.form.getlist('cycle_step[]')
        cycle_counts = request.form.getlist('cycle_count[]')
        cycle_progresses = request.form.getlist('cycle_progress[]')
        cycle_entries = []
        for s, c, p in zip(cycle_steps, cycle_counts, cycle_progresses):
            if not s:
                continue
            entry = {
                'step': s,
                'count': int(safe_float(c, 0)) if c else None,
                'progress': safe_float(p, None) if p else None,
            }
            cycle_entries.append(entry)

        cost_personnel, cost_machinery, cost_total = calculate_daily_cost(personnel, work_time, machinery_list)

        record = {
            'date': request.form.get('record_date'),
            'personnel': personnel,
            'machinery': machinery_list,
            'work_time': work_time,
            'work_content': work_contents,
            'progress_unit': request.form.get('progress_unit'),
            'progress_value': progress_value,
            'progress_total': progress_total,
            'progress_value_float': progress_value,
            'progress_total_float': progress_total,
            'cycle_entries': cycle_entries,
            'weather': request.form.get('weather'),
            'remarks': request.form.get('remarks'),
            'cost_personnel': cost_personnel,
            'cost_machinery': cost_machinery,
            'cost_total': cost_total,
        }
        daily_records.append(record)
        session['proto_daily_records'] = daily_records
        update_project_from_daily(project_data, daily_records, session_key='proto_project_data')
        return redirect(url_for('workmaster_proto_daily'))

    recent_records = daily_records[::-1]
    return render_template(
        'workmaster_proto_daily.html',
        page_title='歩掛マスター（日報・プロトタイプ）',
        current_app='workmaster_proto',
        project_data=project_data,
        recent_records=recent_records,
        master_data=MASTER_DATA,
    )


@app.route('/workmaster_proto_export')
def workmaster_proto_export():
    daily_records = session.get('proto_daily_records', [])
    project_data = session.get('proto_project_data', {})
    if not daily_records:
        return redirect(url_for('workmaster_proto_daily'))

    flattened = []
    for rec in daily_records:
        rec_copy = rec.copy()
        if isinstance(rec_copy.get('machinery'), list):
            rec_copy['machinery'] = ", ".join(rec_copy['machinery'])
        flattened.append(rec_copy)

    df = pd.DataFrame(flattened)
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
    return render_template(
        'workmaster_proto_daily.html',
        page_title='歩掛マスター（日報・プロトタイプ）',
        current_app='workmaster_proto',
        project_data=project_data,
        recent_records=daily_records[::-1],
        master_data=MASTER_DATA,
        export_message="✅ Excelデータのエクスポート処理が完了しました（ダミー）。",
    )

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
    app.run(debug=True, port=5002)
