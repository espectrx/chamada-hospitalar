from flask import Flask, render_template, request, session, redirect, url_for, flash
from flask_socketio import SocketIO, emit, join_room
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import argparse

# Carrega variáveis de ambiente
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'chave-secreta-padrao')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///hospital.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicializa extensões
db = SQLAlchemy(app)
socketio = SocketIO(app, async_mode='threading')
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# Modelos
class Servidor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), unique=True, nullable=False)
    descricao = db.Column(db.String(200), nullable=True)
    ativo = db.Column(db.Boolean, default=True, nullable=False)

    # Relacionamento com usuários
    usuarios = db.relationship('User', backref='servidor', lazy=True)

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'medico' ou 'recepcao'
    sala = db.Column(db.String(10), nullable=True)  # Apenas para médicos
    nome_completo = db.Column(db.String(100), nullable=True)  # Nome completo do usuário
    servidor_id = db.Column(db.Integer, db.ForeignKey('servidor.id'), nullable=False)

    # Constraint para username único por servidor
    __table_args__ = (db.UniqueConstraint('username', 'servidor_id', name='unique_username_servidor'),)

class Chamada(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    paciente = db.Column(db.String(100), nullable=False)
    sala = db.Column(db.String(10), nullable=False)
    medico = db.Column(db.String(80), nullable=False)  # username
    nome_medico = db.Column(db.String(100), nullable=True)  # nome completo
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    cor = db.Column(db.String(20), nullable=False, default='cinza')  # cor do paciente
    classificacao = db.Column(db.String(100), nullable=True)  # classificação da sala
    servidor_id = db.Column(db.Integer, db.ForeignKey('servidor.id'), nullable=False)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Rotas
@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    # Redireciona para seleção de servidor se não houver servidor na sessão
    if not session.get('servidor_id'):
        return redirect(url_for('selecionar_servidor'))
    return redirect(url_for('login'))

@app.route('/servidor', methods=['GET', 'POST'])
def selecionar_servidor():
    if request.method == 'POST':
        servidor_nome = request.form.get('servidor')
        if servidor_nome:
            servidor = Servidor.query.filter_by(nome=servidor_nome, ativo=True).first()
            if servidor:
                session['servidor_id'] = servidor.id
                session['servidor_nome'] = servidor.nome
                flash(f'Servidor "{servidor.nome}" selecionado com sucesso!', 'success')
                return redirect(url_for('login'))
            else:
                flash('Servidor não encontrado ou inativo.', 'danger')
        else:
            flash('Por favor, digite o nome do servidor.', 'danger')

    return render_template('servidor.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    # Verifica se há servidor selecionado
    if not session.get('servidor_id'):
        return redirect(url_for('selecionar_servidor'))

    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    servidor_id = session.get('servidor_id')
    servidor = Servidor.query.get(servidor_id)

    if not servidor or not servidor.ativo:
        session.pop('servidor_id', None)
        session.pop('servidor_nome', None)
        flash('Servidor inválido. Selecione novamente.', 'danger')
        return redirect(url_for('selecionar_servidor'))

    if request.method == 'POST':
        role = request.form.get('role')
        if role == 'medico':
            user = User.query.filter_by(username='medico_demo', servidor_id=servidor_id).first()
            if not user:
                user = User(
                    username='medico_demo',
                    password='',
                    role='medico',
                    sala='1',
                    nome_completo='Genérico',
                    servidor_id=servidor_id
                )
                db.session.add(user)
                db.session.commit()
            login_user(user)
            return redirect(url_for('dashboard'))

        elif role == 'recepcao':
            user = User.query.filter_by(username='recepcao_demo', servidor_id=servidor_id).first()
            if not user:
                user = User(
                    username='recepcao_demo',
                    password='',
                    role='recepcao',
                    nome_completo='Recepção',
                    servidor_id=servidor_id
                )
                db.session.add(user)
                db.session.commit()
            login_user(user)
            return redirect(url_for('dashboard'))

        else:
            flash('Escolha um perfil para entrar.', 'danger')
            return render_template('login.html', servidor=servidor)

    return render_template('login.html', servidor=servidor)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Você foi desconectado', 'info')
    return redirect(url_for('login'))

@app.route('/trocar_servidor')
def trocar_servidor():
    if current_user.is_authenticated:
        logout_user()
    session.pop('servidor_id', None)
    session.pop('servidor_nome', None)
    flash('Servidor desconectado. Selecione um novo servidor.', 'info')
    return redirect(url_for('selecionar_servidor'))

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.role == 'medico':
        ultimas_chamadas = Chamada.query.filter_by(
            medico=current_user.username,
            servidor_id=current_user.servidor_id
        ).order_by(Chamada.timestamp.desc()).limit(5).all()
        chamadas_json = [{
            'id': c.id,
            'paciente': c.paciente,
            'sala': c.sala,
            'medico': c.nome_medico or c.medico,
            'timestamp': c.timestamp.isoformat(),
            'cor': getattr(c, 'cor', 'cinza') or 'cinza'
        } for c in ultimas_chamadas]
        return render_template('medico.html', ultimas_chamadas=chamadas_json)
    return render_template('recepcao.html')

@app.route('/editar_perfil', methods=['POST'])
@login_required
def editar_perfil():
    nome_completo = request.form.get('nome_completo')
    if nome_completo:
        current_user.nome_completo = nome_completo
        db.session.commit()
        flash('Perfil atualizado com sucesso!', 'success')
    return redirect(url_for('dashboard'))

# WebSocket events
@socketio.on('connect')
def handle_connect():
    if current_user.is_authenticated:
        join_room(f'{current_user.role}_{current_user.servidor_id}')
        if current_user.role == 'medico':
            join_room(f'medico_{current_user.sala}_{current_user.servidor_id}')
            # Envia as últimas chamadas ao conectar
            ultimas_chamadas = Chamada.query.filter_by(
                medico=current_user.username,
                servidor_id=current_user.servidor_id
            ).order_by(Chamada.timestamp.desc()).limit(8).all()
            chamadas_json = [{
                'id': c.id,
                'paciente': c.paciente,
                'sala': c.sala,
                'medico': c.nome_medico or c.medico,
                'timestamp': c.timestamp.isoformat(),
                'cor': getattr(c, 'cor', 'cinza') or 'cinza',
                'classificacao': getattr(c, 'classificacao', '') or ''
            } for c in ultimas_chamadas]
            emit('ultimas_chamadas', chamadas_json)
        elif current_user.role == 'recepcao':
            # Envia as últimas 6 chamadas ao conectar
            chamadas = Chamada.query.filter_by(
                servidor_id=current_user.servidor_id
            ).order_by(Chamada.timestamp.desc()).limit(6).all()
            chamadas_json = [{
                'id': c.id,
                'paciente': c.paciente,
                'sala': c.sala,
                'medico': c.nome_medico or c.medico,
                'timestamp': c.timestamp.isoformat(),
                'cor': getattr(c, 'cor', 'cinza') or 'cinza',
                'classificacao': getattr(c, 'classificacao', '') or ''
            } for c in chamadas]
            emit('fila_atual', chamadas_json)

@socketio.on('atualizar_sala')
def handle_atualizar_sala(data):
    if current_user.role != 'medico':
        return
    
    # Atualiza a sala do médico
    current_user.sala = data['sala']
    db.session.commit()
    
    # Notifica o médico
    emit('sala_atualizada', {
        'sala': data['sala']
    })

@socketio.on('chamar_paciente')
def handle_chamar_paciente(data):
    if current_user.role != 'medico':
        return
    # Subtrai 3 horas do horário atual
    horario_chamada = datetime.utcnow() - timedelta(hours=3)
    chamada = Chamada(
        paciente=data['paciente'],
        sala=data['sala'],
        medico=current_user.username,
        nome_medico=current_user.nome_completo,
        timestamp=horario_chamada,
        cor=data.get('cor', 'cinza'),
        classificacao=data.get('classificacao', ''),
        servidor_id=current_user.servidor_id
    )
    db.session.add(chamada)
    db.session.commit()
    chamada_dict = {
        'id': chamada.id,
        'paciente': chamada.paciente,
        'sala': chamada.sala,
        'medico': chamada.nome_medico or chamada.medico,
        'timestamp': chamada.timestamp.isoformat(),
        'cor': chamada.cor,
        'classificacao': chamada.classificacao
    }
    emit('nova_chamada', chamada_dict, room=f'recepcao_{current_user.servidor_id}')
    emit('nova_chamada', chamada_dict, room=f'medico_{current_user.servidor_id}')  # Envia para todos os médicos conectados
    # Atualiza a lista de chamadas do próprio médico
    ultimas_chamadas = Chamada.query.filter_by(
        medico=current_user.username,
        servidor_id=current_user.servidor_id
    ).order_by(Chamada.timestamp.desc()).limit(8).all()
    chamadas_json = [{
        'id': c.id,
        'paciente': c.paciente,
        'sala': c.sala,
        'medico': c.nome_medico or c.medico,
        'timestamp': c.timestamp.isoformat(),
        'cor': getattr(c, 'cor', 'cinza') or 'cinza',
        'classificacao': getattr(c, 'classificacao', '') or ''
    } for c in ultimas_chamadas]
    emit('ultimas_chamadas', chamadas_json, room=f'medico_{current_user.sala}_{current_user.servidor_id}')

@socketio.on('get_fila')
def handle_get_fila():
    if current_user.is_authenticated:
        chamadas = Chamada.query.filter_by(
            servidor_id=current_user.servidor_id
        ).order_by(Chamada.timestamp.desc()).limit(6).all()
        chamadas_json = [{
            'id': c.id,
            'paciente': c.paciente,
            'sala': c.sala,
            'medico': c.nome_medico or c.medico,
            'timestamp': c.timestamp.isoformat(),
            'cor': getattr(c, 'cor', 'cinza') or 'cinza',
            'classificacao': getattr(c, 'classificacao', '') or ''
        } for c in chamadas]
        emit('fila_atual', chamadas_json)

@socketio.on('chat_mensagem')
def handle_chat_mensagem(data):
    if not current_user.is_authenticated or current_user.role != 'medico':
        return
    msg = {
        'nome': current_user.nome_completo or current_user.username,
        'mensagem': data.get('mensagem', ''),
        'horario': datetime.now().isoformat()
    }
    emit('chat_mensagem', msg, room=f'medico_{current_user.servidor_id}')

# Criar servidores e usuários iniciais
def criar_dados_iniciais():
    with app.app_context():
        # Cria servidores se não existirem
        if Servidor.query.count() == 0:
            servidores = [
                Servidor(nome='CAIS Amendoeiras', descricao='Centros de Atenção Integral em Saúde Amendoeiras', ativo=False),
                Servidor(nome='CAIS Cândida de Morais', descricao='Centros de Atenção Integral em Saúde Cândida de Morais', ativo=False),
                Servidor(nome='CAIS Campinas', descricao='Centros de Atenção Integral em Saúde Campinas', ativo=False),
                Servidor(nome='CAIS Vila Nova', descricao='Centros de Atenção Integral em Saúde Vila Nova', ativo=False),
                Servidor(nome='CAIS Finsocial', descricao='Centros de Atenção Integral em Saúde Finsocial', ativo=False),
                Servidor(nome='CAIS Bairro Goiá', descricao='Centros de Atenção Integral em Saúde Bairro Goiá', ativo=False),
                Servidor(nome='CIAMS Urias Magalhães', descricao='Centros de Assistência Integrada Médico–Sanitárias Urias Magalhães', ativo=False),
                Servidor(nome='UPA Jardim Novo Mundo', descricao='Unidade de Pronto Atendimento Jardim Novo Mundo', ativo=False),
                Servidor(nome='UPA Noroeste', descricao='Unidade de Pronto Atendimento Noroeste', ativo=True),
                Servidor(nome='UPA Chácara do Governador', descricao='Unidade de Pronto Atendimento Chácara do Governador', ativo=False),
                Servidor(nome='UPA Jardim América', descricao='Unidade de Pronto Atendimento Jardim América', ativo=False),
                Servidor(nome='UPA Itaipú', descricao='Unidade de Pronto Atendimento Itaipú', ativo=False)
            ]
            for servidor in servidores:
                db.session.add(servidor)
            db.session.commit()

        # Cria usuários se não existirem
        if User.query.count() == 0:
            # Pega o primeiro servidor para criar usuários de exemplo
            servidor_demo = Servidor.query.filter_by(nome='Demo').first()
            if servidor_demo:
                # Cria usuário médico
                medico = User(
                    username='medico1',
                    password='senha123',
                    role='medico',
                    sala='125',
                    nome_completo='Dr. João Silva',
                    servidor_id=servidor_demo.id
                )
                db.session.add(medico)

                # Cria usuário recepção
                recepcao = User(
                    username='recepcao1',
                    password='senha123',
                    role='recepcao',
                    nome_completo='Maria Santos',
                    servidor_id=servidor_demo.id
                )
                db.session.add(recepcao)

                db.session.commit()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    host = '0.0.0.0'  # necessário para Render

    with app.app_context():
        db.drop_all()
        db.create_all()
        criar_dados_iniciais()

    socketio.run(app, host=host, port=port)
    
