import streamlit as st
import requests
from langchain_core.messages import HumanMessage

import time
from dotenv import load_dotenv
import os
from requests.exceptions import ConnectionError, Timeout, RequestException
from streamlit_autorefresh import st_autorefresh


# ========================================
# Load Environment Variables
# ========================================
load_dotenv()
API_BASE_URL = os.getenv("API_BASE_UL")  

# ========================================
# Session State Initialization
# ========================================

if 'access_token' not in st.session_state:
    st.session_state['access_token'] = None

if 'refresh_token' not in st.session_state:
    st.session_state['refresh_token'] = None

if 'user_info' not in st.session_state:
    st.session_state['user_info'] = None

if 'msg_hist' not in st.session_state:
    st.session_state['msg_hist'] = []

if 'show_upload' not in st.session_state:
    st.session_state['show_upload'] = False

if 'thread_titles' not in st.session_state:
    st.session_state['thread_titles'] = {}
    
if "upload_job_id" not in st.session_state:
    st.session_state["upload_job_id"] = None

if "upload_status" not in st.session_state:
    st.session_state["upload_status"] = None
    

if "thread_id" not in st.session_state:
    st.session_state["thread_id"] = None

if "chat_thread" not in st.session_state:
    st.session_state["chat_thread"] = []

if "messages" not in st.session_state:
    st.session_state["messages"] = []

    
    
# new one
if "rate_limited_until" not in st.session_state:
    st.session_state["rate_limited_until"] = 0

if "is_generating" not in st.session_state:
    st.session_state["is_generating"] = False
    

    
    
#========================================
# Authentication Helpers
# ========================================
def get_auth_headers():
    """Get authorization headers with token"""
    if st.session_state['access_token']:
        return {"Authorization": f"Bearer {st.session_state['access_token']}"}
    return {}
def  is_authenticated():
    """Check if user is authenticated"""
    return st.session_state['access_token'] is not None

def  logout():
    """Clear authentication state"""
    st.session_state['access_token'] = None
    st.session_state['refresh_token'] = None
    st.session_state['user_info'] = None
    st.session_state['msg_hist'] = []
    st.session_state['thread_id'] = None
    st.session_state['chat_thread'] = []
    st.session_state['thread_titles'] = {}
    
    st.session_state["rate_limited_until"] = 0
    st.session_state["is_generating"] = False


# ========================================
# API Helper Functions
# ========================================
def handle_api_error(response):
    """Parse API error response and return user-friendly message"""
    try:
        error_data = response.json()
        detail = error_data.get("detail", "Unknown error")
        if "⚠️" in detail or "❌" in detail or len(detail.split()) > 3:
            return detail
        return f"Error {response.status_code}: {detail}"
    except:
        return f"Error {response.status_code}: {response.text}"

def safe_api_call(method, endpoint, **kwargs):
    """Execute API call with centralized error handling"""
    url = f"{API_BASE_URL}{endpoint}"
    timeout = kwargs.pop("timeout", 120)
    
    
    if is_authenticated():
        headers = kwargs.get("headers", {})
        headers.update(get_auth_headers())
        kwargs["headers"] = headers
        
    try:
        response = requests.request(method, url, timeout=timeout, **kwargs)
            # Handle 401 - try token refresh
        if response.status_code == 401 and  is_authenticated() and  st.session_state['refresh_token']:
            
            if refresh_access_token():
                # Retry with new token
                headers = kwargs.get("headers", {})
                headers.update(get_auth_headers())
                kwargs["headers"] = headers
                response = requests.request(method, url, timeout=timeout, **kwargs)
            else:
                logout()
                st.error("❌ Session expired. Please login again.")
                st.rerun()
            
        return response
    except ConnectionError:
        st.error(f"❌ Could not connect to backend at {API_BASE_URL}. Is it running?")
        return None
    except Timeout:
        st.error("⏳ Request timed out. The server took too long to respond.")
        return None
    except RequestException as e:
        st.error(f"⚠️ Network error: {str(e)}")
        return None
    
# if st.session_state.get("current_job"):

#     status_response = safe_api_call(
#         "GET",
#         f"/documents/status/{st.session_state.current_job}"
#     )

#     if status_response and status_response.status_code == 200:
#         status = status_response.json()["status"]

#         if status == "completed":
#             st.success("Document processing completed!")
#             del st.session_state.current_job

#         elif status == "failed":
#             st.error("Document processing failed.")
#             del st.session_state.current_job

#         else:
#             st.info("Processing in background...")
#             st_autorefresh(interval=3000, key="upload_refresh")

# ========================================
# Upload Status Polling (CORRECT VERSION)
# ========================================

if st.session_state.get("current_job"):

    job_id = st.session_state.current_job

    status_response = safe_api_call(
        "GET",
        f"/documents/upload-status/{job_id}"
    )

    if status_response and status_response.status_code == 200:

        status = status_response.json().get("status")

        if status == "done":
            st.success("✅ Document processing completed!")
            del st.session_state.current_job
            st.rerun()

        elif status == "failed":
            st.error("❌ Document processing failed.")
            del st.session_state.current_job

        elif status == "deleted":
            st.warning("⚠️ Document was deleted.")
            del st.session_state.current_job
            st.rerun()

        elif status == "processing":
            st.info("⏳ Processing in background...")
            st_autorefresh(interval=3000, key="upload_refresh")






    
def refresh_access_token():
    """Refresh access token using refresh token"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/auth/refresh",
            headers={"Authorization": f"Bearer {st.session_state['refresh_token']}"},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            st.session_state['access_token'] = data['access_token']
            st.session_state['refresh_token'] = data['refresh_token']
            return True
    except:
        pass
    return False


#========================================
# Authentication API Calls
# ========================================
def register_user(username, email, password):
    """Register new user"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/auth/register",
            json={"username": username, "email": email, "password": password},
            timeout=10
        )
        if response.status_code == 201:
            data = response.json()
            st.session_state['access_token'] = data['access_token']
            st.session_state['refresh_token'] = data['refresh_token']
            fetch_user_info()
            return {"success": True}
        else:
            error = response.json().get("detail", "Registration failed")
            return {"success": False, "message": error}
    except Exception as e:
        return {"success": False, "message": f"Error: {str(e)}"}

def login_user(username, password):
    """Login user"""
    try:
        response = requests.post(
            f"{API_BASE_URL}/auth/login",
            json={"username": username, "password": password},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            st.session_state['access_token'] = data['access_token']
            st.session_state['refresh_token'] = data['refresh_token']
            fetch_user_info()
            return {"success": True}
        else:
            return {"success": False, "message": "Invalid credentials"}
    except Exception as e:
        return {"success": False, "message": f"Error: {str(e)}"}

def fetch_user_info():
    """Fetch current user information"""
    response = safe_api_call("GET", "/auth/me")
    if response and response.status_code == 200:
        st.session_state['user_info'] = response.json()


# ========================================
# Thread Management
# ========================================
def create_new_thread():
    response = safe_api_call("POST", "/threads/new")
    if response and response.status_code == 200:
        return response.json()["thread_id"]
    return None

def get_all_threads():
    response = safe_api_call("GET", "/threads")
    if response and response.status_code == 200:
        return response.json()["threads"]
    return []

def load_thread_history(thread_id):
    response = safe_api_call("GET", f"/threads/{thread_id}/history")
    if response and response.status_code == 200:
        return response.json()["messages"]
    return []


# ========================================
# Chat Functions
# ========================================
# def send_message_stream(message, thread_id):
#     response = safe_api_call(
#         "POST", "/chat", json={"message": message, "thread_id": thread_id}, timeout=90
#     )
#     if response:
#         if response.status_code == 200:
#             return response.json()["reply"]
#         else:
#             st.error(handle_api_error(response))
#     return None

# new one after the slowapi
def send_message_stream(message, thread_id):
    response = safe_api_call(
        "POST",
        "/chat",
        json={"message": message, "thread_id": thread_id},
        timeout=120
    )

    if response is None:
        return {"ok": False, "type": "network"}
    
    if response.status_code == 503:
        return {
            "ok": False,
            "type": "quota",
            "message": response.json().get(
                "detail",
                "AI service temporarily unavailable."
            )
        }

    if response.status_code == 429:
        retry_after = int(response.headers.get("Retry-After", 60))
        return {
            "ok": False,
            "type": "rate_limit",
            "retry_after": retry_after
        }

    if response.status_code != 200:
        return {
            "ok": False,
            "type": "server",
            "message": handle_api_error(response)
        }
    # if response.status_code == 429:
    #     retry_after = int(response.headers.get("Retry-After", 60))
    #     st.session_state.rate_limited_until = time.time() + retry_after
    #     st.session_state.is_generating = False
    #     st.rerun()
 

    return {
        "ok": True,
        "reply": response.json()["reply"]
    }



def stream_text(text):
    """Yield text word by word for streaming effect"""
    if not text:
        return
    words = text.split()
    for word in words:
        yield word + " "
        time.sleep(0.05)
        


# ========================================
# Document Management
# ========================================

def upload_document(file):
    files = {"file": (file.name, file, file.type)}
    response = safe_api_call("POST", "/documents/upload", files=files)

    if response is None:
        return {"success": False, "message": " Network failure"}

    # ✅ SUCCESS
    # if response.status_code == 200:
    #     return {"success": True, "data": response.json()}
    if response.status_code == 200:
        data = response.json()

        return {
            "success": True,
            "job_id": data.get("job_id"),
            "status": data.get("status"),
            "message": data.get("message")
        }

    #  FILE TOO LARGE
    if response.status_code == 413:
        return {"success": False, "message": " File too large (max 2.5 MB)"}

    #  DOCUMENT ISSUES (THIS IS THE KEY FIX)
    if response.status_code == 422:
        try:
            detail = response.json().get("detail", "").lower()
        except Exception:
            detail = ""

        #  HARD NORMALIZATION (NO LEAKAGE)
        if (
            "no readable text" in detail
            or "0 chunks" in detail
            or "empty" in detail
            or "extract" in detail
        ):
            return {
                "success": False,
                "message": " Invalid file format or empty PDF"
            }

        return {
            "success": False,
            "message": " Document processing failed"
        }

    return {"success": False, "message": handle_api_error(response)}



def get_documents():
    response = safe_api_call("GET", "/documents")
    if response and response.status_code == 200:
        return response.json()["documents"]
    return []

def delete_document(filename):
    response = safe_api_call("DELETE", f"/documents/{filename}")
    if response and response.status_code == 200:
        return response.json()
    return None

def clear_all_documents():
    response = safe_api_call("DELETE", "/documents")
    if response and response.status_code == 200:
        return response.json()
    return None

# ========================================
# Thread Title Helpers
# ========================================
def generate_chat_title(text, max_words=4):
    """Create a short, user-friendly title from first user query"""
    if not text:
        return "New Chat"
    text = text.replace("?", "").replace(".", "")
    words = text.split()
    title = " ".join(words[:max_words]).title()
    return title

def update_thread_title_backend(thread_id, title):
    """Send thread title to backend"""
    response = safe_api_call("POST", f"/threads/{thread_id}/title", json={"title": title})
    if response and response.status_code == 200:
        return True
    else:
        #st.error(f"Failed to update thread title: {handle_api_error(response)}")
        return False
    
# def ensure_thread_exists(first_user_message=None):
#     """
#     Ensure a valid thread_id exists.
#     If not, create one (silent auto-create).
#     """
#     if 'thread_id' not in st.session_state or not st.session_state['thread_id']:
#         new_thread_id = create_new_thread()
#         if new_thread_id:
#             st.session_state['thread_id'] = new_thread_id
#             st.session_state['msg_hist'] = []

#             # Add to thread list
#             if new_thread_id not in st.session_state['chat_thread']:
#                 st.session_state['chat_thread'].insert(0, new_thread_id)


#             # Title handling
#             if first_user_message:
#                 title = generate_chat_title(first_user_message)
#             else:
#                 title = f"Chat {str(new_thread_id)[:6]}"

#             st.session_state['thread_titles'][new_thread_id] = title
#             update_thread_title_backend(new_thread_id, title)

#     return st.session_state['thread_id']



# ========================================
# Initialize Session
# ========================================
# if 'thread_id' not in st.session_state:
#     new_thread_id = create_new_thread()
#     if new_thread_id:
#         st.session_state['thread_id'] = new_thread_id

# if 'chat_thread' not in st.session_state:
#     st.session_state['chat_thread'] = get_all_threads()

# Initialize thread titles
for tid in st.session_state['chat_thread']:
    if tid not in st.session_state['thread_titles']:
        messages = load_thread_history(tid)
        if messages:
            st.session_state['thread_titles'][tid] = generate_chat_title(messages[0]['content'])
        else:
            st.session_state['thread_titles'][tid] = f"Chat {str(tid)[:6]}"

# def reset_chat():
#     new_thread_id = create_new_thread()
#     if new_thread_id:
#         st.session_state['thread_id'] = new_thread_id
#         st.session_state['msg_hist'] = []
#         # Add new thread to top
#         if new_thread_id in st.session_state['chat_thread']:
#             st.session_state['chat_thread'].remove(new_thread_id)
#         st.session_state['chat_thread'].insert(0, new_thread_id)


# def reset_chat(first_user_message=None):
#     """Create a new thread and initialize session state"""
#     new_thread_id = create_new_thread()
#     if new_thread_id:
#         st.session_state['thread_id'] = new_thread_id
#         st.session_state['msg_hist'] = []

#         # Add new thread to top of list
#         if new_thread_id in st.session_state['chat_thread']:
#             st.session_state['chat_thread'].remove(new_thread_id)
#         st.session_state['chat_thread'].insert(0, new_thread_id)

#         # Generate title immediately if first message is given
#         if first_user_message:
#             title = generate_chat_title(first_user_message)
#             st.session_state['thread_titles'][new_thread_id] = title
#             update_thread_title_backend(new_thread_id, title)
#         else:
#             # Temporary default title until first user message arrives
#             st.session_state['thread_titles'][new_thread_id] = f"Chat {str(new_thread_id)[:6]}"
            
            
            
# def reset_chat(first_user_message=None):
#     new_thread_id = create_new_thread()
#     if not new_thread_id:
#         return None

#     st.session_state['thread_id'] = new_thread_id
#     st.session_state['msg_hist'] = []

#     # 🔥 REFRESH THREAD LIST FROM BACKEND
#     st.session_state['chat_thread'] = get_all_threads()

#     # Move new thread to top
#     if new_thread_id in st.session_state['chat_thread']:
#         st.session_state['chat_thread'].remove(new_thread_id)
#     st.session_state['chat_thread'].insert(0, new_thread_id)

#     if first_user_message:
#         title = generate_chat_title(first_user_message)
#     else:
#         title = f"Chat {str(new_thread_id)[:6]}"

#     st.session_state['thread_titles'][new_thread_id] = title
#     update_thread_title_backend(new_thread_id, title)

#     return new_thread_id

def reset_chat(first_user_message=None):
    new_thread_id = create_new_thread()
    if not new_thread_id:
        return None

    st.session_state['thread_id'] = new_thread_id
    st.session_state['msg_hist'] = []

    # DO NOT update sidebar here
    # DO NOT generate title here

    return new_thread_id


            
            
# ----------------------------------------
# Ensure a thread exists if user hasn't clicked "New Chat"
# # ----------------------------------------
# if not st.session_state.get('thread_id'):
#     # Temporarily create a new thread with a placeholder title
#     thread_id = reset_chat()
#     st.session_state['thread_id'] = thread_id

#     # Ensure sidebar shows at least a default title
#     if thread_id not in st.session_state['thread_titles']:
#         st.session_state['thread_titles'][thread_id] = f"Chat {str(thread_id)[:6]}"


# ========================================
# UI Components
# ========================================

def show_login_page():
    """Display login/register page"""
    st.title("🔐 RAG Chatbot Login")
    
    tab1, tab2 = st.tabs(["Login", "Register"])
    
    with tab1:
        st.subheader("Login to your account")
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login", use_container_width=True)
            
            if submit:
                if not username or not password:
                    st.error("Please fill all fields")
                else:
                    with st.spinner("Logging in..."):
                        result = login_user(username, password)
                        if result["success"]:
                            st.success("✅ Login successful!")
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.error(f"❌ {result['message']}")
    
    with tab2:
        st.subheader("Create new account")
        with st.form("register_form"):
            new_username = st.text_input("Username", key="reg_username")
            new_email = st.text_input("Email", key="reg_email")
            new_password = st.text_input("Password", type="password", key="reg_password")
            confirm_password = st.text_input("Confirm Password", type="password")
            register_submit = st.form_submit_button("Register", use_container_width=True)
            
            if register_submit:
                if not all([new_username, new_email, new_password, confirm_password]):
                    st.error("Please fill all fields")
                elif new_password != confirm_password:
                    st.error("Passwords don't match")
                elif len(new_password) < 8:
                    st.error("Password must be at least 8 characters")
                else:
                    with st.spinner("Creating account..."):
                        result = register_user(new_username, new_email, new_password)
                        if result["success"]:
                            st.success("✅ Registration successful!")
                            time.sleep(0.5)
                            st.rerun()
                        else:
                            st.error(f" {result['message']}")

# def show_chat_interface():
#     """Display authenticated chat interface"""
    
#     # Sidebar
#     st.sidebar.title(f"👤 {st.session_state['user_info']['username']}")
#     st.sidebar.divider()
    
#     if st.sidebar.button('Logout', use_container_width=True, type='secondary'):
#         logout()
#         st.rerun()
    
#     st.sidebar.divider()
    
#     if st.sidebar.button('New Chat', use_container_width=True, type='primary'):
#         reset_chat()
#         st.rerun()
    
#     st.sidebar.divider()
    
#     # Knowledge Base
#     cooldown_active = time.time() < st.session_state.get("rate_limited_until", 0)
#     docs = [] if cooldown_active else get_documents()
#     kb_title = "📚 Knowledge Base 🟢" if docs else "📚 Knowledge Base"
    
#     with st.sidebar.expander(kb_title, expanded=False):
#         st.caption("Your uploaded documents")
        
#         if cooldown_active:
#             st.info("⏳ Locked during cooldown")
        
#         if docs:
#             st.success(f"✅ {len(docs)} document(s)")
#             for doc in docs:
#                 col1, col2 = st.columns([3, 1])
#                 with col1:
#                     st.text(f"📄 {doc}")
#                 with col2:
#                     if st.button('🗑️', key=f"del_{doc}", disabled=cooldown_active):
#                         result = delete_document(doc)
#                         # if result:
#                         #     st.success("Deleted!")
#                         #     st.rerun()
                        
#                         if result:
#                             st.success("✅ Document deleted successfully!")
#                             st.rerun()
#                         else:
#                             st.error(" Failed to delete document.")
            
#             if st.button('🗑️ Clear All', key='clear_all', type='secondary',
#                         use_container_width=True, disabled=cooldown_active):
#                 # result = clear_all_documents()
#                 # if result:
#                 #     st.success("All cleared!")
#                 #     st.rerun()
                
#                     with st.spinner("Clearing all documents..."):
#                         result = clear_all_documents()

#                         if result:
#                             st.success("✅ All documents cleared!")
#                             st.rerun()
#                         else:
#                             st.error(" Failed to clear documents.")
                
#         else:
#             st.info("📭 No documents yet")
    
#     # Conversations
#     st.sidebar.subheader('💬 Conversations')
#     if st.session_state['chat_thread']:
#         for thread_id in st.session_state['chat_thread']:
#             display_name = st.session_state['thread_titles'].get(thread_id, f"Chat {str(thread_id)[:6]}")
#             if st.sidebar.button(display_name, key=thread_id, use_container_width=True):
#                 st.session_state['thread_id'] = thread_id
#                 messages = load_thread_history(thread_id)
#                 st.session_state['msg_hist'] = messages
#                 st.session_state['chat_thread'].remove(thread_id)
#                 st.session_state['chat_thread'].insert(0, thread_id)
#                 st.rerun()
#     else:
#         st.sidebar.caption("No previous conversations")
    
#     # Main Chat Area
#     st.title("💬 RAG-Enabled Chatbot")
    
#     # Display messages
#     chat_container = st.container()
#     with chat_container:
#         for msg in st.session_state['msg_hist']:
#             with st.chat_message(msg['role']):
#                 st.markdown(msg['content'])
    
#     # File upload modal
#     if st.session_state.get('show_upload', False):
#         st.info("📤 Upload Document")
#         uploaded_file = st.file_uploader("Choose file", type=['pdf', 'txt'], key='file_uploader')
#         col1, col2 = st.columns([2, 1])
#         with col1:
#             if uploaded_file and st.button('Upload', type='primary', key='upload_doc'):
#                 with st.spinner('Processing...'):
#                     #result = upload_document(uploaded_file)
#                     # if result.get("success"):
#                     #     st.success("✅ Uploaded!")
#                     #     st.session_state['show_upload'] = False
#                     #     time.sleep(0.5)
#                     #     st.rerun()
#                     # else:
#                     #     st.error(result["message"])
#                     if uploaded_file is not None:
#                         result = upload_document(uploaded_file)

#                         if result["success"]:
#                             st.success("File uploaded! Document is being processed in background...")

#                             job_id = result["job_id"]
#                             st.session_state.current_job = job_id

#                             #st.info("Document is being processed in background...")
#                         else:
#                             st.error(result["message"])
#         with col2:
#             if st.button('Cancel', key='cancel_upload'):
#                 st.session_state['show_upload'] = False
#                 st.rerun()
    
#     # Cooldown handling
#     now = time.time()
#     until = st.session_state.get("rate_limited_until", 0)
#    # remaining = int(until - now)
#     remaining = max(0, int(until - now))
#     cooldown_active = remaining > 0
    
#     if cooldown_active:
#         st.info(f"⏳ Cooling down... {remaining}s remaining")
#         #st_autorefresh(interval=1000, key=f"cooldown_{remaining}")
#         st_autorefresh(interval=1000, key="cooldown_refresh")

#     else:
#         st.session_state["rate_limited_until"] = 0
    
#     # Chat input

#     col_input, col_plus = st.columns([20, 1])
    
#     with col_input:
#         user_input = st.chat_input(
#             "Type your message...",
#             key="chat_input",
#             disabled=cooldown_active or st.session_state.get("is_generating", False)
#         )
    
#     with col_plus:
#         if st.button("➕", help="Upload document", key="upload_btn"):
#             st.session_state['show_upload'] = True
#             st.rerun()
#     # Handle new message
#     # if user_input:
#     #     st.session_state["is_generating"] = True
        
#     #     try:
#     #         # Ensure thread exists
#     #         if not st.session_state.get('thread_id') or not st.session_state['msg_hist']:
#     #             thread_id = reset_chat(first_user_message=user_input)
#     #         else:
#     #             thread_id = st.session_state['thread_id']
            
#     #         # Update title
#     #         current_title = st.session_state['thread_titles'].get(thread_id)
#     #         if not current_title or current_title.startswith("Chat "):
#     #             title = generate_chat_title(user_input)
#     #             st.session_state['thread_titles'][thread_id] = title
            
#     #         # Add user message
#     #         st.session_state['msg_hist'].append({'role': 'user', 'content': user_input})
#     #         with st.chat_message('user'):
#     #             st.markdown(user_input)
            
#     #         # Get AI response
#     #         with st.chat_message('assistant'):
#     #             message_placeholder = st.empty()
#     #             result = send_message_stream(user_input, thread_id)
                
#     #             if result["ok"]:
#     #                 full_text = ""
#     #                 for chunk in stream_text(result["reply"]):
#     #                     full_text += chunk
#     #                     message_placeholder.markdown(full_text + "▌")
#     #                 message_placeholder.markdown(result["reply"])
#     #                 st.session_state['msg_hist'].append({
#     #                     "role": "assistant",
#     #                     "content": result["reply"]
#     #                 })
#     #             elif result["type"] == "rate_limit":
#     #                 st.session_state["rate_limited_until"] = time.time() + result["retry_after"]
#     #                 message_placeholder.markdown("🚦 Rate limit reached")
#     #             elif result["type"] == "network":
#     #                 message_placeholder.markdown("🔌 Backend not reachable")
#     #             elif result["type"] == "quota":
#     #                     st.error(result["message"])  
#     #             else:
#     #                 message_placeholder.markdown("error occured")
        
#     #     finally:
#     #         st.session_state["is_generating"] = False
        
#     #     if not cooldown_active and not st.session_state["is_generating"]:
#     #         st.rerun()
#     if user_input:
#         st.session_state["is_generating"] = True
        
#         try:
#             # -----------------------------------
#             # 1️⃣ Ensure thread exists (same logic as before)
#             # -----------------------------------
#             is_new_thread = False

#             if not st.session_state.get('thread_id') or not st.session_state['msg_hist']:
#                 thread_id = reset_chat(first_user_message=None)  # 👈 do NOT generate title here
#                 is_new_thread = True
#             else:
#                 thread_id = st.session_state['thread_id']
            
#             # -----------------------------------
#             # 2️⃣ Add user message FIRST
#             # -----------------------------------
#             st.session_state['msg_hist'].append({
#                 'role': 'user',
#                 'content': user_input
#             })

#             with st.chat_message('user'):
#                 st.markdown(user_input)

#             # -----------------------------------
#             # 3️⃣ NOW generate title + show in sidebar
#             #     (ONLY after first message)
#             # -----------------------------------
#             current_title = st.session_state['thread_titles'].get(thread_id)

#             if is_new_thread or not current_title or current_title.startswith("Chat "):
                
#                 title = generate_chat_title(user_input)
#                 st.session_state['thread_titles'][thread_id] = title
#                 update_thread_title_backend(thread_id, title)

#                 # 🔥 Refresh sidebar threads
#                 st.session_state['chat_thread'] = get_all_threads()

#                 # 🔥 Move current thread to top (keep your ordering logic same)
#                 if thread_id in st.session_state['chat_thread']:
#                     st.session_state['chat_thread'].remove(thread_id)
#                 st.session_state['chat_thread'].insert(0, thread_id)

#             # -----------------------------------
#             # 4️⃣ Get AI response (UNCHANGED)
#             # -----------------------------------
#             with st.chat_message('assistant'):
#                 message_placeholder = st.empty()
#                 result = send_message_stream(user_input, thread_id)
                
#                 if result["ok"]:
#                     full_text = ""
#                     for chunk in stream_text(result["reply"]):
#                         full_text += chunk
#                         message_placeholder.markdown(full_text + "▌")
#                     message_placeholder.markdown(result["reply"])
                    
#                     st.session_state['msg_hist'].append({
#                         "role": "assistant",
#                         "content": result["reply"]
#                     })

#                 elif result["type"] == "rate_limit":
#                     st.session_state["rate_limited_until"] = time.time() + result["retry_after"]
#                     message_placeholder.markdown("🚦 Rate limit reached")

#                 elif result["type"] == "network":
#                     message_placeholder.markdown("🔌 Backend not reachable")

#                 elif result["type"] == "quota":
#                     st.error(result["message"])

#                 else:
#                     message_placeholder.markdown("error occured")

#         finally:
#             st.session_state["is_generating"] = False
        
#         if not cooldown_active and not st.session_state["is_generating"]:
#             st.rerun()



# def show_chat_interface():
#     """Display authenticated chat interface"""
    
#     # ---------------- Sidebar ----------------
#     st.sidebar.title(f"👤 {st.session_state['user_info']['username']}")
#     st.sidebar.divider()
    
#     if st.sidebar.button('Logout', use_container_width=True, type='secondary'):
#         logout()
#         st.rerun()
    
#     st.sidebar.divider()
    
#     if st.sidebar.button('New Chat', use_container_width=True, type='primary'):
#         reset_chat()
#         st.rerun()
    
#     st.sidebar.divider()
    
#     # Knowledge Base
#     cooldown_active = time.time() < st.session_state.get("rate_limited_until", 0)
#     docs = [] if cooldown_active else get_documents()
#     kb_title = "📚 Knowledge Base 🟢" if docs else "📚 Knowledge Base"
    
#     with st.sidebar.expander(kb_title, expanded=False):
#         st.caption("Your uploaded documents")
        
#         if cooldown_active:
#             st.info("⏳ Locked during cooldown")
        
#         if docs:
#             st.success(f"✅ {len(docs)} document(s)")
#             for doc in docs:
#                 col1, col2 = st.columns([3, 1])
#                 with col1:
#                     st.text(f"📄 {doc}")
#                 with col2:
#                     if st.button('🗑️', key=f"del_{doc}", disabled=cooldown_active):
#                         result = delete_document(doc)
#                         if result:
#                             st.success("✅ Document deleted successfully!")
#                             st.rerun()
#                         else:
#                             st.error("Failed to delete document.")
            
#             if st.button('🗑️ Clear All', key='clear_all', type='secondary',
#                          use_container_width=True, disabled=cooldown_active):
#                 with st.spinner("Clearing all documents..."):
#                     result = clear_all_documents()
#                     if result:
#                         st.success("✅ All documents cleared!")
#                         st.rerun()
#                     else:
#                         st.error("Failed to clear documents.")
#         else:
#             st.info("📭 No documents yet")
    
#     # Conversations
#     st.sidebar.subheader('💬 Conversations')
#     if st.session_state['chat_thread']:
#         for thread_id in st.session_state['chat_thread']:
#             display_name = st.session_state['thread_titles'].get(thread_id, f"Chat {str(thread_id)[:6]}")
#             if st.sidebar.button(display_name, key=thread_id, use_container_width=True):
#                 st.session_state['thread_id'] = thread_id
#                 messages = load_thread_history(thread_id)
#                 st.session_state['msg_hist'] = messages
#                 st.session_state['chat_thread'].remove(thread_id)
#                 st.session_state['chat_thread'].insert(0, thread_id)
#                 st.rerun()
#     else:
#         st.sidebar.caption("No previous conversations")
    
#     # ---------------- Main Chat Area ----------------
#     st.title("💬 RAG-Enabled Chatbot")
    
#     # Display messages container
#     chat_container = st.container()
#     with chat_container:
#         for msg in st.session_state['msg_hist']:
#             with st.chat_message(msg['role']):
#                 st.markdown(msg['content'])
    
#     # File upload modal
#     if st.session_state.get('show_upload', False):
#         st.info("📤 Upload Document")
#         uploaded_file = st.file_uploader("Choose file", type=['pdf', 'txt'], key='file_uploader')
#         col1, col2 = st.columns([2, 1])
#         with col1:
#             if uploaded_file and st.button('Upload', type='primary', key='upload_doc'):
#                 with st.spinner('Processing...'):
#                     result = upload_document(uploaded_file)
#                     if result["success"]:
#                         st.success("File uploaded! Document is being processed in background...")
#                         st.session_state.current_job = result["job_id"]
#                     else:
#                         st.error(result["message"])
#         with col2:
#             if st.button('Cancel', key='cancel_upload'):
#                 st.session_state['show_upload'] = False
#                 st.rerun()
    
#     # ---------------- Cooldown Handling ----------------
#     now = time.time()
#     until = st.session_state.get("rate_limited_until", 0)
#     remaining = max(0, int(until - now))
#     cooldown_active = remaining > 0
    
#     if cooldown_active:
#         st.info(f"⏳ Cooling down... {remaining}s remaining")
#         st_autorefresh(interval=1000, key="cooldown_refresh")
#     else:
#         st.session_state["rate_limited_until"] = 0
    
#     # ---------------- Chat Input Area ----------------
#     # st.markdown("""
#     #     <style>
#     #     .main-chat-wrapper { display: flex; flex-direction: column; height: 88vh; }
#     #     .messages-area { flex: 1; overflow-y: auto; padding-right: 10px; }
#     #     .input-area { border-top: 1px solid #333; padding-top: 10px; margin-bottom: 150px;}
#     #     </style>
#     # """, unsafe_allow_html=True)
#     st.markdown("""
#         <style>
#         .main-chat-wrapper { 
#             display: flex; 
#             flex-direction: column; 
#             height: 100vh;  /* full viewport height */
#         }
#         .messages-area { 
#             flex: 1;                 /* take all remaining space */
#             overflow-y: auto;        /* scroll when messages overflow */
#             padding: 10px;
#         }
#         .input-area { 
#             border-top: 1px solid #333; 
#             padding: 10px; 
#             position: sticky; 
#             bottom: 0;               /* stick to bottom */
#             background-color: #0e1117;  /* match Streamlit dark mode */
#             z-index: 10;
#         }
#         </style>
#         """, unsafe_allow_html=True)

    
#     st.markdown('<div class="main-chat-wrapper">', unsafe_allow_html=True)    
#     st.markdown('<div class="input-area">', unsafe_allow_html=True)
#     col_input, col_plus = st.columns([20, 1])
#     with col_input:
#         user_input = st.chat_input(
#             "Type your message...",
#             key="chat_input",
#             disabled=st.session_state.get("is_generating", False)
#         )
#     with col_plus:
#         if st.button("➕", key="upload_btn"):
#             st.session_state['show_upload'] = True
#             st.rerun()
#     st.markdown('</div>', unsafe_allow_html=True)
#     st.markdown('</div>', unsafe_allow_html=True)
    
#     # ---------------- Handle User Input ----------------
#     if user_input:
#         st.session_state['msg_hist'].append({"role": "user", "content": user_input})
#         st.session_state["_pending_user_input"] = user_input
#         st.session_state["is_generating"] = True
#         st.rerun()
    
#     if st.session_state.get("_pending_user_input"):
#         user_input = st.session_state.pop("_pending_user_input")
        
#         # Create thread if it doesn't exist
#         if not st.session_state.get("thread_id"):
#             thread_id = create_new_thread()
#             st.session_state["thread_id"] = thread_id
#             title = generate_chat_title(user_input)
#             st.session_state["thread_titles"][thread_id] = title
#             update_thread_title_backend(thread_id, title)
#             st.session_state["chat_thread"] = get_all_threads()
#             if thread_id in st.session_state["chat_thread"]:
#                 st.session_state["chat_thread"].remove(thread_id)
#             st.session_state["chat_thread"].insert(0, thread_id)
#         else:
#             thread_id = st.session_state["thread_id"]
        
#         # ---------------- Assistant Reply ----------------
#         with st.chat_message("assistant"):
#             message_placeholder = st.empty()
#             result = send_message_stream(user_input, thread_id)
#             if result["ok"]:
#                 full_text = ""
#                 for chunk in stream_text(result["reply"]):
#                     full_text += chunk
#                     message_placeholder.markdown(full_text + "▌")
#                 message_placeholder.markdown(result["reply"])
#                 st.session_state['msg_hist'].append({"role": "assistant", "content": result["reply"]})
#             elif result["type"] == "rate_limit":
#                 st.session_state["rate_limited_until"] = time.time() + result["retry_after"]
#                 message_placeholder.markdown("🚦 Rate limit reached")
#             elif result["type"] == "network":
#                 message_placeholder.markdown("🔌 Backend not reachable")
#             elif result["type"] == "quota":
#                 message_placeholder.markdown(result["message"])
#             else:
#                 message_placeholder.markdown("Error occurred")
        
#         st.session_state["is_generating"] = False
#         st.rerun()



def show_chat_interface():
    """Display authenticated chat interface"""
    
    # ---------------- Sidebar ----------------
    st.sidebar.title(f"👤 {st.session_state['user_info']['username']}")
    st.sidebar.divider()
    
    if st.sidebar.button('Logout', use_container_width=True, type='secondary'):
        logout()
        st.rerun()
    
    st.sidebar.divider()
    
    if st.sidebar.button('New Chat', use_container_width=True, type='primary'):
        reset_chat()
        st.rerun()
    
    st.sidebar.divider()
    
    # Knowledge Base
    cooldown_active = time.time() < st.session_state.get("rate_limited_until", 0)
    docs = [] if cooldown_active else get_documents()
    kb_title = "📚 Knowledge Base 🟢" if docs else "📚 Knowledge Base"
    
    with st.sidebar.expander(kb_title, expanded=False):
        st.caption("Your uploaded documents")
        
        if cooldown_active:
            st.info("⏳ Locked during cooldown")
        
        if docs:
            st.success(f"✅ {len(docs)} document(s)")
            for doc in docs:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.text(f"📄 {doc}")
                with col2:
                    if st.button('🗑️', key=f"del_{doc}", disabled=cooldown_active):
                        result = delete_document(doc)
                        if result:
                            st.success("✅ Document deleted successfully!")
                            st.rerun()
                        else:
                            st.error("Failed to delete document.")
            
            if st.button('🗑️ Clear All', key='clear_all', type='secondary',
                         use_container_width=True, disabled=cooldown_active):
                with st.spinner("Clearing all documents..."):
                    result = clear_all_documents()
                    if result:
                        st.success("✅ All documents cleared!")
                        st.rerun()
                    else:
                        st.error("Failed to clear documents.")
        else:
            st.info("📭 No documents yet")
    
    # Conversations
    st.sidebar.subheader('💬 Conversations')
    if st.session_state['chat_thread']:
        for thread_id in st.session_state['chat_thread']:
            display_name = st.session_state['thread_titles'].get(thread_id, f"Chat {str(thread_id)[:6]}")
            if st.sidebar.button(display_name, key=thread_id, use_container_width=True):
                st.session_state['thread_id'] = thread_id
                messages = load_thread_history(thread_id)
                st.session_state['msg_hist'] = messages
                st.session_state['chat_thread'].remove(thread_id)
                st.session_state['chat_thread'].insert(0, thread_id)
                st.rerun()
    else:
        st.sidebar.caption("No previous conversations")
    
    # ---------------- Main Chat Area ----------------
    st.title("💬 RAG-Enabled Chatbot")
    
    #Display messages container
    chat_container = st.container()
    with chat_container:
        for msg in st.session_state['msg_hist']:
            with st.chat_message(msg['role']):
                st.markdown(msg['content'])
    
    
    
    # File upload modal
    if st.session_state.get('show_upload', False):
        st.info("📤 Upload Document")
        uploaded_file = st.file_uploader("Choose file", type=['pdf', 'txt'], key='file_uploader')
        col1, col2 = st.columns([2, 1])
        with col1:
            if uploaded_file and st.button('Upload', type='primary', key='upload_doc'):
                with st.spinner('Processing...'):
                    result = upload_document(uploaded_file)
                    if result["success"]:
                        st.success("File uploaded! Document is being processed in background...")
                        st.session_state.current_job = result["job_id"]
                    else:
                        st.error(result["message"])
        with col2:
            if st.button('Cancel', key='cancel_upload'):
                st.session_state['show_upload'] = False
                st.rerun()
    
    # ---------------- Cooldown Handling ----------------
    now = time.time()
    until = st.session_state.get("rate_limited_until", 0)
    remaining = max(0, int(until - now))
    cooldown_active = remaining > 0
    
    if cooldown_active:
        st.info(f"⏳ Cooling down... {remaining}s remaining")
        st_autorefresh(interval=1000, key="cooldown_refresh")
    else:
        st.session_state["rate_limited_until"] = 0
    
    # ---------------- Chat Input Area ----------------
    # st.markdown("""
    #     <style>
    #     .main-chat-wrapper { display: flex; flex-direction: column; height: 88vh; }
    #     .messages-area { flex: 1; overflow-y: auto; padding-right: 10px; }
    #     .input-area { border-top: 1px solid #333; padding-top: 10px; margin-bottom: 150px;}
    #     </style>
    # """, unsafe_allow_html=True)
    # st.markdown("""
    #     <style>
    #     .main-chat-wrapper { 
    #         display: flex; 
    #         flex-direction: column; 
    #         height: 60vh;  
    #     }
    #     .messages-area { 
    #         flex: 1;                 
    #         overflow-y: auto;        
    #         padding: 10px;
    #     }
    #     .input-area { 
    #         border-top: 1px solid #333; 
    #         padding: 10px; 
    #        # position: fixed; 
    #        # bottom: 200px;               
    #         background-color: #0e1117;  
    #         z-index: 10;
    #        # margin-top: auto; 
    #     }
    #     </style>
    #     """, unsafe_allow_html=True)

    # ---------------- Messages Container ----------------
    # st.markdown('<div class="main-chat-wrapper">', unsafe_allow_html=True)
    # for msg in st.session_state['msg_hist']:
    #         with st.chat_message(msg['role']):
    #             st.markdown(msg['content'])
    # st.markdown('</div>', unsafe_allow_html=True)

    # # ---------------- Chat Input Area ----------------
    # st.markdown('<div class="input-area" style="margin-bottom: 20px;">', unsafe_allow_html=True)
    # col_input, col_plus = st.columns([20, 1])
    # with col_input:
    #     user_input = st.chat_input(
    #         "Type your message...",
    #         key="chat_input",
    #         disabled=st.session_state.get("is_generating", False)
    #     )
    # with col_plus:
    #     if st.button("➕", key="upload_btn"):
    #         st.session_state['show_upload'] = True
    #         st.rerun()
    # st.markdown('</div>', unsafe_allow_html=True)
    
    # ---------------- Chat Layout Wrapper ----------------
    # st.markdown('<div class="main-chat-wrapper">', unsafe_allow_html=True)

    # # ---------------- Messages Area ----------------
    # st.markdown('<div class="messages-area">', unsafe_allow_html=True)

    # st.markdown('</div>', unsafe_allow_html=True)

    # # ---------------- Input Area ----------------
    # st.markdown('<div class="input-area">', unsafe_allow_html=True)

    # col_input, col_plus = st.columns([20, 1])

    # with col_input:
    #     user_input = st.chat_input(
    #         "Type your message...",
    #         key="chat_input",
    #         disabled=st.session_state.get("is_generating", False)
    #     )

    # with col_plus:
    #     if st.button("➕", key="upload_btn"):
    #         st.session_state['show_upload'] = True
    #         st.rerun()

    # st.markdown('</div>', unsafe_allow_html=True)

    # # Close main wrapper
    # st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown("""
    <style>
    /* Make input fixed to bottom */
    .input-area {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        padding: 10px;
        border-top: 1px solid #333;
        background-color: #0e1117;
        z-index: 999;
    }

    /* Prevent messages from hiding behind input */
    .block-container {
        padding-bottom: 140px;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="input-area">', unsafe_allow_html=True)

    col_input, col_plus = st.columns([20, 1])

    with col_input:
        user_input = st.chat_input(
            "Type your message...",
            key="chat_input",
            disabled=st.session_state.get("is_generating", False)
        )

    with col_plus:
        if st.button("➕", key="upload_btn"):
            st.session_state['show_upload'] = True
            st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)




    # ---------------- Handle User Input ----------------
    # if user_input:
    #    # st.session_state['msg_hist'].append({"role": "user", "content": user_input})
    #     st.session_state["_pending_user_input"] = user_input
    #     st.session_state["is_generating"] = True
    #     st.rerun()

    # if st.session_state.get("_pending_user_input"):
    #     user_input = st.session_state.pop("_pending_user_input")
        
    #     st.session_state['msg_hist'].append({"role": "user", "content": user_input})

        
    #     # Thread handling...
    #     if not st.session_state.get("thread_id"):
    #         thread_id = create_new_thread()
    #         st.session_state["thread_id"] = thread_id
    #         title = generate_chat_title(user_input)
    #         st.session_state["thread_titles"][thread_id] = title
    #         update_thread_title_backend(thread_id, title)
    #         st.session_state["chat_thread"] = get_all_threads()
    #         if thread_id in st.session_state["chat_thread"]:
    #             st.session_state["chat_thread"].remove(thread_id)
    #         st.session_state["chat_thread"].insert(0, thread_id)
    #     else:
    #         thread_id = st.session_state["thread_id"]

    #     # ---------------- Stream AI Response ----------------
    #     result = send_message_stream(user_input, thread_id)
    #     if result["ok"]:
    #         # Append full AI response at once (no rerun in loop)
    #         st.session_state['msg_hist'].append({"role": "assistant", "content": result["reply"]})
    #     elif result["type"] == "rate_limit":
    #         st.session_state["rate_limited_until"] = time.time() + result["retry_after"]
    #         st.session_state['msg_hist'].append({"role": "assistant", "content": "🚦 Rate limit reached"})
    #     elif result["type"] == "network":
    #         st.session_state['msg_hist'].append({"role": "assistant", "content": "🔌 Backend not reachable"})
    #     elif result["type"] == "quota":
    #         st.session_state['msg_hist'].append({"role": "assistant", "content": result["message"]})
    #     else:
    #         st.session_state['msg_hist'].append({"role": "assistant", "content": "Error occurred"})

    #     st.session_state["is_generating"] = False
    #     st.rerun()
    
        # ---------------- Handle User Input ----------------
    if user_input and not st.session_state.get("is_generating", False):

        # Lock input
        st.session_state["is_generating"] = True

        # 1️⃣ Append user message immediately
        st.session_state['msg_hist'].append({
            "role": "user",
            "content": user_input
        })

        # 2️⃣ Show user message instantly (no rerun)
        with chat_container:
            with st.chat_message("user"):
                st.markdown(user_input)

        # ---------------- Thread Handling ----------------
        if not st.session_state.get("thread_id"):
            thread_id = create_new_thread()
            st.session_state["thread_id"] = thread_id

            title = generate_chat_title(user_input)
            st.session_state["thread_titles"][thread_id] = title
            update_thread_title_backend(thread_id, title)

            st.session_state["chat_thread"] = get_all_threads()
            if thread_id in st.session_state["chat_thread"]:
                st.session_state["chat_thread"].remove(thread_id)
            st.session_state["chat_thread"].insert(0, thread_id)
        else:
            thread_id = st.session_state["thread_id"]

        # ---------------- STREAM AI RESPONSE ----------------
        with chat_container:
            with st.chat_message("assistant"):
                message_placeholder = st.empty()
                full_response = ""

                result = send_message_stream(user_input, thread_id)

                if result["ok"]:

                    # IMPORTANT: reply must be generator
                    for chunk in result["reply"]:
                        full_response += chunk
                        message_placeholder.markdown(full_response + "▌")

                    message_placeholder.markdown(full_response)

                    # Save final response
                    st.session_state['msg_hist'].append({
                        "role": "assistant",
                        "content": full_response
                    })

                elif result["type"] == "rate_limit":
                    st.session_state["rate_limited_until"] = time.time() + result["retry_after"]
                    message_placeholder.markdown("🚦 Rate limit reached")

                elif result["type"] == "network":
                    message_placeholder.markdown("🔌 Backend not reachable")

                elif result["type"] == "quota":
                    message_placeholder.markdown(result["message"])

                else:
                    message_placeholder.markdown("Error occurred")

        # Unlock input
        st.session_state["is_generating"] = False

        # Single rerun after streaming completes
        st.rerun()









# ========================================
# Main App
# ========================================

# Initialize user session
if is_authenticated() and not st.session_state['user_info']:
    fetch_user_info()

# Load initial data if authenticated
if is_authenticated():
    if not st.session_state['thread_id']:
        st.session_state['chat_thread'] = get_all_threads()
        for tid in st.session_state['chat_thread']:
            if tid not in st.session_state['thread_titles']:
                messages = load_thread_history(tid)
                if messages:
                    st.session_state['thread_titles'][tid] = generate_chat_title(messages[0]['content'])
                else:
                    st.session_state['thread_titles'][tid] = f"Chat {str(tid)[:6]}"

# Show appropriate interface
if is_authenticated():

    # # Load threads from backend once
    # if not st.session_state['chat_thread']:
    #     st.session_state['chat_thread'] = get_all_threads()

    # # Ensure thread_id exists
    # if not st.session_state['thread_id']:
    #     new_thread_id = create_new_thread()
    #     if new_thread_id:
    #         st.session_state['thread_id'] = new_thread_id
    #         st.session_state['chat_thread'].insert(0, new_thread_id)

    show_chat_interface()

else:
    show_login_page()
    
