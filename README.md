# CNA Sentinel — Etapa 2: circuito e testes da Z1

Projeto acadêmico de Edge Computing para um desafio fictício da Marinha do Brasil / Amazul. O objetivo futuro é monitorar um perímetro com dois nós ESP32 (Z1 e Z2), MQTT, dashboard e drone simulado.

O ambiente da Etapa 1 está preparado. A Etapa 2 adiciona um circuito Z1 com PIR, contato magnético simulado por chave, tamper, DHT22, RGB, buzzer e LCD 16x2. O firmware lê os sensores e permite testar as saídas manualmente. Não há máquina de estados de segurança, conexão Wi-Fi/MQTT, dashboard ou lógica de drone.

## Estrutura

```text
CNA-SENTINEL/
├── firmware/
│   ├── platformio.ini
│   ├── src/main.cpp
│   ├── include/config.h
│   └── lib/
├── simulator/
│   ├── diagram.json
│   └── wokwi.toml
├── drone/
├── integration/
├── docs/
├── .env.example
├── .gitignore
└── README.md
```

`lib/`, `drone/`, `integration/` e `docs/` ficam vazias nesta etapa. Git não armazena pastas vazias; ao clonar, recrie-as se necessário. Não foram adicionados arquivos de preenchimento.

## Instalação no VS Code (Windows)

1. Instale o [VS Code](https://code.visualstudio.com/) e abra a pasta `CNA-SENTINEL` em **File > Open Folder**.
2. Em **Extensions** (`Ctrl+Shift+X`), instale **PlatformIO IDE** (`platformio.platformio-ide`) e **Wokwi for VS Code** (`wokwi.wokwi-vscode`). **C/C++** (`ms-vscode.cpptools`) auxilia a edição; **Codex** (`openai.chatgpt`) é o assistente, sem participação na compilação. Essas quatro extensões já foram encontradas neste ambiente durante a preparação.
3. Aguarde o PlatformIO terminar a instalação do Core e use **Developer: Reload Window**, na paleta (`Ctrl+Shift+P`), se solicitado. Se o instalador do PlatformIO pedir Python, instale Python 3 pelo [site oficial](https://www.python.org/downloads/windows/), marque **Add python.exe to PATH**, reabra o VS Code e deixe o PlatformIO concluir a instalação. Não há dependências Python do projeto nesta etapa.
4. Para ativar o Wokwi, pressione `F1`, execute **Wokwi: Request a new License**, autorize a abertura do site, clique em **GET YOUR LICENSE**, entre na sua conta e confirme o retorno ao VS Code. Aguarde a mensagem de licença ativada. Essa ativação depende da sua conta; não coloque a licença no repositório.

O procedimento de licença consta no [guia oficial do Wokwi](https://docs.wokwi.com/vscode/getting-started). A primeira compilação precisa de internet para baixar a plataforma, o framework e as bibliotecas. Não é necessário conectar uma placa física nem configurar uma porta COM para simular.

## Configuração

- Placa: **DOIT ESP32 DEVKIT V1**, identificador `esp32doit-devkit-v1`.
- Plataforma Espressif32 fixada em `6.12.0`, framework Arduino e código C++.
- Serial: **115200 baud** no firmware e no monitor PlatformIO.
- `knolleary/PubSubClient` fixada em `2.8`, preservada para MQTT futuro, sem uso no firmware atual.
- `beegee-tokyo/DHT sensor library for ESPx` (`DHTesp`) `1.19.0` para o DHT22. É a biblioteca recomendada pelo [Wokwi para ESP32](https://docs.wokwi.com/parts/wokwi-dht22).
- `arduino-libraries/LiquidCrystal` `1.0.7` para o [LCD paralelo de 4 bits](https://docs.wokwi.com/parts/wokwi-lcd1602). O buzzer usa LEDC, disponível no Arduino ESP32, sem biblioteca adicional.
- A zona fica em `firmware/include/config.h`, no campo `Config::ZONE_ID`. O valor inicial é `"Z1"`. Para a outra zona, altere somente esse valor para `"Z2"` e recompile. O código-fonte é compartilhado; cada compilação incorpora a zona escolhida.
- `.env.example` contém campos vazios para uso futuro. Não é carregado pelo PlatformIO nem pelo firmware. Não é necessário criar `.env` para esta validação.

A placa está documentada no [PlatformIO](https://docs.platformio.org/en/latest/boards/espressif32/esp32doit-devkit-v1.html).

## Compilar

Com um terminal **PlatformIO: Open PlatformIO Core CLI** aberto pela paleta, execute a partir de `CNA-SENTINEL/`:

```powershell
pio run --project-dir firmware
```

Se o terminal abrir dentro de `firmware/`, use apenas `pio run`. Como alternativa pela interface, abra `CNA-SENTINEL/firmware` em uma janela do VS Code, aguarde a detecção de `platformio.ini` e use **PlatformIO: Build**.

Em um PowerShell comum, se `pio` não estiver no PATH, use o Core instalado pela extensão:

```powershell
& "$env:USERPROFILE\.platformio\penv\Scripts\platformio.exe" run --project-dir firmware
```

O resultado esperado é **SUCCESS**, com os arquivos:

```text
firmware/.pio/build/esp32doit-devkit-v1/firmware.bin
firmware/.pio/build/esp32doit-devkit-v1/firmware.elf
```

## Executar a simulação Z1

1. Compile o firmware e mantenha a pasta `CNA-SENTINEL` aberta no VS Code.
2. Pressione `F1` e execute **Wokwi: Select Config File**, selecionando `simulator/wokwi.toml`.
3. Execute **Wokwi: Start Simulator** pela paleta.
4. No monitor serial do simulador, confira:

```text
CNA SENTINEL INICIADO
ZONA: Z1
```

Mensagens de boot do ESP32 podem aparecer antes dessas linhas. A mensagem do programa aparece uma vez por inicialização. Após mudar a zona e recompilar, pare e inicie a simulação; a segunda linha deverá ser `ZONA: Z2`.

Nesta etapa mantenha a zona em `Z1`, com uma única placa. Após o cabeçalho, são exibidos a ajuda dos comandos e os valores individuais dos sensores. O DHT22 aguarda 2,5 segundos para a primeira leitura.

Se a extensão instalada não oferecer **Wokwi: Select Config File**, abra `CNA-SENTINEL/simulator` como pasta em outra janela do VS Code e execute **Wokwi: Start Simulator**. Nesse caso, compile pela janela de `firmware/` ou da raiz.

Os caminhos de `firmware` e `elf` no TOML são relativos ao próprio `simulator/wokwi.toml`, usando `../firmware/...`. O diagrama permanece junto ao TOML; não mova nem copie os binários. Veja a [configuração oficial do Wokwi](https://docs.wokwi.com/vscode/project-config).

O diagrama usa um único ESP32 e todos os periféricos da Z1. O monitor PlatformIO (`pio device monitor`) é voltado à placa física e não é necessário para esta simulação.

## Pinagem e lógica elétrica da Z1

Todos os GND são comuns. GPIOs trabalham com lógica de 3,3 V. No modelo DevKit V1, `VIN` fornece a alimentação de 5 V usada pelo PIR e LCD na simulação.

| Componente | GPIO | Conexão e interpretação |
| --- | --- | --- |
| PIR | 27 | OUT em D27, VCC em VIN/5 V, GND comum; `INPUT`, HIGH = movimento, LOW = sem movimento. |
| Chave magnética (slide switch) | 26 | Comum 2 em D26, terminal 1 em GND, terminal 3 livre. `INPUT_PULLUP`: esquerda fecha 1–2 = LOW/FECHADO; direita abre o contato com GND = HIGH/ABERTO. |
| Botão tamper | 25 | Contato 1.l em D25, contato 2.l em GND. `INPUT_PULLUP`: pressionado = LOW/ACIONADO; solto = HIGH/NORMAL. |
| DHT22 | 4 | SDA em D4, VCC em 3V3, GND comum, NC livre. Pull-up externo de 4,7 kΩ entre SDA e 3V3. A biblioteca controla o pino bidirecional. |
| RGB vermelho | 16 | GPIO16 aparece como **RX2** na placa Wokwi; resistor de 330 Ω em série até R. |
| RGB verde | 17 | GPIO17 aparece como **TX2** na placa Wokwi; resistor de 330 Ω em série até G. |
| RGB azul | 18 | D18 → resistor de 330 Ω → B. |
| Buzzer piezo | 19 | D19 no terminal 2 (+), terminal 1 (−) em GND. Teste LEDC: 2 kHz por 300 ms, canal 0. |
| LCD RS / E | 13 / 14 | D13 em RS; D14 em E. |
| LCD D4 / D5 / D6 / D7 | 21 / 22 / 23 / 32 | Ligação paralela de 4 bits; D0–D3 ficam livres. |

O [RGB](https://docs.wokwi.com/parts/wokwi-rgb-led) tem `common: cathode`: COM em GND; HIGH acende, LOW apaga. Cada cor tem seu próprio resistor de 330 Ω; não há PWM no RGB. A corrente por canal fica abaixo de 10 mA mesmo desconsiderando a queda do LED.

O LCD tem VDD em VIN/5 V, VSS e RW em GND (somente escrita), V0 em GND (contraste não simulado), A em 5 V através de 220 Ω e K em GND. Assim o LCD não dirige dados de 5 V aos GPIOs. Esta montagem é de simulação: em hardware físico, confira os limiares de entrada do módulo LCD alimentado em 5 V e use adaptação de nível de 3,3 V para 5 V se exigida pelo módulo; confira também a saída de 3,3 V do PIR escolhido. O buzzer representado é piezo passivo, não uma sirene de potência.

O [slide switch](https://docs.wokwi.com/parts/wokwi-slide-switch) e o [botão](https://docs.wokwi.com/parts/wokwi-pushbutton) mantêm o bouncing padrão do Wokwi. O firmware exige 30 ms de estabilidade para aceitar uma mudança; pulsos menores podem ser ignorados. Não há resistor externo nesses dois contatos, pois usam o pull-up interno.

## Leitura e comandos de teste

- Entradas digitais são consultadas a cada passagem do `loop()`; uma mudança estável é relatada pela serial, além de um relatório periódico a cada 1 segundo.
- DHT22 é lido a cada 2,5 segundos por `millis()`. A transação de leitura da biblioteca é síncrona e curta, sem espera de segundos entre chamadas. Falhas são exibidas como `ERRO DHT22`, sem apresentar dados antigos como atuais.
- Primeira linha do LCD: `CNA SENTINEL`. Segunda linha: zona e valores, por exemplo `Z1  24.0C  40%`. `DHT: aguarde` aparece antes da primeira leitura e `DHT: ERRO` em falha. A linha é preenchida com espaços para remover caracteres de valores anteriores.
- RGB e buzzer iniciam desligados e respondem apenas aos comandos manuais. Nenhuma entrada dispara saídas automaticamente.
- Não há `delay()` de segundos no programa. O `loop()` cede 1 ms ao escalonador. Temporizações usam subtração de contadores sem sinal, compatível com a volta do `millis()`.

No campo de entrada do **monitor serial do Wokwi**, envie uma letra minúscula e pressione Enter. Quebras de linha são ignoradas.

| Comando | Resultado esperado |
| --- | --- |
| `r` / `g` / `b` | Vermelho / verde / azul |
| `y` / `c` / `m` | Amarelo / ciano / magenta |
| `w` / `0` | Branco / RGB apagado |
| `s` | Bipe de 2 kHz por 300 ms; para automaticamente. Um novo `s` reinicia a duração. |
| `h` | Reexibe a ajuda |

## Roteiro de validação interativa pendente

1. Inicie o Wokwi e confira o cabeçalho na serial, LCD com `CNA SENTINEL` e `Z1`, RGB apagado e buzzer silencioso.
2. Sem interações, confira `Movimento: NAO DETECTADO`, `Acesso: FECHADO` e `Tamper: NORMAL`. Após 2,5 s simulados, espere temperatura de 24 °C e umidade de 40% (valores iniciais do diagrama).
3. Clique no [PIR](https://docs.wokwi.com/parts/wokwi-pir-motion-sensor) e em **Simulate Motion**: espere `DETECTADO`, retornando a `NAO DETECTADO` após cerca de 5 s sem novo estímulo. O período padrão sem aceitar novo movimento é de 1,2 s após baixar a saída.
4. Mova a chave para a direita: espere `ABERTO`; à esquerda: `FECHADO`.
5. Mantenha o botão pressionado por mais de 30 ms (ou use `t` com foco no diagrama): espere `ACIONADO`; ao soltar, `NORMAL`.
6. Clique no DHT22, altere os controles de temperatura/umidade e aguarde até 2,5 s simulados para observar a alteração na serial e no LCD.
7. Envie cada comando RGB e confira as cores. Envie `s`, confira o bipe e o desligamento automático. Enquanto o buzzer soa, mova a chave e confira que as leituras continuam.
8. Reinicie a simulação e confira o retorno às saídas desligadas. Registre a validação de cada periférico antes da próxima etapa.

Compilação e verificação estática do diagrama não comprovam que esses resultados foram observados. A execução interativa dos oito componentes ainda aguarda validação no VS Code.

## Verificações realizadas — Etapa 2

- Compilação PlatformIO concluída com **SUCCESS** (7,91 s na execução final). RAM: 21.704 bytes (6,6%); flash: 280.281 bytes (21,4%). Binário: `firmware/.pio/build/esp32doit-devkit-v1/firmware.bin` (280.640 bytes), acompanhado de `firmware.elf`.
- Os 14 GPIOs do diagrama foram conferidos contra `config.h`, sem compartilhamento entre periféricos; apenas uma placa está presente. `simulator/wokwi.toml` foi preservado e seus caminhos foram resolvidos até os arquivos gerados.
- Executado o [lint oficial do Wokwi](https://docs.wokwi.com/wokwi-ci/cli-usage) com a CLI `0.29.1`: `wokwi-cli lint simulator/diagram.json --warnings-as-errors`. Resultado: **zero erros e zero avisos**. Há uma nota informativa de que o tipo legado `wokwi-esp32-devkit-v1` não é documentado e pode mudar futuramente; o modelo solicitado foi preservado. A verificação confirmou os terminais `RX2`/`TX2` para GPIO16/GPIO17.
- A CLI foi baixada da release oficial em uma pasta temporária fora do repositório e seu SHA256 foi conferido com o publicado no GitHub. Não foi adicionada como dependência do projeto nem ao PATH. Não é necessária para o teste manual via extensão.
- **Não foi executada a simulação dos periféricos.** O lint verifica tipos, atributos e nomes de pinos, sem validar leituras, imagem no LCD, cores ou som. Esses itens aguardam o roteiro interativo acima e a aprovação do usuário.
- Investigação do timeout do DHT22: a ligação original estava completa e válida (`wokwi-dht22`, `VCC→3V3`, `GND→GND.1`, `SDA→D4`, pull-up em SDA). `dht.setup(Pins::DHT, DHTesp::DHT22)` usa o mesmo GPIO 4 e a leitura ocorre a cada 2,5 s, acima do mínimo de aproximadamente 2 s do DHT22; falhas não interrompem o loop. Não foi encontrada uma causa lógica ou uma conexão invertida nos arquivos.
- Ajuste aplicado para robustez elétrica: o pull-up externo do DATA foi alterado de 10 kΩ para 4,7 kΩ. O restante da pinagem e da arquitetura foi preservado. Essa alteração é uma correção preventiva compatível com o DHT22, mas não pode ser apresentada como causa comprovada sem a simulação reproduzir o antes/depois.
- A execução `wokwi-cli . --timeout 5000` foi tentada e bloqueada antes de iniciar por ausência de `WOKWI_CLI_TOKEN`. Portanto, o TIMEOUT ainda aguarda validação no Wokwi; a compilação e o lint não comprovam leitura funcional do sensor.

## Limites desta etapa

A execução interativa do Wokwi depende da extensão e de uma licença ativada pelo usuário. Não há credenciais, broker MQTT ou serviços externos configurados. A próxima etapa depende da validação do circuito Z1 pelo usuário; não foi implementada a máquina de estados NORMAL/ATENÇÃO/ALERTA/CRÍTICO.

## Simulador de drone

O drone simulado fica em `drone/` e não depende dos ESP32 nem de um broker para o modo local. A máquina percorre `DISPONIVEL`, `DECOLANDO`, `EM_ROTA`, `NA_ZONA`, `INSPECIONANDO`, `RETORNANDO` e `CONCLUIDO`. O resultado da inspeção pode ser `NADA_ENCONTRADO` ou `ANOMALIA_CONFIRMADA`.

Instale as dependências Python:

```powershell
python -m pip install -r drone/requirements.txt
```

Execute missões locais:

```powershell
python drone/main.py --zone Z1 --event ALERTA --result NADA_ENCONTRADO
python drone/main.py --zone Z2 --event CRITICO --result ANOMALIA_CONFIRMADA
```

O modo MQTT recebe missões em `cna/drone/missao` e publica status em `cna/drone/status`. Consulte [MQTT sobre WebSocket](#mqtt-sobre-websocket) para configurar e iniciar esse modo.

Execute os testes do simulador com:

```powershell
python -m pytest -q drone/tests
```

## Etapa 3 — dois nós independentes (Z1 e Z2)

O firmware continua único em `firmware/src/main.cpp`. A zona é selecionada em tempo de compilação por macros obrigatórias no `firmware/platformio.ini`:

```ini
[env:z1]
build_flags = -DCNA_ZONE_Z1

[env:z2]
build_flags = -DCNA_ZONE_Z2
```

`firmware/include/config.h` rejeita a compilação quando nenhuma ou as duas macros são definidas. Os dois ambientes mantêm a mesma placa, plataforma, framework, bibliotecas, pinagem, máquina de estados e comandos seriais; somente `ZONE_ID` muda.

Compile os dois nós a partir da raiz do projeto:

```powershell
pio run -e z1 -e z2 --project-dir firmware
```

Ou compile individualmente:

```powershell
pio run -e z1 --project-dir firmware
pio run -e z2 --project-dir firmware
```

Os binários ficam separados:

```text
firmware/.pio/build/z1/firmware.bin
firmware/.pio/build/z1/firmware.elf
firmware/.pio/build/z2/firmware.bin
firmware/.pio/build/z2/firmware.elf
```

Há dois projetos Wokwi independentes, cada um com uma placa e uma cópia completa do circuito:

```text
simulator/z1/diagram.json   simulator/z1/wokwi.toml
simulator/z2/diagram.json   simulator/z2/wokwi.toml
```

Para simular Z1, abra `simulator/z1/diagram.json` ou selecione `simulator/z1/wokwi.toml` em **Wokwi: Select Config File**. Para Z2, use os arquivos correspondentes em `simulator/z2/`. Cada TOML aponta para seu próprio binário, portanto Z1 e Z2 não compartilham uma imagem compilada.

Os componentes de Z2 usam IDs próprios (`esp_z2`, `pir_z2`, `dht_z2`, `lcd_z2` etc.), mas mantêm a mesma pinagem do Z1. Não há conexões elétricas entre as placas. A identificação da zona pode ser confirmada na serial (`ZONA: Z1` ou `ZONA: Z2`) e na primeira linha do LCD.

Validações desta etapa:

- Z1: PlatformIO **SUCCESS**, RAM 21.680 bytes, flash 282.057 bytes.
- Z2: PlatformIO **SUCCESS**, RAM 21.680 bytes, flash 282.057 bytes.
- `wokwi-cli lint simulator/z1/diagram.json --warnings-as-errors`: zero erros e zero avisos, com a nota informativa do tipo legado `wokwi-esp32-devkit-v1`.
- `wokwi-cli lint simulator/z2/diagram.json --warnings-as-errors`: zero erros e zero avisos, com a mesma nota informativa.
- A simulação funcional interativa de Z1 e Z2 não foi executada nesta sessão; leituras de sensores, LCD, RGB, buzzer, ACK/RESET e ARM/DISARM ainda precisam ser verificadas manualmente no Wokwi.

### Histórico da preparação — Etapa 1

- PlatformIO Core `6.2.0` encontrado no ambiente local; extensões PlatformIO e Wokwi instaladas.
- Formatos INI, JSON e TOML verificados, incluindo a resolução dos caminhos relativos do simulador para a saída do build.
- O timeout inicial foi diagnosticado e corrigido: o Windows marcava o endereço DHCP `192.168.15.9` do Wi-Fi como `Duplicate` e utilizava o endereço automático `169.254.119.137`. Conexões IPv4 falhavam, enquanto IPv6 funcionava. Os servidores de registro consultados não ofereciam IPv6.
- A renovação inicial (`ipconfig /renew "Wi-Fi"`) não resolveu. Após tentar liberar a concessão (`ipconfig /release "Wi-Fi"`, que informou não haver endereço associado) e repetir `ipconfig /renew "Wi-Fi"`, a interface recebeu `192.168.15.14` por DHCP, em estado `Preferred`. O registro `api.registry.platformio.org` passou a responder HTTP 200. Não houve mudança de IP estático, DNS, proxy, firewall ou código do Core.
- `pioarduino.com` foi consultado e retornou falha de resolução DNS (NXDOMAIN também no diagnóstico por DNS público). Nenhuma distribuição alternativa foi adotada.
- Instalação concluída com `platformio.exe pkg install --project-dir firmware`: Espressif32 `6.12.0`, toolchain Xtensa `8.4.0+2021r2-patch5`, Arduino `3.20017.241212+sha.dcc1105b`, esptool `2.40900.250804`, SCons `4.41101.0` e PubSubClient `2.8.0`. O Core permaneceu em `6.2.0`.
- Compilação com a configuração original concluída em 16/11/2026: **SUCCESS**, em 19,97 segundos. RAM: 21.464 bytes (6,6%); flash: 267.149 bytes (20,4%). Gerados `firmware/.pio/build/esp32doit-devkit-v1/firmware.bin` e `firmware.elf` na mesma pasta. Placa, biblioteca MQTT e fontes preservados.
- A compilação do C++ mínimo foi validada; a Etapa 2 amplia esse firmware conforme descrito acima.
## Camada de integração

O bridge em `integration/` intermedeia telemetria e eventos das zonas, missões do drone, comandos ARM/DISARM/ACK/RESET e publicação preparada para Ubidots. O modo local não conecta nem afirma publicação em broker.

```powershell
python -m pip install -r integration/requirements.txt
python -m integration.main --demo
python -m pytest -q integration/tests drone/tests
```

O contrato e o roteiro do dashboard estão em [integration/UBIDOTS.md](integration/UBIDOTS.md).

## MQTT sobre WebSocket

O MQTT Dashboard publica o endpoint do broker público em `broker.hivemq.com`, com WS na porta `8000` e WSS na porta `8884`. O caminho `/mqtt` foi aceito nos dois listeners. Para reproduzir uma sessão específica do navegador, consulte a URL da conexão em **Ferramentas do desenvolvedor → Rede → WS** e use os parâmetros daquela sessão. O broker público é compartilhado e destinado a testes de protocolo. Use um broker isolado para os tópicos fixos do projeto. [MQTT Dashboard](https://www.mqtt-dashboard.com/) · [Cliente WebSocket da HiveMQ](https://www.hivemq.com/demos/websocket-client/)

### Bridge e drone

Na raiz de `CNA-SENTINEL`, instale as dependências e crie o arquivo local de configuração:

```powershell
python -m pip install -r integration/requirements.txt -r drone/requirements.txt
Copy-Item .env.example .env
```

Preencha `MQTT_HOST`, `MQTT_PORT`, `MQTT_TRANSPORT` (`ws` ou `wss`) e `MQTT_WS_PATH` com o caminho exato, incluindo a barra inicial. Os executáveis carregam o `.env` da raiz via python-dotenv, com prioridade para variáveis já definidas no ambiente. Eles usam o Paho MQTT 2.x, que implementa WebSocket, TLS e reconexão. [Documentação do Paho MQTT](https://eclipse.dev/paho/files/paho.mqtt.python/html/)

| Variável | Uso |
| --- | --- |
| `MQTT_USERNAME`, `MQTT_PASSWORD` | Quando o listener exige autenticação MQTT. |
| `MQTT_CA_CERT` | Caminho para o PEM da CA em TLS. Vazio usa as CAs do sistema. |
| `MQTT_CLIENT_CERT`, `MQTT_CLIENT_KEY` | Certificado e chave opcionais para TLS mútuo do drone. |
| `MQTT_BRIDGE_CLIENT_ID`, `MQTT_DRONE_CLIENT_ID` | IDs definitivos `cna-sentinel-bridge` e `cna-sentinel-drone`. Use uma instância de cada por broker. |
| `UBIDOTS_TOKEN`, `UBIDOTS_DEVICE` | Ativam o envio para o Ubidots na Bridge. |
| `UBIDOTS_MIN_INTERVAL_SECONDS` | Intervalo mínimo entre requisições ao Ubidots, em segundos. Padrão `1.2`. |

Para conexões diretas legadas, é possível selecionar `mqtts` (TCP com TLS) nos três componentes. O drone também aceita `mqtt` (TCP sem TLS). O TLS do drone é selecionado por `MQTT_TRANSPORT`.

Execute em terminais separados:

```powershell
python -m integration.main
python drone/main.py --mqtt
```

O argumento `--result ANOMALIA_CONFIRMADA` seleciona o resultado simulado do drone. Os modos locais continuam disponíveis com `python -m integration.main --demo` e `python drone/main.py --zone Z1`.

### Firmware Z1 e Z2

Copie `firmware/include/mqtt_config.h.example` para `firmware/include/mqtt_config.h`. Preencha localmente `CNA_WIFI_SSID`, `CNA_WIFI_PASSWORD`, `CNA_MQTT_HOST`, `CNA_MQTT_PORT`, `CNA_MQTT_TRANSPORT` e `CNA_MQTT_WS_PATH`. Acrescente usuário e senha se exigidos e a CA em PEM para WSS/MQTTS. O horário para validação TLS é obtido por NTP. Cada ambiente seleciona seu ID, `cna-sentinel-z1` ou `cna-sentinel-z2`. O `.env` e o cabeçalho preenchido são de uso local e estão no `.gitignore`.

O PubSubClient 2.8 usa o cliente TCP do Arduino. O ESP-MQTT do SDK ESP-IDF 4.4, incluído no Arduino-ESP32 do PlatformIO, fornece WS/WSS, Last Will e reconexão. Uma tarefa de rede e filas limitadas mantêm as operações de socket fora do loop dos sensores. O firmware continua publicando com QoS 0, assina comandos com QoS 1 e guarda até quatro eventos quando a conexão cai. Sem configuração de rede, a operação local fica disponível. [ESP-MQTT](https://docs.espressif.com/projects/esp-idf/en/release-v4.4/esp32/api-reference/protocols/mqtt.html)

```powershell
pio run -d firmware -e z1 -e z2
```

### Teste de conexão e do fluxo

1. Conecte um cliente MQTT WebSocket ao mesmo broker com um ID próprio. Assine `cna/#` e aguarde nos terminais a confirmação das assinaturas da Bridge e do drone.
2. Com os nós ligados, observe as mensagens `temperatura` e `estado` de Z1 e Z2. Para simular a entrada, publique `25.5` em `cna/zona/Z1/temperatura`, `NORMAL` em `cna/zona/Z1/estado` e `ALERTA` em `cna/zona/Z1/evento`. Repita com Z2. Confira a missão em `cna/drone/missao` e as seis transições em `cna/drone/status`, incluindo o resultado final.
3. Em cada tópico `cna/zona/Z1/comando` e `cna/zona/Z2/comando`, publique um dos comandos `ARM`, `DISARM`, `ACK` ou `RESET` e confira o processamento no monitor serial do nó correspondente.
4. Reinicie o broker de teste. Confira as novas assinaturas, publique `CRITICO` em cada zona se usou `ALERTA` no passo 2 e observe o retorno do fluxo. Durante a interrupção, confira a leitura de sensores e a operação dos atuadores nos ESP32.

O teste automatizado inicia um broker aMQTT em loopback, sobe os dois executáveis, simula as zonas e reinicia o broker. O WSS usa uma CA temporária gerada pelo trustme. Para executar também os testes de rede, instale essas dependências de teste:

```powershell
python -m pip install amqtt==0.12.2 trustme==1.2.1
python -m pytest -q integration/tests drone/tests
```
