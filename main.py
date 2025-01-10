from flask import Flask, render_template, request, session, redirect, url_for, flash
from supabase import create_client
from dotenv import load_dotenv
from obter_dados_tabela import obter_dados_tabela
import pandas as pd
import datetime
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

@app.route("/cadastro_cliente", methods=["GET", "POST"])
def cadastro_cliente():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == "POST":
        opcao_cadastro = request.form.get("opcao_cadastro")

        if opcao_cadastro == "manual":
            cliente = {
                "nome": request.form.get("nome"),
                "contato": request.form.get("contato"),
                "endereco": request.form.get("endereco"),
                "email": request.form.get("email"),
                "user_id": session['user_id']
            }

            if all(cliente.values()):
                # Verificar duplicação
                try:
                    resposta = supabase.table("clientes") \
                        .select("id") \
                        .filter("nome", "eq", cliente["nome"]) \
                        .filter("contato", "eq", cliente["contato"]) \
                        .filter("endereco", "eq", cliente["endereco"]) \
                        .filter("email", "eq", cliente["email"]) \
                        .filter("user_id", "eq", cliente["user_id"]) \
                        .execute()

                    if resposta.data:
                        flash("Cliente já cadastrado!", "danger")
                    else:
                        supabase.table("clientes").insert(cliente).execute()
                        flash("Cliente cadastrado com sucesso!", "success")
                except Exception as e:
                    flash(f"Erro ao cadastrar cliente: {e}", "danger")
            else:
                flash("Por favor, preencha todos os campos.", "danger")

        elif opcao_cadastro == "csv":
            file = request.files.get("csv_file")
            if file and file.filename.endswith(".csv"):
                try:
                    data = pd.read_csv(file)
                    for _, row in data.iterrows():
                        cliente = {
                            "nome": row.get("nome"),
                            "contato": row.get("contato"),
                            "endereco": row.get("endereco", ""),
                            "email": row.get("email"),
                            "user_id": session['user_id']
                        }

                        # Validar campos e evitar duplicados
                        if all([cliente["nome"], cliente["contato"], cliente["email"]]):
                            resposta = supabase.table("clientes") \
                                .select("id") \
                                .filter("nome", "eq", cliente["nome"]) \
                                .filter("contato", "eq", cliente["contato"]) \
                                .filter("email", "eq", cliente["email"]) \
                                .filter("user_id", "eq", cliente["user_id"]) \
                                .execute()

                            if not resposta.data:
                                supabase.table("clientes").insert(cliente).execute()
                    flash("Importação concluída!", "success")
                except Exception as e:
                    flash(f"Erro ao processar o CSV: {e}", "danger")
            else:
                flash("Por favor, envie um arquivo CSV válido.", "danger")

    return render_template("clientes.html")

min_date = datetime.date(1900, 1, 1)

@app.route("/clientes", methods=["GET", "POST"])
def clientes():
    user_id = session['user_id']
    clientes = supabase.table("clientes").select("*").eq("user_id", user_id).execute().data
    vendas = supabase.table("vendas").select("*").eq("user_id", user_id).execute().data

    # Convertendo a coluna 'ativo' de True/False para texto
    for cliente in clientes:
        cliente["ativo"] = "Ativo" if cliente["ativo"] else "Inativo"

    if request.method == "POST":
        # Atualizar cliente
        cliente_id = request.form.get("client_id")
        nome = request.form.get("nome")
        contato = request.form.get("contato")
        endereco = request.form.get("endereco")
        email = request.form.get("email")
        bairro = request.form.get("bairro")
        cidade = request.form.get("cidade")
        estado = request.form.get("estado")
        cep = request.form.get("cep")
        ativo = request.form.get("ativo") == "on"
        genero = request.form.get("genero")
        data_nascimento = request.form.get("data_nascimento")

        cliente_atualizado = {
            "nome": nome,
            "contato": contato,
            "endereco": endereco,
            "email": email,
            "bairro": bairro,
            "cidade": cidade,
            "estado": estado,
            "cep": cep,
            "ativo": ativo,
            "genero": genero,
            "data_nascimento": data_nascimento,
        }

        supabase.table("clientes").update(cliente_atualizado).eq("client__c", cliente_id).execute()
        flash("Cliente atualizado com sucesso!", "success")
        return redirect(url_for("gerenciador_de_clientes"))

    return render_template("gerenciador_clientes.html", clientes=clientes, vendas=vendas, min_date=min_date)


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