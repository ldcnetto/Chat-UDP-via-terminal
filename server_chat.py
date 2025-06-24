# server_chat.py
import socket as skt
import math 
import time
from datetime import datetime # Para timestamps
import os 

# Constantes Globais
MAX_BUFF_SIZE = 1024       # Tamanho máximo do buffer para pacotes UDP
SERVER_HOST = '0.0.0.0'    # Endereço IP para o servidor escutar (0.0.0.0 = todas as interfaces disponíveis)
SERVER_PORT = 7070         # Porta na qual o servidor vai escutar

def get_current_timestamp():
    """Retorna o timestamp atual formatado como string (HH:MM:SS DD/MM/YYYY)."""
    return datetime.now().strftime("%H:%M:%S %d/%m/%Y")

class UDPServer:
    """Representa o servidor de chat UDP que gerencia clientes e retransmite mensagens."""
    def __init__(self, host, port, max_buff):
        """Inicializa o servidor UDP, faz o bind do socket e configura variáveis de estado."""
        self.sckt = skt.socket(skt.AF_INET, skt.SOCK_DGRAM) # Cria socket UDP
        self.sckt.bind((host, port)) # Associa o socket ao endereço e porta especificados
        print(f"Servidor de Chat IF975 iniciado em {host}:{port}")
        print("Aguardando conexões...")
        
        if self.sckt is None: # Verificação adicional de segurança para o socket
            raise Exception("Socket not available.")
        
        self.MAX_BUFF = max_buff # Tamanho máximo do buffer para pacotes
        self.clients = {}  # Dicionário para armazenar clientes conectados: {(ip, port): username}
        # Dicionário para armazenar partes de arquivos de mensagens sendo recebidas de clientes:
        # {(ip, port): {'username': 'nome', 'parts': [], 'total_packets': N, 'file_id': M, 'ready_for_data': True/False}}
        self.incoming_file_parts = {} 

    def _log_server_chat_message(self, ip, port, username, message_text, timestamp):
        """Imprime uma mensagem de chat formatada no console do servidor."""
        print(f"{ip}:{port}/~{username}: {message_text} {timestamp}")

    def _log_server_notification(self, notification_text):
        """Imprime uma notificação (ex: entrada/saída de usuário) no console do servidor."""
        print(notification_text)

    def broadcast_to_clients(self, message_bytes, sender_address=None):
        """Envia uma mensagem em bytes para todos os clientes conectados, exceto o remetente (opcional)."""
        # Itera sobre uma cópia da lista de chaves para permitir modificação segura de self.clients durante a iteração (embora não ocorra aqui)
        for client_addr in list(self.clients.keys()): 
            if client_addr != sender_address: # Não envia de volta para o remetente da notificação
                try:
                    self.sckt.sendto(message_bytes, client_addr)
                except Exception as e: # Captura erros ao enviar para um cliente específico
                    print(f"[DEBUG_SERVER] Error broadcasting to {client_addr}: {e}")

    def send_file_content_to_client(self, target_client_addr, content_bytes, original_sender_info_tuple):
        """Envia o conteúdo de um arquivo (mensagem) fragmentado para um cliente específico."""
        # original_sender_info_tuple = (ip_original, porta_original, username_original)
        
        # Calcula o número de pacotes necessários
        num_packets = math.ceil(len(content_bytes) / self.MAX_BUFF)
        timestamp_for_clients = get_current_timestamp() # Timestamp para a mensagem retransmitida
        
        # Cria o cabeçalho da mensagem que informa ao cliente sobre a mensagem chegando
        header_msg_str = f"MSG_INCOMING:{original_sender_info_tuple[0]}:{original_sender_info_tuple[1]}:{original_sender_info_tuple[2]}:{timestamp_for_clients}:{num_packets}"
        
        try:
            # Envia o cabeçalho
            self.sckt.sendto(header_msg_str.encode('utf-8'), target_client_addr)
            time.sleep(0.001)

            # Envia os fragmentos do conteúdo do arquivo
            for i in range(num_packets):
                chunk = content_bytes[i * self.MAX_BUFF : (i + 1) * self.MAX_BUFF]
                
                self.sckt.sendto(chunk, target_client_addr)
                time.sleep(0.001) # Pequena pausa entre fragmentos
        except Exception as e:
            print(f"[DEBUG_SERVER] Error in send_file_content_to_client to {target_client_addr}: {e}")


    def handle_client_message(self, data, client_address):
        """Processa dados recebidos de um cliente (comandos, cabeçalhos de upload, fragmentos de arquivo)."""
        client_ip, client_port = client_address # Desempacota o endereço do cliente

        # Prioridade 1: Se estamos esperando fragmentos de arquivo deste cliente
        if client_address in self.incoming_file_parts and \
           self.incoming_file_parts[client_address].get('ready_for_data', False) and \
           self.incoming_file_parts[client_address]['total_packets'] > 0:
            
            file_info = self.incoming_file_parts[client_address]
            file_info['parts'].append(data) # Adiciona o fragmento (bytes)

            # Se todos os fragmentos foram recebidos
            if len(file_info['parts']) == file_info['total_packets']:
                full_message_content_bytes = b"".join(file_info['parts']) # Remonta o arquivo
                message_text_from_client = ""
                try: # Tenta decodificar o conteúdo do arquivo como UTF-8
                    message_text_from_client = full_message_content_bytes.decode('utf-8')
                except UnicodeDecodeError: # Fallback se não for UTF-8 válido
                    message_text_from_client = full_message_content_bytes.decode('latin-1', errors='replace')
                    print(f"[DEBUG_SERVER] Mensagem de {client_address} decodificada com fallback (latin-1).")

                original_sender_username = file_info['username'] # Pega o nome do remetente
                del self.incoming_file_parts[client_address] # Limpa o buffer de recebimento para este arquivo

                # Loga a mensagem no console do servidor
                server_timestamp = get_current_timestamp()
                self._log_server_chat_message(client_ip, client_port, original_sender_username, message_text_from_client, server_timestamp)
                
                # Retransmite a mensagem para os outros clientes
                original_sender_info_tuple = (client_ip, client_port, original_sender_username)
                for target_addr in list(self.clients.keys()):
                    if target_addr != client_address: # Não envia de volta para o remetente original
                        self.send_file_content_to_client(target_addr, full_message_content_bytes, original_sender_info_tuple)
            return # Retorna após processar o fragmento

        # Prioridade 2: Tenta decodificar como string para processar comandos ou cabeçalhos
        try:
            message_str = data.decode('utf-8')

            if message_str.startswith("CMD:HI:"): # Comando de conexão
                parts = message_str.split(':', 2)
                username = parts[2]
                self.clients[client_address] = username # Adiciona cliente à lista
                self._log_server_notification(f"{username} entrou na sala.") # Log no servidor
                # Notifica outros clientes
                notification_for_clients = f"NOTIFY:{username} entrou na sala."
                self.broadcast_to_clients(notification_for_clients.encode('utf-8'), sender_address=client_address)

            elif message_str.startswith("CMD:BYE"): # Comando de desconexão
                if client_address in self.clients:
                    username = self.clients.pop(client_address) # Remove cliente
                    self._log_server_notification(f"{username} saiu da sala.") # Log no servidor
                    # Notifica outros clientes
                    notification_for_clients = f"NOTIFY:{username} saiu da sala."
                    self.broadcast_to_clients(notification_for_clients.encode('utf-8'))
                if client_address in self.incoming_file_parts: # Limpa buffer de arquivo se houver
                    del self.incoming_file_parts[client_address]

            elif message_str.startswith("MSG_UPLOAD_START:"): # Cliente quer enviar um arquivo de mensagem
                if client_address not in self.clients: # Verifica se o cliente está registrado
                    print(f"[DEBUG_SERVER] Cliente não registrado {client_address} tentou MSG_UPLOAD_START. Ignorando.")
                    return
                
                parts = message_str.split(':', 1) # Divide em "MSG_UPLOAD_START" e "<num_packets>"
                if len(parts) == 2:
                    try:
                        num_packets = int(parts[1]) # Converte número de pacotes para inteiro
                        username_for_file = self.clients[client_address] # Nome do usuário que está enviando
                        
                        # Prepara para receber os fragmentos do arquivo
                        self.incoming_file_parts[client_address] = {
                            'username': username_for_file,
                            'parts': [],
                            'total_packets': num_packets,
                            'file_id': time.time(), # ID simples para o arquivo (timestamp)
                            'ready_for_data': True # Sinaliza que está pronto para receber os bytes
                        }
                        # print(f"[DEBUG_SERVER] Esperando {num_packets} pacotes para msg de {username_for_file}@{client_address}.")
                    except ValueError: # Se num_packets não for um inteiro válido
                        print(f"[DEBUG_SERVER] MSG_UPLOAD_START de {client_address} com num_packets inválido: '{parts[1]}'")
                else: # Se o formato do MSG_UPLOAD_START estiver incorreto
                    print(f"[DEBUG_SERVER] MSG_UPLOAD_START malformado de {client_address}: '{message_str}'")


            else: # String decodificada, mas não é um comando/cabeçalho conhecido
                print(f"[DEBUG_SERVER] Recebido comando/string decodificado desconhecido de {client_address}: '{message_str}'")

        except UnicodeDecodeError: # Se falhou ao decodificar como string E não era um fragmento esperado
            print(f"[DEBUG_SERVER] Recebida msg indecodificável de {client_address}, e não esperando partes de arquivo atualmente.")
        except Exception as e: # Captura outras exceções durante o processamento
            print(f"[DEBUG_SERVER] Erro ao processar mensagem de {client_address}: {e}")


    def run(self):
        """Loop principal do servidor que escuta por mensagens de clientes e as processa."""
        while True: # Loop infinito para manter o servidor rodando
            try:
                # Espera receber dados de algum cliente
                data, client_address = self.sckt.recvfrom(self.MAX_BUFF)
                # Processa a mensagem recebida
                self.handle_client_message(data, client_address)

            except skt.timeout: # Se o socket tiver timeout
                continue
            except ConnectionResetError: # Quando um cliente "desaparece"
                print(f"[DEBUG_SERVER] Conexão resetada por {client_address}. Limpando.")
                if client_address in self.clients: # Remove cliente se estava na lista
                    username = self.clients.pop(client_address)
                    self._log_server_notification(f"{username} saiu da sala (conexão perdida).")
                    # Notifica outros clientes
                    notification_for_clients = f"NOTIFY:{username} saiu da sala (conexão perdida)."
                    self.broadcast_to_clients(notification_for_clients.encode('utf-8'))
                if client_address in self.incoming_file_parts: # Limpa buffer de arquivo
                    del self.incoming_file_parts[client_address]
            except Exception as e: # Captura outras exceções no loop principal
                print(f"[DEBUG_SERVER] Erro geral no loop run: {e}")
                import traceback # Para debug mais detalhado
                traceback.print_exc()


    def close(self):
        """Fecha o socket do servidor de forma limpa."""
        print("Servidor de Chat encerrando.")
        self.sckt.close()


if __name__ == '__main__':
    # Cria e inicia a instância do servidor
    server = UDPServer(SERVER_HOST, SERVER_PORT, MAX_BUFF_SIZE)
    try:
        server.run() # Mantém o servidor rodando
    except KeyboardInterrupt: # Permite encerrar o servidor com Ctrl+C
        print("\nServidor interrompido pelo usuário.")
    finally: # Bloco executado sempre, mesmo se houver exceção ou interrupção
        server.close() # Garante que o socket do servidor seja fechado