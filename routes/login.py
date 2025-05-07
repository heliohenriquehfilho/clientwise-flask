from flask import Flask, render_template, request, session, redirect, url_for, flash, Blueprint
from supabase import create_client
from dotenv import load_dotenv
from supabase import create_client
import pandas as pd
import datetime
import os
import re

# Initial setup
load_dotenv()

# Supabase setup
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Variáveis de ambiente SUPABASE_URL e SUPABASE_KEY não configuradas.")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

login_bp = Blueprint('login', __name__)

@login_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        try:
            response = supabase.auth.sign_in_with_password({"email": email, "password": password})
            if response.user:
                session['user_id'] = response.user.id
                flash("Login realizado com sucesso!", "success")
                return redirect(url_for('login.dashboard'))
        except Exception as e:
            flash(f"Erro ao autenticar: {e}", "error")
    return render_template('login.html')

@login_bp.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login.login'))
    return render_template('dashboard.html', user_id=session['user_id'])