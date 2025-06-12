#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sistema de Atendimento Hospitalar - Cliente Médico
Interface para médicos nas salas de atendimento
"""

import tkinter as tk
from tkinter import ttk, messagebox
import socket
import json
import threading
from datetime import datetime
import time


def get_local_ip():
    """Obtém o endereço IP local da máquina na rede WiFi"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return '127.0.0.1'

class MedicoClient:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Sistema Hospitalar - Médico")
        self.root.geometry("900x700")
        self.root.resizable(True, True)

        # Configuração de rede
        self.socket = None
        self.connected = False
        self.sala = None
        self.pode_chamar = True
        self.receive_thread = None
        self.running = True

        # Variáveis da interface
        self.server_ip = tk.StringVar(value=get_local_ip())  # Usa IP local por padrão
        self.server_port = tk.StringVar(value="8888")
        self.sala_var = tk.StringVar()
        self.paciente_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Desconectado")
        self.nome_var = tk.StringVar()

        self.setup_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def setup_ui(self):
        """Configura a interface do usuário"""
        # Frame principal
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Configuração de conexão
        conn_frame = ttk.LabelFrame(main_frame, text="Conexão com Servidor", padding="10")
        conn_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Label(conn_frame, text="IP do Servidor:").grid(row=0, column=0, sticky=tk.W)
        ip_entry = ttk.Entry(conn_frame, textvariable=self.server_ip, width=15)
        ip_entry.grid(row=0, column=1, padx=(5, 10))

        ttk.Label(conn_frame, text="Porta:").grid(row=0, column=2, sticky=tk.W)
        ttk.Entry(conn_frame, textvariable=self.server_port, width=8).grid(row=0, column=3, padx=(5, 10))

        self.connect_btn = ttk.Button(conn_frame, text="Conectar", command=self.connect_to_server)
        self.connect_btn.grid(row=0, column=4, padx=(10, 0))

        # Adiciona dica sobre o IP do servidor
        ttk.Label(conn_frame, text="Dica: Use o IP do computador onde o servidor está rodando", 
                 font=('TkDefaultFont', 8)).grid(row=1, column=0, columnspan=5, sticky=tk.W, pady=(5,0))

        # Status
        status_frame = ttk.Frame(main_frame)
        status_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Label(status_frame, text="Status:").grid(row=0, column=0, sticky=tk.W)
        self.status_label = ttk.Label(status_frame, textvariable=self.status_var, foreground="red")
        self.status_label.grid(row=0, column=1, padx=(5, 0), sticky=tk.W)

        # Login da sala
        self.login_frame = ttk.LabelFrame(main_frame, text="Login da Sala", padding="10")
        self.login_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Label(self.login_frame, text="Nome da Sala:").grid(row=0, column=0, sticky=tk.W)
        self.sala_entry = ttk.Entry(self.login_frame, textvariable=self.sala_var, width=20)
        self.sala_entry.grid(row=0, column=1, padx=(5, 10))

        ttk.Label(self.login_frame, text="Nome do Médico:").grid(row=0, column=2, sticky=tk.W)
        self.nome_entry = ttk.Entry(self.login_frame, textvariable=self.nome_var, width=20)
        self.nome_entry.grid(row=0, column=3, padx=(5, 10))

        self.login_btn = ttk.Button(self.login_frame, text="Fazer Login",
                                    command=self.fazer_login, state='disabled')
        self.login_btn.grid(row=0, column=4)

        # Chamada de pacientes
        self.atendimento_frame = ttk.LabelFrame(main_frame, text="Atendimento", padding="10")
        self.atendimento_frame.grid(row=3, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Label(self.atendimento_frame, text="Nome do Paciente:").grid(row=0, column=0, sticky=tk.W)
        self.paciente_entry = ttk.Entry(self.atendimento_frame, textvariable=self.paciente_var, width=30)
        self.paciente_entry.grid(row=0, column=1, padx=(5, 10))

        # Adiciona seleção de cor
        ttk.Label(self.atendimento_frame, text="Cor:").grid(row=0, column=2, sticky=tk.W, padx=(10, 5))
        self.cor_var = tk.StringVar(value="cinza")
        cores = ["cinza", "vermelho", "laranja", "amarelo", "verde", "azul"]
        self.cor_combo = ttk.Combobox(self.atendimento_frame, textvariable=self.cor_var, values=cores, width=10, state="readonly")
        self.cor_combo.grid(row=0, column=3, padx=(5, 10))

        self.chamar_btn = ttk.Button(self.atendimento_frame, text="Chamar Paciente",
                                     command=self.chamar_paciente, state='disabled')
        self.chamar_btn.grid(row=0, column=4)

        # Info da sala atual
        self.info_frame = ttk.LabelFrame(main_frame, text="Informações", padding="10")
        self.info_frame.grid(row=4, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))

        self.info_text = tk.Text(self.info_frame, height=8, width=60, state='disabled')
        self.info_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        scrollbar = ttk.Scrollbar(self.info_frame, orient="vertical", command=self.info_text.yview)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.info_text.configure(yscrollcommand=scrollbar.set)

        # Configurar grid weights
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(4, weight=1)
        self.info_frame.columnconfigure(0, weight=1)
        self.info_frame.rowconfigure(0, weight=1)

        self.add_info("Sistema iniciado. Conecte-se ao servidor para começar.")

    def connect_to_server(self):
        """Conecta ao servidor"""
        if self.connected:
            self.disconnect()
            return

        try:
            ip = self.server_ip.get().strip()
            port = int(self.server_port.get().strip())

            self.add_info(f"Tentando conectar em {ip}:{port}...")

            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(10)  # Timeout de 10 segundos
            self.socket.connect((ip, port))
            self.socket.settimeout(None)  # Remove timeout após conectar

            self.add_info("Conexão TCP estabelecida. Registrando cliente...")

            # Registra como cliente médico
            self.send_message({
                'type': 'register',
                'client_type': 'medico'
            })

            # Aguarda um pouco para o servidor processar o registro
            time.sleep(0.1)

            self.connected = True
            self.status_var.set("Conectado")
            self.status_label.configure(foreground="green")
            self.connect_btn.configure(text="Desconectar")
            self.login_btn.configure(state='normal')

            # Inicia thread para receber mensagens
            self.receive_thread = threading.Thread(target=self.receive_messages)
            self.receive_thread.daemon = True
            self.receive_thread.start()

            self.add_info(f"Conectado ao servidor {ip}:{port} como cliente médico")

        except socket.timeout:
            messagebox.showerror("Erro de Conexão", "Timeout na conexão com o servidor")
            self.add_info("Erro: Timeout na conexão")
        except ConnectionRefusedError:
            messagebox.showerror("Erro de Conexão", "Servidor não está rodando ou recusou a conexão")
            self.add_info("Erro: Conexão recusada pelo servidor")
        except Exception as e:
            messagebox.showerror("Erro de Conexão", f"Não foi possível conectar: {e}")
            self.add_info(f"Erro de conexão: {e}")

    def disconnect(self):
        """Desconecta do servidor"""
        self.add_info("Desconectando do servidor...")

        self.connected = False

        if self.socket:
            try:
                self.socket.close()
            except:
                pass
            self.socket = None

        # Aguarda thread de recepção terminar
        if self.receive_thread and self.receive_thread.is_alive():
            self.receive_thread.join(timeout=2)

        self.status_var.set("Desconectado")
        self.status_label.configure(foreground="red")
        self.connect_btn.configure(text="Conectar")
        self.login_btn.configure(state='disabled')
        self.chamar_btn.configure(state='disabled')
        self.sala = None
        self.pode_chamar = True

        self.add_info("Desconectado do servidor.")

    def fazer_login(self):
        """Faz login da sala"""
        try:
            sala = self.sala_var.get().strip()
            nome = self.nome_var.get().strip()

            if not sala:
                raise ValueError("Nome da sala é obrigatório")
            if not nome:
                raise ValueError("Nome do médico é obrigatório")

            self.add_info(f"Tentando fazer login na sala {sala}...")

            # Envia mensagem de login
            login_msg = {
                'type': 'login_medico',
                'sala': sala,
                'nome': nome,
                'timestamp': time.time()
            }
            self.add_info(f"Enviando mensagem de login: {login_msg}")
            self.send_message(login_msg)

        except ValueError as e:
            messagebox.showerror("Erro", str(e))

    def chamar_paciente(self):
        """Chama próximo paciente"""
        if not self.connected:
            messagebox.showwarning("Aviso", "Não conectado ao servidor")
            return

        paciente = self.paciente_var.get().strip()
        if not paciente:
            messagebox.showwarning("Aviso", "Digite o nome do paciente")
            return

        # Desabilita botão e mostra status
        self.chamar_btn.configure(state=tk.DISABLED, text="Aguardando confirmação...")

        # Envia mensagem de chamada
        chamada_msg = {
            'type': 'chamar_paciente',
            'sala': self.sala,
            'paciente': paciente,
            'cor': self.cor_var.get(),
            'timestamp': time.time()
        }
        self.send_message(chamada_msg)
        self.add_info(f"Chamando paciente: {paciente}")

    def send_message(self, message):
        """Envia mensagem para o servidor"""
        if not self.socket or not self.connected:
            self.add_info("Erro: Não conectado ao servidor")
            return False

        try:
            data = json.dumps(message, ensure_ascii=False).encode('utf-8')
            self.add_info(f"Enviando: {message}")
            self.socket.send(data + b'\n')  # Adiciona quebra de linha
            return True
        except Exception as e:
            self.add_info(f"Erro ao enviar mensagem: {e}")
            self.root.after(0, self.disconnect)
            return False

    def receive_messages(self):
        """Recebe mensagens do servidor"""
        buffer = b''

        while self.connected and self.running:
            try:
                # Recebe dados
                data = self.socket.recv(1024)
                if not data:
                    self.add_info("Servidor fechou a conexão")
                    break

                buffer += data
                self.add_info(f"Dados recebidos: {data.decode('utf-8', errors='ignore')}")  # Log para debug

                # Processa mensagens completas
                while b'\n' in buffer:
                    message, buffer = buffer.split(b'\n', 1)
                    try:
                        msg = json.loads(message.decode('utf-8'))
                        self.root.after(0, lambda m=msg: self.process_message(m))
                    except json.JSONDecodeError:
                        self.add_info(f"Erro ao decodificar mensagem: {message}")

            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    self.add_info(f"Erro na recepção: {e}")
                break

        if self.running:
            self.root.after(0, self.disconnect)

    def process_message(self, message):
        """Processa mensagens recebidas do servidor"""
        try:
            msg_type = message.get('type')
            
            if msg_type == 'login_success':
                self.sala = message.get('sala')
                self.add_info(f"Login realizado com sucesso na sala {self.sala}")
                self.chamar_btn.configure(state='normal')
                
            elif msg_type == 'login_error':
                error_msg = message.get('message', 'Erro desconhecido')
                self.add_info(f"Erro no login: {error_msg}")
                messagebox.showerror("Erro", error_msg)
                
            elif msg_type == 'call_confirmed':
                self.add_info("Chamada confirmada pela recepção")
                self.chamar_btn.configure(state='normal', text="Chamar Paciente")
                self.paciente_var.set("")  # Limpa o campo do paciente
                
            elif msg_type == 'error':
                error_msg = message.get('message', 'Erro desconhecido')
                self.add_info(f"Erro: {error_msg}")
                messagebox.showerror("Erro", error_msg)
                self.chamar_btn.configure(state='normal', text="Chamar Paciente")
                
        except Exception as e:
            self.add_info(f"Erro ao processar mensagem: {e}")
            self.chamar_btn.configure(state='normal', text="Chamar Paciente")

    def add_info(self, text):
        """Adiciona informação ao log"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        self.info_text.configure(state='normal')
        self.info_text.insert(tk.END, f"[{timestamp}] {text}\n")
        self.info_text.see(tk.END)
        self.info_text.configure(state='disabled')

    def on_closing(self):
        """Callback para fechar a aplicação"""
        self.running = False
        if self.connected:
            self.disconnect()
        self.root.destroy()

    def run(self):
        """Inicia a aplicação"""
        self.root.mainloop()


if __name__ == "__main__":
    app = MedicoClient()
    app.run()