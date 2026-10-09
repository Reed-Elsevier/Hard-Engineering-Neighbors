"""Create Sabwat's AWS resources. Idempotent: re-running reports what already exists.

Usage:  python backend/scripts/provision_aws.py

The account is shared with other teams: this script only creates or updates resources named
sabwat-* and tagged Project=sabwat, and never deletes anything.
  - DynamoDB  sabwat-decisions   PK txn_id, SK decided_at   (on-demand)
  - DynamoDB  sabwat-briefs      PK txn_id, TTL expires_at  (on-demand)
  - IAM role  sabwat-ec2-role + instance profile sabwat-ec2-profile, allowed only to
    read/write the sabwat-* tables. Attach the profile to the EC2 instance at launch.
"""

import json
import sys

import boto3
from botocore.exceptions import ClientError

from sabwat.config import settings

TAGS = [{"Key": "Project", "Value": "sabwat"}]
ROLE = "sabwat-ec2-role"
PROFILE = "sabwat-ec2-profile"
POLICY = "sabwat-dynamodb-access"


def ensure_table(ddb, name: str, key_schema: list, attrs: list, ttl_attr: str | None = None) -> str:
    try:
        arn = ddb.describe_table(TableName=name)["Table"]["TableArn"]
        print(f"[exists ] table {name}")
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
            raise
        arn = ddb.create_table(
            TableName=name, KeySchema=key_schema, AttributeDefinitions=attrs,
            BillingMode="PAY_PER_REQUEST", Tags=TAGS,
        )["TableDescription"]["TableArn"]
        ddb.get_waiter("table_exists").wait(TableName=name)
        print(f"[created] table {name}")
    if ttl_attr:
        status = ddb.describe_time_to_live(TableName=name)["TimeToLiveDescription"]
        if status["TimeToLiveStatus"] in ("DISABLED",):
            ddb.update_time_to_live(
                TableName=name, TimeToLiveSpecification={"Enabled": True, "AttributeName": ttl_attr}
            )
            print(f"[updated] TTL on {name}.{ttl_attr}")
    return arn


def ensure_role(iam, account: str) -> None:
    trust = {"Version": "2012-10-17", "Statement": [{
        "Effect": "Allow", "Principal": {"Service": "ec2.amazonaws.com"}, "Action": "sts:AssumeRole",
    }]}
    try:
        iam.get_role(RoleName=ROLE)
        print(f"[exists ] role {ROLE}")
    except iam.exceptions.NoSuchEntityException:
        iam.create_role(RoleName=ROLE, AssumeRolePolicyDocument=json.dumps(trust), Tags=TAGS,
                        Description="Sabwat EC2: DynamoDB access to sabwat-* tables only")
        print(f"[created] role {ROLE}")

    table_arn = f"arn:aws:dynamodb:{settings.aws_region}:{account}:table/sabwat-*"
    policy = {"Version": "2012-10-17", "Statement": [{
        "Effect": "Allow",
        "Action": ["dynamodb:PutItem", "dynamodb:GetItem", "dynamodb:Query",
                   "dynamodb:UpdateItem", "dynamodb:DescribeTable"],
        "Resource": [table_arn, table_arn + "/index/*"],
    }]}
    iam.put_role_policy(RoleName=ROLE, PolicyName=POLICY, PolicyDocument=json.dumps(policy))
    print(f"[updated] inline policy {POLICY} -> {table_arn}")

    try:
        iam.get_instance_profile(InstanceProfileName=PROFILE)
        print(f"[exists ] instance profile {PROFILE}")
    except iam.exceptions.NoSuchEntityException:
        iam.create_instance_profile(InstanceProfileName=PROFILE, Tags=TAGS)
        print(f"[created] instance profile {PROFILE}")
    roles = iam.get_instance_profile(InstanceProfileName=PROFILE)["InstanceProfile"]["Roles"]
    if not any(r["RoleName"] == ROLE for r in roles):
        iam.add_role_to_instance_profile(InstanceProfileName=PROFILE, RoleName=ROLE)
        print(f"[updated] added {ROLE} to {PROFILE}")


def main() -> int:
    session = boto3.session.Session(region_name=settings.aws_region)
    account = session.client("sts").get_caller_identity()["Account"]
    print(f"account {account}  region {settings.aws_region}")
    ddb = session.client("dynamodb")
    ensure_table(
        ddb, settings.ddb_table_decisions,
        [{"AttributeName": "txn_id", "KeyType": "HASH"},
         {"AttributeName": "decided_at", "KeyType": "RANGE"}],
        [{"AttributeName": "txn_id", "AttributeType": "S"},
         {"AttributeName": "decided_at", "AttributeType": "S"}],
    )
    ensure_table(
        ddb, settings.ddb_table_briefs,
        [{"AttributeName": "txn_id", "KeyType": "HASH"}],
        [{"AttributeName": "txn_id", "AttributeType": "S"}],
        ttl_attr="expires_at",
    )
    ensure_role(session.client("iam"), account)
    return 0


if __name__ == "__main__":
    sys.exit(main())
