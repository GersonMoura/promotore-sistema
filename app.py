# -*- coding: utf-8 -*-
"""
PROMOTORE - Sistema Web de Conferência Cadastral
Versão PostgreSQL para Render.com
"""

from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import os
import json
from datetime import datetime
from openai import OpenAI
from pdf2image import convert_from_path
import base64
from io import BytesIO
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
# Importar biblioteca de banco conforme disponibilidade
USE_POSTGRES = False
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    from urllib.parse import urlparse
    if os.environ.get('DATABASE_URL'):
        USE_POSTGRES = True
        print("✅ Usando PostgreSQL")
    else:
        print("⚠️  DATABASE_URL não configurada, usando SQLite")
except ImportError:
    print("⚠️  psycopg2 não disponível, usando SQLite")

if not USE_POSTGRES:
    import sqlite3

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'promotore-secret-key-change-in-production')
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max
app.config['ALLOWED_EXTENSIONS'] = {'pdf', 'jpg', 'jpeg', 'png'}

# Configurar OpenAI
client = OpenAI()

# Função para obter conexão com banco
def get_db_connection():
    """Conecta ao PostgreSQL ou SQLite conforme disponibilidade"""
    if USE_POSTGRES:
        database_url = os.environ.get('DATABASE_URL')
        # Render usa postgres:// mas psycopg2 precisa de postgresql://
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        conn = psycopg2.connect(database_url, sslmode='require')
        return conn
    else:
        # Usar SQLite local
        conn = sqlite3.connect('promotore.db')
        conn.row_factory = sqlite3.Row
        return conn

# Inicializar banco de dados
def init_db():
    """Cria tabelas se não existirem"""
    try:
        # Criar pasta uploads se não existir
        os.makedirs('static/uploads', exist_ok=True)
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        if USE_POSTGRES:
            # Tabela de usuários (PostgreSQL)
            cur.execute('''CREATE TABLE IF NOT EXISTS usuarios (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                nome_completo VARCHAR(255) NOT NULL,
                email VARCHAR(255),
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
            
            # Tabela de processos (PostgreSQL)
            cur.execute('''CREATE TABLE IF NOT EXISTS processos (
                id SERIAL PRIMARY KEY,
                nome_cliente VARCHAR(255) NOT NULL,
                cpf VARCHAR(20),
                usuario_id INTEGER REFERENCES usuarios(id),
                status VARCHAR(50),
                score_conformidade INTEGER,
                conformidades INTEGER,
                alertas INTEGER,
                inconsistencias INTEGER,
                dados_extraidos TEXT,
                relatorio_path VARCHAR(500),
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
            
            # Tabela de documentos (PostgreSQL)
            cur.execute('''CREATE TABLE IF NOT EXISTS documentos (
                id SERIAL PRIMARY KEY,
                processo_id INTEGER REFERENCES processos(id),
                nome_arquivo VARCHAR(255) NOT NULL,
                tipo_documento VARCHAR(100),
                caminho_arquivo VARCHAR(500) NOT NULL,
                processado BOOLEAN DEFAULT FALSE,
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
        else:
            # Tabela de usuários (SQLite)
            cur.execute('''CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                nome_completo TEXT NOT NULL,
                email TEXT,
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )''')
            
            # Tabela de processos (SQLite)
            cur.execute('''CREATE TABLE IF NOT EXISTS processos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome_cliente TEXT NOT NULL,
                cpf TEXT,
                usuario_id INTEGER,
                status TEXT,
                score_conformidade INTEGER,
                conformidades INTEGER,
                alertas INTEGER,
                inconsistencias INTEGER,
                dados_extraidos TEXT,
                relatorio_path TEXT,
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
            )''')
            
            # Tabela de documentos (SQLite)
            cur.execute('''CREATE TABLE IF NOT EXISTS documentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                processo_id INTEGER,
                nome_arquivo TEXT NOT NULL,
                tipo_documento TEXT,
                caminho_arquivo TEXT NOT NULL,
                processado INTEGER DEFAULT 0,
                criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (processo_id) REFERENCES processos(id)
            )''')
        
        # Criar usuário admin padrão se não existir
        cur.execute("SELECT * FROM usuarios WHERE username = 'admin'")
        if not cur.fetchone():
            password_hash = generate_password_hash('admin123')
            if USE_POSTGRES:
                cur.execute(
                    "INSERT INTO usuarios (username, password_hash, nome_completo, email) VALUES (%s, %s, %s, %s)",
                    ('admin', password_hash, 'Administrador', 'admin@promotore.com')
                )
            else:
                cur.execute(
                    "INSERT INTO usuarios (username, password_hash, nome_completo, email) VALUES (?, ?, ?, ?)",
                    ('admin', password_hash, 'Administrador', 'admin@promotore.com')
                )
        
        conn.commit()
        cur.close()
        conn.close()
        print("✅ Banco de dados inicializado com sucesso!")
    except Exception as e:
        print(f"❌ Erro ao inicializar banco: {e}")
        raise

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def processar_documento_gpt4(caminho_pdf, prompt):
    """Processa documento com GPT-4 Vision"""
    images = convert_from_path(caminho_pdf, dpi=300)
    
    messages = [{
        "role": "user",
        "content": [{"type": "text", "text": prompt}]
    }]
    
    for image in images:
        buffered = BytesIO()
        image.save(buffered, format="PNG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode()
        
        messages[0]["content"].append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{img_base64}"
            }
        })
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        max_tokens=4096
    )
    
    return response.choices[0].message.content

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', username=session.get('username'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT id, password_hash, nome_completo FROM usuarios WHERE username = %s", (username,))
            user = cur.fetchone()
            cur.close()
            conn.close()
            
            if user and check_password_hash(user[1], password):
                session['user_id'] = user[0]
                session['username'] = username
                session['nome_completo'] = user[2]
                return redirect(url_for('index'))
            else:
                return render_template('login.html', erro="Usuário ou senha inválidos")
        except Exception as e:
            print(f"Erro no login: {e}")
            return render_template('login.html', erro="Erro ao conectar ao banco de dados")
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/novo_processo', methods=['GET', 'POST'])
def novo_processo():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        nome_cliente = request.form.get('nome_cliente')
        cpf = request.form.get('cpf')
        
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO processos (nome_cliente, cpf, usuario_id, status) VALUES (%s, %s, %s, %s) RETURNING id",
            (nome_cliente, cpf, session['user_id'], 'aguardando_documentos')
        )
        processo_id = cur.fetchone()[0]
        conn.commit()
        cur.close()
        conn.close()
        
        return redirect(url_for('ver_processo', processo_id=processo_id))
    
    return render_template('novo_processo.html')

@app.route('/processos')
def processos():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT * FROM processos WHERE usuario_id = %s ORDER BY criado_em DESC",
        (session['user_id'],)
    )
    processos = cur.fetchall()
    cur.close()
    conn.close()
    
    return render_template('processos.html', processos=processos)

@app.route('/processo/<int:processo_id>')
def ver_processo(processo_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT * FROM processos WHERE id = %s AND usuario_id = %s", (processo_id, session['user_id']))
    processo = cur.fetchone()
    
    cur.execute("SELECT nome_arquivo, tipo_documento, criado_em FROM documentos WHERE processo_id = %s", (processo_id,))
    documentos = cur.fetchall()
    
    cur.close()
    conn.close()
    
    if not processo:
        return "Processo não encontrado", 404
    
    return render_template('processo_detalhes.html', processo=processo, documentos=documentos)

@app.route('/upload/<int:processo_id>', methods=['POST'])
def upload_documentos(processo_id):
    if 'user_id' not in session:
        return jsonify({"erro": "Não autenticado"}), 401
    
    if 'files[]' not in request.files:
        return jsonify({"erro": "Nenhum arquivo enviado"}), 400
    
    files = request.files.getlist('files[]')
    uploaded_files = []
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"{processo_id}_{timestamp}_{filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            file.save(filepath)
            
            cur.execute(
                "INSERT INTO documentos (processo_id, nome_arquivo, caminho_arquivo) VALUES (%s, %s, %s)",
                (processo_id, file.filename, filepath)
            )
            
            uploaded_files.append(file.filename)
    
    conn.commit()
    cur.close()
    conn.close()
    
    return jsonify({"sucesso": True, "arquivos": uploaded_files})

@app.route('/processar/<int:processo_id>', methods=['POST'])
def processar_processo(processo_id):
    if 'user_id' not in session:
        return jsonify({"erro": "Não autenticado"}), 401
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT caminho_arquivo, nome_arquivo FROM documentos WHERE processo_id = %s", (processo_id,))
        documentos = cur.fetchall()
        
        if not documentos:
            return jsonify({"erro": "Nenhum documento encontrado"}), 400
        
        # Processar documentos (simplificado)
        dados_extraidos = {}
        for doc in documentos:
            try:
                prompt = f"Extraia as informações principais deste documento: {doc[1]}"
                resultado = processar_documento_gpt4(doc[0], prompt)
                dados_extraidos[doc[1]] = resultado
            except Exception as e:
                dados_extraidos[doc[1]] = f"Erro: {str(e)}"
        
        # Atualizar processo
        cur.execute(
            "UPDATE processos SET status = %s, dados_extraidos = %s, score_conformidade = %s WHERE id = %s",
            ('processado', json.dumps(dados_extraidos), 85, processo_id)
        )
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({"sucesso": True, "mensagem": "Processamento concluído!"})
    
    except Exception as e:
        return jsonify({"erro": str(e)}), 500

@app.route('/api/estatisticas')
def api_estatisticas():
    if 'user_id' not in session:
        return jsonify({"erro": "Não autenticado"}), 401
    
    conn = get_db_connection()
    cur = conn.cursor()
    
    cur.execute("SELECT COUNT(*) FROM processos WHERE usuario_id = %s", (session['user_id'],))
    total = cur.fetchone()[0]
    
    cur.execute("SELECT COUNT(*) FROM processos WHERE usuario_id = %s AND status = %s", (session['user_id'], 'processado'))
    concluidos = cur.fetchone()[0]
    
    pendentes = total - concluidos
    
    cur.close()
    conn.close()
    
    return jsonify({
        "total": total,
        "concluidos": concluidos,
        "pendentes": pendentes
    })

@app.route('/api/processos-recentes')
def api_processos_recentes():
    if 'user_id' not in session:
        return jsonify({"erro": "Não autenticado"}), 401
    
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, nome_cliente, cpf, status, criado_em FROM processos WHERE usuario_id = %s ORDER BY criado_em DESC LIMIT 5",
        (session['user_id'],)
    )
    
    processos = []
    for row in cur.fetchall():
        processos.append({
            "id": row[0],
            "nome_cliente": row[1],
            "cpf": row[2],
            "status": row[3],
            "criado_em": str(row[4])
        })
    
    cur.close()
    conn.close()
    
    return jsonify(processos)

if __name__ == '__main__':
    # Inicializar banco ao iniciar
    try:
        init_db()
    except Exception as e:
        print(f"Aviso: Não foi possível inicializar banco: {e}")
    
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)

