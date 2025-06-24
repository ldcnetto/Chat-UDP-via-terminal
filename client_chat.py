# client_chat.py
import socket as skt
import os
import math
import time
import threading
import tempfile

MAX_BUFF_SIZE = 1024
SERVER_HOST = '127.0.0.1'
SERVER_PORT = 7070
CLIENT_HOST = '0.0.0.0'

def get_packet_amount(file_path, max_buff):
    """Calcula o número total de pacotes necessários para enviar um arquivo."""
    if not os.path.exists(file_path): return 0
    fsize = os.stat(file_path).st_size
    total_packs = math.ceil(fsize / max_buff)
    return total_packs

def create_temp_txt_file(message_content):
    """Cria um arquivo .txt temporário com o conteúdo da mensagem e retorna seu nome."""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w", encoding="utf-8")
    temp_file.write(message_content)
    temp_file.close()
    return temp_file.name


class UDPClient():
    """Representa o cliente de chat UDP."""
    def __init__(self, server_host, server_port, max_buff, client_bind_port=0):
        """Inicializa o cliente UDP, configura o socket e variáveis de estado."""
        self.sckt = skt.socket(skt.AF_INET, skt.SOCK_DGRAM)
        try:
            self.sckt.bind((CLIENT_HOST, client_bind_port))
        except OSError as e:
            print(f"[CLIENT_ERROR] Bind error: {e}. Tente uma porta diferente ou 0 para escolha do OS.")
            raise
            
        self.client_ip, self.client_port = self.sckt.getsockname()
        print(f"[CLIENT] Bound to {self.client_ip}:{self.client_port}")

        self.sckt.settimeout(1.0) # Timeout para operações de socket (recvfrom)
        
        if self.sckt is None: # Verificação adicional
            raise Exception("Socket not available.")
        
        self.server_address = (server_host, server_port) # Endereço do servidor
        self.MAX_BUFF = max_buff # Tamanho máximo do buffer para pacotes
        self.username = None # Nome do usuário no chat
        self.stop_event = threading.Event() # Sinaliza para threads encerrarem
        self.prompt_lock = threading.Lock() # Sincroniza acesso ao console para o prompt

        self.receiving_message_data = {} # Armazena dados de mensagens fragmentadas em recebimento

    def send_message_file(self, message_content):
        """Converte uma mensagem em um arquivo .txt, fragmenta e envia ao servidor."""
        temp_file_path = None
        try:
            if not message_content.strip(): # Não envia mensagens vazias
                return

            temp_file_path = create_temp_txt_file(message_content)
            num_packets = get_packet_amount(temp_file_path, self.MAX_BUFF)

            # Garante que arquivos pequenos (que gerariam 0 pacotes) sejam enviados como 1 pacote
            if num_packets == 0 and os.path.exists(temp_file_path) and os.stat(temp_file_path).st_size > 0:
                 num_packets = 1
            elif num_packets == 0: # Se o arquivo realmente estiver vazio ou erro
                 if temp_file_path and os.path.exists(temp_file_path): os.remove(temp_file_path)
                 return

            # Informa ao servidor o início do upload da mensagem e o número de pacotes
            start_msg_upload = f"MSG_UPLOAD_START:{num_packets}"
            self.sckt.sendto(start_msg_upload.encode('utf-8'), self.server_address)
            time.sleep(0.001) # Pequena pausa

            # Envia os fragmentos do arquivo
            with open(temp_file_path, 'rb') as f:
                for _ in range(num_packets):
                    chunk = f.read(self.MAX_BUFF)
                    if not chunk: break # Segurança
                    self.sckt.sendto(chunk, self.server_address)
                    time.sleep(0.001) # Pequena pausa
        except Exception as e:
            with self.prompt_lock: # Protege a impressão de erro
                print("\r" + " " * 80 + "\r", end="") # Limpa a linha do prompt
                print(f"[CLIENT_ERROR] Error sending message file: {e}")
                self._display_prompt() # Reexibe o prompt
        finally:
            # Garante a remoção do arquivo temporário
            if temp_file_path and os.path.exists(temp_file_path):
                os.remove(temp_file_path)

    def _display_prompt(self):
        """Exibe o prompt de input '>' se o cliente não estiver parando."""
        if not self.stop_event.is_set():
            print("> ", end="", flush=True)

    def _handle_incoming_server_data(self, data):
        """Processa dados recebidos do servidor (notificações, cabeçalhos de msg, fragmentos de msg)."""
        # Prioriza o tratamento de fragmentos de dados se uma mensagem estiver sendo recebida
        if 'expected_packets' in self.receiving_message_data and \
           self.receiving_message_data['expected_packets'] > 0 and \
           len(self.receiving_message_data.get('parts', [])) < self.receiving_message_data['expected_packets']:
            
            self.receiving_message_data['parts'].append(data) # Adiciona o fragmento

            # Se todos os fragmentos foram recebidos, remonta e exibe a mensagem
            if len(self.receiving_message_data['parts']) == self.receiving_message_data['expected_packets']:
                with self.prompt_lock:
                    print("\r" + " " * 80 + "\r", end="") # Limpa prompt
                    full_content_bytes = b"".join(self.receiving_message_data['parts'])
                    message_text = ""
                    try:
                        message_text = full_content_bytes.decode('utf-8')
                    except UnicodeDecodeError: # Fallback de decodificação
                        message_text = full_content_bytes.decode('latin-1', errors='replace')
                    
                    h = self.receiving_message_data['header_info'] # Pega informações do cabeçalho
                    # Formata e exibe a mensagem no padrão do chat
                    display_msg = f"{h['ip']}:{h['port']}/~{h['username']}: {message_text} {h['timestamp']}"
                    print(display_msg)
                    self.receiving_message_data = {} # Reseta para a próxima mensagem
                    self._display_prompt() # Reexibe prompt
            return # Retorna após processar o fragmento

        # Se não era um fragmento esperado, tenta decodificar como string (para comandos/cabeçalhos)
        try:
            message_str = data.decode('utf-8')

            with self.prompt_lock: # Sincroniza acesso ao console
                print("\r" + " " * 80 + "\r", end="")

                if message_str.startswith("NOTIFY:"): # Processa notificações do servidor
                    print(f"{message_str.split(':', 1)[1]}")
                
                elif message_str.startswith("MSG_INCOMING:"): # Processa cabeçalho de mensagem
                    content_part = message_str[len("MSG_INCOMING:"):]
                    try:
                        # Dá parse no cabeçalho para obter as informações da mensagem
                        parts_temp = content_part.rsplit(':', 1)
                        if len(parts_temp) != 2:
                            raise ValueError("MSG_INCOMING: Não foi possível isolar num_packets.")
                        
                        num_packets_str = parts_temp[1]
                        num_packets = int(num_packets_str)

                        before_num_packets = parts_temp[0]
                        fields_before_timestamp = before_num_packets.split(':', 3)
                        if len(fields_before_timestamp) == 4:
                            header_info = {
                                'ip': fields_before_timestamp[0],
                                'port': fields_before_timestamp[1],
                                'username': fields_before_timestamp[2],
                                'timestamp': fields_before_timestamp[3],
                            }
                            # Prepara para receber os fragmentos da mensagem
                            self.receiving_message_data = {
                                'header_info': header_info,
                                'parts': [],
                                'expected_packets': num_packets
                            }
                        else: # Erro de formatação no cabeçalho
                            print(f"[CLIENT_ERROR] Malformed MSG_INCOMING (campos antes do timestamp): '{before_num_packets}'")
                            self.receiving_message_data = {}
                            
                    except ValueError as e: # Erro ao converter num_packets ou no parse
                         print(f"[CLIENT_ERROR] Erro ao parsear MSG_INCOMING ('{content_part}'): {e}")
                         self.receiving_message_data = {}
                    except IndexError: # Erro de formatação (faltando partes)
                         print(f"[CLIENT_ERROR] Malformed MSG_INCOMING (IndexError ao parsear): '{content_part}'")
                         self.receiving_message_data = {}
                else: # A string foi decodificada, mas não é em um formato conhecido
                    print(f"\n--- DEBUG CLIENT UNEXPECTED STRING (after explicit binary check) ---")
                    print(f"String decodificada: '{message_str}'")
                    print(f"Dados brutos originais (primeiros 50 bytes): {data[:50]}")
                    print(f"Estado atual de receiving_message_data: {self.receiving_message_data}")
                    print(f"--- FIM DEBUG ---")
                    print(f"[FROM_SERVER_UNEXPECTED_STRING]: {message_str}")
              
                self._display_prompt() 

        except UnicodeDecodeError: # Falhou ao decodificar como string
            with self.prompt_lock:
                print("\r" + " " * 80 + "\r", end="") # Limpa prompt
                print(f"[CLIENT_ERROR] Recebeu dados binários que não são parte de uma mensagem esperada (estado: {self.receiving_message_data}). Dados (primeiros 50): {data[:50]}")
                self._display_prompt() # Reexibe prompt
        
        except Exception as e: # Captura outras exceções
            with self.prompt_lock:
                print("\r" + " " * 80 + "\r", end="") # Limpa prompt
                print(f"[CLIENT_ERROR] Erro em _handle_incoming_server_data: {e}")
                self._display_prompt() # Reexibe prompt

    def receive_messages(self):
        """Loop executado em uma thread para receber mensagens do servidor continuamente."""
        while not self.stop_event.is_set(): # Continua enquanto o cliente estiver ativo
            try:
                # Recebe dados do servidor (buffer um pouco maior para cabeçalhos)
                data, server_addr_recv = self.sckt.recvfrom(self.MAX_BUFF + 256) 
                # Verifica se a mensagem veio do servidor esperado
                if server_addr_recv == self.server_address:
                    self._handle_incoming_server_data(data) # Processa os dados recebidos
            except skt.timeout:
                continue
            except ConnectionResetError:
                with self.prompt_lock:
                    print("\r" + " " * 80 + "\r", end="")
                    print("[CLIENT_ERROR] Erro de conexão com o servidor (reset).")
                    self._display_prompt()
            except OSError as e: # Ex: socket fechado durante o recvfrom
                 if self.stop_event.is_set(): break 
                 with self.prompt_lock:
                    print("\r" + " " * 80 + "\r", end="")
                    print(f"[CLIENT_ERROR] Erro de socket em receive_messages: {e}")
                    self._display_prompt()
                 break # Sai do loop de recebimento se o socket tiver problemas
            except Exception as e: 
                with self.prompt_lock:
                    print("\r" + " " * 80 + "\r", end="")
                    print(f"[CLIENT_ERROR] Erro geral em receive_messages: {e}")
                    self._display_prompt()

    def run(self):
        """Inicia o cliente: ele pega nome de usuário, conecta ao servidor e gerencia loops de envio/recebimento."""
        self.username = input("Digite seu nome de usuário: ")
        if not self.username.strip(): # Valida nome de usuário
            print("Nome de usuário não pode ser vazio. Saindo.")
            return

        # Envia comando de conexão para o servidor
        connect_cmd = f"CMD:HI:{self.username}"
        self.sckt.sendto(connect_cmd.encode('utf-8'), self.server_address)

        print("[CLIENT] Escutando por mensagens do servidor...")
        # Inicia thread para receber mensagens do servidor
        receiver_thread = threading.Thread(target=self.receive_messages, daemon=True)
        receiver_thread.start()

        print(f"Conectado como {self.username}. Digite sua mensagem ou 'bye' para sair.")
        self._display_prompt() # Exibe o prompt inicial

        try:
            # Loop principal com o objetivo de ler input do usuário e enviar mensagens
            while not self.stop_event.is_set():
                user_input = input() # Bloqueia esperando input

                if self.stop_event.is_set(): break # Verifica se deve parar após o input

                with self.prompt_lock: 
                    if user_input.strip().lower() == "bye":
                        bye_cmd = "CMD:BYE"
                        self.sckt.sendto(bye_cmd.encode('utf-8'), self.server_address)
                        print("Desconectando...") 
                        self.stop_event.set() # Para as threads
                        break
                    elif user_input.strip(): # Se não for 'bye' e não for vazio, envia como mensagem
                        self.send_message_file(user_input)
                    
                    if not self.stop_event.is_set() and user_input.strip().lower() != "bye":
                        self._display_prompt()
        
        except KeyboardInterrupt: # Trata Ctrl+C
            with self.prompt_lock:
                print("\nDesconectando por interrupção do usuário (Ctrl+C)...")
                if self.username and not self.stop_event.is_set(): # Envia 'bye' se estava conectado
                    bye_cmd = "CMD:BYE"
                    self.sckt.sendto(bye_cmd.encode('utf-8'), self.server_address)
                self.stop_event.set() # Sinaliza para threads pararem
        finally: # Bloco de limpeza executado sempre ao sair do try
            self.stop_event.set() # Garante que está setado para todas as threads
            print("[CLIENT] Encerrando...")
            if receiver_thread.is_alive(): # Espera a thread de recebimento finalizar
                 receiver_thread.join(timeout=1.0)
            self.close() # Fecha o socket do cliente
            print("[CLIENT] Finalizado.")

    def close(self):
        """Fecha o socket do cliente de forma segura."""
        if self.sckt: # Verifica se o socket ainda existe
            try:
                self.sckt.close()
            except Exception as e: # Para quando encontrar possíveis erros ao fechar
                print(f"[CLIENT_WARN] Erro ao fechar socket: {e}")
            finally:
                self.sckt = None # Define como None para evitar uso posterior


if __name__ == '__main__':
    client_bind_port_arg = 0 # Deixa o OS escolher a porta por padrão
    try:
        # Cria e inicia a instância do cliente
        client = UDPClient(SERVER_HOST, SERVER_PORT, MAX_BUFF_SIZE, client_bind_port=client_bind_port_arg)
        client.run()
    except OSError as e:
        print(f"[CLIENT_FATAL_ERROR] Não foi possível iniciar o cliente devido a um erro de OS (ex: bind): {e}")
    except Exception as e:
        print(f"[CLIENT_FATAL_ERROR] Erro inesperado ao iniciar o cliente: {e}")