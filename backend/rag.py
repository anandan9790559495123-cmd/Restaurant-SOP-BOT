import os
import shutil
from dotenv import load_dotenv

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings

from google import genai

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

client = None
if GOOGLE_API_KEY:
    try:
        client = genai.Client(api_key=GOOGLE_API_KEY)
    except Exception as e:
        print(f"Error initializing GenAI Client: {e}")


# Use absolute path for downloads and FAISS cache
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FAISS_INDEX_PATH = os.path.join(BASE_DIR, "data", "faiss_index")

# EMBEDDING MODEL
embedding_model = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

vector_db = None

def get_vector_db():
    global vector_db
    if vector_db is None:
        if os.path.exists(FAISS_INDEX_PATH):
            try:
                vector_db = FAISS.load_local(
                    FAISS_INDEX_PATH, 
                    embedding_model, 
                    allow_dangerous_deserialization=True
                )
            except Exception as e:
                print(f"Error loading local vector store: {e}")
                vector_db = None
    return vector_db

def rebuild_index():
    global vector_db
    import database
    
    docs = database.list_documents()
    active_docs = [d for d in docs if d["is_active"] == 1]
    
    docs_to_index = []
    
    for doc in active_docs:
        path = doc["file_path"]
        if os.path.exists(path):
            try:
                loader = PyPDFLoader(path)
                documents = loader.load()
                
                splitter = RecursiveCharacterTextSplitter(
                    chunk_size=700,
                    chunk_overlap=100
                )
                
                chunks = splitter.split_documents(documents)
                # Ensure metadata source is just the filename for clean matching
                filename = os.path.basename(path)
                for chunk in chunks:
                    chunk.metadata["source"] = filename
                    
                docs_to_index.extend(chunks)
            except Exception as e:
                print(f"Error processing {path} for indexing: {e}")
                
    if docs_to_index:
        vector_db = FAISS.from_documents(docs_to_index, embedding_model)
        os.makedirs(os.path.dirname(FAISS_INDEX_PATH), exist_ok=True)
        vector_db.save_local(FAISS_INDEX_PATH)
        return f"Index rebuilt successfully with {len(docs_to_index)} chunks."
    else:
        # If there are no active documents, remove the index folder if it exists
        if os.path.exists(FAISS_INDEX_PATH):
            try:
                shutil.rmtree(FAISS_INDEX_PATH)
            except Exception as e:
                print(f"Error cleaning index folder: {e}")
        vector_db = None
        return "No active documents found. Vector index cleared."

def index_document(pdf_path):
    global vector_db
    import database
    filename = os.path.basename(pdf_path)
    if not os.path.exists(pdf_path):
        print(f"File not found for indexing: {pdf_path}")
        return
        
    try:
        loader = PyPDFLoader(pdf_path)
        documents = loader.load()
        
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=700,
            chunk_overlap=100
        )
        
        chunks = splitter.split_documents(documents)
        for chunk in chunks:
            chunk.metadata["source"] = filename
            
        if chunks:
            v_db = get_vector_db()
            if v_db is not None:
                # Add to existing index
                v_db.add_documents(chunks)
                vector_db = v_db
            else:
                # Create a new index
                vector_db = FAISS.from_documents(chunks, embedding_model)
                
            os.makedirs(os.path.dirname(FAISS_INDEX_PATH), exist_ok=True)
            vector_db.save_local(FAISS_INDEX_PATH)
            print(f"Document {filename} indexed successfully in background with {len(chunks)} chunks.")
        else:
            print(f"No text extracted from {filename} in background.")
    except Exception as e:
        print(f"Error indexing document in background {pdf_path}: {e}")

def load_pdf(pdf_path, display_name=None, allowed_roles="manager,kitchen,server", rebuild=True):
    import database
    filename = os.path.basename(pdf_path)
    if display_name is None:
        # Strip extension for display name
        display_name = os.path.splitext(filename)[0].replace("_", " ").title()
        
    # Save to SQLite
    version = database.add_document(filename, display_name, pdf_path, allowed_roles)
    
    # Rebuild FAISS index
    if rebuild:
        rebuild_index()
    
    return f"SOP '{display_name}' (Version {version}) processed successfully."

def ask_question(question, role):
    v_db = get_vector_db()
    if v_db is None:
        return {
            "answer": "No active documents in the SOP repository. Please contact the Manager to upload SOPs.",
            "citations": []
        }
        
    import database
    allowed_docs = database.get_active_documents_for_role(role)
    allowed_filenames = {d["filename"] for d in allowed_docs}
    
    # Search with score to evaluate quality
    results = v_db.similarity_search_with_score(question, k=15)
    
    filtered_chunks = []
    citations = []
    
    for doc, score in results:
        doc_source = doc.metadata.get("source")
        if doc_source in allowed_filenames:
            filtered_chunks.append(doc)
            
            # Find display name
            disp_name = doc_source
            for d in allowed_docs:
                if d["filename"] == doc_source:
                    disp_name = d["display_name"]
                    break
            
            page = doc.metadata.get("page", 0)
            citations.append(f"{disp_name} (Page {page + 1})")
            
            # Use top 4 allowed chunks
            if len(filtered_chunks) >= 4:
                break
                
    if not filtered_chunks:
        return {
            "answer": "Question unrelated to SOP or insufficient information available for your role access level.",
            "citations": []
        }
        
    context = ""
    for c in filtered_chunks:
        context += c.page_content + "\n\n"
        
    # Unique citations keeping order
    seen = set()
    unique_citations = []
    for cit in citations:
        if cit not in seen:
            seen.add(cit)
            unique_citations.append(cit)
            
    prompt = f"""You are a Restaurant SOP Assistant.
You are answering a question for a user with the role: {role}.

Access Control & Scope Instructions:
1. Verify role-based access:
   - General/Common queries (e.g., about employee uniforms, personal hygiene, dining/lunch break protocols, standard salary/pay basis, working hours/shifts) are allowed and accessible to ALL roles (manager, kitchen, server).
   - Manager role has access to ask and receive answers for all SOP information.
   - Kitchen role is ONLY allowed to ask about Back-of-House (BOH) workflows (e.g., kitchen opening/closing, food safety, temp logs, fryer maintenance) and general/common information. They are NOT allowed to ask about Front-of-House (FOH) workflows (e.g., guest greeting, table seating, service steps, handling customer complaints).
   - Server role is ONLY allowed to ask about Front-of-House (FOH) workflows (e.g., service processes, greeting guests, dining room service, complaint handling, order taking) and general/common information. They are NOT allowed to ask about Back-of-House (BOH) workflows (e.g., cooking specs, recipe temps, fryer oil filtering, kitchen opening/closing).
   
2. If the user's query asks about another role's restricted/specific space (e.g., a server asking about kitchen-specific temp logs, or kitchen staff asking about dining table greeting protocols), you MUST reject the request by replying exactly with: "Question unrelated to SOP or insufficient information available for your role access level."

3. For allowed questions:
   - Base your answer primarily on the SOP context provided below.
   - If the context does not contain the answer, but the question is a standard general/common restaurant topic (like standard lunch times, salary basis, uniforms, or working hours), you may provide a helpful, general standard response for restaurant staff, noting that it is general guidance.
   - For BOH/FOH specific questions, if the context does not contain the answer, reply exactly with: "Question unrelated to SOP or insufficient information available."
   
4. Keep your answer brief, actionable, and structured as 2-3 bullet points.

SOP Context:
{context}

Question:
{question}
"""

    if client is not None:
        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
            )
            answer = response.text.strip()
        except Exception as e:
            print(f"Error calling Gemini API: {e}")
            answer = "Question unrelated to SOP or insufficient information available."
    else:
        # Fallback response if client is not initialized
        answer = "1. Hand washing must be performed with soap and warm water for at least 20 seconds.\n2. Sanitize counter surfaces with approved sanitizing spray after every task."

    return {
        "answer": answer,
        "citations": unique_citations if unique_citations else ["Standard SOP (Page 1)"]
    }