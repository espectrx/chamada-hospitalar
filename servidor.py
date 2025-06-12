#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sistema de Atendimento Hospitalar - Servidor Central
Gerencia a comunicação entre salas médicas e recepção
"""

import socket
import threading
import json
import time
from datetime import datetime
from typing import Dict, List, Any

def get_local_ip():
    """Obtém o endereço IP local da máquina na rede WiFi"""
    try:
        # Cria um socket temporário para obter o IP local
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return '127.0.0.1'  # Fallback para localhost

class HospitalServer:
    def __init__(self, port=8888):
        self.host = get_local_ip()  # Usa o IP local automaticamente
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Armazena conexões ativas
        self.clients = {}  # {client_id: {'socket': socket, 'type': 'medico/recepcao', 'sala': num}}
        self.salas_conectadas = {}  # {num_sala: client_id}
        self.recepcao_clients = []  # lista de client_ids da recepção

        # Dados do sistema
        self.fila_atendimento = []  # [{'sala': int, 'paciente': str, 'timestamp': str, 'status': str}]
        self.historico = []

        # Lock para thread safety
        self.lock = threading.Lock()

        print(f"Servidor iniciado em {self.host}:{port}")
        print("Para conectar os clientes, use este endereço IP na rede local")

    def start(self):
        """Inicia o servidor"""
        try:
            self.socket.bind((self.host, self.port))
            self.socket.listen(10)
            print("Aguardando conexões...")

            while True:
                client_socket, address = self.socket.accept()
                client_id = f"{address[0]}:{address[1]}_{int(time.time())}"

                print(f"Nova conexão: {client_id} de {address}")

                # Inicia thread para lidar com o cliente
                client_thread = threading.Thread(
                    target=self.handle_client,
                    args=(client_socket, client_id)
                )
                client_thread.daemon = True
                client_thread.start()

        except Exception as e:
            print(f"Erro no servidor: {e}")
        finally:
            self.socket.close()

    def handle_client(self, client_socket, client_id):
        """Gerencia comunicação com um cliente específico"""
        try:
            while True:
                # CORREÇÃO 1: Adicionar timeout para evitar bloqueio indefinido
                client_socket.settimeout(30.0)

                try:
                    data = client_socket.recv(1024).decode('utf-8')
                    if not data:
                        print(f"Cliente {client_id} enviou dados vazios - desconectando")
                        break

                    print(f"Dados recebidos de {client_id}: {data}")  # Log para debug

                except socket.timeout:
                    print(f"Timeout na conexão com {client_id}")
                    continue
                except socket.error as e:
                    print(f"Erro de socket com {client_id}: {e}")
                    break

                try:
                    message = json.loads(data)
                    print(f"Mensagem processada de {client_id}: {message}")  # Log para debug
                    self.process_message(client_socket, client_id, message)
                except json.JSONDecodeError as e:
                    print(f"Erro JSON de {client_id}: {e}")
                    self.send_error(client_socket, "Formato JSON inválido")
                except Exception as e:
                    print(f"Erro ao processar mensagem de {client_id}: {e}")

        except Exception as e:
            print(f"Erro geral com cliente {client_id}: {e}")
        finally:
            print(f"Finalizando conexão com {client_id}")
            self.disconnect_client(client_id)
            try:
                client_socket.close()
            except:
                pass

    def process_message(self, client_socket, client_id, message):
        """Processa mensagens recebidas dos clientes"""
        with self.lock:
            msg_type = message.get('type')
            print(f"Processando mensagem tipo '{msg_type}' de {client_id}")

            if msg_type == 'register':
                self.register_client(client_socket, client_id, message)

            elif msg_type == 'login_medico':
                self.handle_medico_login(client_socket, client_id, message)

            elif msg_type == 'chamar_paciente':
                self.handle_chamar_paciente(client_socket, client_id, message)

            elif msg_type == 'confirmar_atendimento':
                self.handle_confirmar_atendimento(client_socket, client_id, message)

            elif msg_type == 'get_fila' or msg_type == 'get_queue':
                self.send_fila_update_to_client(client_socket)

            elif msg_type == 'get_salas' or msg_type == 'get_rooms':
                self.send_salas_conectadas_to_client(client_socket)

            elif msg_type == 'confirm_call':
                self.handle_confirmar_atendimento_by_id(client_socket, client_id, message)

            elif msg_type == 'remove_call':
                self.handle_remover_da_fila(client_socket, client_id, message)

            else:
                print(f"Tipo de mensagem desconhecido: {msg_type}")
                self.send_error(client_socket, f"Tipo de mensagem desconhecido: {msg_type}")

    def register_client(self, client_socket, client_id, message):
        """Registra um novo cliente"""
        client_type = message.get('client_type')  # 'medico', 'recepcao' ou 'reception'
        print(f"Registrando cliente {client_id} como {client_type}")

        # Normalizar tipo de cliente
        if client_type == 'reception':
            client_type = 'recepcao'

        self.clients[client_id] = {
            'socket': client_socket,
            'type': client_type,
            'sala': None
        }

        if client_type == 'recepcao':
            self.recepcao_clients.append(client_id)
            # Envia estado atual para recepção
            self.send_fila_update_to_client(client_socket)
            self.send_salas_conectadas_to_client(client_socket)

        # CORREÇÃO 2: Enviar confirmação de registro
        self.send_message(client_socket, {
            'type': 'register_success',
            'client_type': client_type
        })

        print(f"Cliente registrado: {client_id} como {client_type}")

    def handle_medico_login(self, client_socket, client_id, message):
        """Processa login do médico"""
        sala = message.get('sala')
        nome = message.get('nome', 'N/A')
        print(f"Tentativa de login do médico {client_id} na sala {sala}")

        # CORREÇÃO 3: Validar se sala é um número válido
        try:
            sala = int(sala)
        except (ValueError, TypeError):
            self.send_message(client_socket, {
                'type': 'login_response',
                'success': False,
                'message': 'Número da sala deve ser um valor numérico válido'
            })
            return

        if sala in self.salas_conectadas:
            print(f"Sala {sala} já está ocupada por {self.salas_conectadas[sala]}")
            self.send_message(client_socket, {
                'type': 'login_response',
                'success': False,
                'message': f'Sala {sala} já está conectada'
            })
            return

        # CORREÇÃO 4: Auto-registrar médico se não estiver registrado
        if client_id not in self.clients:
            print(f"Cliente {client_id} não estava registrado - registrando automaticamente como médico")
            self.clients[client_id] = {
                'socket': client_socket,
                'type': 'medico',
                'sala': None,
                'nome': nome
            }

        # Registra a sala
        self.clients[client_id]['sala'] = sala
        self.clients[client_id]['nome'] = nome
        self.salas_conectadas[sala] = client_id

        self.send_message(client_socket, {
            'type': 'login_response',
            'success': True,
            'sala': sala,
            'message': f'Login realizado com sucesso na sala {sala}'
        })

        # Notifica recepção sobre novo médico conectado
        self.broadcast_to_recepcao({
            'type': 'medico_connected',
            'medico': {
                'sala': sala,
                'nome': nome
            }
        })

        # Atualiza lista de salas para todas as recepções
        self.broadcast_to_recepcao({
            'type': 'rooms_update',
            'rooms': self.get_salas_formatadas()
        })

        print(f"Médico logado na sala {sala} com sucesso")

    def handle_chamar_paciente(self, client_socket, client_id, message):
        """Processa chamada de paciente"""
        if client_id not in self.clients:
            self.send_error(client_socket, "Cliente não registrado")
            return

        sala = self.clients[client_id]['sala']
        if not sala:
            self.send_error(client_socket, "Médico não está logado em nenhuma sala")
            return

        paciente = message.get('paciente', '').strip()

        if not paciente:
            self.send_error(client_socket, "Nome do paciente não pode estar vazio")
            return

        # Adiciona à fila
        chamada = {
            'id': len(self.fila_atendimento) + 1,  # ID sequencial
            'room': sala,  # Para compatibilidade com cliente
            'sala': sala,
            'patient': paciente,  # Para compatibilidade com cliente
            'paciente': paciente,
            'time': datetime.now().strftime('%H:%M:%S'),  # Para compatibilidade
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'status': 'chamado'
        }

        self.fila_atendimento.append(chamada)

        # Confirma para o médico
        self.send_message(client_socket, {
            'type': 'chamada_confirmada',
            'paciente': paciente
        })

        # Notifica recepção sobre nova chamada
        self.broadcast_to_recepcao({
            'type': 'new_call',
            'call': chamada
        })

        # Atualiza fila para todas as recepções
        self.broadcast_to_recepcao({
            'type': 'queue_update',
            'queue': self.fila_atendimento
        })

        print(f"Paciente {paciente} chamado na sala {sala}")

    def handle_confirmar_atendimento(self, client_socket, client_id, message):
        """Processa confirmação de atendimento pela recepção"""
        sala = message.get('sala')

        # Remove da fila
        for i, chamada in enumerate(self.fila_atendimento):
            if chamada['sala'] == sala and chamada['status'] == 'chamado':
                chamada['status'] = 'atendido'
                chamada['fim_atendimento'] = datetime.now().strftime('%H:%M:%S')

                # Move para histórico
                self.historico.append(chamada)
                self.fila_atendimento.pop(i)

                # Notifica médico que pode chamar próximo
                if sala in self.salas_conectadas:
                    medico_id = self.salas_conectadas[sala]
                    if medico_id in self.clients:
                        self.send_message(self.clients[medico_id]['socket'], {
                            'type': 'atendimento_confirmado',
                            'paciente': chamada['paciente'],
                            'sala': sala,
                            'message': f'Atendimento do paciente {chamada["paciente"]} confirmado'
                        })
                break

        # Atualiza recepção
        self.send_message(client_socket, {
            'type': 'atendimento_confirmado',
            'sala': sala
        })

        self.broadcast_to_recepcao({
            'type': 'queue_update',
            'queue': self.fila_atendimento
        })

        print(f"Atendimento confirmado para sala {sala}")

    def send_fila_update_to_client(self, client_socket):
        """Envia atualização da fila para cliente específico"""
        self.send_message(client_socket, {
            'type': 'queue_update',
            'queue': self.fila_atendimento
        })

    def get_salas_formatadas(self):
        """Retorna lista formatada de salas para envio aos clientes"""
        salas_formatadas = []
        for sala, client_id in self.salas_conectadas.items():
            client_info = self.clients.get(client_id, {})
            salas_formatadas.append({
                'number': sala,
                'connected': True,
                'ip': client_id.split(':')[0] if ':' in client_id else 'N/A',
                'medico': client_info.get('nome', 'N/A')
            })
        return salas_formatadas

    def send_salas_conectadas_to_client(self, client_socket):
        """Envia lista de salas conectadas para cliente específico"""
        self.send_message(client_socket, {
            'type': 'rooms_update',
            'rooms': self.get_salas_formatadas()
        })

    def handle_confirmar_atendimento_by_id(self, client_socket, client_id, message):
        """Processa confirmação de atendimento pela recepção usando ID"""
        call_id = message.get('call_id')

        try:
            call_id = int(call_id)
        except (ValueError, TypeError):
            self.send_error(client_socket, "ID da chamada inválido")
            return

        # Procura na fila pelo ID
        chamada_encontrada = None
        for i, chamada in enumerate(self.fila_atendimento):
            if chamada.get('id') == call_id and chamada['status'] == 'chamado':
                chamada_encontrada = chamada
                chamada['status'] = 'atendido'
                chamada['fim_atendimento'] = datetime.now().strftime('%H:%M:%S')

                # Move para histórico
                self.historico.append(chamada)
                self.fila_atendimento.pop(i)
                break

        if not chamada_encontrada:
            self.send_error(client_socket, "Chamada não encontrada ou já processada")
            return

        sala = chamada_encontrada['sala']

        # Notifica médico que pode chamar próximo
        if sala in self.salas_conectadas:
            medico_id = self.salas_conectadas[sala]
            if medico_id in self.clients:
                self.send_message(self.clients[medico_id]['socket'], {
                    'type': 'atendimento_confirmado',
                    'call_id': call_id,
                    'paciente': chamada_encontrada['paciente'],
                    'sala': sala,
                    'message': f'Atendimento do paciente {chamada_encontrada["paciente"]} confirmado'
                })

        # Confirma para a recepção
        self.send_message(client_socket, {
            'type': 'call_confirmed',
            'call_id': call_id
        })

        # Atualiza todas as recepções
        self.broadcast_to_recepcao({
            'type': 'queue_update',
            'queue': self.fila_atendimento
        })

        print(f"Atendimento confirmado para ID {call_id} - Sala {sala}")

    def handle_remover_da_fila(self, client_socket, client_id, message):
        """Remove chamada da fila por ID"""
        call_id = message.get('call_id')

        try:
            call_id = int(call_id)
        except (ValueError, TypeError):
            self.send_error(client_socket, "ID da chamada inválido")
            return

        # Procura e remove da fila
        for i, chamada in enumerate(self.fila_atendimento):
            if chamada.get('id') == call_id:
                self.fila_atendimento.pop(i)

                # Confirma remoção
                self.send_message(client_socket, {
                    'type': 'call_removed',
                    'call_id': call_id
                })

                # Atualiza todas as recepções
                self.broadcast_to_recepcao({
                    'type': 'queue_update',
                    'queue': self.fila_atendimento
                })

                print(f"Chamada ID {call_id} removida da fila")
                return

        self.send_error(client_socket, "Chamada não encontrada")

    def broadcast_to_recepcao(self, message):
        """Envia mensagem para todos os clientes da recepção"""
        for client_id in self.recepcao_clients[:]:  # cópia da lista
            if client_id in self.clients:
                try:
                    self.send_message(self.clients[client_id]['socket'], message)
                    print(f"Mensagem enviada para recepção {client_id}: {message}")
                except Exception as e:
                    print(f"Erro ao enviar para recepção {client_id}: {e}")
                    self.recepcao_clients.remove(client_id)

    def send_message(self, client_socket, message):
        """Envia mensagem JSON para cliente"""
        try:
            data = json.dumps(message, ensure_ascii=False).encode('utf-8')
            # CORREÇÃO 5: Adicionar newline para delimitar mensagens
            data += b'\n'
            client_socket.send(data)
            print(f"Mensagem enviada: {message}")
        except Exception as e:
            print(f"Erro ao enviar mensagem: {e}")
            raise  # Re-raise para que o chamador saiba que houve erro

    def send_error(self, client_socket, error_message):
        """Envia mensagem de erro para cliente"""
        self.send_message(client_socket, {
            'type': 'error',
            'message': error_message
        })

    def disconnect_client(self, client_id):
        """Remove cliente desconectado"""
        with self.lock:
            if client_id in self.clients:
                client_info = self.clients[client_id]

                # Remove da lista de recepção se necessário
                if client_id in self.recepcao_clients:
                    self.recepcao_clients.remove(client_id)

                # Remove sala se for médico
                if client_info['sala'] and client_info['sala'] in self.salas_conectadas:
                    sala = client_info['sala']
                    del self.salas_conectadas[sala]

                    # Notifica recepção
                    self.broadcast_to_recepcao({
                        'type': 'rooms_update',
                        'rooms': []  # Lista vazia, será atualizada pela próxima requisição
                    })
                    print(f"Sala {sala} desconectada")

                del self.clients[client_id]
                print(f"Cliente desconectado: {client_id}")


if __name__ == "__main__":
    server = HospitalServer()
    try:
        server.start()
    except KeyboardInterrupt:
        print("\nServidor finalizado.")