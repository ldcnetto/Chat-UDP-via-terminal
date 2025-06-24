# Redes de Computadores - 2025.1

## Servidor de Chat UDP com Transferência de Arquivos .txt

O projeto consiste no desenvolvimento de um servidor de chat de sala única utilizando o protocolo UDP. As mensagens trocadas são arquivos `.txt` que são transferidos, fragmentados, se necessário, e reconstruídos para serem exibidos como mensagens nos terminais dos clientes.

## Funcionalidades

- **Comunicação UDP:** Utiliza sockets UDP para toda a comunicação entre clientes e o servidor.
- **Mensagens como Arquivos `.txt`:**
  1.  O usuário cliente digita uma mensagem.
  2.  A aplicação cliente converte essa mensagem em um arquivo `.txt` temporário.
  3.  O cliente envia o conteúdo deste arquivo `.txt` para o servidor.
  4.  O servidor retransmite o conteúdo do arquivo `.txt` para todos os outros clientes conectados.
  5.  Os clientes destinatários recebem o conteúdo, remontam se necessário, e exibem a mensagem em seu terminal.
- **Fragmentação e Reconstrução:** Arquivos `.txt` (mensagens) maiores que o buffer de 1024 bytes são automaticamente fragmentados em pacotes UDP menores para transmissão e reconstruídos no destino (seja o servidor ou outro cliente).
- **Chat de Sala Única Multi-Cliente:** O servidor suporta múltiplos clientes conectados simultaneamente. Todas as mensagens enviadas por um cliente são vistas por todos os outros clientes na sala.
- **Comandos de Cliente:**
  - Conexão à sala: O cliente informa seu nome de usuário ao se conectar. Internamente, um comando `CMD:HI:<nome_usuario>` é utilizado.
  - Saída da sala: O usuário pode digitar `bye` para se desconectar. Internamente, um comando `CMD:BYE` é utilizado.
- **Notificações:**
  - Quando um usuário entra na sala, os outros clientes recebem uma notificação (ex: "Leo entrou na sala.").
  - Quando um usuário sai da sala, os outros clientes também são notificados.
- **Formato de Exibição de Mensagens:** As mensagens são exibidas nos terminais dos clientes (e logadas no servidor) no formato:
  `<IP_remetente>:<PORTA_remetente>/~<nome_usuario_remetente>: <mensagem_contida_no_txt> <hora-data_do_servidor>`
  Exemplo: `127.0.0.1:54321/~Alice: Olá todo mundo! 10:30:00 20/06/2025`

## Estrutura do Projeto

O projeto é composto pelos seguintes arquivos:

- `server_chat.py`: Contém o código do servidor UDP. Ele gerencia as conexões dos clientes, recebe as mensagens (como arquivos `.txt`), e as retransmite para os demais participantes da sala. Também informa as atividades do chat em seu próprio console.
- `client_chat.py`: Contém o código do cliente UDP. Permite que o usuário se conecte ao servidor com um nome, envie mensagens (que são convertidas em `.txt`), e receba/exiba mensagens de outros usuários e notificações do servidor.
- `README.md`: Este arquivo.

## Requisitos para Execução

- Python 3.x
- Nenhuma biblioteca externa é necessária além das padrão do Python (`socket`, `os`, `math`, `time`, `threading`, `tempfile`, `datetime`).

## Como Executar

1.  **Iniciar o Servidor:**
    Abra um terminal e execute o script do servidor:

    ```bash
    python server_chat.py
    ```

    O servidor começará a escutar por conexões na porta e host configurados (padrão: `0.0.0.0:7070`).

2.  **Iniciar Clientes:**
    Abra um novo terminal para cada cliente que deseja conectar. Execute o código do cliente:

    ```bash
    python client_chat.py
    ```

    - O cliente solicitará que você digite um nome de usuário.
    - Após dar o nome, você estará conectado à sala de chat.
    - Você pode iniciar múltiplos clientes desta forma, cada um em seu próprio terminal.

3.  **Interagindo no Chat:**
    - No terminal de um cliente, digite sua mensagem e pressione Enter para enviá-la.
    - A mensagem aparecerá nos terminais de todos os outros clientes conectados.
    - Para sair do chat, digite `bye` e pressione Enter.
    - Para sair forçadamente (em qualquer um dos códigos), você pode usar `Ctrl+C`.

## Demonstração da Fragmentação

Para demonstrar a fragmentação de arquivos `.txt` (mensagens):

1.  Conecte pelo menos dois clientes ao servidor.
2.  Em um dos clientes, envie uma mensagem bem longa.
3.  Observe que a mensagem completa vai ser recebida e exibida corretamente no terminal de outro cliente, mesmo tendo sido fragmentada para transmissão via UDP.
4.  O servidor também mostrará a mensagem completa em seu console. Os prints de debug (se ativos nos códigos) nos terminais do servidor podem mostrar os pacotes sendo enviados/recebidos.

## Observações da Etapa 1

- A comunicação é totalmente feita via UDP, o que significa que não há garantia de entrega ou ordem dos pacotes nesta etapa. A lógica implementada para remontar mensagens fragmentadas assume que todos os pacotes de uma única mensagem chegam, mas não trata perdas entre diferentes mensagens ou pacotes de controle.
- A transferência confiável com RDT 3.0 será implementada apenas na Etapa 2.

## Autores

- Jadson Alan de Abreu Souza
- Leônidas Dantas de Castro Netto
