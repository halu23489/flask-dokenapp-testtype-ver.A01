import os
import io
import zipfile
import logging
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, send_file, flash, g, session, jsonify
from PIL import Image
import ezdxf
import pandas as pd
from io import StringIO, BytesIO
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import re
from werkzeug.routing import BuildError

# optional HEIC support
try:
    import pillow_heif
    pillow_heif.register_heif_opener()
    HEIF_AVAILABLE = True
except Exception:
    HEIF_AVAILABLE = False

# ログを抑制
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

# --- 定数定義 ---
MAX_TAGS = 5
FORBIDDEN_WORDS = ['spam', 'test']
MAX_ARTICLE_LENGTH = 5000
MAX_COMMENT_LENGTH = 1000

def check_spam_content(body, max_len):
    """プレースホルダーのスパムチェック関数"""
    if len(body) > max_len:
        return True, f"本文が長すぎます (最大 {max_len} 文字)"
    return False, ""

# --- アプリ設定 ---
app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET', 'your_super_secret_key_z_system_proto_0')
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

APP_NAME = 'ITショクチョー！'
APP_CONFIG = {
    'app_name': APP_NAME,
    'app_title': 'Ζシステムシリーズ：現場の総合アプリ',
    'app_subtitle': '現場に携わる技術者のための',
    'nav': {
        'home': {'name': '🏠 ホーム', 'url': 'index'},
    }
}

DB_PATH = os.path.join(os.path.dirname(__file__), 'data.db')

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db

def init_db():
    db = sqlite3.connect(DB_PATH)
    cur = db.cursor()
    cur.execute('''
    CREATE TABLE IF NOT EXISTS articles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        body TEXT NOT NULL,
        tags TEXT,
        created_at TEXT NOT NULL
    )
    ''')
    cur.execute('''
    CREATE TABLE IF NOT EXISTS comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        article_id INTEGER NOT NULL,
        body TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(article_id) REFERENCES articles(id) ON DELETE CASCADE
    )
    ''')
    db.commit()
    db.close()

try:
    init_db()
except Exception:
    logging.getLogger(__name__).warning('DB 初期化に失敗しました（起動後に再試行してください）。')

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

app.jinja_env.globals.update(zip=zip, enumerate=enumerate, len=len)

def safe_url_for(endpoint, **values):
    """url_for を安全に呼び出す。存在しない endpoint の場合は '#' を返す"""
    try:
        return url_for(endpoint, **values)
    except BuildError:
        return '#'

app.jinja_env.globals['safe_url_for'] = safe_url_for

@app.context_processor
def inject_global_config():
    return {
        'app_name': APP_CONFIG['app_name'],
        'app_title': APP_CONFIG['app_title'],
        'app_subtitle': APP_CONFIG['app_subtitle'],
        'nav': APP_CONFIG['nav'],
        'safe_url_for': safe_url_for,
    }

# レートリミッター設定
storage_uri = os.environ.get('RATELIMIT_STORAGE_URI', 'memory://')
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per hour"],
    storage_uri=storage_uri,
    app=app
)

# ===== ホームページ =====
@app.route('/')
def index():
    """スマホアプリ風のホームダッシュボード"""
    ctx = {
        'page_title': 'ホーム',
        'current_app': 'home',
    }
    return render_template('index.html', **ctx)

# ===== 歩掛マスター =====
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
    return render_template('workmaster_basic.html', page_title='歩掛マスター：基本情報入力', current_app='workmaster', data=data)

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
    return render_template('workmaster_detail.html', page_title='歩掛マスター：詳細内容入力', current_app='workmaster', data=data)

@app.route('/workmaster_daily', methods=['GET', 'POST'])
def workmaster_daily():
    basic = session.get('workmaster_basic', {})
    detail = session.get('workmaster_detail', {})
    daily_records = session.get('workmaster_daily_records', [])
    
    if request.method == 'POST':
        record = {
            'date': request.form.get('date'),
            'workers': request.form.get('workers'),
            'operators': request.form.get('operators'),
            'machines': request.form.get('machines'),
            'hours': request.form.get('hours'),
            'weather': request.form.get('weather'),
            'progress': request.form.get('progress'),
            'remarks': request.form.get('remarks'),
        }
        daily_records.append(record)
        session['workmaster_daily_records'] = daily_records
        return redirect(url_for('workmaster_daily'))
    
    return render_template('workmaster_daily.html', page_title='歩掛マスター：日次記録', current_app='workmaster', basic=basic, detail=detail, records=daily_records)

@app.route('/workmaster_export_excel')
def workmaster_export_excel():
    basic = session.get('workmaster_basic', {})
    detail = session.get('workmaster_detail', {})
    daily_records = session.get('workmaster_daily_records', [])
    
    if not daily_records:
        flash('記録データがありません。', 'warning')
        return redirect(url_for('workmaster_daily'))
    
    try:
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            # 基本情報シート
            basic_df = pd.DataFrame([basic]).T
            basic_df.columns = ['内容']
            basic_df.to_excel(writer, sheet_name='基本情報')
            
            # 詳細情報シート
            detail_df = pd.DataFrame([detail]).T
            detail_df.columns = ['内容']
            detail_df.to_excel(writer, sheet_name='詳細情報')
            
            # 日次記録シート
            records_df = pd.DataFrame(daily_records)
            records_df.to_excel(writer, sheet_name='日次記録', index=False)
        
        output.seek(0)
        return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                        as_attachment=True, download_name='workmaster_export.xlsx')
    except Exception as e:
        flash(f'Excel出力に失敗しました: {e}', 'danger')
        return redirect(url_for('workmaster_daily'))

# ===== HEIC to JPG 変換 =====
@app.route('/converter')
def converter_page():
    """HEIC to JPG 変換ページ"""
    ctx = {
        'page_title': 'HEIC to JPG 変換',
        'current_app': 'converter',
        'HEIF_AVAILABLE': HEIF_AVAILABLE
    }
    return render_template('converter.html', **ctx)

@app.route('/convert', methods=['POST'])
@limiter.limit("30 per hour")
def convert_file():
    heic_files = request.files.getlist('heic_file')
    
    if not heic_files or all(f.filename == '' for f in heic_files):
        flash('ファイルが選択されていません。', 'warning')
        return redirect(url_for('converter_page'))
    
    if not HEIF_AVAILABLE:
        flash('サーバーに HEIC を処理するライブラリ(pillow-heif)がインストールされていません。', 'danger')
        return redirect(url_for('converter_page'))
    
    zip_buffer = io.BytesIO()
    converted_count = 0
    
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for heic in heic_files:
            if heic.filename == '' or not heic.filename.lower().endswith(('.heic', '.heif')):
                continue
            
            try:
                original_name = heic.filename
                base = os.path.splitext(original_name)[0]
                jpg_filename = f'{base}.jpg'
                
                data = heic.read()
                img = Image.open(io.BytesIO(data))
                
                exif = img.info.get('exif', None)
                rgb = img.convert('RGB')
                
                jpg_buffer = io.BytesIO()
                save_kwargs = {'format': 'JPEG', 'quality': 95}
                if exif:
                    save_kwargs['exif'] = exif
                
                rgb.save(jpg_buffer, **save_kwargs)
                jpg_buffer.seek(0)
                
                zf.writestr(jpg_filename, jpg_buffer.getvalue())
                converted_count += 1
            except Exception as e:
                logging.warning(f"ファイル '{heic.filename}' の変換に失敗: {e}")
                pass
    
    if converted_count == 0:
        flash('有効なHEICファイルの変換にすべて失敗しました。', 'danger')
        return redirect(url_for('converter_page'))
    
    zip_buffer.seek(0)
    flash(f'{converted_count} 件のHEICファイルをJPGに変換しました。', 'success')
    return send_file(zip_buffer, mimetype='application/zip', as_attachment=True, download_name='Converted_HEIC_Files.zip')

# ===== 単位換算 =====
@app.route('/unit_converter', methods=['GET', 'POST'])
def unit_converter_page():
    MATERIALS = {
        'soil_compacted': {'label': '土(締固め)', 'density': 1700},
        'crushed_stone': {'label': '砕石', 'density': 2000},
        'concrete_rebar': {'label': 'コンクリート（有筋）', 'density': 2400},
        'concrete_plain': {'label': 'コンクリート（無筋）', 'density': 2350},
        'asphalt': {'label': 'アスファルト', 'density': 2300},
        'steel': {'label': '鋼材', 'density': 7850},
    }
    
    result = None
    if request.method == 'POST':
        try:
            mode = request.form.get('mode', 'unit')
            weight_table = {'kg':1.0, 'g':0.001, 't':1000.0, 'lb':0.45359237}
            volume_table = {'m3':1.0, 'l':0.001, 'ml':0.000001}
            
            if mode == 'unit':
                category = request.form.get('category', 'length')
                value = float(request.form.get('value', '0') or 0)
                frm = request.form.get('from_unit')
                to = request.form.get('to_unit')
                
                def convert(value, frm, to, table):
                    base = value * table[frm]
                    return base / table[to]
                
                if category == 'length':
                    table = {'m':1.0, 'cm':0.01, 'mm':0.001, 'km':1000.0, 'ft':0.3048, 'in':0.0254}
                elif category == 'weight':
                    table = weight_table
                elif category == 'volume':
                    table = volume_table
                else:
                    raise ValueError('未対応のカテゴリ')
                
                if frm not in table or to not in table:
                    raise ValueError('不正な単位')
                
                out_val = convert(value, frm, to, table)
                result = {
                    'mode': 'unit',
                    'value': value,
                    'from': frm,
                    'to': to,
                    'out': round(out_val, 6)
                }
            else:  # material mode
                direction = request.form.get('direction', 'vol_to_mass')
                value = float(request.form.get('value', '0') or 0)
                vol_unit = request.form.get('vol_unit', 'm3')
                mass_unit = request.form.get('mass_unit', 'kg')
                material_key = request.form.get('material')
                if material_key not in MATERIALS:
                    raise ValueError('不正な材料')
                
                density = MATERIALS[material_key]['density']
                
                if vol_unit not in volume_table or mass_unit not in weight_table:
                    raise ValueError('不正な単位')
                
                if direction == 'vol_to_mass':
                    vol_m3 = value * volume_table[vol_unit]
                    mass_kg = vol_m3 * density
                    out_mass = mass_kg / weight_table[mass_unit]
                    result = {
                        'mode': 'material',
                        'direction': direction,
                        'material': MATERIALS[material_key]['label'],
                        'value': value,
                        'from_unit': vol_unit,
                        'to_unit': mass_unit,
                        'out': round(out_mass, 6),
                        'density': density
                    }
                else:
                    mass_kg = value * weight_table[mass_unit]
                    vol_m3 = mass_kg / density
                    out_vol = vol_m3 / volume_table[vol_unit]
                    result = {
                        'mode': 'material',
                        'direction': direction,
                        'material': MATERIALS[material_key]['label'],
                        'value': value,
                        'from_unit': mass_unit,
                        'to_unit': vol_unit,
                        'out': round(out_vol, 6),
                        'density': density
                    }
        except Exception as e:
            flash(f'換算に失敗しました: {e}', 'danger')
    
    ctx = {
        'page_title': '単位換算',
        'current_app': 'unit_converter',
        'result': result,
        'materials': MATERIALS
    }
    return render_template('unit_converter.html', **ctx)

# ===== DXF座標出力 =====
@app.route('/dxf_tool')
def dxf_tool_page():
    ctx = {
        'page_title': 'DXF座標出力ツール',
        'current_app': 'dxf_tool'
    }
    return render_template('dxf_tool.html', **ctx)

@app.route('/generate_dxf', methods=['POST'])
@limiter.limit("60 per hour")
def generate_dxf():
    coord_text = (request.form.get('coordinate_data') or '').strip()
    layer_name = (request.form.get('app_layer') or 'POINTS').strip()
    filename = (request.form.get('dxf_name') or 'coordinate_output').strip()
    
    if not coord_text:
        flash('座標データが入力されていません。', 'warning')
        return redirect(url_for('dxf_tool_page'))
    
    points = []
    for raw_line in coord_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = [p.strip() for p in line.split(',') if p.strip()]
        if len(parts) == 1:
            continue
        if len(parts) == 2:
            label = ''
            try:
                x = float(parts[0])
                y = float(parts[1])
            except Exception:
                continue
        else:
            try:
                x = float(parts[-2])
                y = float(parts[-1])
                label = ','.join(parts[:-2])
            except Exception:
                continue
        points.append({'label': label, 'x': x, 'y': y})
    
    if not points:
        flash('有効な座標が見つかりませんでした。フォーマットを確認してください。', 'warning')
        return redirect(url_for('dxf_tool_page'))
    
    try:
        doc = ezdxf.new(dxfversion='R2010')
        if layer_name not in doc.layers:
            doc.layers.new(name=layer_name)
        msp = doc.modelspace()
        
        for pt in points:
            x, y = pt['x'], pt['y']
            msp.add_point((x, y), dxfattribs={'layer': layer_name})
            if pt['label']:
                txt = msp.add_text(str(pt['label']), dxfattribs={'height': 0.25, 'layer': layer_name})
                txt.set_pos((x + 0.2, y + 0.2), align='LEFT')
        
        buf = BytesIO()
        doc.saveas(buf)
        buf.seek(0)
        download_name = f"{filename}.dxf"
        return send_file(buf, mimetype='application/dxf', as_attachment=True, download_name=download_name)
    except Exception as e:
        flash(f'DXF 生成に失敗しました: {e}', 'danger')
        return redirect(url_for('dxf_tool_page'))

# ===== 計算ツール =====
@app.route('/calculator')
def calculator():
    ctx = {
        'page_title': '計算ツール',
        'current_app': 'calculator'
    }
    return render_template('calc.html', **ctx)

# ===== 比較見積もりツール =====
@app.route('/comparison_tool')
def comparison_tool_page():
    ctx = {
        'page_title': '比較見積もりツール',
        'current_app': 'comparison_tool'
    }
    return render_template('comparison_tool.html', **ctx)

# ===== フォーラム（詰所） =====
@app.route('/forum', methods=['GET'])
def forum():
    tag = request.args.get('tag', '').strip().lower()
    db = get_db()
    cur = db.cursor()
    if tag:
        like = f'%{tag}%'
        cur.execute("SELECT * FROM articles WHERE lower(tags) LIKE ? ORDER BY created_at DESC", (like,))
    else:
        cur.execute("SELECT * FROM articles ORDER BY created_at DESC")
    articles = cur.fetchall()
    
    def get_tag_list(tags_str):
        return [t.strip() for t in (tags_str or '').split(',') if t.strip()]
    
    ctx = {
        'page_title': '知恵袋・掲示板',
        'current_app': 'forum',
        'articles': articles,
        'tag': tag,
        'get_tag_list': get_tag_list
    }
    return render_template('forum.html', **ctx)

@app.route('/post_article', methods=['POST'])
@limiter.limit("5 per minute")
def post_article_submit():
    title = (request.form.get('title') or '').strip()
    body = (request.form.get('body') or '').strip()
    tags_raw = (request.form.get('tags') or '').strip()
    
    tags = [t.strip().lower() for t in tags_raw.split(',') if t.strip()]
    if len(tags) > MAX_TAGS:
        flash(f'タグは最大 {MAX_TAGS} 個までです。', 'warning')
        return redirect(url_for('forum'))
    
    for t in tags:
        for w in FORBIDDEN_WORDS:
            if w.lower() in t.lower():
                flash('タグに不適切な語句が含まれています。', 'warning')
                return redirect(url_for('forum'))
    tags_joined = ','.join(tags)
    
    if not body:
        flash('本文は必須です。', 'warning')
        return redirect(url_for('forum'))
    
    is_spam, reason = check_spam_content(body, MAX_ARTICLE_LENGTH)
    if is_spam:
        flash(f'投稿を受け付けられません: {reason}', 'warning')
        return redirect(url_for('forum'))
    
    db = get_db()
    cur = db.cursor()
    cur.execute("INSERT INTO articles (title, body, tags, created_at) VALUES (?, ?, ?, ?)",
                (title, body, tags_joined, datetime.utcnow().isoformat()))
    db.commit()
    flash('記事を投稿しました（匿名）。', 'success')
    return redirect(url_for('forum'))

@app.route('/article/<int:article_id>', methods=['GET'])
def view_article(article_id):
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM articles WHERE id = ?", (article_id,))
    article = cur.fetchone()
    if not article:
        flash('記事が見つかりません。', 'warning')
        return redirect(url_for('forum'))
    
    cur.execute("SELECT * FROM comments WHERE article_id = ? ORDER BY created_at ASC", (article_id,))
    comments = cur.fetchall()
    
    similar = []
    if article['tags']:
        tags = [t.strip() for t in article['tags'].split(',') if t.strip()]
        if tags:
            q_like = ' OR '.join(['lower(tags) LIKE ?' for _ in tags])
            params = [f'%{t}%' for t in tags]
            cur.execute(f"SELECT * FROM articles WHERE ({q_like}) AND id != ? ORDER BY created_at DESC LIMIT 6", (*params, article_id))
            similar = cur.fetchall()
    
    def get_tag_list(tags_str):
        return [t.strip() for t in (tags_str or '').split(',') if t.strip()]
    
    ctx = {
        'page_title': article['title'] or '記事',
        'current_app': 'forum',
        'article': article,
        'comments': comments,
        'similar': similar,
        'get_tag_list': get_tag_list
    }
    return render_template('article.html', **ctx)

@app.route('/post_comment/<int:article_id>', methods=['POST'])
@limiter.limit("10 per hour")
def post_comment_submit(article_id):
    body = (request.form.get('comment_body') or '').strip()
    if not body:
        flash('コメントを入力してください。', 'warning')
        return redirect(url_for('view_article', article_id=article_id))
    
    is_spam, reason = check_spam_content(body, MAX_COMMENT_LENGTH)
    if is_spam:
        flash(f'コメントを受け付けられません: {reason}', 'warning')
        return redirect(url_for('view_article', article_id=article_id))
    
    db = get_db()
    cur = db.cursor()
    cur.execute("INSERT INTO comments (article_id, body, created_at) VALUES (?, ?, ?)",
                (article_id, body, datetime.utcnow().isoformat()))
    db.commit()
    flash('コメントを投稿しました（匿名）。', 'success')
    return redirect(url_for('view_article', article_id=article_id))

@app.route('/_routes_debug')
def _routes_debug():
    out = []
    for rule in app.url_map.iter_rules():
        out.append(f"{rule.endpoint} -> {rule.rule} [{','.join(rule.methods)}]")
    return "<br>".join(sorted(out))

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)
