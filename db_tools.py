import pandas as pd

def getAllPatientsToText(dbCursor):
    tableQuery = '''
        SELECT
            s.story_id,
            c.contact_id,
            s.age_id,
            ins.created_at,
            s.status,
            i.product,
            c.first_name AS patient_first_name,
            c.phone_number AS patient_phone_number,
            c.email AS patient_email,
            c.subtype AS patient_subtype,
            c2.first_name AS doctor_first_name,
            c2.last_name AS doctor_last_name,
            c3.first_name AS dme_first_name,
            c3.npi AS dme_npi,
            i.denial_letter,
            c5.email AS salesperson_email
        FROM story_fresh AS s
        LEFT JOIN contacts_fresh AS c
        ON c.contact_id = s.destination
        LEFT JOIN insurance_fresh AS i
        ON i.insurance_id = s.story_id
        LEFT JOIN story_fresh AS s2 
        ON s2.type = 'prescriberFax' 
            AND c.contact_id = s2.destination
        LEFT JOIN contacts_fresh AS c2 
        ON s2.origin = c2.contact_id
        LEFT JOIN contacts_fresh AS c3 
        ON c3.contact_id = (
            SELECT origin 
            FROM story_fresh 
            WHERE story_id = s.story_id 
                AND origin IS NOT NULL
            ORDER BY created_at DESC
            LIMIT 1
        )
        LEFT JOIN story_fresh AS s3
        ON s3.type = 'clinicPatient'
            AND s3.destination = c.contact_id
        LEFT JOIN story_fresh AS s4
        ON s4.type = 'inservice'
            AND s4.destination = s3.origin
        LEFT JOIN contacts_fresh AS c5
        ON c5.contact_id = s4.origin
        LEFT JOIN (
            SELECT DISTINCT ON (insurance_id)
                insurance_id, created_at
            FROM insurance
            ORDER BY insurance_id, created_at ASC
        ) ins
        ON ins.insurance_id = s.story_id
        WHERE s.type = 'insurance'
        AND s.status IN (
            'needPrescriptionOnly',
            'needPrescriptionAndMedicalRecords',
            'needMedicalRecordsOnly',
            'appeal',
            'submitted',
            'auth',
            'insufficientDiagnosis',
            'insufficientRecords',
            'insuranceVerification',
            'pcpReferral',
            'newClaim',
            'readyToBill',
            'requestedInfoAdded',
            'deliveryTicket',
            'info',
            'insuranceCard',
            'insuranceTerminated',
            'missingPatientInfo',
            'missingProductInfo',
            'needDoctor',
            'needDME',
            'EOB',
            'notCovered',
            'reject',
            'rejectAuth',
            'returned'
        );
    '''
    dbCursor.execute(tableQuery)
    columnNames = [desc[0] for desc in dbCursor.description]
    rows = dbCursor.fetchall()
    df = pd.DataFrame(rows, columns=columnNames)
    return df

def getStatusBeginTime(ageId, dbCursor):
    # Convert numpy types to Python native types
    if pd.notna(ageId):
        ageId = int(ageId)
        
    tableQuery = '''
        SELECT
            a.begin_time
        FROM age_table AS a
        WHERE a.age_id = %s
    '''
    dbCursor.execute(tableQuery, (ageId, ))
    beginTime = dbCursor.fetchall()
    return beginTime[0][0]

def hasPatientOptedOut(patientContactId, dbCursor):
    # Convert numpy types to Python native types
    if pd.notna(patientContactId):
        patientContactId = int(patientContactId)
    
    tableQuery = '''
        SELECT
            s.status
        FROM story_fresh AS s
        WHERE s.destination = %s
            AND s.type = 'insuranceTextingOptout'
    '''
    dbCursor.execute(tableQuery, (patientContactId, ))
    status = dbCursor.fetchall()
    if len(status) == 0:
        return None
    else:
        return status[0][0]

def getTemplateFromDb(templateName, dbCursor):
    tableQuery = '''
        SELECT
            scc.text_message
        FROM status_change_communication AS scc
        WHERE scc.status = %s 
            AND scc.story_type = 'insurance'
    '''
    dbCursor.execute(tableQuery, (templateName, ))
    template = dbCursor.fetchall()
    if len(template) == 0:
        return None
    else:
        return template[0][0]