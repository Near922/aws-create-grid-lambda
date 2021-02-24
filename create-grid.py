import os
import boto3
import json
import time
import base64
import requests

AMI = os.environ['AMI']
INSTANCE_TYPE = os.environ['INSTANCE_TYPE']
KEY_NAME = os.environ['KEY_NAME']
#SUBNET_ID = os.environ['SUBNET_ID']
REGION = os.environ['REGION']

ec2 = boto3.client('ec2', region_name=REGION)

def lambda_handler(event, context):
    message = event['message']
    max_instances = event['max_instances']
    hub_reservation = ec2.run_instances(
        ImageId=AMI,
        InstanceType=INSTANCE_TYPE,
        KeyName=KEY_NAME,
        #SubnetId=SUBNET_ID,
        MaxCount=1,
        MinCount=1,
        InstanceInitiatedShutdownBehavior='terminate',
        SecurityGroupIds = ["sg-05cb7aa1a36b2b629", "sg-0eaa528f08987cee8"],
        UserData = """<powershell>
        Set-Location c:/drivers
        java -jar selenium-server-standalone-3.141.59.jar -role hub
        </powershell>
        <persist>true</persist>""",
        IamInstanceProfile = {"Name":"SaveVideoS3" }
    )


    
    hub = hub_reservation['Instances'][0]
    hub_id = hub['InstanceId']



    #wait until IP address is available
    public_ip = None
    attempts = 0
    while public_ip == None:
        res = ec2.describe_instances(InstanceIds=[hub_id])
        if 'PublicIpAddress' in  res['Reservations'][0]['Instances'][0]:
            public_ip = res['Reservations'][0]['Instances'][0]['PublicIpAddress']
            hub_ip_address = "http://" + res['Reservations'][0]['Instances'][0]['PublicIpAddress'] + ":4444/grid/register"
        else:
            attempts +=1
            time.sleep(30)
            if attempts > 10:
                raise Exception("Could not get public IP of hub")
    

    node_reservations = ec2.run_instances(
        ImageId=AMI,
        InstanceType=INSTANCE_TYPE,
        KeyName=KEY_NAME,
        #SubnetId=SUBNET_ID,
        MaxCount=max_instances,
        MinCount=max_instances,
        InstanceInitiatedShutdownBehavior='terminate',
        SecurityGroupIds = ["sg-05cb7aa1a36b2b629", "sg-0eaa528f08987cee8"],
        #UserData = f"""<powershell>
        #Set-Location c:/drivers
        #java -jar selenium-server-standalone-3.141.59.jar -role node -hub {hub_ip_address} -port 5555 -nodeConfig \"c:\\drivers\\nodeconfig.json.txt\"
        #</powershell>
        #<persist>true</persist>""",
        IamInstanceProfile = {"Name":"SaveVideoS3" }

    )
    
    #get node instance ids
    node_ids = []
    for instance in node_reservations['Instances']:
        node_ids.append(instance['InstanceId'])
        
    waiter = ec2.get_waiter('instance_status_ok')
    waiter.wait(InstanceIds=[hub_id])
    waiter.wait(InstanceIds=node_ids)
    nodes_descriptions = ec2.describe_instances(InstanceIds=node_ids)
    headers = {'Content-Type' : 'application/json', 'Accept' : 'application/json'}
    body = {'hub_ip_address' : hub_ip_address}
    for instance in node_descriptions['Instances']:
        node_grid_url = "http://" + instance['PublicIpAddress'] + ":3000/startGidNode"
        rquests.post(node_grid_url, body)

            
    response = {}
    response["ip_address"] = public_ip
    response["instance_id"] = hub_id
    response["node_ids"] = ','.join(node_ids)
    return response
