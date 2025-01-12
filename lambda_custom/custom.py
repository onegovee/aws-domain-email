import boto3
import cfnresponse
import logging

def lambda_handler(event, context):
  log = logging.getLogger()
  #log.setLevel(logging.INFO)
  print(event)
  
  try:
    ses = boto3.client('ses')
    ResourceType = event['ResourceType']
    RequestType = event['RequestType']
    responseData = {}
    records = []

    if ResourceType == "Custom::InvokeCustomLambda":
      ZoneName = event['ResourceProperties']['ZoneName']

      # Changes to custom resource properties will cause cfn to create a new resource and delete the old one
      # This means CREATE and UPDATE events are effectively the same
      if RequestType in {"Create", "Update"}:
        print("Got CREATE/UPDATE request for " + ZoneName)

        # Create DKIM tokens for identity verification
        # Creating DKIM tokens also creates the identity
        # https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/ses.html#SES.Client.verify_domain_dkim
        dkim = ses.verify_domain_dkim(Domain=ZoneName)
        tokens = dkim['DkimTokens']

        # Create DNS records to complete identity verification
        for DkimTokens in tokens:
          record = {
            "Name": "{dkim_token}._domainkey.{zone_name}".format(dkim_token=DkimTokens,zone_name=ZoneName),
            "Type": "CNAME",
            "TTL": "60",
            "ResourceRecords": [
              "{dkim_token}.dkim.amazonses.com".format(dkim_token=DkimTokens)
            ]
          }
          records.append(record)

        # Send data back to cfn
        responseData['records'] = records
        responseData['message'] = "Created verification identity for " + ZoneName

      # 'ResourceProperties' in DELETE events are the same as 'OldResourceProperties' in UPDATE events
      elif RequestType == "Delete":
        print("Got DELETE request for " + ZoneName)
        ses.delete_identity(Identity=ZoneName)
        print("Deleted identity verification for " + ZoneName)
        # This is here mainly for changes to the identity/ZoneName
        # If a duplicate identity is submitted for verification
        # The identity may be deleted but the DNS records will not
        # And then magically restored even though logging will show it was deleted here

    elif ResourceType == "Custom::SetActiveRuleSet" and RequestType != "Delete":
      RuleSetName = event['ResourceProperties']['RuleSetName']
      print("Setting the following SES rule set as active: " + RuleSetName)
      ses.set_active_receipt_rule_set(RuleSetName=RuleSetName)

    else:
      print("Lambda got RequestType: " + RequestType + " but did nothing")

  # Send FAILED back to cfn for any unexpected error
  except Exception:
    log.exception('Signaling failure to CloudFormation.')
    cfnresponse.send(event, context, cfnresponse.FAILED, {})
  
  else:
    # Always send SUCCESS back to cfn if lambda did what it was supposed to do
    cfnresponse.send(event, context, cfnresponse.SUCCESS, responseData)