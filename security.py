import os
import hashlib
from flask import session, redirect, url_for, flash
from functools import wraps

# Função para verificar a senha da pasta
def verificar_senha_pasta(senha):
    # Hash da senha (você pode alterar esta senha)
    senha_hash = hashlib.sha256('biaufg'.encode()).hexdigest()
    return hashlib.sha256(senha.encode()).hexdigest() == senha_hash

# Decorator para proteger rotas que precisam de senha da pasta
def requer_senha_pasta(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('pasta_autenticada'):
            return redirect(url_for('autenticar_pasta'))
        return f(*args, **kwargs)
    return decorated_function

# Função para verificar se a pasta está autenticada
def pasta_autenticada():
    return session.get('pasta_autenticada', False)

# Função para autenticar a pasta
def autenticar_pasta(senha):
    if verificar_senha_pasta(senha):
        session['pasta_autenticada'] = True
        return True
    return False 