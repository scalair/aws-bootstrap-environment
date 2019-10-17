# Bootstrap Environment script
Creates: 
- a DynamoDB entry for state locking
- a S3 bucket to store Terraform state
- a key pair in EC2 and stores it to Vault

## Install
```pip3.7 install -r requirements.txt```

## Usage example
```python3.7 bootstrap-environment.py --bucket_name my-awesome-bucket --dynamodb_name my-awesome-table --keypair_name my-awesome-keypair --env_region eu-west-1 --vault_path secret/foo/bar```
