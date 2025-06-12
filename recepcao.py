#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sistema de Atendimento Hospitalar - Cliente Recepção
Interface para gerenciar fila de atendimento e confirmar consultas
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


class RecepcaoClient:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Sistema Hospitalar - Recepção")
        self.root.geometry("900x700")
        self.root.resizable(True, True)

        # Configuração de rede
        self.socket = None
        self.connected = False
        self.receive_thread = None
        self.running = True

        # Dados
        self.fila_atendimento = []
        self.salas_conectadas = []
        self.medicos_conectados = {}  # Dicionário para rastrear médicos conectados

        # Variáveis da interface
        self.server_ip = tk.StringVar(value=get_local_ip())  # Usa IP local por padrão
        self.server_port = tk.StringVar(value="8888")
        self.status_var = tk.StringVar(value="Desconectado")

        self.setup_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Auto-conectar ao iniciar
        self.root.after(1000, self.auto_connect)

    def setup_ui(self):
        """Configura a interface do usuário"""
        # Configurar grid weights
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        # Frame principal
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        main_frame.grid_rowconfigure(1, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)
        main_frame.grid_columnconfigure(1, weight=2)

        # Configuração de conexão
        conn_frame = ttk.LabelFrame(main_frame, text="Conexão com Servidor", padding="10")
        conn_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Label(conn_frame, text="IP do Servidor:").grid(row=0, column=0, sticky=tk.W)
        ip_entry = ttk.Entry(conn_frame, textvariable=self.server_ip, width=15)
        ip_entry.grid(row=0, column=1, padx=(5, 10))

        ttk.Label(conn_frame, text="Porta:").grid(row=0, column=2, sticky=tk.W)
        ttk.Entry(conn_frame, textvariable=self.server_port, width=8).grid(row=0, column=3, padx=(5, 10))

        self.connect_btn = ttk.Button(conn_frame, text="Conectar", command=self.connect_to_server)
        self.connect_btn.grid(row=0, column=4, padx=(10, 0))

        # Status
        ttk.Label(conn_frame, text="Status:").grid(row=0, column=5, padx=(20, 5), sticky=tk.W)
        self.status_label = ttk.Label(conn_frame, textvariable=self.status_var, foreground="red")
        self.status_label.grid(row=0, column=6, sticky=tk.W)

        # Adiciona dica sobre o IP do servidor
        ttk.Label(conn_frame, text="Dica: Use o IP do computador onde o servidor está rodando", 
                 font=('TkDefaultFont', 8)).grid(row=1, column=0, columnspan=7, sticky=tk.W, pady=(5,0))

        # Frame esquerdo - Salas conectadas
        left_frame = ttk.LabelFrame(main_frame, text="Salas Conectadas", padding="10")
        left_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 5))
        left_frame.grid_rowconfigure(0, weight=1)
        left_frame.grid_columnconfigure(0, weight=1)

        # Lista de salas
        self.salas_listbox = tk.Listbox(left_frame, height=15, font=('Arial', 10))
        self.salas_listbox.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        salas_scrollbar = ttk.Scrollbar(left_frame, orient="vertical", command=self.salas_listbox.yview)
        salas_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.salas_listbox.configure(yscrollcommand=salas_scrollbar.set)

        # Botão para atualizar salas
        ttk.Button(left_frame, text="Atualizar Salas", command=self.request_rooms_update).grid(
            row=1, column=0, columnspan=2, pady=(10, 0), sticky=(tk.W, tk.E)
        )

        # Frame direito - Fila de atendimento
        right_frame = ttk.LabelFrame(main_frame, text="Fila de Atendimento", padding="10")
        right_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(5, 0))
        right_frame.grid_rowconfigure(0, weight=1)
        right_frame.grid_columnconfigure(0, weight=1)

        # Treeview para fila
        columns = ('ID', 'Sala', 'Paciente', 'Horário', 'Status', 'Cor')
        self.fila_tree = ttk.Treeview(right_frame, columns=columns, show='headings', height=15)

        # Configurar colunas
        self.fila_tree.heading('ID', text='ID')
        self.fila_tree.heading('Sala', text='Sala')
        self.fila_tree.heading('Paciente', text='Paciente')
        self.fila_tree.heading('Horário', text='Horário')
        self.fila_tree.heading('Status', text='Status')
        self.fila_tree.heading('Cor', text='Cor')

        self.fila_tree.column('ID', width=50, anchor='center')
        self.fila_tree.column('Sala', width=70, anchor='center')
        self.fila_tree.column('Paciente', width=200)
        self.fila_tree.column('Horário', width=80, anchor='center')
        self.fila_tree.column('Status', width=100, anchor='center')
        self.fila_tree.column('Cor', width=80, anchor='center')

        self.fila_tree.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S))

        fila_scrollbar = ttk.Scrollbar(right_frame, orient="vertical", command=self.fila_tree.yview)
        fila_scrollbar.grid(row=0, column=3, sticky=(tk.N, tk.S))
        self.fila_tree.configure(yscrollcommand=fila_scrollbar.set)

        # Frame de botões
        buttons_frame = ttk.Frame(right_frame)
        buttons_frame.grid(row=1, column=0, columnspan=3, pady=(10, 0), sticky=(tk.W, tk.E))
        buttons_frame.grid_columnconfigure(0, weight=1)
        buttons_frame.grid_columnconfigure(1, weight=1)

        # Botões de ação
        self.confirmar_btn = ttk.Button(buttons_frame, text="Confirmar Atendimento",
                                        command=self.confirmar_atendimento, state='disabled')
        self.confirmar_btn.grid(row=0, column=0, padx=(0, 5), sticky=(tk.W, tk.E))

        self.atualizar_btn = ttk.Button(buttons_frame, text="Atualizar Fila",
                                        command=self.request_queue_update)
        self.atualizar_btn.grid(row=0, column=1, padx=(5, 0), sticky=(tk.W, tk.E))

        # Remover da fila
        self.remove_btn = ttk.Button(buttons_frame, text="Remover da Fila",
                                     command=self.remover_da_fila, state='disabled')
        self.remove_btn.grid(row=1, column=0, columnspan=2, pady=(5, 0), sticky=(tk.W, tk.E))

        # Bind para seleção na árvore
        self.fila_tree.bind('<<TreeviewSelect>>', self.on_fila_select)

        # Frame de logs
        log_frame = ttk.LabelFrame(main_frame, text="Log de Atividades", padding="10")
        log_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(10, 0))
        log_frame.grid_columnconfigure(0, weight=1)

        self.log_text = tk.Text(log_frame, height=6, wrap=tk.WORD, font=('Consolas', 9))
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E))

        log_scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        log_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.log_text.configure(yscrollcommand=log_scrollbar.set)

    def auto_connect(self):
        """Conecta automaticamente ao servidor na inicialização"""
        if not self.connected:
            self.connect_to_server()

    def connect_to_server(self):
        """Conecta ao servidor central"""
        if self.connected:
            self.disconnect_from_server()
            return

        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.server_ip.get(), int(self.server_port.get())))
            self.socket.settimeout(30.0)

            # Registrar como recepção
            register_msg = {
                'type': 'register',
                'client_type': 'reception',
                'timestamp': time.time()
            }
            self.send_message(register_msg)

            self.connected = True
            self.status_var.set("Conectado")
            self.status_label.configure(foreground="green")
            self.connect_btn.configure(text="Desconectar")

            # Iniciar thread para receber mensagens
            self.receive_thread = threading.Thread(target=self.receive_messages)
            self.receive_thread.daemon = True
            self.receive_thread.start()

            self.log_message("Conectado ao servidor com sucesso")

            # Solicitar atualização inicial
            self.request_rooms_update()
            self.request_queue_update()

        except Exception as e:
            self.log_message(f"Erro ao conectar: {e}")
            messagebox.showerror("Erro", f"Não foi possível conectar ao servidor:\n{e}")
            self.disconnect_from_server()

    def disconnect_from_server(self):
        """Desconecta do servidor"""
        self.connected = False
        self.status_var.set("Desconectado")
        self.status_label.configure(foreground="red")
        self.connect_btn.configure(text="Conectar")

        if hasattr(self, 'socket'):
            try:
                self.socket.close()
            except:
                pass

        self.log_message("Desconectado do servidor")

    def send_message(self, message):
        """Envia mensagem para o servidor"""
        if self.connected:
            try:
                data = json.dumps(message, ensure_ascii=False).encode('utf-8')
                data += b'\n'  # Adiciona newline para delimitar mensagens
                self.socket.send(data)
                self.log_message(f"Mensagem enviada: {message}")
            except Exception as e:
                self.log_message(f"Erro ao enviar mensagem: {e}")
                self.disconnect_from_server()

    def receive_messages(self):
        """Thread para receber mensagens do servidor"""
        buffer = b''

        while self.running and self.connected:
            try:
                data = self.socket.recv(65536)
                if not data:
                    self.log_message("Servidor fechou a conexão")
                    break

                buffer += data
                self.log_message(f"Dados recebidos: {data.decode('utf-8', errors='ignore')}")

                # Processa mensagens completas
                while b'\n' in buffer:
                    message, buffer = buffer.split(b'\n', 1)
                    try:
                        msg = json.loads(message.decode('utf-8'))
                        self.root.after(0, lambda m=msg: self.process_message(m))
                    except json.JSONDecodeError:
                        self.log_message(f"Erro ao decodificar mensagem: {message}")

            except socket.timeout:
                continue
            except Exception as e:
                if self.running:
                    self.log_message(f"Erro na recepção: {e}")
                break

        if self.running:
            self.root.after(0, self.disconnect_from_server)

    def process_message(self, message):
        """Processa mensagens recebidas do servidor"""
        try:
            msg_type = message.get('type')
            
            if msg_type == 'queue_update':
                self.fila_atendimento = message.get('queue', [])
                self.update_fila_display()
                
            elif msg_type == 'rooms_update':
                self.salas_conectadas = message.get('rooms', [])
                self.medicos_conectados = message.get('doctors', {})
                self.update_salas_display()
                
            elif msg_type == 'patient_called':
                # Atualiza a fila quando um paciente é chamado
                self.request_queue_update()
                
            elif msg_type == 'error':
                error_msg = message.get('message', 'Erro desconhecido')
                self.log_message(f"Erro: {error_msg}")
                messagebox.showerror("Erro", error_msg)
                
        except Exception as e:
            self.log_message(f"Erro ao processar mensagem: {e}")

    def update_salas_display(self):
        """Atualiza a exibição das salas conectadas"""
        try:
            self.salas_listbox.delete(0, tk.END)
            self.log_message(f"Atualizando display de salas. Total: {len(self.salas_conectadas)}")
            
            for sala in self.salas_conectadas:
                status = "🟢" if sala.get('connected', False) else "🔴"
                medico = self.medicos_conectados.get(sala.get('number'))
                medico_info = f" - Dr(a). {medico.get('nome', 'N/A')}" if medico else ""
                sala_text = f"{status} Sala {sala.get('number', 'N/A')}{medico_info}"
                self.log_message(f"Adicionando sala: {sala_text}")
                self.salas_listbox.insert(tk.END, sala_text)
        except Exception as e:
            self.log_message(f"Erro ao atualizar display de salas: {e}")

    def update_fila_display(self):
        """Atualiza a exibição da fila de atendimento"""
        # Limpa a árvore
        for item in self.fila_tree.get_children():
            self.fila_tree.delete(item)

        # Mapeamento de cores para valores hexadecimais
        cores = {
            'cinza': '#808080',
            'vermelho': '#FF0000',
            'laranja': '#FFA500',
            'amarelo': '#FFFF00',
            'verde': '#00FF00',
            'azul': '#0000FF'
        }

        # Adiciona cada item da fila
        for item in self.fila_atendimento:
            # Cria um quadrado colorido para representar a cor
            cor = item.get('cor', 'cinza')
            cor_hex = cores.get(cor, '#808080')
            cor_tag = f"cor_{item['id']}"
            self.fila_tree.tag_configure(cor_tag, background=cor_hex)
            
            # Formata o horário
            horario = datetime.fromtimestamp(item['timestamp']).strftime('%H:%M')
            
            # Insere o item na árvore
            self.fila_tree.insert('', 'end', values=(
                item['id'],
                item['sala'],
                item['paciente'],
                horario,
                item['status'],
                ''  # Coluna de cor vazia, pois a cor é mostrada no background
            ), tags=(cor_tag,))

    def on_fila_select(self, event):
        """Callback para seleção na fila"""
        selection = self.fila_tree.selection()
        if selection:
            item = self.fila_tree.item(selection[0])
            values = item['values']

            # Habilitar botões apenas se não estiver confirmado
            if len(values) > 4 and '✓' not in str(values[4]):
                self.confirmar_btn.configure(state='normal')
                self.remove_btn.configure(state='normal')
            else:
                self.confirmar_btn.configure(state='disabled')
                self.remove_btn.configure(state='disabled')
        else:
            self.confirmar_btn.configure(state='disabled')
            self.remove_btn.configure(state='disabled')

    def confirmar_atendimento(self):
        """Confirma atendimento do paciente selecionado"""
        selection = self.fila_tree.selection()
        if not selection:
            messagebox.showwarning("Aviso", "Selecione um paciente da fila")
            return

        item = self.fila_tree.item(selection[0])
        call_id = item['values'][0]  # ID é o primeiro valor

        if self.connected:
            msg = {
                'type': 'confirm_call',
                'call_id': call_id,
                'timestamp': time.time()
            }
            self.log_message(f"Confirmando atendimento para ID {call_id}")
            self.send_message(msg)
        else:
            messagebox.showwarning("Aviso", "Não conectado ao servidor")

    def remover_da_fila(self):
        """Remove o item selecionado da fila"""
        selection = self.fila_tree.selection()
        if not selection:
            messagebox.showwarning("Aviso", "Selecione um item para remover")
            return

        item = self.fila_tree.item(selection[0])
        values = item['values']

        if len(values) < 5:
            return

        call_id = values[0]
        patient = values[2]

        # Confirmar com o usuário
        if messagebox.askyesno("Confirmar", f"Remover {patient} da fila de atendimento?"):
            # Enviar remoção para o servidor
            remove_msg = {
                'type': 'remove_call',
                'call_id': call_id,
                'timestamp': datetime.now().isoformat()
            }

            if self.send_message(remove_msg):
                self.log_message(f"Removido da fila: {patient}")
                # Atualizar fila
                self.request_queue_update()
            else:
                messagebox.showerror("Erro", "Não foi possível remover da fila")

    def request_rooms_update(self):
        """Solicita atualização da lista de salas"""
        if self.connected:
            msg = {
                'type': 'get_rooms',
                'timestamp': time.time()
            }
            self.log_message("Solicitando atualização da lista de salas")
            self.send_message(msg)

    def request_queue_update(self):
        """Solicita atualização da fila"""
        if self.connected:
            msg = {
                'type': 'get_queue',
                'timestamp': time.time()
            }
            self.log_message("Solicitando atualização da fila de atendimento")
            self.send_message(msg)

    def log_message(self, message):
        """Adiciona mensagem ao log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"

        self.log_text.insert(tk.END, log_entry)
        self.log_text.see(tk.END)

        # Limitar tamanho do log
        lines = self.log_text.get("1.0", tk.END).split('\n')
        if len(lines) > 100:
            self.log_text.delete("1.0", "2.0")

    def on_closing(self):
        """Callback para fechar a aplicação"""
        if self.connected:
            self.disconnect_from_server()

        self.running = False
        self.root.destroy()

    def run(self):
        """Inicia a aplicação"""
        self.root.mainloop()


if __name__ == "__main__":
    app = RecepcaoClient()
    app.run()