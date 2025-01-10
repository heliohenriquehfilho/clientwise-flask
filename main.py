from flask import Flask, render_template, request, session, redirect, url_for, flash
from supabase import create_client
from dotenv import load_dotenv
from obter_dados_tabela import obter_dados_tabela
import pandas as pd
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

def calcular_valor_total(preco, desconto, quantidade):
    """Calcula o valor total do produto."""
    return round((preco - (preco * (desconto / 100))) * quantidade, 2)

# Lista de vendas fictícias
vendas = []

def obter_dados_tabela(nome_tabela, user_id=None):
    """Busca dados da Supabase com tratamento de exceção."""
    try:
        query = supabase.table(nome_tabela).select("nome")
        if user_id:
            query = query.eq("user_id", user_id)
        dados = query.execute().data
        return dados or []
    except Exception as e:
        print(f"Erro ao buscar {nome_tabela}: {e}")
        return []

def formatar_produtos(produtos_json):
    if produtos_json is None:
        return ""  # Retorna uma string vazia caso o valor seja None

    produtos_formatados = []
    for produto in produtos_json:
        if all(key in produto for key in ['nome', 'quantidade', 'desconto', 'preco']):
            produtos_formatados.append(f"{produto['nome']} - Quantidade: {produto['quantidade']} - Desconto: {produto['desconto']}% - Preço: R${produto['preco']}")
    
    return ", ".join(produtos_formatados)

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

@app.route('/sales', methods=['GET', 'POST'])
def sales():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']

    clientes = obter_dados_tabela("clientes", user_id)
    produtos = obter_dados_tabela("produtos", user_id)
    vendedores = obter_dados_tabela("vendedores", user_id)

    if request.method == 'POST':
        venda_id = request.form.get('venda_id')
        if venda_id:
            supabase.table("vendas").delete().eq("id", venda_id).execute()
            flash(f"Venda '{venda_id}' excluída com sucesso.", "success")

    vendas = supabase.table("vendas").select("*").eq("user_id", user_id).execute().data
    
    if vendas:
        for venda in vendas:
            venda['produtos_formatados'] = formatar_produtos(venda.get('produtos'))

        vendas_df = pd.DataFrame(vendas)
        return render_template('sales.html', vendas=vendas_df.to_dict(orient='records'))
    
    flash("Nenhuma venda encontrada.", "info")
    return render_template('sales.html', clientes=clientes, produtos=produtos, vendedores=vendedores)

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

@app.route('/cadastro_venda', methods=["GET", "POST"])
def cadastro_venda():
    user_id = session.get('user_id')
    if not user_id:
        flash("Faça login para acessar esta funcionalidade.", "error")
        return redirect(url_for('login'))

    clientes = obter_dados_tabela("clientes", user_id)
    produtos = obter_dados_tabela("produtos", user_id)
    vendedores = obter_dados_tabela("vendedores", user_id)

    if not clientes:
        flash("Nenhum cliente encontrado. Cadastre clientes primeiro.", "info")

    # Lógica de cadastro de venda permanece inalterada...
    return render_template("sales.html", clientes=clientes, produtos=produtos, vendedores=vendedores)


if __name__ == '__main__':
    app.run(debug=True)