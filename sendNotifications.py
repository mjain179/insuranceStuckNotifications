from db_tools import *
from config import *
import dotenv
import os
import json
from twilio.rest import Client
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import psycopg2
import pandas as pd
from datetime import datetime, timezone

dotenv.load_dotenv()
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')
DIVYESH_PHONE = os.getenv('DIVYESH_PHONE')

def createConnection():
    params = game_db_config()
    gameDbConn = psycopg2.connect(**params)
    gameDbCur = gameDbConn.cursor()
    return gameDbConn, gameDbCur

def get_mail_credentials():
    with open('mail_credentials.json') as json_file:
        data = json.load(json_file)
        return data['email'], data['password']

def convertToUtc(ts):
    if ts is None or (isinstance(ts, float) and pd.isna(ts)):
        return None
    t = pd.Timestamp(ts)
    if t.tzinfo is None or t.tz is None:
        return t.tz_localize('UTC')
    return t.tz_convert('UTC')

def calculatePatientDurationInPipeline(patient, dbCursor):
    durationInDays = -1
    if pd.isna(patient['age_id']):
        nowUtc = pd.Timestamp.now(tz='UTC')
        convertedCreatedAt = convertToUtc(patient['created_at'])
        differenceInTimes = nowUtc - convertedCreatedAt
        durationInDays = differenceInTimes.days
        if durationInDays == 0:
            return -1
    else:
        patientBeginTime = getStatusBeginTime(patient['age_id'], dbCursor)
        nowUtc = datetime.now(timezone.utc)
        differenceInTimes = nowUtc - patientBeginTime
        durationInDays = differenceInTimes.days
        if durationInDays == 0:
            return -1
    return durationInDays

def fillTemplate(template, patient):
    # Handle product
    product = ''
    if patient['product'] == None or pd.isna(patient['product']):
        product = "Motus Hand or Foot"
    elif 'hand' in patient['product'].lower():
        product = "Motus Hand"
    else:
        product = "Motus Foot"
    
    # Handle doctor_first_name
    doctor_first_name = ''
    if pd.isna(patient['doctor_first_name']) or patient['doctor_first_name'] == "#NA" or patient['doctor_first_name'] == '':
        doctor_first_name = patient['doctor_last_name'] if not pd.isna(patient['doctor_last_name']) else ''
    else:
        doctor_first_name = patient['doctor_first_name']
    
    # Handle dme_first_name with default
    dme_first_name = patient['dme_first_name'] if not pd.isna(patient['dme_first_name']) else "our billing partner"
    
    # Handle other fields with defaults
    patient_first_name = patient['patient_first_name'] if not pd.isna(patient['patient_first_name']) else ''
    dme_npi = patient['dme_npi'] if not pd.isna(patient['dme_npi']) else ''
    patient_insurance_id = patient['story_id'] if not pd.isna(patient['story_id']) else ''
    denial_letter = patient['denial_letter'] if not pd.isna(patient['denial_letter']) else ''
    
    return template.format(
        patient_first_name=patient_first_name,
        first_name=patient_first_name,
        product=product,
        doctor_first_name=doctor_first_name,
        dme_first_name=dme_first_name,
        dme_npi=dme_npi,
        patient_insurance_id=patient_insurance_id,
        denial_letter=denial_letter
    )

def sendMessage(client, filledTemplate, phoneNumber):    
    messageBody = f"{filledTemplate}"
    try:
        message = client.messages.create(
            body=messageBody, 
            from_=TWILIO_PHONE_NUMBER,
            to=phoneNumber
        )
    except Exception as e:
        print(f"Failed to send SMS: {e}")

def sendEmail(filledTemplate, patientEmail, patientFirstName, salespersonEmail=None):
    try:
        # Get mail credentials
        email_user, email_password = get_mail_credentials()
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = 'service@motusnova.com'
        msg['To'] = patientEmail
        msg['Subject'] = 'Insurance Claim Update from Motus Nova'
        
        # Add CC if salesperson email exists
        if salespersonEmail and salespersonEmail != '':
            msg['Cc'] = salespersonEmail
        
        # Convert text message to HTML format (preserve line breaks)
        html_content = filledTemplate.replace('\n', '<br>')
        
        # Attach HTML body
        msg.attach(MIMEText(html_content, 'html'))
        
        # Create SMTP session
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(email_user, email_password)
        
        # Send email
        recipients = [patientEmail]
        if salespersonEmail and salespersonEmail != '':
            recipients.append(salespersonEmail)
        
        server.send_message(msg)
        server.quit()
        
        print(f"Email sent successfully to {patientEmail}")
        
    except Exception as e:
        print(f"Failed to send email: {e}")

def main():
    print("=== Starting Insurance Reminder Script ===")
    print("Timestamp:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    dbConnection, dbCursor = createConnection()
    
    print("Fetching patients from database...")
    patientsToText = getAllPatientsToText(dbCursor)
    print(f"Found {len(patientsToText)} patients to process\n")
    
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    messagesSent = 0
    emailsSent = 0
    skippedCount = 0
    readyMessages = pd.DataFrame()
    
    # Define statuses that require clinicReferral subtype check
    restricted_statuses = ['notCovered', 'reject', 'rejectAuth']
    
    for index, patient in patientsToText.iterrows():
        print(f"\n--- Processing Patient {index + 1}/{len(patientsToText)} ---")
        print(f"Insurance ID: {patient['story_id']}, Contact ID: {patient['contact_id']}, Status: {patient['status']}")
        
        # Check for required fields
        if pd.isna(patient['patient_first_name']) or pd.isna(patient['patient_phone_number']) or pd.isna(patient['contact_id']):
            print(f"⊗ Skipping - Missing required data (name/phone/contact_id)")
            skippedCount += 1
            continue
        
        # Check if status requires clinicReferral subtype
        if patient['status'] in restricted_statuses:
            patient_subtype = patient['patient_subtype'] if not pd.isna(patient['patient_subtype']) else ''
            if patient_subtype != 'clinicReferral':
                print(f"⊗ Skipping - Status '{patient['status']}' requires clinicReferral subtype (current: {patient_subtype})")
                skippedCount += 1
                continue
            else:
                print(f"✓ Patient has clinicReferral subtype - proceeding with {patient['status']} notification")
        
        # Check opt-out status
        optedOut = hasPatientOptedOut(patient['contact_id'], dbCursor)
        if optedOut != None:
            print(f"⊗ Skipping - Patient has opted out (status: {optedOut})")
            skippedCount += 1
            continue
        
        # Calculate duration and get template
        patientDuration = calculatePatientDurationInPipeline(patient, dbCursor)
        templateName = patient['status'] + '_' + str(patientDuration)
        print(f"Duration in pipeline: {patientDuration} days")
        print(f"Looking for template: {templateName}")
        
        template = getTemplateFromDb(templateName, dbCursor)
        
        if template == None:
            print(f"⊗ Skipping - No template found for: {templateName}")
            skippedCount += 1
            continue
        
        print(f"✓ Template found")
        filledTemplate = fillTemplate(template, patient)
        
        # Send text message
        print(f"Sending SMS to: {patient['patient_phone_number']}")
        sendMessage(client, filledTemplate, patient['patient_phone_number'])
        messagesSent += 1
        print(f"✓ SMS sent successfully")
        
        # Send email if email exists
        if not pd.isna(patient['patient_email']) and patient['patient_email'] != '':
            salesperson_email = None
            if not pd.isna(patient['salesperson_email']) and patient['salesperson_email'] != '':
                salesperson_email = patient['salesperson_email']
                print(f"Sending email to: {patient['patient_email']} (CC: {salesperson_email})")
            else:
                print(f"Sending email to: {patient['patient_email']} (no CC)")
            
            sendEmail(filledTemplate, patient['patient_email'], patient['patient_first_name'], salesperson_email)
            emailsSent += 1
            print(f"✓ Email sent successfully")
        else:
            print(f"⊗ No email address available")
    
    print("\n=== Summary ===")
    print(f"Total patients processed: {len(patientsToText)}")
    print(f"Messages sent: {messagesSent}")
    print(f"Emails sent: {emailsSent}")
    print(f"Patients skipped: {skippedCount}")
    
    summaryMessage = f"Sent {messagesSent} text messages and {emailsSent} emails today"
    print(f"\nSending summary to 4704495817: {summaryMessage}")
    sendMessage(client, summaryMessage, "4704495817")
    
    dbCursor.close()
    dbConnection.close()
    print("\n=== Script Complete ===")


if __name__ == "__main__":
    main()