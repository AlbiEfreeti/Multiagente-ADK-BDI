# Instalación rápida del agente `bdi_agent_example`

Este agente genera proyectos Multi-Agente en **AgentSpeak/Jason** usando **Google ADK**.

 copia los comandos, ejecútalos en orden y debería quedar funcionando.
 
 ** Se recomienda usar entornos virtuales tipo conda o venv **

## 1. Requisitos previos

- Python 3.11 o 3.12
- `pip`
- Acceso a terminal
- Jason instalado si quieres que el agente pruebe automáticamente los proyectos que genera

Descomprime el fichero bdi_agent_example.zip

## 2. Entrar en la carpeta correcta

Sitúate en la carpeta padre del agente:

Comprueba que dentro está la carpeta `bdi_agent_example/`.

## 3. Instalar dependencias

```bash
pip install -r bdi_agent_example/requirements.txt
```

Las dependencias revisadas para este proyecto son:

- `google-adk`
- `litellm`
- `agentspeak`
- `chromadb`
- `pypdf`
- `python-dotenv`
- `typing-extensions`


## 4. Instalar Jason para validar los MAS

Este paso es **necesario**, porque el agente intenta probar automáticamente el código `.mas2j` y `.asl` que genera.

El código ahora busca Jason en este orden:

1. Variable de entorno `JASON_BIN`
2. Comando `jason` disponible en el `PATH`
3. Ruta `/Applications/jason` en macOS

Si Jason no está en el `PATH`, podéis indicar la ruta manualmente.

### macOS / Linux

```bash
export JASON_BIN="/ruta/al/ejecutable/jason"
```

### Windows PowerShell

```powershell
$env:JASON_BIN="C:\ruta\a\jason.bat"
```

