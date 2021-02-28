# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

#  Lambda for IAM Rightsizing with CloudKnox and AWS Config
#  - Creates new IAM Policy and detaches existing policies for IAM user
#  - New IAM Policy created based on policy data retrieved from CloudKnox JEP Controller 


# @kmmahaj


import json
import sys
import datetime
import boto3
import botocore
import datetime
import time
import random
from botocore.exceptions import ClientError

try:
    import liblogging
except ImportError:
    pass

import http.client
import mimetypes
import ssl

## AWS Secrets Manager - retrieve secretstring
def get_secret_value(key='CloudKnoxSecretString'):
          secretsmanager = boto3.client('secretsmanager')
          secret_list = secretsmanager.list_secrets()['SecretList']
          output = {}
          for s in secret_list:
              if key in s.values():
                  output = secretsmanager.get_secret_value(SecretId=key)['SecretString']
          return(output)


##  Identity Usage CloudKnox API - Retrieve PCI score:
def getCloudKnoxRemediationPolicy(apiId, accessToken, serviceId, timestamp, url, accountId, userarn, port):
    conn = http.client.HTTPSConnection(url, port)
    content_type = "application/json"
    print('apiId: '+ apiId )
    print('accessToken: '+ accessToken )
    print('serviceId: '+ serviceId )
    print('timestamp: '+ timestamp )
    print('url: ' + url)
    print('accountId: ' + accountId)
    print('userarn: ' + userarn)
    
    headers = {
      'X-CloudKnox-Access-Token': accessToken,
      'X-CloudKnox-API-Id': apiId,
      'X-CloudKnox-Service-Account-Id': serviceId,
      'X-CloudKnox-Timestamp-Millis': timestamp,
      'Content-Type': content_type
    }
    
    endTime = int(round(time.time() * 1000))
    startTime = endTime - (90*86400*1000)
    
    cloudknoxDict = {}
    cloudknoxDict['authSystemInfo'] = {'id': accountId,
                                        'type': 'AWS'}
    cloudknoxDict['identityType'] = 'USER'
    cloudknoxDict['identityIds'] = [userarn]
    cloudknoxDict['aggregation'] = {'type': 'SUMMARY'}
    cloudknoxDict['requestParams'] = {"scope": None,
                                "resource": None,
                                "resources": None,
                                "condition": None
                            }
    cloudknoxDict['filter'] = {'historyDays': 90,
                                'preserveReads': True,
                                 "historyDuration": {
                                    "startTime": startTime,
                                    "endTime": endTime
                                }
                             }
    payload = json.dumps(cloudknoxDict)

    print('payload: ' + payload)
    
    conn.request("POST", "/api/v2/role-policy/new", payload, headers)
    res = conn.getresponse()
    data = res.read()
    data_raw = data.decode()
    print('data_raw: ' + data_raw)
    dataResponse = json.loads(data.decode("utf-8"))
    default_policy = {
    'Version': '2012-10-17',
    'Statement': [{
        'Sid': 'AllowIAM',
        'Effect': 'Allow',
        'Action': ['iam:CreateRole'],
        'Resource': '*'
    }]
    }
    #defaultpolicyDict = eval(default_policy)

    if (len(dataResponse['data'])==0):
    #    policyText = '{\n  "Version" : "2008-10-17",\n  "Statement" : [ {\n    "Sid" : "Allow IAM",\n    "Effect" : "Allow",\n "Action" : [ "iam:CreateRole" ],\\n "Resource" : [ "*" ]\n } ]\n}'
       
        policyData ={}
        policyData['policyName'] = "ck_activity_test"
        policyData['policy'] = default_policy
        print("inside data length 0")
        dataList = [{}] * 1
        dataList[0] = policyData
        return dataList
    if dataResponse.get('errorCode'):
    #    policyText = '{\n  "Version" : "2008-10-17",\n  "Statement" : [ {\n    "Sid" : "Allow IAM",\n    "Effect" : "Allow",\n    "Resource" : "*",\n "Action" : [ "iam:CreateRole" ]\n } ]\n}'
        policyData ={}
        policyData['policyName'] = "ck_activity_test"
        policyData['policy'] = default_policy
        print("inside error code")
        dataList = [{}] * 1
        dataList[0] = policyData
        return dataList
        
    print('dataResponse_policy: ' + dataResponse['data'][0]['policyName'])
    return dataResponse['data']

## Authenticate CloudKnox API - Retrieve accessToken:
def getAccessToken(serviceId,timestamp,accessKey,secretKey,url,port):
    conn = http.client.HTTPSConnection(url, port)
    content_type = "application/json"
    print('serviceId-accessToken: '+ serviceId )
    print('timestamp-accessToken: '+ timestamp )
    print('accessKey-accessToken: '+ accessKey )
    print('secretKey-accessToken: '+ secretKey )
    print('url-accessToken: ' + url)

    headers = {
      'X-CloudKnox-Service-Account-Id': serviceId,
      'X-CloudKnox-Timestamp-Millis': timestamp,
      'Content-Type': content_type
    }

    cloudknoxDict = {}
    cloudknoxDict['serviceAccountId'] = serviceId
    cloudknoxDict['accessKey'] = accessKey
    cloudknoxDict['secretKey'] = secretKey

    payload = json.dumps(cloudknoxDict)
    print('payload-accessToken: ' + payload)
    
    conn.request("POST", "/api/v2/service-account/authenticate", payload, headers)
    res = conn.getresponse()
    data = res.read()
    data_raw = data.decode()
    print('data_raw: ' + data_raw)
    dataResponse = json.loads(data.decode("utf-8"))
    print('accessToken: ' + dataResponse['accessToken'])
    return dataResponse['accessToken']

def lambda_handler(event, context):
    
    ## CloudKnox Details in Secrets Manager
    secretList = json.loads(get_secret_value('CloudKnoxSecretString'))
    serviceId=""
    apiId=""
    accessKey=""
    secretKey=""
    accessToken=""
    accountId=""
    url=""
    
    serviceId_key='serviceId'
    apiId_key='apiId'
    accessKey_key='accessKey'
    secretKey_key='secretKey'
    accountId_key= 'accountId'
    url_key='url'
    
    # userarn = event['userarn']
    #userarn = event['parameterValue']
    #userarn_1 = userarn.split(':')[-1] 
    #username = userarn_1.replace("user/","")

    config = boto3.client('config')
    resourceid = event['parameterValue']
    response = config.list_discovered_resources(
        resourceType='AWS::IAM::User',
        resourceIds=[
            resourceid
        ]
    )
    username = response['resourceIdentifiers'][0]['resourceName']
    print('config user resourceid: ' + resourceid)
    print('username: ' + username)

      
    if serviceId_key in secretList:
        serviceId = secretList[serviceId_key]
    if apiId_key in secretList:
        apiId = secretList[apiId_key]
    if accessKey_key in secretList:
        accessKey = secretList[accessKey_key]
    if secretKey_key in secretList:
        secretKey = secretList[secretKey_key]
    if accountId_key in secretList:
        accountId = secretList[accountId_key]
    if url_key in secretList:
        url = secretList[url_key]

    millis = int(round(time.time() * 1000))
    timestamp = str(millis)
    
    userarn = 'arn:aws:iam::' + accountId +':user/' + username

    accessToken = getAccessToken(serviceId,timestamp,accessKey,secretKey,url,443)
    print('accessToken is: ' + accessToken)
    iampolicy = getCloudKnoxRemediationPolicy(apiId, accessToken, serviceId, timestamp, url, accountId, userarn, 443)
    
    iamClient = boto3.client('iam')
    iampolicydict={}
    count = 0
    for policy in iampolicy:
        count = count + 1
        cloudknoxiampolicy = policy['policy']
        iampolicydict['Version'] = cloudknoxiampolicy['Version']
        iampolicydict['Statement'] = cloudknoxiampolicy['Statement'][:3]
        
        PolicyDocument = json.dumps(iampolicydict)
        print('PolicyDocument: ' + PolicyDocument)
        
        PolicyName = 'CloudKnoxRemediationPolicy-' + username + '-' +   str(random.randint(1,21)*5)
        print('To be attached PolicyName: ' + PolicyName)
        
        response_attachedpolicies = iamClient.list_attached_user_policies(
                                        UserName=username,
                                    )
        if len(response_attachedpolicies['AttachedPolicies'])>0:
            for attachedpolicy in response_attachedpolicies['AttachedPolicies']:
                policyarn = attachedpolicy['PolicyArn']
                print('AttachedPolicyArn to be detached: ' + policyarn)
                response_detach = iamClient.detach_user_policy(
                                    UserName=username,
                                    PolicyArn=policyarn
                )
         

        response_group = iamClient.list_groups_for_user(
                        UserName=username,
        )
        print('Grouplength: ' + str(len(response_group['Groups'])))
        
        if len(response_group['Groups'])>0:
            for group in response_group['Groups']:
                groupname = group['GroupName']
                print('GroupName: ' + groupname)
                response = iamClient.remove_user_from_group(
                        GroupName=groupname,
                        UserName=username
                )
        
        iampolicylist = iamClient.list_policies(
                            Scope='All',
                            OnlyAttached=False
                        )

        if len(iampolicylist['Policies'])>0:
            for iampolicy in iampolicylist['Policies']:
                if (iampolicy['PolicyName'] == PolicyName):
                    print('Policy already exists: ' + iampolicy['PolicyName'])
                    response_delete = iamClient.delete_policy(
                                         PolicyArn=iampolicy['Arn']
                                       )
        
        print('Create new managed policy: ' + PolicyName) 
        response_create = iamClient.create_policy(
                                PolicyName=PolicyName,
                                PolicyDocument=PolicyDocument
                           )
        PolicyArn = response_create['Policy']['Arn']
        print('Attach new managed policy: ' + PolicyArn)
        response = iamClient.attach_user_policy(
                            UserName=username,
                            PolicyArn=PolicyArn
                    )
                
        
    return 

