import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(url, key)

def obter_dados_tabela(nome_tabela, user_id):
    """Função para obter dados de uma tabela do Supabase"""
    try:
        response = supabase.table(nome_tabela).select("*").eq("user_id", user_id).execute()
        return response.data
    except Exception as e:
        return []