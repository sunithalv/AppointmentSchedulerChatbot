import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from langchain.agents import Tool
from langchain_google_community import GmailToolkit
from google.oauth2.credentials import Credentials
from langchain_google_community.gmail.utils import (
    build_resource_service,
    get_gmail_credentials,
)
from langgraph.prebuilt import create_react_agent
import json
from datetime import datetime, timedelta
import re
import pytz

class GoogleCalendarTool(Tool):
    def __init__(self):
        # Initialize the Tool without storing credentials
        super().__init__(
            name="google_calendar_tool",
            description="A tool to create events in Google Calendar.",
            func=self.run
        )

    def _get_service(self, creds):
        """Initialize the service object for Google Calendar API."""
        return build('calendar', 'v3', credentials=creds)
    
    def preprocess_date_string(self,date_str):
        # Remove ordinal suffixes (like "nd", "rd", "st", "th") from the day
        date_str = re.sub(r'(\d{1,2})(st|nd|rd|th)', r'\1', date_str)
        # Ensure there is a space between the day and month if not present
        date_str = re.sub(r'(\d{1,2})([A-Za-z])', r'\1 \2', date_str)
        return date_str

    def convert_to_google_calendar_format(self,date_str):
        # Preprocess the date string
        date_str = self.preprocess_date_string(date_str)
        
        # Define the timezone for IST
        timezone = pytz.timezone('Asia/Kolkata')  # IST timezone
        
        # Remove the 'IST' part since it's handled by the timezone
        date_str = date_str.replace("IST", "").strip()

        current_year = datetime.now().year
        # Parse the date string without the timezone abbreviation
        start_datetime = datetime.strptime(date_str, "%d %b %H:%M").replace(current_year)

        # If the parsed date is in the past, adjust to the next year
        now = datetime.now()
        if start_datetime < now:
            start_datetime = start_datetime.replace(year=current_year + 1)
        
        
        # Localize to the IST timezone
        start_datetime = timezone.localize(start_datetime)

        # Add 2 hours to get the end time
        end_datetime = start_datetime + timedelta(hours=2)

        # Convert to Google Calendar compatible format (ISO 8601)
        start_time_iso = start_datetime.isoformat()
        end_time_iso = end_datetime.isoformat()

        return start_time_iso, end_time_iso
    def run(self, input_data: dict, creds):
        """Run method to create an event in Google Calendar."""
        # Parse custom formatted start and end times
        start_datetime, end_datetime = self.convert_to_google_calendar_format(input_data['start_time'])

        # Initialize the service (this could be done when the tool is first used)
        service = self._get_service(creds)

        # Example input_data: {"service": "Meeting", "location": "Zoom", "start_time": "2024-11-18T10:00:00", "end_time": "2024-11-18T11:00:00"}
        event = {
            'summary': input_data['service'],
            'location': input_data['location'],
            'description': f"Meeting scheduled from {input_data['start_time']}.",
            'start': {
                'dateTime': start_datetime,
                'timeZone': 'Asia/Kolkata',
            },
            'end': {
                'dateTime': end_datetime,
                'timeZone': 'Asia/Kolkata',
            },
            'conferenceData': {
                'createRequest': {
                    'requestId': "sample123",  # Use a unique ID for idempotency
                    'conferenceSolutionKey': {'type': 'hangoutsMeet'},
                },
            },
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'popup', 'minutes': 10},
                ],
            },
        }

        # Insert the event into Google Calendar with conference data
        event_result = service.events().insert(
            calendarId='primary',
            body=event,
            conferenceDataVersion=1
        ).execute()
        # Return the Google Meet link
        conference_data = event_result.get('conferenceData', {})
        entry_points = conference_data.get('entryPoints', [])
        meet_link = next((ep['uri'] for ep in entry_points if ep['entryPointType'] == 'video'), None)
        return meet_link if meet_link else "Google Meet link not created."

def create_google_calendar_event(input_data):
    creds = authenticate_google_account()
    google_calendar_tool = GoogleCalendarTool()
    meet_link = google_calendar_tool.run(input_data=input_data, creds=creds)
    #print(f"Event created: {meet_link}")
    return meet_link
    
def send_email(input_data,llm):
    creds = authenticate_gmail()
    convert_json(creds)
    credentials = get_gmail_credentials(
    token_file="gmail-token.json",
    scopes=["https://mail.google.com/"],
    client_secrets_file="credentials.json",
    )
    api_resource = build_resource_service(credentials=credentials)
    toolkit = GmailToolkit(api_resource=api_resource)
    agent_executor = create_react_agent(llm, toolkit.get_tools())
    email_template=get_email_template(input_data)
    events = agent_executor.stream(
    {"messages": [("user", email_template)]},
    stream_mode="values",
    )
    # try:
    #     for event in events:
    #         event["messages"][-1].pretty_print()
    # except Exception as e:
    #     print(f"Error: {e}")



def authenticate_google_account():
    creds = None
    SCOPES = ['https://www.googleapis.com/auth/calendar.events']
    # The file token.pickle stores the user's access and refresh tokens.
    # It is created automatically when the authorization flow completes for the first time.
    if os.path.exists('calender-token.pickle'):
        with open('calender-token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(
                port=8080,access_type="offline", prompt="consent")
            #creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('calender-token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    return creds

def authenticate_gmail():
    creds = None
    # Add the required Gmail scopes
    SCOPES = [
        "https://mail.google.com/",  # Full access, or replace with specific scopes
    ]
    # The file token.pickle stores the user's access and refresh tokens.
    # It is created automatically when the authorization flow completes for the first time.
    if os.path.exists('gmail-token.pickle'):
        with open('gmail-token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(
                port=8080,access_type="offline", prompt="consent")
        # Save the credentials for the next run
        with open('gmail-token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    return creds

def convert_json(credentials):
    # Check if the object supports serialization to JSON
    if isinstance(credentials, Credentials):
        # Convert credentials to a JSON serializable format
        credentials_data = credentials.to_json()
        
        # Save the pickle file to JSON file
        with open("gmail-token.json", "w") as f:
            json.dump(json.loads(credentials_data), f, indent=4)

        print("Credentials successfully converted to JSON!")
    else:
        print("The token.pickle file does not contain a supported Credentials object.")

def get_email_template(input_data):
    service=input_data['service']
    location=input_data['location']
    start_time=input_data['start_time']
    fullName=input_data['fullname']
    email=input_data['email']
    meet_link=input_data['meet_link']

    email_template=f"""
    Please create and send a proper formatted email to {email} and Subject: "Appointment Confirmed"  
    in the following format.The meet_link should be in a clickable url format.

    <p>Dear {fullName},</p>
    <p>I hope this email finds you well. I am writing to confirm the details of the scheduled quick call with me.</p>
    <p>Please find the information below:</p>
    <p>
        <strong>Service Type:</strong> {service}<br>
        <strong>Location:</strong> {location}<br>
        <strong>Datetime:</strong> {start_time} <br>
        <strong>Link:</strong> <a href="{meet_link}">{meet_link}</a>
    </p><br>
    <p>
        If you have any questions or need to make any changes, please feel free to reach out.<br>
        You can reply to this email or contact us directly at (000)-000 0000.
    </p><br>
    <p>I look forward to connecting with you on {start_time}. Thank you for choosing my service, and I am excited to assist you.</p><br>
    <p>Best regards,<br>Scheduler</p>
    """
    return email_template



