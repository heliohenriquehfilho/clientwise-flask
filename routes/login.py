from flask import Flask, render_template, request, session, redirect, url_for, flash
from supabase import create_client
from dotenv import load_dotenv
import pandas as pd
import datetime
import os
import re

def login(supabase):
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