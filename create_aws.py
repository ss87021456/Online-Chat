import os
import boto3
from pathlib import Path


def launch_app_server():
    ec2 = boto3.resource('ec2')

    USER_SCRIPT = Path('aws-setup.sh').read_text()

    # create a new EC2 instance
    instances = ec2.create_instances(
         ImageId='ami-0653e888ec96eab9b',
         MinCount=1,
         MaxCount=1,
         InstanceType='t2.micro',
         UserData=USER_SCRIPT,
         KeyName='jack',
        SecurityGroupIds=[os.getenv('SecurityGroupIds')]
     )

    instances[0].wait_until_running()
    instances[0].reload() # from stack-overflow, ensure to get public ip
    ip_address = instances[0].public_ip_address
    print("Application Server launched at {}".format(ip_address))
    
    return ip_address

def terminate_app_server(ip_address):
    ec2 = boto3.resource('ec2')

    filter_instances = ec2.instances.filter(Filters=[{
    'Name': 'ip-address',
    'Values': [ip_address]}])

    for instance in filter_instances:
        instance.terminate()

if __name__ == '__main__':
    launch_app_server()

