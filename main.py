from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse, JSONResponse
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from datetime import datetime, date, timezone, timedelta
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
REDIRECT_URI = os.getenv("REDIRECT_URI", "http://localhost:8000/auth/callback")
print(f"Using REDIRECT_URI: {REDIRECT_URI}")

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
                            <h4>📅 Single Month</h4>
                            <p>Generate CSV for one specific month only</p>
                            <div class="row mb-3">
                                <div class="col-6">
                                    <label>Month:</label>
                                    <select id="singleMonth" class="form-select">
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
                                    <select id="singleYear" class="form-select">
                                        <option value="2024">2024</option>
                                        <option value="2025">2025</option>
                                    </select>
                                </div>
                            </div>
                            <button id="singleBtn" onclick="startSingleMonthGeneration()" class="btn btn-success">Generate Single CSV</button>
                        </div>
                    </div>
                </div>
                
                <div class="col-md-6">
                    <div class="card">
                        <div class="card-body text-center">
                            <h4>📚 Multiple Months</h4>
                            <p>Generate single CSV file with all emails from selected month to July 2025</p>
                            <div class="row mb-3">
                                <div class="col-6">
                                    <label>Start Month:</label>
                                    <select id="multiMonth" class="form-select">
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
                                    <select id="multiYear" class="form-select">
                                        <option value="2024">2024</option>
                                        <option value="2025">2025</option>
                                    </select>
                                </div>
                            </div>
                            <button id="multiBtn" onclick="startMultiMonthGeneration()" class="btn btn-primary">Generate Combined CSV</button>
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
            
            async function startSingleMonthGeneration() {{
                const month = document.getElementById('singleMonth').value;
                const year = document.getElementById('singleYear').value;
                
                // Validate date (only Dec 2024+)
                const selectedDate = new Date(year, month - 1, 1);
                const minDate = new Date(2024, 11, 1); // December 2024
                const maxDate = new Date(2025, 6, 31); // July 2025
                
                if (selectedDate < minDate) {{
                    alert('Email collection starts from December 2024!');
                    return;
                }}
                
                if (selectedDate > maxDate) {{
                    alert('Email collection only available up to July 2025!');
                    return;
                }}
                
                // Hide buttons, show progress
                document.getElementById('singleBtn').style.display = 'none';
                document.getElementById('multiBtn').style.display = 'none';
                document.getElementById('progressSection').style.display = 'block';
                document.getElementById('successSection').style.display = 'none';
                
                try {{
                    updateProgress(10, 'Starting single month email collection...');
                    
                    const response = await fetch('/api/start-generation', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{
                            month: parseInt(month), 
                            year: parseInt(year),
                            mode: 'single'
                        }})
                    }});
                    
                    if (!response.ok) {{
                        throw new Error('Failed to start generation');
                    }}
                    
                    const data = await response.json();
                    generationId = data.generation_id;
                    
                    startProgressPolling();
                    
                }} catch (error) {{
                    showError('Failed to start generation: ' + error.message);
                }}
            }}
            
            async function startMultiMonthGeneration() {{
                const month = document.getElementById('multiMonth').value;
                const year = document.getElementById('multiYear').value;
                
                // Validate date (only Dec 2024+)
                const selectedDate = new Date(year, month - 1, 1);
                const minDate = new Date(2024, 11, 1); // December 2024
                const endDate = new Date(2025, 6, 31); // July 2025
                
                if (selectedDate < minDate) {{
                    alert('Email collection starts from December 2024!');
                    return;
                }}
                
                if (selectedDate > endDate) {{
                    alert('Start month cannot be after July 2025!');
                    return;
                }}
                
                // Calculate months from start to July 2025
                const monthsToProcess = [];
                let currentMonth = new Date(selectedDate);
                while (currentMonth <= endDate) {{
                    monthsToProcess.push({{
                        month: currentMonth.getMonth() + 1,
                        year: currentMonth.getFullYear(),
                        name: currentMonth.toLocaleString('default', {{ month: 'long', year: 'numeric' }})
                    }});
                    currentMonth.setMonth(currentMonth.getMonth() + 1);
                }}
                
                console.log(`Will process ${{monthsToProcess.length}} months:`, monthsToProcess);
                
                // Hide buttons, show progress
                document.getElementById('singleBtn').style.display = 'none';
                document.getElementById('multiBtn').style.display = 'none';
                document.getElementById('progressSection').style.display = 'block';
                document.getElementById('successSection').style.display = 'none';
                
                try {{
                    // Start generation process
                    updateProgress(10, 'Starting multi-month email collection...');
                    
                    const response = await fetch('/api/start-generation', {{
                        method: 'POST',
                        headers: {{'Content-Type': 'application/json'}},
                        body: JSON.stringify({{
                            month: parseInt(month), 
                            year: parseInt(year),
                            mode: 'multi'
                        }})
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
            
            let downloadedFiles = new Set();
            
            function startProgressPolling() {{
                progressInterval = setInterval(async () => {{
                    try {{
                        const response = await fetch(`/api/generation-status/${{generationId}}`);
                        const status = await response.json();
                        
                        updateProgress(status.progress, status.message);
                        
                        // Handle downloads based on mode
                        if (status.mode === 'single') {{
                            // Single file download when complete
                            if (status.status === 'completed' && status.completed_files && status.completed_files.length > 0) {{
                                clearInterval(progressInterval);
                                showSuccess(1, status.total_email_count);
                                // Auto-download the single file
                                setTimeout(() => {{
                                    downloadFile(0, status.completed_files[0].filename);
                                }}, 500);
                            }}
                        }} else {{
                            // Multi-month mode - single combined file when complete
                            if (status.status === 'completed' && status.completed_files && status.completed_files.length > 0) {{
                                clearInterval(progressInterval);
                                showSuccess(1, status.total_email_count);
                                // Auto-download the combined file
                                setTimeout(() => {{
                                    downloadFile(0, status.completed_files[0].filename);
                                }}, 500);
                            }}
                        }}
                        
                        if (status.status === 'completed' && (!status.completed_files || status.completed_files.length === 0)) {{
                            clearInterval(progressInterval);
                            showSuccess(0, 0);
                        }} else if (status.status === 'failed') {{
                            clearInterval(progressInterval);
                            showError(status.message);
                        }}
                    }} catch (error) {{
                        console.error('Error polling status:', error);
                    }}
                }}, 1000); // Poll every second
            }}
            
            function downloadFile(fileIndex, filename) {{
                console.log(`Auto-downloading: ${{filename}}`);
                window.location.href = `/api/download/${{generationId}}?file_index=${{fileIndex}}`;
            }}
            
            function updateProgress(percent, message) {{
                document.getElementById('progressBar').style.width = percent + '%';
                document.getElementById('progressText').textContent = Math.round(percent) + '%';
                document.getElementById('statusText').textContent = message;
            }}
            
            function showSuccess(fileCount, totalEmailCount) {{
                document.getElementById('progressSection').style.display = 'none';
                document.getElementById('successSection').style.display = 'block';
                document.getElementById('successMessage').textContent = 
                    `Successfully processed ${{totalEmailCount}} emails in ${{fileCount}} CSV file. File has been automatically downloaded.`;
                
                // Hide download button since files are auto-downloaded
                document.getElementById('downloadBtn').style.display = 'none';
            }}
            
            function showError(message) {{
                document.getElementById('progressSection').style.display = 'none';
                document.getElementById('singleBtn').style.display = 'block';
                document.getElementById('multiBtn').style.display = 'block';
                alert('Error: ' + message);
            }}
            
            function resetForm() {{
                document.getElementById('successSection').style.display = 'none';
                document.getElementById('singleBtn').style.display = 'block';
                document.getElementById('multiBtn').style.display = 'block';
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
        mode = data.get('mode', 'multi')  # Default to multi for backward compatibility
        
        # Generate unique ID for this generation task
        generation_id = secrets.token_urlsafe(16)
        
        # Calculate months to process based on mode
        if mode == 'single':
            # Single month only
            months_to_process = [{
                'month': month,
                'year': year,
                'name': calendar.month_name[month]
            }]
        else:
            # Multiple months from start to July 2025
            start_date = datetime(year, month, 1)
            end_date = datetime(2025, 7, 31)  # July 2025
            months_to_process = []
            
            current_month = start_date
            while current_month <= end_date:
                months_to_process.append({
                    'month': current_month.month,
                    'year': current_month.year,
                    'name': calendar.month_name[current_month.month]
                })
                if current_month.month == 12:
                    current_month = current_month.replace(year=current_month.year + 1, month=1)
                else:
                    current_month = current_month.replace(month=current_month.month + 1)
        
        # Initialize status
        generation_status[generation_id] = {
            'status': 'processing',
            'progress': 0,
            'message': 'Starting...',
            'session_id': session_id,
            'months_to_process': months_to_process,
            'current_month_index': 0,
            'completed_files': [],
            'total_email_count': 0,
            'mode': mode
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
        "completed_files": status.get('completed_files', []),
        "total_email_count": status.get('total_email_count', 0),
        "current_month_index": status.get('current_month_index', 0),
        "months_to_process": status.get('months_to_process', []),
        "mode": status.get('mode', 'multi')
    }

@app.get("/api/download/{generation_id}")
async def download_csv(generation_id: str, file_index: int = 0):
    """Download a specific CSV file"""
    if generation_id not in generation_status:
        raise HTTPException(status_code=404, detail="Generation not found")
    
    status = generation_status[generation_id]
    completed_files = status.get('completed_files', [])
    
    if not completed_files:
        raise HTTPException(status_code=400, detail="No files available")
    
    if file_index >= len(completed_files):
        raise HTTPException(status_code=400, detail="File index out of range")
    
    file_info = completed_files[file_index]
    
    return StreamingResponse(
        io.StringIO(file_info['csv_content']),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={file_info['filename']}"}
    )

async def process_emails_background(generation_id: str):
    """Background task to process emails for multiple months"""
    try:
        status = generation_status[generation_id]
        session_id = status['session_id']
        months_to_process = status['months_to_process']
        total_months = len(months_to_process)
        
        # Update progress
        status['progress'] = 10
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
        status['progress'] = 15
        status['message'] = 'Connecting to Gmail API...'
        service = build('gmail', 'v1', credentials=credentials)
        
        # Test connection
        profile = service.users().getProfile(userId='me').execute()
        print(f"Connected to Gmail for: {profile['emailAddress']}")
        
        mode = status.get('mode', 'multi')
        
        if mode == 'single':
            # Single month processing
            month_info = months_to_process[0]
            current_month = month_info['month']
            current_year = month_info['year']
            month_name = month_info['name']
            
            status['progress'] = 20
            status['message'] = f'Processing {month_name} {current_year}...'
            
            print(f"Processing emails for {current_month}/{current_year}")
            
            # Process this month
            month_emails = await process_single_month(service, current_month, current_year, status, 20)
            
            if month_emails:
                # Create CSV for this month
                csv_content = create_csv_content(month_emails)
                filename = f"{user_data['email'].split('@')[0]}_{month_name.lower()}_{current_year}.csv"
                
                # Store completed file
                file_info = {
                    'filename': filename,
                    'csv_content': csv_content,
                    'email_count': len(month_emails),
                    'month': current_month,
                    'year': current_year,
                    'month_name': month_name
                }
                status['completed_files'].append(file_info)
                status['total_email_count'] = len(month_emails)
                
                print(f"Completed {month_name} {current_year}: {len(month_emails)} emails")
            
        else:
            # Multi-month processing - combine all emails into single file
            all_emails = []
            
            for month_index, month_info in enumerate(months_to_process):
                current_month = month_info['month']
                current_year = month_info['year']
                month_name = month_info['name']
                
                # Update progress for current month
                base_progress = 20 + (month_index / total_months) * 70
                status['progress'] = base_progress
                status['message'] = f'Processing {month_name} {current_year}...'
                status['current_month_index'] = month_index
                
                print(f"Processing emails for {current_month}/{current_year}")
                
                # Process this month
                month_emails = await process_single_month(service, current_month, current_year, status, base_progress)
                
                if month_emails:
                    all_emails.extend(month_emails)
                    print(f"Completed {month_name} {current_year}: {len(month_emails)} emails")
                else:
                    print(f"No emails found for {month_name} {current_year}")
            
            # Create single combined CSV file
            if all_emails:
                csv_content = create_csv_content(all_emails)
                start_month = calendar.month_name[months_to_process[0]['month']].lower()
                start_year = months_to_process[0]['year']
                end_month = calendar.month_name[months_to_process[-1]['month']].lower()
                end_year = months_to_process[-1]['year']
                
                if len(months_to_process) == 1:
                    filename = f"{user_data['email'].split('@')[0]}_{start_month}_{start_year}.csv"
                else:
                    filename = f"{user_data['email'].split('@')[0]}_{start_month}_{start_year}_to_{end_month}_{end_year}.csv"
                
                # Store combined file
                file_info = {
                    'filename': filename,
                    'csv_content': csv_content,
                    'email_count': len(all_emails),
                    'months_included': len(months_to_process)
                }
                status['completed_files'].append(file_info)
                status['total_email_count'] = len(all_emails)
                
                print(f"Created combined CSV with {len(all_emails)} emails from {len(months_to_process)} months")
        
        # Mark as completed
        status['status'] = 'completed'
        status['progress'] = 100
        status['message'] = f'Completed! Generated {len(status["completed_files"])} CSV files with {status["total_email_count"]} total emails.'
        
        print(f"Successfully generated {len(status['completed_files'])} CSV files")
        
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
        
        if not to_header:
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
        
        # Use internalDate for consistent timezone handling
        try:
            # Get internalDate (milliseconds since epoch) from Gmail API
            internal_date_ms = message.get('internalDate')
            if not internal_date_ms:
                return None
            
            # Convert to datetime in UTC
            dt_utc = datetime.fromtimestamp(int(internal_date_ms) / 1000, tz=timezone.utc)
            
            # Convert to IST (UTC + 5:30)
            ist_tz = timezone(timedelta(hours=5, minutes=30))
            dt_ist = dt_utc.astimezone(ist_tz)
            
            # Format without timezone label (already converted to IST)
            sent_date = dt_ist.strftime('%d/%m/%Y %H:%M:%S')
        except Exception as e:
            print(f"Error parsing internalDate for message {message_id}: {e}")
            return None
        
        # Filter out loopwork.co domain emails
        if recipient_email.lower().endswith('@loopwork.co'):
            return None  # Skip this email
        
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

async def process_single_month(service, month, year, status, base_progress):
    """Process emails for a single month"""
    try:
        # Date range for month
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, month + 1, 1)
        
        # Search sent emails
        query = f"in:sent after:{start_date.strftime('%Y/%m/%d')} before:{end_date.strftime('%Y/%m/%d')}"
        print(f"Gmail API Query: {query}")
        
        # Get all messages with pagination
        all_messages = []
        page_token = None
        page_count = 0
        
        while True:
            page_count += 1
            status['message'] = f'Fetching {calendar.month_name[month]} {year} emails (page {page_count})...'
            
            request_params = {
                'userId': 'me',
                'q': query,
                'maxResults': 500
            }
            if page_token:
                request_params['pageToken'] = page_token
            
            try:
                messages_result = service.users().messages().list(**request_params).execute()
                messages = messages_result.get('messages', [])
            except HttpError as e:
                if e.resp.status == 429:
                    print(f"Rate limit hit, waiting 60 seconds...")
                    status['message'] = f'Rate limit reached, waiting... ({calendar.month_name[month]} {year})'
                    await asyncio.sleep(60)
                    continue
                elif e.resp.status == 403:
                    print(f"Quota exceeded: {e}")
                    return None
                else:
                    print(f"Gmail API error: {e}")
                    return None
            
            if not messages:
                break
            
            all_messages.extend(messages)
            print(f"Fetched page {page_count}: {len(messages)} messages (total: {len(all_messages)})")
            
            page_token = messages_result.get('nextPageToken')
            if not page_token:
                break
            
            await asyncio.sleep(0.1)
        
        print(f"Total messages found for {calendar.month_name[month]} {year}: {len(all_messages)}")
        
        if not all_messages:
            return []
        
        # Process messages
        all_emails = []
        total_messages = len(all_messages)
        
        for i, message in enumerate(all_messages):
            if i % 10 == 0:  # Update progress every 10 emails
                progress = base_progress + (i / total_messages) * (70 / len(status['months_to_process']))
                status['progress'] = min(progress, 90)
                status['message'] = f'Processing {calendar.month_name[month]} {year} email {i+1} of {total_messages}...'
            
            try:
                email_data = get_email_details(service, message['id'])
                if email_data:
                    all_emails.append(email_data)
            except HttpError as e:
                if e.resp.status == 429:
                    print(f"Rate limit hit while processing message, waiting 30 seconds...")
                    await asyncio.sleep(30)
                    try:
                        email_data = get_email_details(service, message['id'])
                        if email_data:
                            all_emails.append(email_data)
                    except:
                        print(f"Failed to process message {message['id']} after retry")
                elif e.resp.status == 403:
                    print(f"Quota exceeded while processing messages")
                    return all_emails  # Return what we have so far
                else:
                    print(f"Error processing message {message['id']}: {e}")
            except Exception as e:
                print(f"Unexpected error processing message {message['id']}: {e}")
            
            await asyncio.sleep(0.05)
        
        return all_emails
        
    except Exception as e:
        print(f"Error processing month {month}/{year}: {e}")
        return []


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)