# Configuração manual do dashboard Ubidots

O bridge publica variáveis no dispositivo definido por `UBIDOTS_DEVICE`, usando o token de `UBIDOTS_TOKEN`. Sem essas variáveis, o modo local apenas registra os payloads e não faz chamadas externas.

| Variável | Tipo | Unidade | Origem |
|---|---|---|---|
| `z1_temperatura` | numérico | °C | `cna/zona/Z1/temperatura` |
| `z2_temperatura` | numérico | °C | `cna/zona/Z2/temperatura` |
| `z1_estado` | código numérico | — | `cna/zona/Z1/estado` |
| `z2_estado` | código numérico | — | `cna/zona/Z2/estado` |
| `z1_ultimo_evento` | código numérico | — | `cna/zona/Z1/evento` |
| `z2_ultimo_evento` | código numérico | — | `cna/zona/Z2/evento` |
| `estado_drone` | código numérico | — | `cna/drone/status` |
| `zona_inspecionada` | código numérico | — | `cna/drone/status` |
| `resultado_inspecao` | código numérico | — | `cna/drone/status` |

## Códigos e contexto

| Variável | Códigos |
|---|---|
| `z1_estado`, `z2_estado` | 0 `NORMAL`, 1 `ATENCAO`, 2 `ALERTA`, 3 `CRITICO`, 4 `ONLINE`, 5 `OFFLINE` |
| `z1_ultimo_evento`, `z2_ultimo_evento` | 2 `ALERTA`, 3 `CRITICO` |
| `estado_drone` | 0 `DISPONIVEL`, 1 `DECOLANDO`, 2 `EM_ROTA`, 3 `NA_ZONA`, 4 `INSPECIONANDO`, 5 `RETORNANDO`, 6 `CONCLUIDO` |
| `zona_inspecionada` | 1 `Z1`, 2 `Z2` |
| `resultado_inspecao` | 0 `SEM_RESULTADO` (inspeção ainda sem resultado), 1 `NADA_ENCONTRADO`, 2 `ANOMALIA_CONFIRMADA` |

O código é enviado no campo `value`. O texto original fica em `context.label`, que pode ser exibido nos widgets com suporte a contexto. Rótulos desconhecidos recebem o código `-1` e mantêm o texto recebido. A temperatura permanece em graus Celsius.

```json
{
  "z1_ultimo_evento": {"value": 2, "context": {"label": "ALERTA"}}
}
```

O Ubidots usa o contexto para armazenar texto associado a uma leitura numérica. [Documentação sobre contexto](https://help.ubidots.com/en/articles/1081412-using-context-to-display-text-in-ubidots-widgets)

## Frequência e fila de envio

A Bridge enfileira cada atualização em memória e envia uma por vez, na ordem de chegada. O intervalo mínimo entre os inícios das tentativas é configurado por `UBIDOTS_MIN_INTERVAL_SECONDS` e vale 1,2 segundo por padrão. Use ponto decimal no `.env` e um valor maior que zero.

Em caso de HTTP 429, erro 5xx ou falha de rede, a mesma atualização permanece na frente da fila. A espera dobra a cada falha até 60 segundos, respeitando o intervalo mínimo configurado e um prazo maior informado em `Retry-After`. A Bridge registra as rejeições HTTP definitivas e passa para o próximo item. Os envios e as esperas ocorrem em uma tarefa separada do MQTT. [Códigos HTTP do Ubidots](https://docs.ubidots.com/v1.6/reference/response-codes)

Ao encerrar, a Bridge para de consumir MQTT e dá até dois segundos para esvaziar a fila. Se o prazo expirar, cancela as esperas e registra que restaram atualizações. A fila é volátil e os itens restantes se perdem quando o processo termina.

## Widgets

Widgets recomendados

- dois indicadores numéricos ou cartões para temperatura Z1/Z2;
- dois cartões de estado operacional;
- tabela ou indicador de último evento por zona;
- cartão de estado do drone;
- cartões para zona inspecionada e resultado da última inspeção;
- controles de comando separados por zona, publicando `ARM`, `DISARM`, `ACK` ou `RESET` no tópico de comando correspondente.

## Tópicos MQTT

O bridge preserva os tópicos definidos no projeto: `cna/zona/Z1|Z2/{temperatura,estado,evento,comando}`, `cna/drone/missao` e `cna/drone/status`.

O firmware usa ESP-MQTT com publicações em QoS 0 e assinatura de comandos em QoS 1.

## Pendências para conexão real

1. Confirmar host, porta, transporte, caminho e requisitos de autenticação e TLS do broker.
2. Configurar os ESP32 e a Bridge conforme o [README](../README.md#mqtt-sobre-websocket).
3. Configurar no Ubidots o dispositivo, variáveis e widgets.
