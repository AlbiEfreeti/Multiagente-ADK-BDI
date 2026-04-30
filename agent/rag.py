from pathlib import Path
import warnings

warnings.filterwarnings("ignore")

BASE_DIR = Path(__file__).parent.absolute()
DOCS_PATH = [str(BASE_DIR / "docs")]

VECTORSTORE = None

def load_documents(paths):
    texts = []
    
    def extract_file(f):
        if f.suffix.lower() == ".pdf":
            try:
                import pypdf
                reader = pypdf.PdfReader(str(f))
                text = "\n".join(page.extract_text() for page in reader.pages if page.extract_text())
                if text.strip():
                    texts.append(text)
            except ImportError:
                texts.append("Aviso: Falta instalar pypdf para procesar " + f.name)
            except Exception:
                pass
        elif f.suffix.lower() in {".txt", ".md", ".asl", ".java", ".html"}:
            try:
                texts.append(f.read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                pass

    for p in paths:
        path = Path(p)
        if path.is_dir():
            for f in path.rglob("*"):
                extract_file(f)
        else:
            if path.exists():
                extract_file(path)
    return texts

def chunk_text(text, chunk_size=800, overlap=120):
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks

def build_vectorstore(paths):
    # Import locally to prevent framework collision
    import chromadb
    
    db_path = str(BASE_DIR / ".rag_db")
    client = chromadb.PersistentClient(path=db_path)
    collection = client.get_or_create_collection("jason_docs")
    
    if collection.count() > 0:
        return collection
        
    docs = load_documents(paths)
    if not docs:
        return collection

    all_chunks = []
    ids = []
    idx = 0
    for doc in docs:
        for chunk in chunk_text(doc):
            all_chunks.append(chunk)
            ids.append(f"chunk_{idx}")
            idx += 1
            
    # Add in batches to avoid ChromaDB limits. 
    # Notice we don't encode embeddings manually here, Chroma uses ONNX runtime naturally.
    batch_size = 5000
    for i in range(0, len(ids), batch_size):
        collection.add(
            ids=ids[i:i+batch_size], 
            documents=all_chunks[i:i+batch_size]
        )
        
    return collection

def init_rag(paths=None):
    global VECTORSTORE
    if paths is None:
        paths = DOCS_PATH
    if VECTORSTORE is None:
        VECTORSTORE = build_vectorstore(paths)

def search_local_docs(query: str, k: int = 4) -> str:
    """
    Busca información en la documentación local de Jason BDI (carpeta 'docs').
    Utiliza esta herramienta cuando tengas dudas sobre cómo programar una característica
    específica en Jason/AgentSpeak o necesites consultar la sintaxis teórica y tutoriales.
    
    Args:
        query: La pregunta textual para buscar.
        k: Número de fragmentos teóricos a recuperar (4 por defecto).
    """
    try:
        init_rag() 
        
        if VECTORSTORE.count() == 0:
            return f"Aviso RAG: No se encontraron documentos indexados en la carpeta '{DOCS_PATH[0]}' o está vacía."
            
        result = VECTORSTORE.query(
            query_texts=[query],
            n_results=k
        )
        
        docs_found = result.get("documents", [])
        if docs_found and docs_found[0]:
            text_blocks = [f"--- Fragmento {i+1} ---\n{t}" for i, t in enumerate(docs_found[0])]
            return "RESULTADOS DE LA DOCUMENTACIÓN (RAG):\n\n" + "\n\n".join(text_blocks)
        else:
            return "No se encontró información relevante para tu consulta en los documentos locales."
            
    except Exception as e:
        return f"Error interno en RAG al consultar la documentación: {e}"
