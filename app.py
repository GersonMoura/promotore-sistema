# -*- coding: utf-8 -*-
"""
PROMOTORE - Versão Simplificada para Teste
Apenas login e dashboard
"""

from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
import os
import sqlite3

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'promotore-secret-key-2025')

# Função para obter conexão com banco
def get_db_connection():
    """Conecta ao SQLite"""
    conn = sqlite3.connect('promotore.db')
    conn.row_factory = sqlite3.Row
    return conn

# Inicializar banco de dados
def init_db():
    """Cria tabelas se não existirem"""
    try:
        os.makedirs('static/uploads', exist_ok=True)
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Tabela de usuários
        cur.execute('''CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            nome_completo TEXT NOT NULL,
            email TEXT,
            criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        
        # Criar usuário admin padrão se não existir
        cur.execute("SELECT * FROM usuarios WHERE username = 'admin'")
        if not cur.fetchone():
            password_hash = generate_password_hash('admin123')
            cur.execute(
                "INSERT INTO usuarios (username, password_hash, nome_completo, email) VALUES (?, ?, ?, ?)",
                ('admin', password_hash, 'Administrador', 'admin@promotore.com')
            )
        
        conn.commit()
        cur.close()
        conn.close()
        print("✅ Banco de dados inicializado!")
    except Exception as e:
        print(f"❌ Erro ao inicializar banco: {e}")

# Inicializar banco ao importar
init_db()

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html', username=session.get('username'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT id, password_hash, nome_completo FROM usuarios WHERE username = ?", (username,))
            user = cur.fetchone()
            cur.close()
            conn.close()
            
            if user and check_password_hash(user['password_hash'], password):
                session['user_id'] = user['id']
                session['username'] = username
                session['nome_completo'] = user['nome_completo']
                return redirect(url_for('index'))
            else:
                return render_template('login.html', erro="Usuário ou senha inválidos")
        except Exception as e:
            print(f"Erro no login: {e}")
            return render_template('login.html', erro=f"Erro: {e}")
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)

