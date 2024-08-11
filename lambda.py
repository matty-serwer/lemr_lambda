import json
import boto3
from botocore.exceptions import ClientError
from datetime import datetime
import urllib.parse
import uuid

dynamodb = boto3.resource('dynamodb', region_name="us-east-1")
table = dynamodb.Table('PatientsTable')


def lambda_handler(event, context):
    print('Request event: ', json.dumps(event))  # Log the entire event object
    try:
        resource = event.get('resource', 'UNKNOWN')
        method = event.get('httpMethod', 'UNKNOWN')

        if resource == 'UNKNOWN' or method == 'UNKNOWN':
            return response_with_cors(400, 'Invalid request. Resource or method not found.')

        if resource == '/patients' and method == 'POST':
            return create_patient(event)
        elif resource == '/patients/{id}' and method == 'GET':
            return get_patient(event)
        elif resource == '/patients/{id}' and method == 'PUT':
            return update_patient(event)
        elif resource == '/patients/{id}' and method == 'DELETE':
            return delete_patient(event)
        elif resource == '/patients/{id}/notes' and method == 'POST':
            return add_note_to_patient(event)
        elif resource == '/patients/{id}/notes' and method == 'GET':
            return get_all_notes_for_patient(event)
        elif resource == '/patients/{id}/notes/{noteId}' and method == 'GET':
            return get_note(event)
        elif resource == '/patients/{id}/notes/{noteId}' and method == 'PUT':
            return update_note(event)
        elif resource == '/patients/{id}/notes/{noteId}' and method == 'DELETE':
            return delete_note(event)
        else:
            return response_with_cors(405, 'Method Not Allowed')
    except ClientError as e:
        return response_with_cors(500, f'Error: {e.response["Error"]["Message"]}')
    except Exception as e:
        return response_with_cors(500, f'Unexpected error: {str(e)}')


def response_with_cors(status_code, body):
    return {
        'statusCode': status_code,
        'headers': {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Methods': 'GET,POST,PUT,DELETE,OPTIONS',
            'Access-Control-Allow-Headers': 'Content-Type,Authorization',
        },
        'body': json.dumps(body)
    }


def create_patient(event):
    body = json.loads(event['body'])
    patient = {
        'id': body['id'],
        'type': 'Patient',  # Ensure 'type' is set to 'Patient'
        'name': body['name'],
        'email': body['email'],
        'dateOfBirth': body['dateOfBirth'],
        'bloodType': body['bloodType'],
        'allergies': body['allergies'],
        'medicalHistory': body['medicalHistory'],
        'emergencyContacts': body['emergencyContacts'],
        'currentMedications': body['currentMedications'],
        'createdAt': datetime.now().isoformat(),
        'updatedAt': datetime.now().isoformat(),
        'notes': []
    }

    table.put_item(Item=patient)

    return response_with_cors(201, patient)


def get_patient(event):
    patient_id = urllib.parse.unquote(event['pathParameters']['id'])

    response = table.get_item(
        Key={
            'id': patient_id,
            'type': 'Patient'
        }
    )

    if 'Item' in response:
        return response_with_cors(200, response['Item'])
    else:
        return response_with_cors(404, 'Patient not found')


def update_patient(event):
    patient_id = urllib.parse.unquote(event['pathParameters']['id'])
    body = json.loads(event['body'])

    update_expression = "SET "
    expression_attribute_values = {}

    for key, value in body.items():
        update_expression += f"{key} = :{key}, "
        expression_attribute_values[f":{key}"] = value

    update_expression += "updatedAt = :updatedAt"
    expression_attribute_values[":updatedAt"] = datetime.now().isoformat()

    response = table.update_item(
        Key={
            'id': patient_id,
            'type': 'Patient'
        },
        UpdateExpression=update_expression,
        ExpressionAttributeValues=expression_attribute_values,
        ReturnValues="ALL_NEW"
    )

    return response_with_cors(200, response['Attributes'])


def delete_patient(event):
    patient_id = urllib.parse.unquote(event['pathParameters']['id'])

    table.delete_item(
        Key={
            'id': patient_id,
            'type': 'Patient'
        }
    )

    return response_with_cors(204, None)


def add_note_to_patient(event):
    patient_id = urllib.parse.unquote(event['pathParameters']['id'])
    body = json.loads(event['body'])

    # Generate a unique ID for the note if not provided
    note_id = body.get('id', f"Note#{uuid.uuid4()}")

    # Validate required fields
    if 'author' not in body or 'content' not in body:
        return response_with_cors(400, 'Missing required fields: author and content are required.')

    # Ensure content is a list of strings, with at least one string
    content_list = [body['content']] if isinstance(body['content'], str) else body['content']

    note = {
        'id': note_id,
        'patientId': patient_id,
        'author': body['author'],
        'createdAt': datetime.now().isoformat(),
        'updatedAt': datetime.now().isoformat(),
        'type': 'Note',
        'content': content_list  # Ensure content is a list of strings
    }

    try:
        response = table.update_item(
            Key={'id': patient_id, 'type': 'Patient'},
            UpdateExpression="SET notes = list_append(if_not_exists(notes, :empty_list), :note)",
            ExpressionAttributeValues={
                ':note': [note],
                ':empty_list': []
            },
            ReturnValues="ALL_NEW"
        )
        return response_with_cors(201, response['Attributes'])
    except ClientError as e:
        return response_with_cors(500, f"Error adding note: {e.response['Error']['Message']}")


def get_all_notes_for_patient(event):
    patient_id = urllib.parse.unquote(event['pathParameters']['id'])

    response = table.get_item(Key={'id': patient_id, 'type': 'Patient'})

    if 'Item' in response and 'notes' in response['Item']:
        return response_with_cors(200, response['Item']['notes'])
    else:
        return response_with_cors(404, 'No notes found for this patient')


def get_note(event):
    patient_id = urllib.parse.unquote(event['pathParameters']['id'])
    note_id = urllib.parse.unquote(event['pathParameters']['noteId'])

    response = table.get_item(Key={'id': patient_id, 'type': 'Patient'})

    if 'Item' not in response or 'notes' not in response['Item']:
        return response_with_cors(404, 'Note not found')

    notes = response['Item']['notes']
    note = next((note for note in notes if note['id'] == note_id), None)

    if not note:
        return response_with_cors(404, 'Note not found')

    return response_with_cors(200, note)


def update_note(event):
    patient_id = urllib.parse.unquote(event['pathParameters']['id'])
    note_id = urllib.parse.unquote(event['pathParameters']['noteId'])
    body = json.loads(event['body'])

    response = table.get_item(Key={'id': patient_id, 'type': 'Patient'})

    if 'Item' not in response or 'notes' not in response['Item']:
        return response_with_cors(404, 'Note not found')

    notes = response['Item']['notes']
    note_index = next((i for i, note in enumerate(notes) if note['id'] == note_id), None)

    if note_index is None:
        return response_with_cors(404, 'Note not found')

    for key, value in body.items():
        notes[note_index][key] = value

    notes[note_index]['updatedAt'] = datetime.now().isoformat()

    response = table.update_item(
        Key={'id': patient_id, 'type': 'Patient'},
        UpdateExpression="SET notes = :notes",
        ExpressionAttributeValues={
            ':notes': notes
        },
        ReturnValues="ALL_NEW"
    )

    return response_with_cors(200, response['Attributes'])


def delete_note(event):
    patient_id = urllib.parse.unquote(event['pathParameters']['id'])
    note_id = urllib.parse.unquote(event['pathParameters']['noteId'])

    response = table.get_item(Key={'id': patient_id, 'type': 'Patient'})

    if 'Item' not in response or 'notes' not in response['Item']:
        return response_with_cors(404, 'Note not found')

    notes = response['Item']['notes']
    new_notes = [note for note in notes if note['id'] != note_id]

    table.update_item(
        Key={'id': patient_id, 'type': 'Patient'},
        UpdateExpression="SET notes = :notes",
        ExpressionAttributeValues={
            ':notes': new_notes
        }
    )

    return response_with_cors(204, None)
