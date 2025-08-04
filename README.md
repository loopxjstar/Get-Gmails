# Gmail Email CSV Exporter

A web application that exports Gmail sent emails to CSV files with real-time progress tracking.

## Features

- 🔐 **Google OAuth Authentication** - Secure Gmail API access
- 📊 **Progress Tracking** - Real-time progress bars during email collection
- 📅 **Monthly Export** - Generate CSV files for specific months
- 🔄 **Full Pagination** - Handles unlimited emails per month
- 🛡️ **Rate Limit Handling** - Robust API error handling and retries
- 📋 **Complete Data** - Exports date, recipient name, email, thread ID, and message ID

## CSV Output Format

Each CSV file contains the following columns:
- `sent_date` - When the email was sent (MM/DD/YYYY HH:MM:SS)
- `recipient_name` - Name of the recipient
- `recipient_email` - Email address of the recipient  
- `thread_id` - Gmail thread ID for conversation grouping
- `message_id` - Unique Gmail message ID

## Setup Instructions

### 1. Clone the Repository
```bash
git clone <repository-url>
cd back-date-email-fetching
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Google Cloud Setup
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing one
3. Enable the Gmail API
4. Create OAuth 2.0 credentials:
   - **Application type**: Web application
   - **Authorized JavaScript origins**: `http://localhost:8000`
   - **Authorized redirect URIs**: `http://localhost:8000/auth/callback`
5. Copy the Client ID and Client Secret

### 4. Environment Configuration
1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```
2. Edit `.env` and add your Google credentials:
   ```
   GOOGLE_CLIENT_ID=your_client_id_here
   GOOGLE_CLIENT_SECRET=your_client_secret_here
   ```

### 5. Run the Application
```bash
python3 main.py
```

The application will be available at `http://localhost:8000`

## Usage

1. **Sign In**: Click "Sign in with Google" and authorize the application
2. **Select Month**: Choose the month and year you want to export
3. **Generate CSV**: Click "Generate CSV" and wait for the progress to complete
4. **Download**: Once processing is complete, click "Download CSV"

## Technical Details

### Gmail API Limits
- **Maximum messages per request**: 500
- **Rate limiting**: Built-in handling with automatic retries
- **Quota management**: Graceful failure with user-friendly messages

### Date Range
- Email collection starts from **December 2024**
- Cannot export emails from future dates
- Supports any month from December 2024 onwards

### File Naming
CSV files are named using the format: `{account_name}_{month}.csv`
- Example: `john_doe_december.csv`

## Architecture

- **Backend**: FastAPI (Python)
- **Authentication**: Google OAuth 2.0
- **API**: Gmail API v1
- **Frontend**: Bootstrap 5 + Vanilla JavaScript
- **Progress Tracking**: Real-time polling with background tasks

## Error Handling

The application handles various scenarios:
- **Rate Limiting**: Automatic 60-second waits and retries
- **Quota Exceeded**: Graceful failure with clear error messages
- **Network Issues**: Retry logic for transient failures
- **Large Email Volumes**: Efficient pagination and progress tracking

## Development

To run in development mode:
```bash
python3 main.py
```

The server will start on `http://localhost:8000` with auto-reload enabled.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

MIT License - see LICENSE file for details