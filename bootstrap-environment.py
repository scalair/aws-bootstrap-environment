#!/usr/bin/env python
import argparse
import boto3
import hvac
import os
from os.path import expanduser

def parse_args():
    description = '''
Script to bootstrap a new environment
'''
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--bucket_name',
        help='Name of the S3 bucket',
                required=True,
        action='store')
    parser.add_argument('--dynamodb_name',
        help='Name of the DynamoDB table',
                required=True,
        action='store')
    parser.add_argument('--keypair_name',
        help='Name of the KeyPair',
                required=True,
        action='store')
    parser.add_argument('--region',
        help='Region of the environment to bootstrap',
                required=True,
        action='store')
    parser.add_argument('--vault_path',
        help='Path in Vault where the ssh keys will be stored',
                required=True,
        action='store')
    parser.add_argument('--vault_ca_path',
        help='Path to the CA of Vault. Might not be required for every OS depending on how you install it',
                default='/usr/local/share/ca-certificates/vault.prod.scalair.eu-west-1.ca.cert.pem',
        action='store')

    args = parser.parse_args()

    return args


def main():
    args = parse_args()
    bucket_name    = args.bucket_name
    dynamodb_name  = args.dynamodb_name
    keypair_name   = args.keypair_name
    vault_path     = args.vault_path
    vault_ca_path  = args.vault_ca_path
    region         = args.region

    session        = boto3.session.Session()
    dynamodb       = session.client(service_name='dynamodb')
    s3             = session.client(service_name='s3')
    ec2            = session.client(service_name='ec2', region_name=region)

    vault = vault_auth(vault_ca_path)
   
    # Create the table in dynamoDB to store Terraform lock state
    create_locktable(dynamodb, dynamodb_name)

    # Create the S3 bucket
    create_s3_bucket(s3, bucket_name, region)

    # Create the ssh keys, add them to AWS and Vault
    create_key_pairs(ec2, vault, vault_path, keypair_name)


def create_locktable(dynamodb, dynamodb_name):
    """
    Create dynamodb table for state file locking

    Args:
        dynamodb:       dynamodb object
        dynamodb_name:  Name of the table
    """
    tables = dynamodb.list_tables()
    if dynamodb_name not in tables['TableNames']:
        print("DynamoDB terraform state lock table for {} does not exist. Creating...".format(dynamodb_name))
        locktable = dynamodb.create_table(
            TableName=dynamodb_name,
            KeySchema=[
                {
                    'AttributeName': 'LockID',
                    'KeyType': 'HASH'
                }
            ],
            AttributeDefinitions=[
                {
                    'AttributeName': 'LockID',
                    'AttributeType': 'S'
                }
            ],
            ProvisionedThroughput={
                'ReadCapacityUnits': 5,
                'WriteCapacityUnits': 5
            }
        )

        dynamodb.get_waiter('table_exists').wait(TableName=dynamodb_name)
    else:
        print("DynamoDB tfsatte lock table for {} already exists. Skipping Creation...".format(dynamodb_name))


def create_s3_bucket(s3, bucket_name, region):
    """
    Create the s3 bucket

    Args:
        s3:             S3 object
        bucket_name:    Name of the S3 bucket
        region:         Region
    """
    response = s3.list_buckets()
    buckets = {}
    bucket_exist = False
    for bucket in response['Buckets']:
        if bucket['Name'] == bucket_name:
            bucket_exist = True

    if not bucket_exist:
        print("Bucket "+bucket_name+" does not exist. Creating...")
        s3.create_bucket(Bucket=bucket_name, CreateBucketConfiguration={'LocationConstraint': region})
    else:
        print("Bucket "+bucket_name+" already exists. Skipping...")

def vault_auth(vault_ca_path):
    """
    Authenticate to Vault

    Return:
        Vault object
    """
    home = expanduser("~")
    f = open(home + "/.vault-token", "rb")
    vault_token = f.read()
    f.close()
    return hvac.Client(url=os.environ['VAULT_ADDR'], token=vault_token, verify=vault_ca_path)


def create_key_pairs(ec2, vault, vault_path, keypair_name):
    """
    Create key-pairs in ec2 and upload the private keys to Vault

    Args:
        ec2:            ec2 object
        vault:          Vault object
        vault_path:     Path in Vault where the private keys will be stored, for instance `secret/foo/bar`
    """
    response = ec2.describe_key_pairs()
    key_pairs_list = []
    for key in response['KeyPairs']:
        key_pairs_list.append(key['KeyName'])


    if keypair_name not in key_pairs_list:
        print("Creating '{}' key".format(keypair_name))
        keypair = ec2.create_key_pair(KeyName=keypair_name)
        vault.write(vault_path, private_key=keypair['KeyMaterial'])
    else:
        print("Skipping '{}' key".format(keypair_name))

if __name__ == "__main__":
    main()
