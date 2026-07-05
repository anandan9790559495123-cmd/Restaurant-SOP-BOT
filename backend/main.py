from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
import shutil
import os
import re
from typing import Optional

from auth import authenticate
from rag import load_pdf, ask_question, rebuild_index
import database

app = FastAPI(title="Restaurant SOP Bot Backend")

# Enable CORS for local cross-origin development (e.g. Live Server, file schemes, Streamlit port)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Path to the frontend static directory
FRONTEND_STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend", "static")
os.makedirs(FRONTEND_STATIC_DIR, exist_ok=True)

# Mount frontend/static at /static path
app.mount("/static", StaticFiles(directory=FRONTEND_STATIC_DIR), name="static")


@app.get("/", response_class=RedirectResponse)
def home():
    return RedirectResponse(url="/static/index.html")


@app.post("/login")
def login(
    username: str = Form(...),
    password: str = Form(...)
):
    user = authenticate(username, password)
    if user:
        return {
            "success": True,
            "role": user["role"],
            "username": user["username"],
            "display_name": user.get("display_name", user["username"]),
            "designation": user.get("designation", "Staff")
        }
    return {
        "success": False,
        "message": "Invalid credentials"
    }


@app.post("/update_profile")
def update_profile(
    username: str = Form(...),
    display_name: str = Form(...)
):
    display_name = display_name.strip()
    
    # 1. Validation: length 2-30
    if len(display_name) < 2 or len(display_name) > 30:
        return {
            "success": False,
            "message": "Name must be between 2 and 30 characters."
        }
        
    # 2. Validation: Letters, spaces, hyphens, periods, apostrophes only
    if not re.match(r"^[A-Za-z]+([ '-][A-Za-z]+)*$", display_name):
        return {
            "success": False,
            "message": "Name can only contain letters, spaces, hyphens, and apostrophes."
        }
        
    # 3. Validation: Avoid obvious random typing (e.g., no vowels like 'zxcv', or too many repeated letters)
    vowels = re.findall(r"[aeiouAEIOU]", display_name)
    if not vowels:
        return {
            "success": False,
            "message": "Please enter a realistic name containing at least one vowel."
        }
        
    # Update DB
    database.update_user_display_name(username, display_name)
    return {
        "success": True,
        "message": "Display name updated successfully.",
        "display_name": display_name
    }


@app.get("/staff")
def get_staff():
    conn = database.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT username, display_name, designation, role FROM users")
    rows = cursor.fetchall()
    conn.close()
    
    staff_list = []
    for r in rows:
        d = dict(r)
        
        # Assign premium icons based on role and designation
        icon = "fa-user"
        desig_lower = d["designation"].lower()
        if "general manager" in desig_lower:
            icon = "fa-user-tie"
        elif "head chef" in desig_lower:
            icon = "fa-hat-wizard"
        elif "sous chef" in desig_lower:
            icon = "fa-fire-burner"
        elif "waiter" in desig_lower:
            icon = "fa-bell-concierge"
        elif "waitress" in desig_lower:
            icon = "fa-champagne-glasses"
        elif "bartender" in desig_lower:
            icon = "fa-martini-glass-citrus"
            
        staff_list.append({
            "username": d["username"],
            "name": d["display_name"],
            "designation": d["designation"],
            "role": d["role"],
            "icon": icon
        })
        
    return {
        "success": True,
        "staff": staff_list
    }


@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    display_name: Optional[str] = Form(None),
    allowed_roles: Optional[str] = Form("manager,kitchen,server")
):
    try:
        path = os.path.join(UPLOAD_FOLDER, file.filename)
        
        with open(path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        result = load_pdf(path, display_name, allowed_roles)
        return {
            "success": True,
            "message": result
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"UPLOAD ERROR: {str(e)}"
        }


@app.post("/ask")
def ask(
    question: str = Form(...),
    role: str = Form(...),
    username: str = Form(...)
):
    try:
        result = ask_question(question, role)
        
        # Save to chat history database
        chat_id = database.save_chat_message(
            username=username,
            role=role,
            question=question,
            answer=result["answer"],
            citations=result.get("citations", [])
        )
        
        result["chat_id"] = chat_id
        return result
    except Exception as e:
        return {
            "answer": f"QUESTION ERROR: {str(e)}",
            "citations": [],
            "chat_id": None
        }


@app.post("/feedback")
def submit_feedback(
    chat_id: int = Form(...),
    rating: int = Form(...), # 1 or -1
    comments: str = Form("")
):
    try:
        database.save_feedback(chat_id, rating, comments)
        return {
            "success": True,
            "message": "Feedback submitted successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/history")
def get_history(username: str = Query(...)):
    try:
        history = database.get_chat_history(username)
        return {
            "success": True,
            "history": history
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/clear_history")
def clear_history(username: str = Form(...)):
    try:
        database.clear_chat_history(username)
        return {
            "success": True,
            "message": "Chat history cleared"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documents")
def get_documents():
    try:
        docs = database.list_documents()
        return {
            "success": True,
            "documents": docs
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/documents/preview")
def preview_document(filename: str = Query(...)):
    try:
        path = os.path.join(UPLOAD_FOLDER, filename)
        if not os.path.exists(path):
            path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads", filename)
            
        if os.path.exists(path):
            import pypdf
            reader = pypdf.PdfReader(path)
            num_pages = len(reader.pages)
            text = ""
            if num_pages > 0:
                text = reader.pages[0].extract_text()
            return {
                "success": True,
                "pages": num_pages,
                "preview": text[:1200] if text else "No extractable text found on the first page."
            }
        return {
            "success": False,
            "message": f"Physical file '{filename}' not found on server disk."
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Error parsing PDF: {str(e)}"
        }


@app.post("/documents/toggle")
def toggle_document(
    filename: str = Form(...),
    is_active: bool = Form(...)
):
    try:
        database.toggle_document_status(filename, is_active)
        rebuild_msg = rebuild_index()
        return {
            "success": True,
            "message": f"Status updated. {rebuild_msg}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/documents/update_roles")
def update_roles(
    filename: str = Form(...),
    allowed_roles: str = Form(...)
):
    try:
        database.update_document_roles(filename, allowed_roles)
        # Note: roles are evaluated dynamically, no index rebuild needed for role changes
        return {
            "success": True,
            "message": "Permissions updated successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/documents/delete")
def delete_document(filename: str = Form(...)):
    try:
        # Find document details
        docs = database.list_documents()
        doc = next((d for d in docs if d["filename"] == filename), None)
        
        # Delete from database
        database.delete_document(filename)
        
        # Delete file if exists
        if doc and os.path.exists(doc["file_path"]):
            try:
                os.remove(doc["file_path"])
            except Exception as e:
                print(f"Error removing physical file: {e}")
                
        # Rebuild index
        rebuild_msg = rebuild_index()
        return {
            "success": True,
            "message": f"Document deleted. {rebuild_msg}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/index/refresh")
def refresh_index():
    try:
        msg = rebuild_index()
        return {
            "success": True,
            "message": msg
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analytics")
def get_analytics_dashboard(role: str = Query(...)):
    if role != "manager":
        raise HTTPException(status_code=403, detail="Access denied. Managers only.")
    try:
        stats = database.get_analytics()
        logs = database.get_feedback_logs()
        return {
            "success": True,
            "stats": stats,
            "logs": logs
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/documents/clear_all")
def clear_all_documents():
    try:
        # List all documents to get their file paths
        docs = database.list_documents()
        
        # Clear from database
        database.clear_all_documents()
        
        # Delete all physical files
        for doc in docs:
            if os.path.exists(doc["file_path"]):
                try:
                    os.remove(doc["file_path"])
                except Exception as e:
                    print(f"Error removing physical file {doc['file_path']}: {e}")
                    
        # Rebuild index (this will clear the FAISS vector index)
        rebuild_msg = rebuild_index()
        return {
            "success": True,
            "message": f"All documents deleted from repository. {rebuild_msg}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analytics/delete_log")
def delete_log(
    chat_id: int = Form(...),
    role: str = Form(...)
):
    if role != "manager":
        raise HTTPException(status_code=403, detail="Access denied. Managers only.")
    try:
        database.delete_chat_log(chat_id)
        return {
            "success": True,
            "message": "Audit log entry deleted successfully."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analytics/clear_logs")
def clear_all_logs(role: str = Form(...)):
    if role != "manager":
        raise HTTPException(status_code=403, detail="Access denied. Managers only.")
    try:
        database.clear_all_feedback_and_history()
        return {
            "success": True,
            "message": "All audit logs and quality feedback cleared successfully."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))