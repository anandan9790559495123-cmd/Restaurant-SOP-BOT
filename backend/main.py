from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
import shutil
import os
import re
from typing import Optional
from datetime import datetime, timedelta

from auth import authenticate
from rag import load_pdf, ask_question, rebuild_index, index_document
import database
from email_utils import generate_otp, send_otp_email

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
        elif "head of kitchen" in desig_lower:
            icon = "fa-kitchen-set"
        elif "head chef" in desig_lower:
            icon = "fa-hat-wizard"
        elif "sous chef" in desig_lower:
            icon = "fa-fire-burner"
        elif "cashier" in desig_lower:
            icon = "fa-cash-register"
        elif "waitress" in desig_lower:
            icon = "fa-champagne-glasses"
        elif "waiter" in desig_lower:
            icon = "fa-bell-concierge"
        elif "bartender" in desig_lower:
            icon = "fa-martini-glass-citrus"
        elif "cleaner" in desig_lower:
            icon = "fa-broom"
            
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
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    display_name: Optional[str] = Form(None),
    allowed_roles: Optional[str] = Form("manager,kitchen,server")
):
    try:
        path = os.path.join(UPLOAD_FOLDER, file.filename)
        
        with open(path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        result = load_pdf(path, display_name, allowed_roles, rebuild=False)
        background_tasks.add_task(index_document, path)
        return {
            "success": True,
            "message": result + " Indexing will complete in the background."
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
def get_analytics_dashboard(
    role: str = Query(...),
    username: Optional[str] = Query(None)
):
    try:
        if role == "manager":
            stats = database.get_analytics()
            logs = database.get_feedback_logs()
        else:
            if not username:
                raise HTTPException(status_code=400, detail="Username is required for worker stats.")
            stats = database.get_worker_analytics(username, role)
            logs = database.get_worker_feedback_logs(username)
        return {
            "success": True,
            "stats": stats,
            "logs": logs
        }
    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
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
    role: str = Form(...),
    username: str = Form(...)
):
    if role != "manager":
        # Check if the log actually belongs to this username
        conn = database.get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM chat_history WHERE id = ?", (chat_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row or row["username"] != username:
            raise HTTPException(status_code=403, detail="Access denied. You can only delete your own logs.")
            
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


@app.post("/change_role_username")
def change_role_username(
    old_username: str = Form(...),
    new_username: str = Form(...),
    new_role: str = Form(...),
    new_display_name: str = Form(...)
):
    new_username = new_username.strip()
    new_display_name = new_display_name.strip()
    
    # 1. Validation for display name
    if len(new_display_name) < 2 or len(new_display_name) > 30:
        return {
            "success": False,
            "message": "Name must be between 2 and 30 characters."
        }
    if not re.match(r"^[A-Za-z]+([ '-][A-Za-z]+)*$", new_display_name):
        return {
            "success": False,
            "message": "Name can only contain letters, spaces, hyphens, and apostrophes."
        }
    vowels = re.findall(r"[aeiouAEIOU]", new_display_name)
    if not vowels:
        return {
            "success": False,
            "message": "Please enter a realistic name containing at least one vowel."
        }
        
    # 2. Validation for new username
    if not new_username:
        return {
            "success": False,
            "message": "Username cannot be empty."
        }
    if new_username != old_username:
        # Check if username is already taken
        existing = database.get_user_profile(new_username)
        if existing:
            return {
                "success": False,
                "message": f"Username '{new_username}' is already taken."
            }
            
    # Determine new designation based on new role
    if new_role == "manager":
        new_designation = "General Manager"
    elif new_role == "kitchen":
        new_designation = "Head Chef"
    elif new_role == "server":
        new_designation = "Service Staff"
    elif new_role == "cashier":
        new_designation = "Cashier"
    elif new_role == "cleaner":
        new_designation = "Cleaner"
    else:
        new_designation = "Staff"
        
    try:
        database.update_user_role_and_username(
            old_username=old_username,
            new_username=new_username,
            new_role=new_role,
            new_designation=new_designation,
            new_display_name=new_display_name
        )
        return {
            "success": True,
            "username": new_username,
            "role": new_role,
            "display_name": new_display_name,
            "designation": new_designation,
            "message": "Role and username updated successfully."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/register_staff")
def register_staff(
    username: str = Form(...),
    password: str = Form(...),
    display_name: str = Form(...),
    role: str = Form(...),
    email: str = Form(...)
):
    username = username.strip()
    display_name = display_name.strip()
    password = password.strip()
    email_val = email.strip().lower() if email else None
    
    if not email_val:
        return {"success": False, "message": "Email is required for password recovery."}
    
    if not username:
        return {"success": False, "message": "Username cannot be empty."}
    if not password or len(password) < 4:
        return {"success": False, "message": "Password must be at least 4 characters."}
        
    existing = database.get_user_profile(username)
    if existing:
        return {"success": False, "message": f"Username '{username}' is already taken."}
        
    if len(display_name) < 2 or len(display_name) > 30:
        return {"success": False, "message": "Name must be between 2 and 30 characters."}
    if not re.match(r"^[A-Za-z]+([ '-][A-Za-z]+)*$", display_name):
        return {"success": False, "message": "Name can only contain letters, spaces, hyphens, and apostrophes."}
    vowels = re.findall(r"[aeiouAEIOU]", display_name)
    if not vowels:
        return {"success": False, "message": "Please enter a realistic name containing at least one vowel."}
        
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email_val):
        return {"success": False, "message": "Please enter a valid email address."}
    
    # Check if email is already used by another user
    existing_email = database.get_user_by_email(email_val)
    if existing_email:
        return {"success": False, "message": "This email is already linked to another account."}
        
    # Map role + optional designation
    designation_map = {
        "manager": "General Manager",
        "kitchen": "Head Chef",
        "server": "Service Staff",
    }
    designation = designation_map.get(role, "Staff")
        
    try:
        database.add_user(username, password, display_name, role, designation, email=email_val)
        return {"success": True, "message": "Staff registered successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/request_role_change")
def request_role_change(
    username: str = Form(...),
    requested_role: str = Form(...),
    requested_username: str = Form(...),
    requested_display_name: str = Form(...)
):
    requested_username = requested_username.strip()
    requested_display_name = requested_display_name.strip()
    
    if not requested_username:
        return {"success": False, "message": "Requested username cannot be empty."}
        
    if requested_username != username:
        existing = database.get_user_profile(requested_username)
        if existing:
            return {"success": False, "message": f"Username '{requested_username}' is already taken."}
            
    if len(requested_display_name) < 2 or len(requested_display_name) > 30:
        return {"success": False, "message": "Name must be between 2 and 30 characters."}
    if not re.match(r"^[A-Za-z]+([ '-][A-Za-z]+)*$", requested_display_name):
        return {"success": False, "message": "Name can only contain letters, spaces, hyphens, and apostrophes."}
    vowels = re.findall(r"[aeiouAEIOU]", requested_display_name)
    if not vowels:
        return {"success": False, "message": "Please enter a realistic name containing at least one vowel."}
        
    try:
        user_prof = database.get_user_profile(username)
        if not user_prof:
            return {"success": False, "message": "User profile not found."}
        current_role = user_prof["role"]
        
        database.create_role_request(username, current_role, requested_role, requested_username, requested_display_name)
        return {"success": True, "message": "Role change request submitted successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/role_requests")
def get_role_requests(
    role: str = Query(...),
    username: Optional[str] = Query(None)
):
    try:
        if role == "manager":
            reqs = database.get_pending_role_requests()
        else:
            if not username:
                raise HTTPException(status_code=400, detail="Username is required for user requests.")
            reqs = database.get_user_role_requests(username)
        return {"success": True, "requests": reqs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/respond_role_request")
def respond_role_request(
    request_id: int = Form(...),
    action: str = Form(...),
    role: str = Form(...)
):
    if role != "manager":
        raise HTTPException(status_code=403, detail="Access denied. Managers only.")
        
    try:
        req = database.get_role_request(request_id)
        if not req:
            return {"success": False, "message": "Request not found."}
            
        if req["status"] != "pending":
            return {"success": False, "message": "Request is already processed."}
            
        if action == "approve":
            requested_role = req["requested_role"]
            designation_map = {
                "manager": "General Manager",
                "kitchen": "Head Chef",
                "server": "Service Staff",
            }
            new_designation = designation_map.get(requested_role, "Staff")
                
            database.update_user_role_and_username(
                old_username=req["username"],
                new_username=req["requested_username"],
                new_role=req["requested_role"],
                new_designation=new_designation,
                new_display_name=req["requested_display_name"]
            )
            database.update_role_request_status(request_id, "approved")
            return {"success": True, "message": "Request approved and applied successfully."}
        else:
            database.update_role_request_status(request_id, "rejected")
            return {"success": True, "message": "Request rejected successfully."}
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================
# PASSWORD MANAGEMENT & OTP
# =============================================

@app.post("/forgot_password")
def forgot_password(email: str = Form(...)):
    """Send OTP to user's registered email for password reset."""
    email = email.strip().lower()
    if not email:
        return {"success": False, "message": "Email cannot be empty."}
    
    user = database.get_user_by_email(email)
    if not user:
        return {"success": False, "message": "No account found with this email address."}
    
    otp_code = generate_otp()
    expires_at = (datetime.now() + timedelta(minutes=10)).isoformat()
    database.save_otp(email, otp_code, expires_at)
    
    try:
        send_otp_email(email, otp_code)
        return {"success": True, "message": "OTP sent to your email address."}
    except Exception as e:
        return {"success": False, "message": f"Failed to send email: {str(e)}"}


@app.post("/verify_otp")
def verify_otp_endpoint(email: str = Form(...), otp: str = Form(...)):
    """Verify the OTP code."""
    email = email.strip().lower()
    otp = otp.strip()
    
    if not otp or len(otp) != 6:
        return {"success": False, "message": "Please enter a valid 6-digit OTP."}
    
    result = database.verify_otp(email, otp)
    if result:
        return {"success": True, "message": "OTP verified successfully."}
    else:
        return {"success": False, "message": "Invalid or expired OTP. Please try again."}


@app.post("/reset_password")
def reset_password(
    email: str = Form(...),
    otp: str = Form(...),
    new_password: str = Form(...)
):
    """Reset password after OTP verification."""
    email = email.strip().lower()
    otp = otp.strip()
    new_password = new_password.strip()
    
    if not new_password or len(new_password) < 4:
        return {"success": False, "message": "Password must be at least 4 characters."}
    
    # Verify OTP is still valid
    result = database.verify_otp(email, otp)
    if not result:
        return {"success": False, "message": "Invalid or expired OTP. Please request a new one."}
    
    user = database.get_user_by_email(email)
    if not user:
        return {"success": False, "message": "User not found."}
    
    # Update password and mark OTP as used
    database.update_user_password(user["username"], new_password)
    database.mark_otp_used(email)
    
    return {"success": True, "message": "Password reset successfully! You can now log in with your new password."}


@app.post("/change_password")
def change_password(
    username: str = Form(...),
    current_password: str = Form(...),
    new_password: str = Form(...)
):
    """Change password for a logged-in user."""
    new_password = new_password.strip()
    
    if not new_password or len(new_password) < 4:
        return {"success": False, "message": "New password must be at least 4 characters."}
    
    # Verify current password
    user = database.get_user_profile(username)
    if not user:
        return {"success": False, "message": "User not found."}
    
    if user["password"] != current_password:
        return {"success": False, "message": "Current password is incorrect."}
    
    if current_password == new_password:
        return {"success": False, "message": "New password must be different from current password."}
    
    database.update_user_password(username, new_password)
    return {"success": True, "message": "Password changed successfully!"}


@app.post("/update_email")
def update_email(
    username: str = Form(...),
    email: str = Form(...)
):
    """Update user email address."""
    email = email.strip().lower()
    
    if not email:
        return {"success": False, "message": "Email cannot be empty."}
    
    # Basic email format validation
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        return {"success": False, "message": "Please enter a valid email address."}
    
    # Check if email is already used by another user
    existing = database.get_user_by_email(email)
    if existing and existing["username"] != username:
        return {"success": False, "message": "This email is already linked to another account."}
    
    database.update_user_email(username, email)
    return {"success": True, "message": "Email updated successfully.", "email": email}


@app.post("/delete_staff")
def delete_staff(
    target_username: str = Form(...),
    role: str = Form(...),
    username: str = Form(...)
):
    """Permanently delete a staff account. Manager-only action."""
    if role != "manager":
        raise HTTPException(status_code=403, detail="Access denied. Managers only.")
    
    if target_username == username:
        return {"success": False, "message": "You cannot delete your own account."}
    
    target = database.get_user_profile(target_username)
    if not target:
        return {"success": False, "message": f"User '{target_username}' not found."}
    
    try:
        database.delete_user(target_username)
        return {"success": True, "message": f"Staff account '{target_username}' permanently deleted."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/register_staff_with_designation")
def register_staff_with_designation(
    username: str = Form(...),
    password: str = Form(...),
    display_name: str = Form(...),
    role: str = Form(...),
    designation: str = Form(...),
    email: str = Form(...)
):
    """Register new staff with a specific designation."""
    username = username.strip()
    display_name = display_name.strip()
    password = password.strip()
    designation = designation.strip()
    email_val = email.strip().lower() if email else None
    
    if not email_val:
        return {"success": False, "message": "Email is required for password recovery."}
    
    if not username:
        return {"success": False, "message": "Username cannot be empty."}
    if not password or len(password) < 4:
        return {"success": False, "message": "Password must be at least 4 characters."}
        
    existing = database.get_user_profile(username)
    if existing:
        return {"success": False, "message": f"Username '{username}' is already taken."}
        
    if len(display_name) < 2 or len(display_name) > 30:
        return {"success": False, "message": "Name must be between 2 and 30 characters."}
    if not re.match(r"^[A-Za-z]+([ '-][A-Za-z]+)*$", display_name):
        return {"success": False, "message": "Name can only contain letters, spaces, hyphens, and apostrophes."}
    vowels = re.findall(r"[aeiouAEIOU]", display_name)
    if not vowels:
        return {"success": False, "message": "Please enter a realistic name containing at least one vowel."}
        
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email_val):
        return {"success": False, "message": "Please enter a valid email address."}
    
    # Check if email is already used by another user
    existing_email = database.get_user_by_email(email_val)
    if existing_email:
        return {"success": False, "message": "This email is already linked to another account."}
    
    # Validate designation belongs to the right role
    valid_designations = {
        "manager": ["General Manager"],
        "kitchen": ["Head Chef", "Sous Chef", "Head of Kitchen"],
        "server": ["Waiter", "Waitress", "Bartender", "Cashier", "Senior Waiter", "Service Staff", "Cleaner"]
    }
    
    if designation not in valid_designations.get(role, []):
        # Fall back to default designation for the role
        designation_defaults = {
            "manager": "General Manager",
            "kitchen": "Head Chef",
            "server": "Service Staff"
        }
        designation = designation_defaults.get(role, "Staff")
    
    try:
        database.add_user(username, password, display_name, role, designation, email=email_val)
        return {"success": True, "message": f"Staff '{display_name}' registered as {designation} successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))