# Guia passo a passo — CP4 Smart Lamp (FIWARE na AWS)

Este guia resume o roteiro seguido pela equipe para configurar a stack FIWARE na AWS, provisionar a Smart Lamp e validar a integração com o ESP32 (Wokwi). É o mesmo fluxo documentado na collection do Postman (`postman/CP4_SmartLamp.postman_collection.json`).

## 1. Subir a instância AWS

- EC2 Ubuntu, 20 GiB gp3.
- Security Group inicial:
  - `22` (SSH) → Meu IP
  - `1026` (Orion), `4041` (IoT Agent), `8666` (STH-Comet), `1883` (Mosquitto) → Meu IP
- Após "Executar instância", aguarde `Status: 3/3 verificações aprovadas` e anote o **IPv4 público**.

## 2. Conectar via SSH

```bash
ssh -i "fiware-key.pem" ubuntu@<ip-publico-da-ec2>
```

## 3. Instalar Docker, Compose e Git

```bash
sudo apt update
sudo apt install -y git docker.io docker-compose-v2
sudo usermod -aG docker $USER
sudo systemctl enable --now docker
exit
```
Conecte novamente por SSH e rode `docker ps` para confirmar que não há erro de permissão.

## 4. Clonar o repositório e subir a stack

```bash
git clone <url-deste-repositorio>
cd cp4-smart-lamp-fiware
docker compose up -d
docker ps
```
Esperado: `fiware-orion`, `fiware-iot-agent`, `fiware-sth-comet`, `fiware-mosquitto`, `fiware-mongo-internal` e `fiware-mongo-historical` com status `running`/`healthy`.

## 5. Configurar o Postman

- Importe a collection e crie/edite a variável `url` = IP público atual da EC2.
- Headers padrão usados em quase todas as requisições:
  ```
  fiware-service: smart
  fiware-servicepath: /
  ```

## 6. IoT Agent — Health check e Service Group

1. **Health Check**: `GET http://{{url}}:4041/iot/about` → esperado `200 OK`.
2. **Provisioning a Service Group**: `POST http://{{url}}:4041/iot/services`
   ```json
   {
     "services": [
       {
         "apikey": "TEF",
         "cbroker": "http://{{url}}:1026",
         "entity_type": "Thing",
         "resource": ""
       }
     ]
   }
   ```
   Esperado: `201 Created`. Confirme com `GET http://{{url}}:4041/iot/services`.

## 7. Provisionar a Smart Lamp (device lamp001)

`POST http://{{url}}:4041/iot/devices`
```json
{
  "devices": [
    {
      "device_id": "lamp001",
      "entity_name": "urn:ngsi-ld:Lamp:001",
      "entity_type": "Lamp",
      "protocol": "PDI-IoTA-UltraLight",
      "transport": "MQTT",
      "commands": [
        { "name": "on", "type": "command" },
        { "name": "off", "type": "command" }
      ],
      "attributes": [
        { "object_id": "s", "name": "state", "type": "Text" },
        { "object_id": "l", "name": "luminosity", "type": "Integer" }
      ]
    }
  ]
}
```
Esperado: `201 Created`. Confirme com `GET http://{{url}}:4041/iot/devices`.

## 8. Registrar os comandos no Orion (ponto de atenção)

`POST http://{{url}}:1026/v2/registrations`
```json
{
  "description": "Lamp Commands",
  "dataProvided": {
    "entities": [{ "id": "urn:ngsi-ld:Lamp:001", "type": "Lamp" }],
    "attrs": ["on", "off"]
  },
  "provider": {
    "http": { "url": "http://iot-agent:4041" },
    "legacyForwarding": false
  }
}
```
**Importante:** use `legacyForwarding: false` (não `true`). Com `true` o Orion tenta o endpoint legado NGSIv1 (`/v1/updateContext`) e recebe `404`; com `false` ele encaminha corretamente para `/v2/op/update`, que o IoT Agent atual aceita.

Ao testar o comando com:
```
PATCH http://{{url}}:1026/v2/entities/urn:ngsi-ld:Lamp:001/attrs?type=Lamp
```
```json
{ "on": { "type": "command", "value": "" } }
```
o esperado é `204 No Content`, confirmando `Postman → Orion → forwarding NGSIv2 → IoT Agent → comando aceito`.

## 9. Simular o ESP32

- **Wokwi** (`codigo.ino`): atualize `default_BROKER_MQTT` com o IP atual da EC2, confirme a porta `1883` liberada para `0.0.0.0/0` e aperte Play.
- **Ou script Python** (rodando na própria EC2, sem precisar abrir portas): `python3 scripts/esp32_mockup_SmartLamp.py` com `BROKER_MQTT = "127.0.0.1"`.

Serial esperado:
```
Conectando-se na rede: Wokwi-GUEST
Conectado com sucesso na rede Wokwi-GUEST
Tentando se conectar ao Broker MQTT: <ip>
Conectado com sucesso ao broker MQTT!
```

## 10. Conferir luminosidade e estado no Orion

```
GET http://{{url}}:1026/v2/entities/urn:ngsi-ld:Lamp:001/attrs/luminosity
GET http://{{url}}:1026/v2/entities/urn:ngsi-ld:Lamp:001/attrs/state
```
Esperado: `200 OK` com `{"type": "Integer", "value": <n>}` / `{"type": "Text", "value": "on"|"off"}`.

## 11. STH-Comet — histórico de luminosidade

1. **Health Check**: `GET http://{{url}}:8666/version` → `200 OK`.
2. **Subscribe Luminosity**: `POST http://{{url}}:1026/v2/subscriptions`
   ```json
   {
     "description": "Notify STH-Comet of all Luminosity changes",
     "subject": {
       "entities": [{ "id": "urn:ngsi-ld:Lamp:001", "type": "Lamp" }],
       "condition": { "attrs": ["luminosity"] }
     },
     "notification": {
       "http": { "url": "http://sth-comet:8666/notify" },
       "attrs": ["luminosity"],
       "attrsFormat": "legacy"
     }
   }
   ```
   Use o hostname interno do Docker (`sth-comet`), não o IP público — quem chama esse endpoint é o Orion dentro do container.
3. **Request Luminosity** (histórico):
   ```
   GET http://{{url}}:8666/STH/v1/contextEntities/type/Lamp/id/urn:ngsi-ld:Lamp:001/attributes/luminosity?lastN=30
   ```
   Esperado: `200 OK` com os últimos valores e timestamps.

## 12. Ao encerrar / retomar a instância

- Os containers, volumes e arquivos ficam salvos no disco da EC2 enquanto a instância não for terminada (parar/iniciar não apaga nada).
- O que muda ao reiniciar é o **IP público** — atualize:
  - variável `url` no Postman;
  - `default_BROKER_MQTT` no `sketch.ino`;
  - regra da porta `1883` no Security Group (volte para `0.0.0.0/0` só durante o teste, e para o seu IP depois).
- Ao reconectar via SSH, se os containers não estiverem rodando:
  ```bash
  cd ~/cp4-smart-lamp-fiware
  docker compose up -d
  ```

## Checklist rápido de validação

- [ ] Health Check IoT Agent → `200`
- [ ] Service Group criado → `201`
- [ ] Device `lamp001` provisionado → `201`
- [ ] Registration de comandos (`legacyForwarding: false`) → `201`
- [ ] Comando `on`/`off` via PATCH → `204`
- [ ] Luminosidade/estado consultados no Orion → `200`
- [ ] Subscription do STH-Comet criada → `201`
- [ ] Histórico de luminosidade no STH-Comet → `200`
