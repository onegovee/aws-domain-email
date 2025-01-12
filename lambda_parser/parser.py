import json
import boto3
import botocore
import email
from email.header import decode_header

ses = boto3.client('ses')

def lambda_handler(event, context):
  print(event)

  records = event['Records']
  for record in records:
    message = record['Sns']['Message']
    print(message)
    json_msg = json.loads(message)
    content = json_msg['content']
    print(content)

    parsed_msg = email.message_from_string(content)

    try:
      if parsed_msg.is_multipart():
        for part in parsed_msg.walk():
          content_type = part.get_content_type()
          if content_type == 'text/plain':
            decoded_msg = decode_email_body(part)
            print(decoded_msg)
      else:
        decoded_msg = decode_email_body(parsed_msg)
        print(decoded_msg)
    except botocore.exceptions.ClientError as error:
      raise error

def decode_email_body(part):
  charset = part.get_content_charset()
  payload = part.get_payload(decode=True)
  decoded_msg = payload.decode(charset or 'utf-8', 'replace')
  return decoded_msg