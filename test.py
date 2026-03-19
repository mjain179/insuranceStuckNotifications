# from db_tools import *
# from config import *
# import dotenv
# import os
# import json
# from twilio.rest import Client
# import smtplib
# from email.mime.text import MIMEText
# from email.mime.multipart import MIMEMultipart
# import psycopg2
# import pandas as pd
# from datetime import datetime, timezone

# dotenv.load_dotenv()
# TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
# TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
# TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')

# def createConnection():
#     params = game_db_config()
#     gameDbConn = psycopg2.connect(**params)
#     gameDbCur = gameDbConn.cursor()
#     return gameDbConn, gameDbCur

# def get_mail_credentials():
#     with open('mail_credentials.json') as json_file:
#         data = json.load(json_file)
#         return data['email'], data['password']

# def convertToUtc(ts):
#     if ts is None or (isinstance(ts, float) and pd.isna(ts)):
#         return None
#     t = pd.Timestamp(ts)
#     if t.tzinfo is None or t.tz is None:
#         return t.tz_localize('UTC')
#     return t.tz_convert('UTC')

# # def calculatePatientDurationInPipeline(patient, dbCursor):
# #     durationInDays = -1
# #     if pd.isna(patient['age_id']):
# #         nowUtc = pd.Timestamp.now(tz='UTC')
# #         convertedCreatedAt = convertToUtc(patient['created_at'])
# #         differenceInTimes = nowUtc - convertedCreatedAt
# #         durationInDays = differenceInTimes.days
# #         if durationInDays == 0:
# #             return -1
# #     else:
# #         patientBeginTime = getStatusBeginTime(patient['age_id'], dbCursor)
# #         nowUtc = datetime.now(timezone.utc)
# #         differenceInTimes = nowUtc - patientBeginTime
# #         durationInDays = differenceInTimes.days
# #         if durationInDays == 0:
# #             return -1
# #     return durationInDays

# def calculatePatientDurationInPipeline(patient, dbCursor):
#     return 10

# def fillTemplate(template, patient):
#     product = ''
#     if patient['product'] == None or pd.isna(patient['product']):
#         product = "Motus Hand or Foot"
#     elif 'hand' in patient['product'].lower():
#         product = "Motus Hand"
#     else:
#         product = "Motus Foot"
    
#     doctor_first_name = ''
#     if pd.isna(patient['doctor_first_name']) or patient['doctor_first_name'] == "#NA" or patient['doctor_first_name'] == '':
#         doctor_first_name = patient['doctor_last_name'] if not pd.isna(patient['doctor_last_name']) else ''
#     else:
#         doctor_first_name = patient['doctor_first_name']
    
#     dme_first_name = patient['dme_first_name'] if not pd.isna(patient['dme_first_name']) else "our billing partner"
#     patient_first_name = patient['patient_first_name'] if not pd.isna(patient['patient_first_name']) else ''
#     dme_npi = patient['dme_npi'] if not pd.isna(patient['dme_npi']) else ''
#     patient_insurance_id = patient['story_id'] if not pd.isna(patient['story_id']) else ''
#     denial_letter = patient['denial_letter'] if not pd.isna(patient['denial_letter']) else ''
    
#     return template.format(
#         patient_first_name=patient_first_name,
#         first_name=patient_first_name,
#         product=product,
#         doctor_first_name=doctor_first_name,
#         dme_first_name=dme_first_name,
#         dme_npi=dme_npi,
#         patient_insurance_id=patient_insurance_id,
#         denial_letter=denial_letter
#     )

# def main(test_story_id):
#     dbConnection, dbCursor = createConnection()
    
#     # Modified query to only get the test patient
#     tableQuery = f'''
#         SELECT
#             s.story_id,
#             c.contact_id,
#             s.age_id,
#             ins.created_at,
#             s.status,
#             i.product,
#             c.first_name AS patient_first_name,
#             c.phone_number AS patient_phone_number,
#             c.email AS patient_email,
#             c.subtype AS patient_subtype,
#             c2.first_name AS doctor_first_name,
#             c2.last_name AS doctor_last_name,
#             c3.first_name AS dme_first_name,
#             c3.npi AS dme_npi,
#             i.denial_letter,
#             c5.email AS salesperson_email
#         FROM story_fresh AS s
#         LEFT JOIN contacts_fresh AS c ON c.contact_id = s.destination
#         LEFT JOIN insurance_fresh AS i ON i.insurance_id = s.story_id
#         LEFT JOIN story_fresh AS s2 ON s2.type = 'prescriberFax' AND c.contact_id = s2.destination
#         LEFT JOIN contacts_fresh AS c2 ON s2.origin = c2.contact_id
#         LEFT JOIN contacts_fresh AS c3 ON c3.contact_id = (
#             SELECT origin FROM story_fresh 
#             WHERE story_id = s.story_id AND origin IS NOT NULL
#             ORDER BY created_at DESC LIMIT 1
#         )
#         LEFT JOIN story_fresh AS s3 ON s3.type = 'clinicPatient' AND s3.destination = c.contact_id
#         LEFT JOIN story_fresh AS s4 ON s4.type = 'inservice' AND s4.destination = s3.origin
#         LEFT JOIN contacts_fresh AS c5 ON c5.contact_id = s4.origin
#         LEFT JOIN (
#             SELECT DISTINCT ON (insurance_id) insurance_id, created_at
#             FROM insurance ORDER BY insurance_id, created_at ASC
#         ) ins ON ins.insurance_id = s.story_id
#         WHERE s.story_id = {test_story_id}
#     '''
    
#     dbCursor.execute(tableQuery)
#     columnNames = [desc[0] for desc in dbCursor.description]
#     rows = dbCursor.fetchall()
#     patientsToText = pd.DataFrame(rows, columns=columnNames)
    
#     print("\n=== PATIENT DATA ===")
#     print(patientsToText.to_string())
#     print("\n")
    
#     if len(patientsToText) == 0:
#         print(f"No patient found with story_id = {test_story_id}")
#         dbCursor.close()
#         dbConnection.close()
#         return
    
#     patient = patientsToText.iloc[0]

#     patient['status'] = 'newClaim'
    
#     # Define statuses that require clinicReferral subtype check
#     restricted_statuses = ['notCovered', 'reject', 'rejectAuth']
    
#     # Check if status requires clinicReferral subtype
#     if patient['status'] in restricted_statuses:
#         patient_subtype = patient['patient_subtype'] if not pd.isna(patient['patient_subtype']) else ''
#         if patient_subtype != 'clinicReferral':
#             print(f"\n⊗ STOPPING - Status '{patient['status']}' requires clinicReferral subtype")
#             print(f"Current subtype: {patient_subtype}")
#             print("Patient does not meet criteria for this notification.")
#             dbCursor.close()
#             dbConnection.close()
#             return
#         else:
#             print(f"\n✓ Patient has clinicReferral subtype - proceeding with {patient['status']} notification")
    
#     # Check opt-out status
#     optedOut = hasPatientOptedOut(patient['contact_id'], dbCursor)
#     print(f"Opted out status: {optedOut}")
    
#     if optedOut != None:
#         print("Patient has opted out. Exiting.")
#         dbCursor.close()
#         dbConnection.close()
#         return
    
#     # Calculate duration and get template
#     patientDuration = calculatePatientDurationInPipeline(patient, dbCursor)
#     print(f"Patient duration in pipeline: {patientDuration} days")
    
#     templateName = patient['status'] + '_' + str(patientDuration)
#     print(f"Template name: {templateName}")
    
#     template = getTemplateFromDb(templateName, dbCursor)
    
#     if template == None:
#         print(f"No template found for: {templateName}")
#         dbCursor.close()
#         dbConnection.close()
#         return
    
#     print(f"\n=== TEMPLATE ===")
#     print(template)
    
#     filledTemplate = fillTemplate(template, patient)
#     print(f"\n=== FILLED TEMPLATE ===")
#     print(filledTemplate)
    
#     # Ask for confirmation before sending
#     print("\n=== READY TO SEND ===")
#     print(f"SMS to: {patient['patient_phone_number']}")
#     print(f"Email to: {patient['patient_email']}")
#     if not pd.isna(patient['salesperson_email']) and patient['salesperson_email'] != '':
#         print(f"CC to: {patient['salesperson_email']}")
    
#     confirm = input("\nDo you want to send? (yes/no): ")
    
#     if confirm.lower() == 'yes':
#         # Send SMS
#         client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
#         try:
#             message = client.messages.create(
#                 body=filledTemplate, 
#                 from_=TWILIO_PHONE_NUMBER,
#                 to=patient['patient_phone_number']
#             )
#             print(f"✓ SMS sent successfully. SID: {message.sid}")
#         except Exception as e:
#             print(f"✗ Failed to send SMS: {e}")
        
#         # Send Email
#         if not pd.isna(patient['patient_email']) and patient['patient_email'] != '':
#             try:
#                 # Get mail credentials
#                 email_user, email_password = get_mail_credentials()
                
#                 # Create message
#                 msg = MIMEMultipart()
#                 msg['From'] = 'service@motusnova.com'
#                 msg['To'] = patient['patient_email']
#                 msg['Subject'] = 'Insurance Claim Update from Motus Nova'
                
#                 # Add CC if salesperson email exists
#                 if not pd.isna(patient['salesperson_email']) and patient['salesperson_email'] != '':
#                     msg['Cc'] = patient['salesperson_email']
                
#                 # Convert text message to HTML format (preserve line breaks)
#                 html_content = filledTemplate.replace('\n', '<br>')
                
#                 # Attach HTML body
#                 msg.attach(MIMEText(html_content, 'html'))
                
#                 # Create SMTP session
#                 server = smtplib.SMTP('smtp.gmail.com', 587)
#                 server.starttls()
#                 server.login(email_user, email_password)
                
#                 # Send email
#                 recipients = [patient['patient_email']]
#                 if not pd.isna(patient['salesperson_email']) and patient['salesperson_email'] != '':
#                     recipients.append(patient['salesperson_email'])
                
#                 server.send_message(msg)
#                 server.quit()
                
#                 print(f"✓ Email sent successfully to {patient['patient_email']}")
                
#             except Exception as e:
#                 print(f"✗ Failed to send email: {e}")
#         else:
#             print("No email address available for patient")
#     else:
#         print("Send cancelled")
    
#     dbCursor.close()
#     dbConnection.close()

# if __name__ == "__main__":
#     main(130355)


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
    with open('../mail_credentials.json') as json_file:
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
        # Get the latest created_at from story table for this insurance record
        latest_insurance_update = getLatestInsuranceUpdate(patient['story_id'], dbCursor)
        
        if latest_insurance_update is not None:
            nowUtc = datetime.now(timezone.utc)
            
            # Convert to UTC if needed
            if latest_insurance_update.tzinfo is None:
                latest_insurance_update = latest_insurance_update.replace(tzinfo=timezone.utc)
            
            differenceInTimes = nowUtc - latest_insurance_update
            durationInDays = differenceInTimes.days
            if durationInDays == 0:
                return -1
        else:
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

def sendEmail(filledTemplate, patientEmail, patientFirstName, patient_data, salespersonEmail=None, use_html_file=False):
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
        
        # Use HTML file or convert text to HTML
        if use_html_file:
            with open('rejectEmailTemplate.html', 'r') as f:
                html_content = f.read()
            # Extract product from patient_data
            product = ''
            if patient_data['product'] == None or pd.isna(patient_data['product']):
                product = "Motus Hand or Foot"
            elif 'hand' in patient_data['product'].lower():
                product = "Motus Hand"
            else:
                product = "Motus Foot"
            
            # Fill the product placeholder
            html_content = html_content.replace('{product}', product)
        else:
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
    # TEST MODE CONFIGURATION
    # Set TEST_PATIENT_ID to a specific story_id to test only that patient
    # Set to None to process all patients (production mode)
    TEST_PATIENT_ID = 12345  # Replace with actual story_id to test, or set to None for production
    
    print("=== Starting Insurance Reminder Script ===")
    if TEST_PATIENT_ID is not None:
        print(f"*** TEST MODE: Only processing patient with story_id = {TEST_PATIENT_ID} ***\n")
    
    dbConnection, dbCursor = createConnection()
    
    print("Fetching patients from database...")
    patientsToText = getAllPatientsToText(dbCursor)
    print(f"Found {len(patientsToText)} patients in database\n")
    
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    messagesSent = 0
    emailsSent = 0
    skippedCount = 0
    readyMessages = pd.DataFrame()
    
    # Define statuses that require clinicReferral subtype check
    restricted_statuses = ['notCovered', 'reject', 'rejectAuth']
    
    for index, patient in patientsToText.iterrows():
        # TEST MODE FILTER: Only process the test patient
        if TEST_PATIENT_ID is not None:
            if patient['story_id'] != TEST_PATIENT_ID:
                continue
            else:
                print(f"*** Found test patient with story_id = {TEST_PATIENT_ID} ***\n")
        
        print(f"\n--- Processing Patient {index + 1}/{len(patientsToText)} ---")
        print(f"Insurance ID: {patient['story_id']}, Contact ID: {patient['contact_id']}, Status: {patient['status']}")
        
        # Check for required fields
        if pd.isna(patient['patient_first_name']) or pd.isna(patient['patient_phone_number']) or pd.isna(patient['contact_id']):
            print(f"⊗ Skipping - Missing required data (name/phone/contact_id)")
            skippedCount += 1
            continue

        # Skip all delivery_ticket statuses
        if 'deliveryTicket' in patient['status']:
            print(f"Skipping - delivery_ticket status (no notifications sent for this status)")
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
            
            # Use HTML template for restricted statuses
            use_html_template = patient['status'] in restricted_statuses
            if use_html_template:
                print(f"Using HTML template (rejectEmailTemplate.html) for status: {patient['status']}")
            
            sendEmail(filledTemplate, patient['patient_email'], patient['patient_first_name'], patient, salesperson_email, use_html_template)
            emailsSent += 1
            print(f"✓ Email sent successfully")
        else:
            print(f"⊗ No email address available")
    
    print("\n=== Summary ===")
    if TEST_PATIENT_ID is not None:
        print(f"TEST MODE: Processed only patient with story_id = {TEST_PATIENT_ID}")
    print(f"Total patients in database: {len(patientsToText)}")
    print(f"Messages sent: {messagesSent}")
    print(f"Emails sent: {emailsSent}")
    print(f"Patients skipped: {skippedCount}")
    
    # Only send summary message in production mode
    if TEST_PATIENT_ID is None:
        summaryMessage = f"Sent {messagesSent} text messages and {emailsSent} emails today"
        print(f"\nSending summary to 4704495817: {summaryMessage}")
        sendMessage(client, summaryMessage, "4704495817")
    else:
        print("\n*** TEST MODE: Skipping summary message to 4704495817 ***")
    
    dbCursor.close()
    dbConnection.close()
    print("\n=== Script Complete ===")


if __name__ == "__main__":
    main()