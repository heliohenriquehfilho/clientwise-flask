from logging import exception

from flask import Flask, render_template, request, session, redirect, url_for, flash
from flask import jsonify
from supabase import create_client
from dotenv import load_dotenv
import pandas as pd
import json
import datetime
import os
import re

from routes.login import login

# Initial setup
load_dotenv()
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "default_secret_key")

# Supabase setup
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
        query = supabase.table(nome_tabela).select("*")
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

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        print(f"Tentando registrar: {email}, {password}")  # Log para debug
        if not is_valid_email(email):
            flash("Email inválido. Certifique-se de incluir um domínio válido.", "error")
        else:
            try:
                response = supabase.auth.sign_up({"email": email, "password": password})
                print(f"Resposta Supabase: {response}")  # Log para debug
                if response.user:
                    flash("Usuário registrado com sucesso! Confirme o email recebido.", "success")
                    return redirect(url_for('login_handler'))
                else:
                    flash("Erro ao registrar usuário.", "error")
            except Exception as e:
                print(f"Erro Supabase: {e}")  # Log para debug
                flash(f"Erro ao registrar usuário: {e}", "error")
    return render_template('login.html')

# Rota para login
@app.route('/login', methods=['GET', 'POST'])
def login_handler():
    return login(supabase)

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

@app.route("/edit_cliente", methods=["POST"])
def edit_cliente():
    try:
        client_id = request.form.get("client_id")
        nome = request.form.get("nome")
        contato = request.form.get("contato")
        email = request.form.get("email")
        ativo = request.form.get("ativo") == "on"  # Checkbox retorna "on" se marcado
        genero = request.form.get("genero")

        # Atualizando cliente no Supabase
        cliente_atualizado = {
            "nome": nome,
            "contato": contato,
            "email": email,
            "ativo": ativo,
            "genero": genero,
        }

        supabase.table("clientes").update(cliente_atualizado).eq("client__c", client_id).execute()
        flash("Cliente atualizado com sucesso!", "success")
    except Exception as e:
        flash(f"Erro ao atualizar cliente: {e}", "danger")

    return redirect(url_for("gerenciador_de_clientes"))

min_date = datetime.date(1900, 1, 1)

@app.route("/clientes", methods=["GET", "POST"])
def clientes():
    user_id = session['user_id']
    # Recuperar clientes e vendas do banco de dados
    clientes = supabase.table("clientes").select("*").eq("user_id", user_id).execute().data
    vendas = supabase.table("vendas").select("*").eq("user_id", user_id).execute().data

    # Dados para o gráfico de vendas (agrupando por mês, como exemplo)
    vendas_por_mes = {}
    for venda in vendas:
        mes = venda["data_venda"].split("-")[1]  # Supondo que a data está no formato "YYYY-MM-DD"
        vendas_por_mes[mes] = vendas_por_mes.get(mes, 0) + venda["valor"]

    vendas_labels = list(vendas_por_mes.keys())
    vendas_values = list(vendas_por_mes.values())

    # Dados para o gráfico de clientes ativos/inativos
    ativos = sum(1 for cliente in clientes if cliente["ativo"])
    inativos = len(clientes) - ativos

        # Convertendo a coluna 'ativo' de True/False para texto
    for cliente in clientes:
        cliente["ativo"] = "Ativo" if cliente["ativo"] else "Inativo"

    # Calcular Vendas x Clientes
    vendas_vs_clientes = {}
    cliente_vendas = 0
    for cliente in clientes:
        cliente_vendas = sum(1 for venda in vendas if venda["cliente"] == cliente["nome"])  # contagem de vendas por cliente
        vendas_vs_clientes[cliente["nome"]] = cliente_vendas + 1

    if request.method == "POST":
        # Atualizar cliente
        cliente_id = request.form.get("clientid")
        print(cliente_id)
        nome = request.form.get("editNome")
        contato = request.form.get("editContato")
        endereco = request.form.get("editEndereco")
        email = request.form.get("editEmail")
        bairro = request.form.get("editBairro")
        cidade = request.form.get("editCidade")
        estado = request.form.get("editEstado")
        cep = request.form.get("editCep")
        genero = request.form.get("editGenero")
        data_nascimento = request.form.get("editDataNascimento")

        if not data_nascimento:
            data_nascimento = None

        ativo = request.form.get("editAtivo") == "true"  # Convertendo string para booleano

        cliente_atualizado = {
            "nome": nome,
            "contato": contato,
            "endereco": endereco,
            "email": email,
            "bairro": bairro,
            "cidade": cidade,
            "estado": estado,
            "cep": cep,
            "genero": genero,
            "data_nascimento": data_nascimento,
            "ativo": ativo,
        }

        supabase.table("clientes").update(cliente_atualizado).eq("client__c", cliente_id).execute()
        flash("Cliente atualizado com sucesso!", "success")

        clientes = supabase.table("clientes").select("*").eq("user_id", user_id).execute().data
        vendas = supabase.table("vendas").select("*").eq("user_id", user_id).execute().data

        # Dados para o gráfico de vendas (agrupando por mês, como exemplo)
        vendas_por_mes = {}
        for venda in vendas:
            mes = venda["data_venda"].split("-")[1]  # Supondo que a data está no formato "YYYY-MM-DD"
            vendas_por_mes[mes] = vendas_por_mes.get(mes, 0) + venda["valor"]

        vendas_labels = list(vendas_por_mes.keys())
        vendas_values = list(vendas_por_mes.values())

        # Calcular Vendas x Clientes
        vendas_vs_clientes = {}
        for cliente in clientes:
            cliente_vendas = sum(1 for venda in vendas if venda["cliente"] == cliente["nome"])  # contagem de vendas por cliente
            vendas_vs_clientes[cliente["nome"]] = cliente_vendas  # Armazenar a quantidade de vendas por cliente


        # Passar para o template
        return render_template(
            "gerenciador_clientes.html",
            clientes=clientes,
            vendas=vendas,
            vendas_labels=vendas_labels,
            vendas_values=vendas_values,
            vendas_vs_clientes=vendas_vs_clientes,  # Passando os dados para o histograma
            active_clients_count=ativos,
            inactive_clients_count=inativos,
            min_date=min_date
        )


    # Passar para o template
    return render_template(
        "gerenciador_clientes.html",
        clientes=clientes,
        vendas=vendas,
        vendas_labels=vendas_labels,
        vendas_values=vendas_values,
        vendas_vs_clientes=vendas_vs_clientes,  # Passando os dados para o histograma
        active_clients_count=ativos,
        inactive_clients_count=inativos,
        min_date=min_date
    )


@app.route('/sales', methods=['GET', 'POST'])
def sales():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    clientes = obter_dados_tabela("clientes", user_id)
    produtos = obter_dados_tabela("produtos", user_id)
    vendedores = obter_dados_tabela("vendedores", user_id)

    clientes_df = pd.DataFrame(clientes)
    vendas = supabase.table("vendas").select("*").eq("user_id", user_id).execute().data

    # Processamento de vendas existentes
    if vendas:
        for venda in vendas:
            venda['produtos_formatados'] = formatar_produtos(venda.get('produtos'))
        vendas_df = pd.DataFrame(vendas)
    else:
        vendas_df = pd.DataFrame()

    # Inserção de uma nova venda
    if request.method == "POST":
        produto = request.form.get("produto")
        cliente = request.form.get("cliente")
        vendedor = request.form.get("vendedor")
        data_venda = request.form.get("data_venda")
        pagamento = request.form.get("pagamento")
        quantidade = request.form.get("quantidade")

        # Buscar preço do produto
        preco_unitario = next((p['preco'] for p in produtos if p['nome'] == produto), None)
        if preco_unitario is None:
            flash("Erro: Produto não encontrado.", "fail")
            return redirect(url_for('sales'))

        valor = int(quantidade) * float(preco_unitario)

        venda = {
            "user_id": user_id,
            "produtos": produto,
            "cliente": cliente,
            "vendedor": vendedor,
            "data_venda": data_venda,
            "pagamento": pagamento,
            "quantidade": quantidade,
            "valor": valor,
        }

        try:
            supabase.table("vendas").insert(venda).execute()
            flash("Venda cadastrada com sucesso!", "success")
        except Exception as e:
            flash(f"Erro ao cadastrar venda: {e}", "fail")

        return redirect(url_for('sales'))  # Redirecionamento após POST

    return render_template(
        'sales.html',
        clientes_df=clientes_df.to_dict('records'),
        vendas=vendas_df.to_dict(orient='records'),
        vendedores=vendedores,
        produtos=produtos,
    )

# Rota para gerenciador financeiro
@app.route('/finances')
def finances():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('finances.html')

@app.route('/investments', methods=["GET", "POST"])
def investments():
    user_id = session['user_id']

    # Obtém os investimentos do banco de dados
    investimentos = obter_dados_tabela("investimento", user_id)
    investimentos_df = pd.DataFrame(investimentos)
    investimentos_ativos = investimentos_df[investimentos_df['encerrado'] == False]
    investimento_encerrado = investimentos_df[investimentos_df['encerrado'] == True]

    investimento_selecionado = request.args.get('investimento_selecionado')

    if investimento_selecionado:
        # Use .iterrows() para iterar pelas linhas do DataFrame
        investimento_series = investimentos_df[investimentos_df['investimento__c'] == investimento_selecionado]

        if not investimento_series.empty:
            investimento = investimento_series.iloc[0].to_dict()
            historico_pagamentos = investimento.get("historico_pagamentos", [])
            if isinstance(historico_pagamentos, str):
                historico_pagamentos = json.loads(historico_pagamentos)
            pagamentos = pd.DataFrame(historico_pagamentos)
            pagamentos_vazios = pagamentos.empty  # Verifica se o DataFrame de pagamentos está vazio

            investimentos = obter_dados_tabela("investimento", user_id)
            investimentos_df = pd.DataFrame(investimentos)
            investimentos_ativos = investimentos_df[investimentos_df['encerrado'] == False]
            investimento_encerrado = investimentos_df[investimentos_df['encerrado'] == True]

            return render_template(
                'investments.html',
                investimentos_df=investimentos_ativos.to_dict('records'),
                investimento_encerrado=investimento_encerrado.to_dict('records'),
                investimento=investimento,
                pagamentos=pagamentos,
                pagamentos_vazios=pagamentos_vazios,
            )
        
        if investimento is not None:
            historico_pagamentos = investimento.get("historico_pagamentos", [])
            if isinstance(historico_pagamentos, str):
                historico_pagamentos = json.loads(historico_pagamentos)
            pagamentos = pd.DataFrame(historico_pagamentos)
            pagamentos_vazios = pagamentos.empty  # Verifica se o DataFrame de pagamentos está vazio

            investimentos = obter_dados_tabela("investimento", user_id)
            investimentos_df = pd.DataFrame(investimentos)
            investimentos_ativos = investimentos_df[investimentos_df['encerrado'] == False]
            investimento_encerrado = investimentos_df[investimentos_df['encerrado'] == True]

            return render_template(
                'investments.html', 
                investimentos_df=investimentos_ativos.to_dict('records'),
                investimento_encerrado=investimento_encerrado.to_dict('records'), 
                investimento=investimento, 
                pagamentos=pagamentos, 
                pagamentos_vazios=pagamentos_vazios)

    return render_template(
        'investments.html', 
        investimentos_df=investimentos_ativos.to_dict('records'),
        investimento_encerrado=investimento_encerrado.to_dict('records'))


@app.route('/atualizar_investimento', methods=['POST', 'GET'])
def atualizar_investimento():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "Usuário não autenticado"}), 401

    if not request.is_json:
        return jsonify({"error": "Requisição deve ser JSON"}), 400

    data = request.get_json()

    # Validação dos dados recebidos
    investment_id = data.get('investment_id')
    pagamento_data = data.get('data_pagamento')
    pagamento_valor = data.get('valor_pagamento')
    sentido = data.get('sentido', True)
    encerrar = data.get('encerrar', False)

    if not investment_id or not pagamento_data or not pagamento_valor:
        return jsonify({"error": "Dados insuficientes"}), 400

    try:
        pagamento_valor = float(pagamento_valor)
    except ValueError:
        return jsonify({"error": "Valor do pagamento inválido"}), 400

    # Obtém o investimento específico do banco de dados
    investimentos = obter_dados_tabela("investimento", user_id)
    investimento = next((inv for inv in investimentos if inv["investimento__c"] == investment_id), None)

    if not investimento:
        return jsonify({"error": "Investimento não encontrado"}), 404

    # Atualização do histórico de pagamentos
    historico_pagamentos = json.loads(investimento.get("historico_pagamentos", "[]"))
    historico_pagamentos.append({"data": pagamento_data, "valor": pagamento_valor})

    # Atualização do contador de pagamentos e cálculo do restante
    pagamentos = investimento.get("pagamentos", 0) + 1
    duracao = investimento.get("duracao", 0)
    restante = max(0, (duracao - pagamentos) * investimento.get("valor", 0))

    # Atualização do status do investimento
    investimento["sentido"] = sentido
    investimento["encerrado"] = encerrar or not sentido
    investimento["historico_pagamentos"] = json.dumps(historico_pagamentos)  # Salva como string JSON
    investimento["pagamentos"] = pagamentos

    # Atualiza o banco de dados
    supabase.table("investimento").update({
        "sentido": investimento["sentido"],
        "encerrado": investimento["encerrado"],
        "historico_pagamentos": investimento["historico_pagamentos"],
        "pagamentos": pagamentos
    }).eq("investimento__c", investment_id).execute()

    # Mensagem de retorno
    if investimento["encerrado"]:
        message = "Investimento encerrado com sucesso!"
    else:
        message = f"Pagamento adicionado com sucesso! Restante a pagar: R$ {restante:.2f}"

    return jsonify({"message": message}), 200


@app.route('/cadastrar_investimento', methods=['POST', 'GET'])
def cadastrar_investimento():
    user_id = session.get('user_id')

    if request.method == "POST":
        nome = request.form.get("nome")
        descricao = request.form.get("descricao")
        valor = float(request.form.get("valor"))
        tipo = request.form.get("pagamento")
        duracao = int(request.form.get("duracao"))

        valor_total = duracao * valor

        investimento = {
            "user_id": user_id,
            "nome": nome,
            "descricao": descricao,
            "valor": valor,
            "tipo_pagamento": tipo,
            "duracao": duracao,
            "valor_total": valor_total,
            "status": True,
            "pagamentos": 0,
            "encerrado": False,
            "historico_pagamentos": []
        }

        try:
            supabase.table("investimento").insert(investimento).execute()
            flash("Venda cadastrada com sucesso!", "success")
        except Exception as e:
            flash(f"Erro ao cadastrar venda: {e}", "fail")

        investimentos = obter_dados_tabela("investimento", user_id)
        investimentos_df = pd.DataFrame(investimentos)
        investimentos_ativos = investimentos_df[investimentos_df['encerrado'] == False]
        investimento_encerrado = investimentos_df[investimentos_df['encerrado'] == True]

        return render_template(
            'investments.html', 
            investimentos_df=investimentos_ativos.to_dict('records'),
            investimento_encerrado=investimento_encerrado.to_dict('records'), 
            investimento=investimento)

@app.route('/deletar_investimento', methods=['POST', 'GET'])
def deletar_investimento():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))  # Redireciona para login se o usuário não estiver autenticado.

    if request.method == "POST":
        investimento_id = request.form.get('investimento_id')

        if not investimento_id:
            return "ID do investimento não fornecido.", 400  # Retorna erro se o ID for inválido.
        
        # Atualiza o status do investimento para encerrado
        supabase.table("investimento").delete().eq("investimento__c", investimento_id).execute()

        investimentos = obter_dados_tabela("investimento", user_id)
        investimentos_df = pd.DataFrame(investimentos)
        investimentos_ativos = investimentos_df[investimentos_df['encerrado'] == False]
        investimento_encerrado = investimentos_df[investimentos_df['encerrado'] == True]

        return render_template(
            'investments.html', 
            investimentos_df=investimentos_ativos.to_dict('records'),
            investimento_encerrado=investimento_encerrado.to_dict('records'))

@app.route('/encerrar_investimento', methods=['POST', 'GET'])
def encerrar_investimento():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))  # Redireciona para login se o usuário não estiver autenticado.

    if request.method == "POST":
        investimento_id = request.form.get('investimento_id')

        if not investimento_id:
            return "ID do investimento não fornecido.", 400  # Retorna erro se o ID for inválido.

        # Atualiza o status do investimento para encerrado
        supabase.table("investimento").update({"encerrado": True}).eq("investimento__c", investimento_id).execute()
        investimentos = obter_dados_tabela("investimento", user_id)
        investimentos_df = pd.DataFrame(investimentos)
        investimentos_ativos = investimentos_df[investimentos_df['encerrado'] == False]
        investimento_encerrado = investimentos_df[investimentos_df['encerrado'] == True]

        return render_template(
            'investments.html', 
            investimentos_df=investimentos_ativos.to_dict('records'),
            investimento_encerrado=investimento_encerrado.to_dict('records'))

    investimentos = obter_dados_tabela("investimento", user_id)
    investimentos_df = pd.DataFrame(investimentos)
    investimentos_ativos = investimentos_df[investimentos_df['encerrado'] == False]
    investimento_encerrado = investimentos_df[investimentos_df['encerrado'] == True]

    return render_template(
        'investments.html', 
        investimentos_df=investimentos_ativos.to_dict('records'),
        investimento_encerrado=investimento_encerrado.to_dict('records'))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)