import os
import boto3
from botocore.exceptions import ClientError
import email
from email import policy
from email.parser import BytesParser
import re

s3 = boto3.client('s3')
ses = boto3.client('ses')

bucket_name = os.environ['BUCKET_NAME']
forward_to_address = os.environ['FORWARD_TO_ADDRESS']
domain = os.environ['DOMAIN']

def lambda_handler(event, context):
  print(event)
  # Extract the message ID and receipient from the SES event
  message_id = event['Records'][0]['ses']['mail']['messageId']
  original_recipient = event['Records'][0]['ses']['mail']['destination'][0]

  # Retrieve the raw email object from S3 using the prefix + message ID
  object_key = (original_recipient + "/" + message_id)
  get_object_response = s3.get_object(Bucket=bucket_name, Key=object_key)
  raw_email = get_object_response['Body'].read()

  # Parse the email to extract the original sender and subject
  mail = BytesParser(policy=policy.default).parsebytes(raw_email)
  original_sender = mail['From']
  original_subject = mail['Subject']
  
  # get 'friendly name' from sender address
  # this is a hack but it's to myself and I consent so..
  if re.search(r'<[^>]*>', original_sender):
    # Remove '<*>'
    friendly_name = re.sub(r'<[^>]*>', '', original_sender).strip()
  else:
    # Return empty string if there's no 'friendly name'
    friendly_name = ''

  # Create a noreply address under the verified domain
  if friendly_name:
    noreply_address = f"{friendly_name} <noreply@{domain}>"
  else:
    noreply_address = f"noreply@{domain}"

  # Replace original sender and return-path with the noreply address
  mail.replace_header('From', noreply_address)
  mail.replace_header('Return-Path', f"noreply@{domain}")

  # Add/replace header for replies to original sender
  if mail.get('Reply-To'):
    mail.replace_header('Reply-To', original_sender)
  else:
    mail.add_header('Reply-To', original_sender)
  
  # To prevent "Duplicate header 'DKIM-Signature'" error
  for header in list(mail.keys()):
    if header == "DKIM-Signature" and "amazonses.com" in mail[header]:
      del mail[header]

  # Forward the email using SES, keeping its original content
  try:
    send_raw_email_response = ses.send_raw_email(
      Source=original_recipient,  # Your verified SES sender email
      Destinations=[forward_to_address],  # Forwarding recipient(s)
      RawMessage={'Data': mail.as_bytes()}
    )
    print(send_raw_email_response)
  except ClientError as error:
    print(error.response)