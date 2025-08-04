Email Collection Service - Project Context

  Background:

  I'm building an email collection service that fetches Gmail sent emails and stores them in cloud storage for a CSV Analytics
  Dashboard to consume. This is a separate microservice from the main dashboard application.

  Architecture Overview:

  [Email Collection Service] → [Supabase Database + Storage] → [Dashboard Application]
           ↓                           ↓                              ↓
     Gmail API + OAuth           Metadata + CSV Files           Fetches filtered data
     FastAPI Backend             PostgreSQL + File Storage      Existing Streamlit app
     Background Processing       Structured by account/date     No changes needed

  Technical Requirements:

  Tech Stack: FastAPI + Supabase + PostgreSQL
  Storage: Supabase Storage (CSV files)
  Database: PostgreSQL (file metadata)
  Authentication: Gmail OAuth2 with this Client ID: 336564416468-j8pj5104gb52feasie7j64o1vd9r7lva.apps.googleusercontent.com

  Database Schema:

  CREATE TABLE email_files (
      id SERIAL PRIMARY KEY,
      account_email VARCHAR(255) NOT NULL,
      start_date DATE NOT NULL,
      end_date DATE NOT NULL,
      file_path VARCHAR(500) NOT NULL,
      record_count INTEGER,
      file_size_mb DECIMAL(8,2),
      created_at TIMESTAMP DEFAULT NOW(),
      updated_at TIMESTAMP DEFAULT NOW()
  );

  CREATE INDEX idx_account_date ON email_files(account_email, start_date, end_date);

  File Storage Structure:

  emails/
  ├── john.doe@company.com/
  │   ├── sent_emails_2024-01-01_2024-01-31.csv
  │   ├── sent_emails_2024-02-01_2024-02-29.csv
  │   └── sent_emails_2024-03-01_2024-03-31.csv
  └── jane.smith@company.com/
      └── sent_emails_2024-01-01_2024-01-31.csv

  Required API Endpoints:

  GET /accounts - List available email accounts
  GET /date-ranges/{account} - Get available date ranges for account
  GET /emails/{account}?start_date=X&end_date=Y - Get merged CSV data
  POST /collect/{account} - Trigger email collection for account

  Gmail API Integration:

  - Use Gmail API to fetch sent emails (in:sent query)
  - Handle pagination (Gmail limits 500 emails per request)
  - Support large datasets (potentially 10,000+ emails)
  - Extract: recipient_name, sent_date, Recipient Email (same format as existing CSV)
  - Apply same preprocessing rules as current dashboard (domain filtering, time adjustments, etc.)

  CSV Output Format:

  Must match existing Send Mails CSV format:
  recipient_name,sent_date,Recipient Email
  John Doe,02/07/2025 19:34:57,john@example.com
  Jane Smith,02/07/2025 19:35:12,jane@test.com

  Dashboard Integration:

  The existing dashboard will call these APIs to replace manual CSV upload:
  1. User selects account from dropdown (populated by /accounts)
  2. User selects date range (constrained by /date-ranges/{account})
  3. Dashboard calls /emails/{account}?start_date=X&end_date=Y
  4. Returns merged CSV data as pandas DataFrame
  5. Continues with existing processing pipeline (unchanged)

  What to Build:

  1. FastAPI application with Gmail OAuth flow
  2. Supabase integration (database + storage)
  3. Gmail API client with pagination support
  4. Email collection endpoints
  5. Data filtering APIs for dashboard consumption
  6. Background job processing for large email collections
  7. Error handling and logging
  8. Simple frontend for testing OAuth flow (optional)

  Immediate Goals:

  - Set up Supabase project and database
  - Implement Gmail OAuth authentication
  - Build email collection with pagination
  - Create CSV storage with proper file structure
  - Build API endpoints for dashboard integration
  - Test with real Gmail account

  Notes:

  - This service will handle historical email collection (backdate emails)
  - Real-time sync will be implemented later
  - Focus on reliability and data integrity
  - Support multiple user accounts
  - Optimize for dashboard's filtering requirements

  ---
  Please build this email collection service with the above specifications. Start with project setup, Supabase configuration, and 
  Gmail OAuth implementation.