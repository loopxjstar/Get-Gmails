from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse, JSONResponse
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from datetime import datetime, date
import secrets
import email
import csv
import io
import calendar
import os
from dotenv import load_dotenv
import traceback
import asyncio

load_dotenv()

app = FastAPI(title="Email CSV Generator")

# Simple in-memory storage
user_sessions = {}
oauth_states = {}
generation_status = {}  # Track generation progress

# Google OAuth config
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = "http://localhost:8000/auth/callback"

client_config = {
    "web": {
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": [REDIRECT_URI]
    }
}

@app.get("/", response_class=HTMLResponse)
async def home():
    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Email CSV Generator</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
        <style>
            .hero {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; min-height: 100vh; display: flex; align-items: center; }}
        </style>
    </head>
    <body>
        <div class="hero">
            <div class="container">
                <div class="row justify-content-center">
                    <div class="col-md-6">
                        <div class="card p-5 text-center">
                            <h1 class="text-dark mb-4">📧 Email CSV Generator</h1>
                            <p class="text-muted mb-4">Generate monthly CSV files of your sent emails starting from December 2024</p>
                            <a href="/auth/login" class="btn btn-primary btn-lg">🔐 Sign in with Google</a>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </body>
    </html>
    """)

@app.get("/auth/login")
async def login():
    try:
        flow = Flow.from_client_config(
            client_config,
            scopes=['https://www.googleapis.com/auth/gmail.readonly']
        )
        flow.redirect_uri = REDIRECT_URI
        
        state = secrets.token_urlsafe(32)
        oauth_states[state] = True
        
        auth_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            state=state
        )
        
        return RedirectResponse(url=auth_url)
        
    except Exception as e:
        print(f"Login error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/auth/callback")
async def callback(code: str = Query(...), state: str = Query(...)):
    try:
        if state not in oauth_states:
            raise HTTPException(status_code=400, detail="Invalid state")
        
        flow = Flow.from_client_config(client_config, scopes=['https://www.googleapis.com/auth/gmail.readonly'])
        flow.redirect_uri = REDIRECT_URI
        flow.fetch_token(code=code)
        
        credentials = flow.credentials
        service = build('gmail', 'v1', credentials=credentials)
        profile = service.users().getProfile(userId='me').execute()
        user_email = profile['emailAddress']
        
        print(f"Successfully authenticated user: {user_email}")
        
        # Store user session
        session_id = secrets.token_urlsafe(32)
        user_sessions[session_id] = {
            'email': user_email,
            'credentials': {
                'token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'token_uri': credentials.token_uri,
                'client_id': credentials.client_id,
                'client_secret': credentials.client_secret,
                'scopes': credentials.scopes
            }
        }
        
        response = RedirectResponse(url="/dashboard")
        response.set_cookie(key="session_id", value=session_id, httponly=True)
        return response
        
    except Exception as e:
        print(f"Callback error: {e}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in user_sessions:
        return RedirectResponse(url="/")
    
    user_email = user_sessions[session_id]['email']
    
    return HTMLResponse(f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Dashboard</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body>
        <div class="container mt-4">
            <h2>📊 Dashboard - {user_email}</h2>
            <p>Choose how to generate your email CSV files:</p>
            
            <div class="row mt-4">
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-body text-center">
                            <h4>📅 Specific Month</h4>
                            <p>Generate CSV for one specific month</p>
                            <div class="row mb-3">
                                <div class="col-6">
                                    <label>Month:</label>
                                    <select id="month" class="form-select">
                                        <option value="12">December</option>
                                        <option value="1">January</option>
                                        <option value="2">February</option>
                                        <option value="3">March</option>
                                        <option value="4">April</option>
                                        <option value="5">May</option>
                                        <option value="6">June</option>
                                        <option value="7">July</option>
                                        <option value="8">August</option>
                                        <option value="9">September</option>
                                        <option value="10">October</option>
                                        <option value="11">November</option>
                                    </select>
                                </div>
                                <div class="col-6">
                                    <label>Year:</label>
                                    <select id="year" class="form-select">
                                        <option value="2024">2024</option>
                                        <option value="2025">2025</option>
                                    </select>
                                </div>
                            </div>
                            <button id="generateBtn" onclick="startGeneration()" class="btn btn-primary">Generate CSV</button>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Progress Section -->
            <div id="progressSection" class="row mt-4" style="display:none;">
                <div class="col-12">
                    <div class="card">
                        <div class="card-body">
                            <h5>⚙️ Processing...</h5>
                            <div class="progress mb-3">
                                <div id="progressBar" class="progress-bar progress-bar-striped progress-bar-animated" 
                                     role="progressbar" style="width: 0%">
                                    <span id="progressText">0%</span>
                                </div>
                            </div>
                            <div id="statusText" class="text-muted">Initializing...</div>
                            <button id="cancelBtn" onclick="cancelGeneration()" class="btn btn-outline-danger btn-sm mt-2" style="display:none;">
                                Cancel
                            </button>
                        </div>
                    </div>
                </div>
            </div>
            
            <!-- Success Section -->
            <div id="successSection" class="row mt-4" style="display:none;">
                <div class="col-12">
                    <div class="alert alert-success">
                        <h5>✅ Generation Complete!</h5>
                        <p id="successMessage"></p>
                        <button id="downloadBtn" class="btn btn-success">Download CSV</button>
                        <button onclick="resetForm()" class="btn btn-outline-secondary ms-2">Generate Another</button>
                    </div>
                </div>
            </div>
        </div>
        
        <script>
            let generationId = null;
            let progressInterval = null;
            
            async function startGeneration() {{
                const month = document.getElementById('month').value;
                const year = document.getElementById('year').value;
                
                // Validate date (no future dates, only Dec 2024+)
                const currentDate = new Date();
                const selectedDate = new Date(year, month - 1, 1);
                const minDate = new Date(2024, 11, 1); // December 2024
                
                if (selectedDate > currentDate) {{
                    alert('Cannot generate CSV for future dates!');
                    return;
                }}
                
                if (selectedDate < minDate) {{
                    alert('Email collection starts from December 2024!');
                    return;
                }}
                
                // Hide form, show progress
                document.getElementById('generateBtn').style.display = 'none';
                document.getElementById('progressSection').style.display = 'block';
                document.getElementById('successSection').style.display = 'none';
                
                try {{
                    // Start generation process
                    updateProgress(10, 'Starting email collection...');
                    
                    const response = await fetch('/api/start-generation', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{month: parseInt(month), year: parseInt(year)}})
                    }});
                    
                    if (!response.ok) {{
                        throw new Error('Failed to start generation');
                    }}
                    
                    const data = await response.json();
                    generationId = data.generation_id;
                    
                    // Start polling for progress
                    startProgressPolling();
                    
                }} catch (error) {{
                    showError('Failed to start generation: ' + error.message);
                }}
            }}
            
            function startProgressPolling() {{
                progressInterval = setInterval(async () => {{
                    try {{
                        const response = await fetch(`/api/generation-status/${{generationId}}`);
                        const status = await response.json();
                        
                        updateProgress(status.progress, status.message);
                        
                        if (status.status === 'completed') {{
                            clearInterval(progressInterval);
                            showSuccess(status.filename, status.email_count);
                        }} else if (status.status === 'failed') {{
                            clearInterval(progressInterval);
                            showError(status.message);
                        }}
                    }} catch (error) {{
                        console.error('Error polling status:', error);
                    }}
                }}, 1000); // Poll every second
            }}
            
            function updateProgress(percent, message) {{
                document.getElementById('progressBar').style.width = percent + '%';
                document.getElementById('progressText').textContent = Math.round(percent) + '%';
                document.getElementById('statusText').textContent = message;
            }}
            
            function showSuccess(filename, emailCount) {{
                document.getElementById('progressSection').style.display = 'none';
                document.getElementById('successSection').style.display = 'block';
                document.getElementById('successMessage').textContent = 
                    `Successfully processed ${{emailCount}} emails. File: ${{filename}}`;
                
                // Set up download button
                document.getElementById('downloadBtn').onclick = () => {{
                    window.location.href = `/api/download/${{generationId}}`;
                }};
            }}
            
            function showError(message) {{
                document.getElementById('progressSection').style.display = 'none';
                document.getElementById('generateBtn').style.display = 'block';
                alert('Error: ' + message);
            }}
            
            function resetForm() {{
                document.getElementById('successSection').style.display = 'none';
                document.getElementById('generateBtn').style.display = 'block';
                generationId = null;
            }}
            
            function cancelGeneration() {{
                if (progressInterval) {{
                    clearInterval(progressInterval);
                }}
                // TODO: Send cancel request to server
                resetForm();
            }}
        </script>
    </body>
    </html>
    """)

@app.post("/api/start-generation")
async def start_generation(request: Request):
    """Start the email generation process"""
    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in user_sessions:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        data = await request.json()
        month = data['month']
        year = data['year']
        
        # Generate unique ID for this generation task
        generation_id = secrets.token_urlsafe(16)
        
        # Initialize status
        generation_status[generation_id] = {
            'status': 'processing',
            'progress': 0,
            'message': 'Starting...',
            'session_id': session_id,
            'month': month,
            'year': year,
            'csv_content': None,
            'filename': None,
            'email_count': 0
        }
        
        # Start background task (we'll implement this next)
        asyncio.create_task(process_emails_background(generation_id))
        
        return {"generation_id": generation_id, "status": "started"}
        
    except Exception as e:
        print(f"Error starting generation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/generation-status/{generation_id}")
async def get_generation_status(generation_id: str):
    """Get the current status of email generation"""
    if generation_id not in generation_status:
        raise HTTPException(status_code=404, detail="Generation not found")
    
    status = generation_status[generation_id]
    return {
        "status": status['status'],
        "progress": status['progress'],
        "message": status['message'],
        "filename": status.get('filename'),
        "email_count": status.get('email_count', 0)
    }

@app.get("/api/download/{generation_id}")
async def download_csv(generation_id: str):
    """Download the generated CSV"""
    if generation_id not in generation_status:
        raise HTTPException(status_code=404, detail="Generation not found")
    
    status = generation_status[generation_id]
    if status['status'] != 'completed':
        raise HTTPException(status_code=400, detail="Generation not completed")
    
    return StreamingResponse(
        io.StringIO(status['csv_content']),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={status['filename']}"}
    )

async def process_emails_background(generation_id: str):
    """Background task to process emails"""
    try:
        status = generation_status[generation_id]
        session_id = status['session_id']
        month = status['month']
        year = status['year']
        
        # Update progress
        status['progress'] = 20
        status['message'] = 'Authenticating with Gmail...'
        
        # Get user session
        user_data = user_sessions[session_id]
        creds_data = user_data['credentials']
        
        # Recreate credentials
        credentials = Credentials(
            token=creds_data['token'],
            refresh_token=creds_data['refresh_token'],
            token_uri=creds_data['token_uri'],
            client_id=creds_data['client_id'],
            client_secret=creds_data['client_secret'],
            scopes=creds_data['scopes']
        )
        
        # Refresh if needed
        if credentials.expired and credentials.refresh_token:
            status['message'] = 'Refreshing credentials...'
            credentials.refresh(GoogleRequest())
        
        # Build Gmail service
        status['progress'] = 30
        status['message'] = 'Connecting to Gmail API...'
        service = build('gmail', 'v1', credentials=credentials)
        
        print(f"Processing emails for {month}/{year} - User ID: 'me'")
        
        # Test connection
        profile = service.users().getProfile(userId='me').execute()
        print(f"Connected to Gmail for: {profile['emailAddress']}")
        
        # Date range for month
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, month + 1, 1)
        
        # Search sent emails
        query = f"in:sent after:{start_date.strftime('%Y/%m/%d')} before:{end_date.strftime('%Y/%m/%d')}"
        print(f"Gmail API Query: {query}")
        
        status['progress'] = 40
        status['message'] = f'Searching emails for {calendar.month_name[month]} {year}...'
        
        # Get all messages with pagination
        all_messages = []
        page_token = None
        page_count = 0
        
        while True:
            page_count += 1
            status['progress'] = 40 + min(page_count * 5, 20)  # Progress 40-60% for fetching
            status['message'] = f'Fetching message list (page {page_count})...'
            
            request_params = {
                'userId': 'me',
                'q': query,
                'maxResults': 500  # Use maximum allowed
            }
            if page_token:
                request_params['pageToken'] = page_token
            
            try:
                messages_result = service.users().messages().list(**request_params).execute()
                messages = messages_result.get('messages', [])
            except HttpError as e:
                if e.resp.status == 429:  # Rate limit exceeded
                    print(f"Rate limit hit, waiting 60 seconds...")
                    status['message'] = 'Rate limit reached, waiting 60 seconds...'
                    await asyncio.sleep(60)
                    continue
                elif e.resp.status == 403:  # Quota exceeded
                    print(f"Quota exceeded: {e}")
                    status['status'] = 'failed'
                    status['message'] = 'Gmail API quota exceeded. Please try again later.'
                    return
                else:
                    print(f"Gmail API error: {e}")
                    status['status'] = 'failed'
                    status['message'] = f'Gmail API error: {str(e)}'
                    return
            
            if not messages:
                break
            
            all_messages.extend(messages)
            print(f"Fetched page {page_count}: {len(messages)} messages (total: {len(all_messages)})")
            
            page_token = messages_result.get('nextPageToken')
            if not page_token:
                break
            
            # Small delay between API calls
            await asyncio.sleep(0.1)
        
        print(f"Total messages found: {len(all_messages)}")
        
        if not all_messages:
            status['status'] = 'completed'
            status['progress'] = 100
            status['message'] = 'No emails found for this period'
            status['email_count'] = 0
            status['csv_content'] = 'sent_date,recipient_name,recipient_email,thread_id,message_id\\n'
            status['filename'] = f"{user_data['email'].split('@')[0]}_{calendar.month_name[month].lower()}.csv"
            return
        
        # Process messages
        all_emails = []
        total_messages = len(all_messages)
        
        for i, message in enumerate(all_messages):
            status['progress'] = 60 + (i / total_messages) * 30  # Progress 60-90% for processing
            status['message'] = f'Processing email {i+1} of {total_messages}...'
            
            try:
                email_data = get_email_details(service, message['id'])
                if email_data:
                    all_emails.append(email_data)
            except HttpError as e:
                if e.resp.status == 429:  # Rate limit exceeded
                    print(f"Rate limit hit while processing message, waiting 30 seconds...")
                    status['message'] = f'Rate limit reached, waiting... ({i+1}/{total_messages})'
                    await asyncio.sleep(30)
                    # Retry the same message
                    try:
                        email_data = get_email_details(service, message['id'])
                        if email_data:
                            all_emails.append(email_data)
                    except:
                        print(f"Failed to process message {message['id']} after retry")
                elif e.resp.status == 403:  # Quota exceeded
                    print(f"Quota exceeded while processing messages")
                    status['status'] = 'failed'
                    status['message'] = 'Gmail API quota exceeded during processing. Please try again later.'
                    return
                else:
                    print(f"Error processing message {message['id']}: {e}")
            except Exception as e:
                print(f"Unexpected error processing message {message['id']}: {e}")
            
            # Small delay to avoid rate limiting
            await asyncio.sleep(0.05)  # Reduced delay since we're doing more requests
        
        # Generate CSV
        status['progress'] = 95
        status['message'] = 'Generating CSV...'
        
        csv_content = create_csv_content(all_emails)
        filename = f"{user_data['email'].split('@')[0]}_{calendar.month_name[month].lower()}.csv"
        
        # Complete
        status['status'] = 'completed'
        status['progress'] = 100
        status['message'] = f'Completed! Generated CSV with {len(all_emails)} emails.'
        status['csv_content'] = csv_content
        status['filename'] = filename
        status['email_count'] = len(all_emails)
        
        print(f"Successfully generated CSV with {len(all_emails)} emails")
        
    except Exception as e:
        print(f"Background processing error: {e}")
        print(traceback.format_exc())
        status['status'] = 'failed'
        status['message'] = f'Error: {str(e)}'

def get_email_details(service, message_id):
    """Extract email details from message"""
    try:
        message = service.users().messages().get(userId='me', id=message_id, format='full').execute()
        headers = message['payload'].get('headers', [])
        
        to_header = next((h['value'] for h in headers if h['name'] == 'To'), '')
        date_header = next((h['value'] for h in headers if h['name'] == 'Date'), '')
        
        if not to_header or not date_header:
            return None
        
        # Parse recipient (handle first recipient if multiple)
        first_recipient = to_header.split(',')[0].strip()
        if '<' in first_recipient and '>' in first_recipient:
            name_part = first_recipient.split('<')[0].strip().strip('"')
            email_part = first_recipient.split('<')[1].split('>')[0].strip()
            recipient_name = name_part if name_part else email_part
            recipient_email = email_part
        else:
            recipient_email = first_recipient.strip()
            recipient_name = recipient_email
        
        # Parse date
        try:
            dt = email.utils.parsedate_to_datetime(date_header)
            sent_date = dt.strftime('%m/%d/%Y %H:%M:%S')
        except:
            sent_date = datetime.now().strftime('%m/%d/%Y %H:%M:%S')
        
        # Get thread ID and message ID
        thread_id = message.get('threadId', '')
        message_id = message.get('id', '')
        
        return {
            'sent_date': sent_date,
            'recipient_name': recipient_name,
            'recipient_email': recipient_email,
            'thread_id': thread_id,
            'message_id': message_id
        }
        
    except Exception as e:
        print(f"Error parsing email {message_id}: {e}")
        return None

def create_csv_content(emails):
    """Create CSV content from email list"""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['sent_date', 'recipient_name', 'recipient_email', 'thread_id', 'message_id'])
    
    # Sort by date and write
    for email_data in sorted(emails, key=lambda x: x['sent_date']):
        writer.writerow([email_data['sent_date'], email_data['recipient_name'], email_data['recipient_email'], email_data['thread_id'], email_data['message_id']])
    
    return output.getvalue()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)