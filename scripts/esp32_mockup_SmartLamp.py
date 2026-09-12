#Precisa instalar: pip install paho-mqtt
#
# CP4 - Smart Lamp (Debuggers Tecnologia)
# Simulador em Python que imita o comportamento do ESP32 (fiware_ngsi_mqtt_esp32 / sketch.ino),
# útil para testar a stack FIWARE direto na instância EC2 sem precisar abrir o Wokwi.
#
# Base original: esp32_mockup_SmartLamp.py, de Fábio Henrique Cabrini
# (https://github.com/fabiocabrini/fiware)

import random
import time
import paho.mqtt.client as mqtt

# ==============================================================================
# CONFIGURAÇÕES - Mesmos parâmetros do código C++ (sketch.ino)
# ==============================================================================
# Quando este script roda DENTRO da própria EC2 (mesma máquina do Mosquitto),
# use "127.0.0.1". Se rodar de outro lugar, troque pelo IP público atual da EC2
# (o mesmo valor usado na variável {{url}} do Postman e no BROKER_MQTT do sketch.ino).
BROKER_MQTT = "127.0.0.1"
BROKER_PORT = 1883
ID_MQTT = "fiware_001"

TOPICO_SUBSCRIBE = "/TEF/lamp001/cmd"
TOPICO_PUBLISH_1 = "/TEF/lamp001/attrs"
TOPICO_PUBLISH_2 = "/TEF/lamp001/attrs/l"

TOPIC_PREFIX = "lamp001"

# Estado interno da placa
estado_led = "0"  # '0' = OFF, '1' = ON


# ==============================================================================
# CALLBACKS MQTT
# ==============================================================================
def on_connect(client, userdata, flags, rc):
    """Executado quando conecta ao Broker (Equivalente ao reconnectMQTT)"""
    if rc == 0:
        print(f"Conectado com sucesso ao broker MQTT: {BROKER_MQTT}")
        client.subscribe(TOPICO_SUBSCRIBE)
        print(f"Inscrito no tópico: {TOPICO_SUBSCRIBE}")
        # Envio inicial conforme o setup() do C++
        client.publish(TOPICO_PUBLISH_1, "s|on")
    else:
        print(f"Falha ao conectar no broker. Código de retorno: {rc}")


def on_message(client, userdata, msg):
    """Executado ao receber comandos (Equivalente ao mqtt_callback)"""
    global estado_led
    payload = msg.payload.decode("utf-8")
    print(f"- Mensagem recebida: {payload}")

    on_cmd = f"{TOPIC_PREFIX}@on|"
    off_cmd = f"{TOPIC_PREFIX}@off|"

    if payload == on_cmd:
        estado_led = "1"
        print(" -> [hardware] LED Onboard LIGADO (HIGH)")

    elif payload == off_cmd:
        estado_led = "0"
        print(" -> [hardware] LED Onboard DESLIGADO (LOW)")


# ==============================================================================
# FUNÇÕES DE SIMULAÇÃO
# ==============================================================================
def envia_estado_output_mqtt(client):
    """Equivalente ao EnviaEstadoOutputMQTT()"""
    if estado_led == "1":
        client.publish(TOPICO_PUBLISH_1, "s|on")
        print("- Led Ligado")
    else:
        client.publish(TOPICO_PUBLISH_1, "s|off")
        print("- Led Desligado")

    print("- Estado do LED onboard enviado ao broker!")


def handle_luminosity(client):
    """Equivalente ao handleLuminosity()"""
    # Simula o analogRead(34) e o map(0, 4095, 0, 100)
    sensor_value = random.randint(0, 4095)
    luminosity = int((sensor_value / 4095.0) * 100)

    mensagem = str(luminosity)
    print(f"Valor da luminosidade: {mensagem}")
    client.publish(TOPICO_PUBLISH_2, mensagem)


# ==============================================================================
# EXECUÇÃO PRINCIPAL (Setup + Loop)
# ==============================================================================
if __name__ == "__main__":
    print("------Conexao WI-FI------")
    print("Conectando-se na rede: Wokwi-GUEST")
    print("Conectado com sucesso na rede Wokwi-GUEST")
    print("IP obtido: 192.168.1.100 (Simulado)")

    # Configuração do Cliente MQTT
    client = mqtt.Client(client_id=ID_MQTT)
    client.on_connect = on_connect
    client.on_message = on_message

    print(f"* Tentando se conectar ao Broker MQTT: {BROKER_MQTT}")
    try:
        client.connect(BROKER_MQTT, BROKER_PORT, 60)
    except Exception as e:
        print(f"Erro ao conectar ao broker: {e}")
        exit(1)

    # Inicia a escuta em segundo plano
    client.loop_start()

    # Aguarda inicialização
    time.sleep(2)

    # Equivale ao void loop() do ESP32
    try:
        while True:
            envia_estado_output_mqtt(client)
            handle_luminosity(client)
            print("-" * 40)
            time.sleep(1)  # Mantém a cadência do loop original

    except KeyboardInterrupt:
        print("\nEncerrando simulador ESP32...")
        client.loop_stop()
        client.disconnect()
