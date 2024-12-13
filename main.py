from flask import Flask, render_template, request, session, redirect, url_for, flash
from supabase import create_client
from dotenv import load_dotenv
import os
import re

# Configuração inicial
load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "default_secret_key")

# Configuração do Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Variáveis de ambiente SUPABASE_URL e SUPABASE_KEY não configuradas.")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Função para validar email
def is_valid_email(email):
    email_regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z]{2,}(\.[a-zA-Z]{2,})*$'
    return re.match(email_regex, email) is not None

# Rota inicial
@app.route('/')
def index():
    if 'user_id' in session:
        return render_template('dashboard.html', user_id=session['user_id'])
    return render_template('login.html')

# Rota para registro
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        if not is_valid_email(email):
            flash("Email inválido. Certifique-se de incluir um domínio válido.", "error")
        else:
            try:
                response = supabase.auth.sign_up({"email": email, "password": password})
                if response.user:
                    flash("Usuário registrado com sucesso! Confirme o email recebido.", "success")
                    return redirect(url_for('login'))
                else:
                    flash("Erro ao registrar usuário.", "error")
            except Exception as e:
                flash(f"Erro ao registrar usuário: {e}", "error")
    return render_template('register.html')

# Rota para login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        try:
            response = supabase.auth.sign_in_with_password({"email": email, "password": password})
            if response.user:
                session['user_id'] = response.user.id
                flash("Login realizado com sucesso!", "success")
                return redirect(url_for('dashboard'))
            else:
                flash("Email ou senha inválidos.", "error")
        except Exception as e:
            flash(f"Erro ao autenticar: {e}", "error")
    return render_template('login.html')

# Rota para logout
@app.route('/logout')
def logout():
    session.clear()
    flash("Logout realizado com sucesso.", "success")
    return redirect(url_for('index'))

# Rota do dashboard
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html', user_id=session['user_id'])

# Rota para gerenciador de vendas
@app.route('/sales')
def sales():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('sales.html')

# Rota para gerenciador financeiro
@app.route('/finances')
def finances():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('finances.html')

# Rota para gerenciador de investimentos
@app.route('/investments')
def investments():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('investments.html')

if __name__ == '__main__':
    app.run(debug=True)