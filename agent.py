import sys
import subprocess
import shutil
import urllib.request
import urllib.error
import json
import os
from pathlib import Path
from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from . import rag   
#from rag import consultar_documentacion 


OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)

MAX_RETRIES = 5
current_retries = 0
best_mas_state = {}
best_error_count = float('inf')


def resolve_jason_command():
    """
    Busca el ejecutable de Jason en este orden:
    1. Variable de entorno JASON_BIN
    2. Comando 'jason' disponible en el PATH
    3. Ruta típica de macOS (/Applications/jason)
    4. Ruta típica de Windows (C:\\Jason\\bin\\jason.bat)
    """
    env_path = os.getenv("JASON_BIN")
    if env_path:
        return env_path

    path_command = shutil.which("jason")
    if path_command:
        return path_command

    default_macos_path = "/Applications/jason"
    if Path(default_macos_path).exists():
        return default_macos_path

    default_windows_paths = [
        r"C:\Jason\bin\jason.bat",
        r"C:\Program Files\Jason\bin\jason.bat",
        r"C:\Program Files (x86)\Jason\bin\jason.bat",
    ]
    for windows_path in default_windows_paths:
        if Path(windows_path).exists():
            return windows_path

    return None

def search_github_examples(path: str = "") -> str:
    """
    Permite acceder a los ejemplos oficiales de código de Jason (BDI) en GitHub.
    Útil para consultar cómo se implementan ciertas características en Jason.
    
    Args:
        path: La ruta relativa del archivo o directorio de ejemplo a consultar dentro de la carpeta 'examples' de Jason.
              Déjalo vacío ("") para listar los directorios y archivos de la raíz de ejemplos.
              Puedes usar esta herramienta primero con "" para ver qué ejemplos hay, y luego llamarla 
              de nuevo con la ruta específica, ej. "blocks/blocks.mas2j" o "auction/ag1.asl".
    """
    base_api_url = "https://api.github.com/repos/jason-lang/jason/contents/examples"
    url = f"{base_api_url}/{path}".strip("/")
    
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Python-urllib'})
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode('utf-8'))
            
            if isinstance(data, list):
                items = [f"[{item['type']}] {item['path'].replace('examples/', '', 1)}" for item in data]
                return f"Contenido de '{path or 'raíz'}':\n" + "\n".join(items)
            
            elif isinstance(data, dict) and data.get("type") == "file":
                download_url = data.get("download_url")
                if download_url:
                    req_file = urllib.request.Request(download_url, headers={'User-Agent': 'Python-urllib'})
                    with urllib.request.urlopen(req_file) as f_res:
                        return f_res.read().decode('utf-8')
                return "Error: No se encontró la URL de descarga del archivo."
            else:
                return "Respuesta inesperada de la API de GitHub."
                
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return f"Error: No se encontró la ruta '{path}' en los ejemplos de Jason."
        if e.code == 403:
            return "Error: Límite de peticiones a la API de GitHub excedido. Inténtalo más tarde."
        return f"Error HTTP al acceder a GitHub: {e.code} - {e.reason}"
    except Exception as e:
        return f"Error al intentar acceder a los ejemplos: {e}"

def test_mas_code(mas2j_code: str, agents_dict: dict) -> str:
    """
    Guarda y ejecuta el código en un directorio temporal para probar el sistema Multi-Agente usando jason.
    NO guarda los archivos definitivamente, solo devuelve la salida para que verifiques si funciona.
    Tiene un límite de 5 intentos por sesión.
    
    Args:
        mas2j_code: El contenido completo del archivo de configuración .mas2j.
        agents_dict: Un diccionario donde la clave es el nombre del archivo (ej. "agent1.asl") 
                     y el valor es el contenido de ese archivo .asl.
    """
    global current_retries, best_mas_state, best_error_count
    
    if current_retries >= MAX_RETRIES:
         return f"ERROR: Has superado el límite de {MAX_RETRIES} intentos. Por favor, utiliza 'save_mas_code' para guardar el último código de inmediato y termina tu respuesta."
         
    current_retries += 1
    
    temp_dir = Path("temp_mas_project")
    
    try:
        # Limpiar si ya existe
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
        temp_dir.mkdir()
        
        # Guardar .mas2j
        mas2j_file = temp_dir / "temp.mas2j"
        mas2j_file.write_text(mas2j_code, encoding="utf-8")
        
        # Guardar archivos .asl
        for filename, content in agents_dict.items():
            if not filename.endswith(".asl"):
                filename += ".asl"
            (temp_dir / filename).write_text(content, encoding="utf-8")
            
        jason_command = resolve_jason_command()
        if not jason_command:
            return (
                "ERROR: No se ha encontrado Jason. Instálalo y define la variable "
                "de entorno JASON_BIN o añade el comando 'jason' al PATH."
            )

        result = subprocess.run(
            [jason_command, "mas", "start", "--mas2j=temp.mas2j", "--console"],
            cwd=str(temp_dir),
            capture_output=True,
            text=True,
            timeout=15
        )
        
        # Heurística simple para contar errores basándonos en STDERR y el código de retorno
        error_count = 0
        if result.returncode != 0:
            error_count += 10
        if result.stderr:
            error_count += len(result.stderr.split('\n'))
            
        if error_count < best_error_count:
            best_error_count = error_count
            best_mas_state = {
                "mas2j": mas2j_code,
                "agents": agents_dict
            }
            
        # Format output
        output = f"=== EJECUCIÓN DE PRUEBA (Intento {current_retries}/{MAX_RETRIES}) ===\nReturn code: {result.returncode}\n"
        if result.stdout:
            output += f"--- STDOUT ---\n{result.stdout}\n"
        if result.stderr:
            output += f"--- STDERR ---\n{result.stderr}\n"
            
        return output
        
    except subprocess.TimeoutExpired as e:
        # En muchos sistemas, jason arranca la GUI y se queda pillado. Guardamos el estado.
        if best_error_count == float('inf'):
            best_mas_state = {
                "mas2j": mas2j_code,
                "agents": agents_dict
            }
            
        output = f"=== EJECUCIÓN DE PRUEBA (Intento {current_retries}/{MAX_RETRIES}) ===\n"
        output += "AVISO: La ejecución alcanzó el tiempo límite (15s). Esto es normal si Jason arranca una interfaz y no finaliza solo.\n"
        if hasattr(e, 'stdout') and e.stdout:
            stdout_str = e.stdout.decode('utf-8') if isinstance(e.stdout, bytes) else e.stdout
            output += f"--- STDOUT (parcial) ---\n{stdout_str}\n"
        return output
        
    except FileNotFoundError:
        return "ERROR: El comando 'jason' no se encuentra en el sistema. Asegúrate de tener instalado Jason y agregado al PATH."
    except Exception as e:
        return f"ERROR inesperado al ejecutar: {e}"
    finally:
        # Limpiar
        if temp_dir.exists():
            shutil.rmtree(temp_dir)

def save_mas_code(mas_name: str, mas2j_code: str = "", agents_dict: dict = None) -> str:
    """
    Guarda el sistema MAS completo (el .mas2j y los .asl) en su propia subcarpeta dentro de 'output'.
    Si provees 'mas2j_code' y 'agents_dict', guardará esos. Si están vacíos, usará el 'mejor' código que lograste ejecutar en tus pruebas.
    
    Args:
        mas_name: Nombre del proyecto (se usará para la subcarpeta en 'output' y el archivo .mas2j).
    """
    global current_retries, best_mas_state, best_error_count
    
    if agents_dict is None:
        agents_dict = {}
        
    project_dir = OUTPUT_DIR / mas_name
    project_dir.mkdir(parents=True, exist_ok=True)
    
    code_mas2j = mas2j_code if mas2j_code else best_mas_state.get("mas2j", "")
    code_agents = agents_dict if agents_dict else best_mas_state.get("agents", {})
    
    if not code_mas2j or not isinstance(code_agents, dict) or not code_agents:
         return "ERROR: No hay código generado para guardar o no se ha probado previamente."
         
    try:
        # Guardar .mas2j
        mas_filename = f"{mas_name}.mas2j" if not mas_name.endswith(".mas2j") else mas_name
        (project_dir / mas_filename).write_text(str(code_mas2j), encoding="utf-8")
        
        # Guardar .asl
        for filename, content in code_agents.items():
            if not filename.endswith(".asl"):
                filename += ".asl"
            (project_dir / filename).write_text(str(content), encoding="utf-8")
        
        # Resetear estado para próximas llamadas del usuario
        current_retries = 0
        best_mas_state = {}
        best_error_count = float('inf')
        
        return f"ÉXITO: Proyecto BDI guardado correctamente en {project_dir}"
    except Exception as e:
        return f"ERROR inesperado al guardar: {e}"

# Configuramos el modelo, asumiendo la configuración habitual
model = LiteLlm(
    #model="openai/gpt-oss-120b", 
    model= "openai/Qwen3.6-35B-A3B-FP8",
    api_base="https://api.poligpt.upv.es/",
    api_key="sk-LFXs1kjaSxtEDgOMlPUOpA"
)

root_agent = LlmAgent(
    name="BDI_Developer",
    model=model,
    description="Agente experto en desarrollador proyectos Multi-Agente BDI en Jason",
    instruction=(
        "Eres un agente experto programador en AgentSpeak y Jason, orientado a sistemas Multi-Agente BDI (Belief-Desire-Intention). "
        "Tu objetivo es crear proyectos MAS completos que cumplan con las especificaciones del usuario.\n\n"
        "INSTRUCCIONES CRÍTICAS:\n"
        "1. Analiza lo que pide el usuario y diseña la estructura del sistema: un archivo de configuración .mas2j y uno o más agentes en archivos .asl.\n"
        "2. IMPORTANTE SINTAXIS .mas2j: El archivo de configuración DEBE seguir estrictamente esta estructura:\n"
        "   MAS nombre_proyecto {\n"
        "       infrastructure: Centralised\n"
        "       agents:\n"
        "           nombre_agente_1;\n"
        "           nombre_agente_2 #3; /* Si necesitas instanciar 3 copias */\n"
        "   }\n"
        "   REGLAS MAS2J: Usa 'MAS' en mayúsculas. NO pongas la extensión '.asl' en la lista de agentes. Acaba cada declaración de agente con punto y coma (;).\n"
        "3. IMPORTANTE SINTAXIS AGENTSPEAK (.asl):\n"
        "   - Las creencias y objetivos se deben declarar al principio del fichero, antes de los planes.\n"
        "   - Las variables DEBEN empezar con letra Mayúscula (ej. PosX). Los átomos y literales con minúscula (ej. mesa).\n"
        "   - Para poder operar con un valor de una creencia hay que intanciarlo siempre primero en una variable.\n"
        "   - El formato estricto de un plan es: +!meta(Arg) : contexto <- accion1; accion2. ¡ATENCIÓN: TODOS los planes y creencias DEBEN terminar obligatoriamente con un PUNTO FINAL (.)!\n"
        "   - ¡Evita el error 'No plan for event'! Debes añadir SIEMPRE un plan de contingencia genérico por si falla el contexto: +!meta(_) <- .print(\"Fallo en \", meta).\n"
        "   - Las internal actions nativas de Jason siempre llevan un punto delante (ej. .print(\"Hola\"); .wait(1000);) y recuerda cerrar el plan con PUNTO (.).\n"
        "   - Para iniciar la ejecución debes añadir una creencia o un objetivo inicial en el agente que inicie el sistema. Por ejemplo: DEBES poner \"!start.\" para poder ejecutar al inicio el plan \"+!start <- accion. \" \n"
        "4. Si necesitas inspiración o código de ejemplo, utiliza la herramienta 'search_github_examples(path)'.\n"
        "5. Si necesitas teoría técnica, tutoriales o sintaxis de Programación BDI, usa 'search_local_docs(query)'.\n"
        "6. REGLA PROHIBITIVA ESTRICTA: ESTÁ TOTALMENTE PROHIBIDO DEVOLVER EL CÓDIGO FINAL DE JASON DIRECTAMENTE EN LA RESPUESTA DE TEXTO (MARKDOWN).\n"
        "7. PASO 1 (INVESTIGACIÓN OBLIGATORIA): ANTES de proponer ningún código, ESTÁS OBLIGADO a llamar a la herramienta 'search_local_docs(query)'. Debes buscar en la teoría oficial cómo se implementa lo que el usuario pide.\n"
        "8. PASO 2 (Verificación Práctica): Tras investigar y diseñar el código mentalmente, LLAMA SÍ O SÍ a 'test_mas_code(mas2j_code, agents_dict)' para probar si el sistema compila.\n"
        "9. PASO 3 (Corrección Iterativa): Si 'test_mas_code' falla, lee la excepción devuelta en el log, modifica tu código y vuelve a ejecutar 'test_mas_code' (límite de 5 intentos).\n"
        "10. PASO 4 (Guardado Final): Únicamente cuando la prueba no dé errores o agotes tus intentos, estás OBLIGADO a llamar a 'save_mas_code(mas_name, mas2j_code, agents_dict)' para persistir el proyecto.\n"
        "11. PASO 5 (Notificar al usuario): Informa del éxito de la creación y da un breve resumen.\n"
        "12. CATASTROFE DE SINTAXIS (MUY IMPORTANTE): Al usar las herramientas, SIEMPRE debes usar estrictamente el nombre técnico exacto ('search_github_examples', 'search_local_docs', 'test_mas_code', 'save_mas_code'). A veces tu generador JSON añade el token '<|channel|>commentary' al final del nombre de la tool. ESTO PROVOCA UN ERROR FATAL. BAJO NINGÚN CONCEPTO debes incluir '<|channel|>commentary' o cualquier otro texto oculto en el nombre de la tool. Limítate a generar el nombre en minúsculas y tal cual es."
    ),
    tools=[search_github_examples, rag.search_local_docs, test_mas_code, save_mas_code]
)

