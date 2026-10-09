"""Launch (or find) the Sabwat EC2 instance and manage who can reach it. Idempotent.

Usage (from repo root, with fresh AWS keys in .env):
  python deploy/launch_ec2.py                    # create key pair, security group, instance
  python deploy/launch_ec2.py --allow 1.2.3.4    # also allow another IP (e.g. venue Wi-Fi)
  python deploy/launch_ec2.py --open-all         # judging window: port 8000 open to everyone
  python deploy/launch_ec2.py --close-all        # undo --open-all
  python deploy/launch_ec2.py --status

Shared account: only touches resources named/tagged sabwat; never deletes instances.
The instance gets the sabwat-ec2-profile role (DynamoDB sabwat-* only), so no AWS keys go on it.
"""

import argparse
import os
import stat
import sys
import urllib.request
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from sabwat.config import settings  # loads .env (import after sys.path tweak)

NAME = "sabwat"
SG_NAME = "sabwat-web"
KEY_NAME = "sabwat-key"
KEY_PATH = Path.home() / ".ssh" / "sabwat-key.pem"
PROFILE = "sabwat-ec2-profile"
INSTANCE_TYPE = "t3.small"
TAGS = [{"Key": "Project", "Value": "sabwat"}]
PORTS = (22, 8000)  # SSH for deploys; 8000 for the app

USER_DATA = """#!/bin/bash
apt-get update -y
apt-get install -y python3-venv python3-pip
mkdir -p /home/ubuntu/sabwat && chown ubuntu:ubuntu /home/ubuntu/sabwat
"""


def my_ip() -> str:
    return urllib.request.urlopen("https://checkip.amazonaws.com", timeout=10).read().decode().strip()


def ubuntu_ami(ssm) -> tuple[str, str]:
    # Prefer 26.04 (Python 3.14, same as local dev); fall back to 24.04.
    for ver in ("26.04", "24.04"):
        try:
            name = f"/aws/service/canonical/ubuntu/server/{ver}/stable/current/amd64/hvm/ebs-gp3/ami-id"
            return ver, ssm.get_parameter(Name=name)["Parameter"]["Value"]
        except ClientError:
            continue
    sys.exit("No Ubuntu AMI found via SSM")


def ensure_key(ec2) -> None:
    try:
        ec2.describe_key_pairs(KeyNames=[KEY_NAME])
        print(f"[exists ] key pair {KEY_NAME}" + ("" if KEY_PATH.exists() else f"  (WARNING: {KEY_PATH} missing)"))
    except ClientError:
        key = ec2.create_key_pair(KeyName=KEY_NAME, KeyType="ed25519",
                                  TagSpecifications=[{"ResourceType": "key-pair", "Tags": TAGS}])
        KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
        KEY_PATH.write_text(key["KeyMaterial"])
        os.chmod(KEY_PATH, stat.S_IRUSR | stat.S_IWUSR)
        print(f"[created] key pair {KEY_NAME} -> {KEY_PATH}")


def ensure_sg(ec2) -> str:
    vpc = ec2.describe_vpcs(Filters=[{"Name": "isDefault", "Values": ["true"]}])["Vpcs"][0]["VpcId"]
    found = ec2.describe_security_groups(Filters=[{"Name": "group-name", "Values": [SG_NAME]},
                                                  {"Name": "vpc-id", "Values": [vpc]}])["SecurityGroups"]
    if found:
        print(f"[exists ] security group {SG_NAME}")
        return found[0]["GroupId"]
    sg = ec2.create_security_group(GroupName=SG_NAME, VpcId=vpc,
                                   Description="Sabwat demo: SSH and app port, restricted IPs",
                                   TagSpecifications=[{"ResourceType": "security-group", "Tags": TAGS}])
    print(f"[created] security group {SG_NAME}")
    return sg["GroupId"]


def allow(ec2, sg_id: str, cidr: str, ports=PORTS) -> None:
    for port in ports:
        try:
            ec2.authorize_security_group_ingress(GroupId=sg_id, IpPermissions=[{
                "IpProtocol": "tcp", "FromPort": port, "ToPort": port,
                "IpRanges": [{"CidrIp": cidr, "Description": "sabwat"}]}])
            print(f"[allowed] {cidr} -> port {port}")
        except ClientError as e:
            if e.response["Error"]["Code"] != "InvalidPermission.Duplicate":
                raise
            print(f"[exists ] {cidr} -> port {port}")


def revoke(ec2, sg_id: str, cidr: str, port: int) -> None:
    try:
        ec2.revoke_security_group_ingress(GroupId=sg_id, IpPermissions=[{
            "IpProtocol": "tcp", "FromPort": port, "ToPort": port, "IpRanges": [{"CidrIp": cidr}]}])
        print(f"[revoked] {cidr} -> port {port}")
    except ClientError:
        print(f"[absent ] {cidr} -> port {port}")


def find_instance(ec2):
    res = ec2.describe_instances(Filters=[{"Name": "tag:Name", "Values": [NAME]},
                                          {"Name": "instance-state-name", "Values": ["pending", "running", "stopped"]}])
    inst = [i for r in res["Reservations"] for i in r["Instances"]]
    return inst[0] if inst else None


def ensure_instance(ec2, ssm, sg_id: str):
    inst = find_instance(ec2)
    if inst:
        print(f"[exists ] instance {inst['InstanceId']} ({inst['State']['Name']})")
        return inst
    ver, ami = ubuntu_ami(ssm)
    inst = ec2.run_instances(
        ImageId=ami, InstanceType=INSTANCE_TYPE, MinCount=1, MaxCount=1, KeyName=KEY_NAME,
        SecurityGroupIds=[sg_id], IamInstanceProfile={"Name": PROFILE}, UserData=USER_DATA,
        BlockDeviceMappings=[{"DeviceName": "/dev/sda1", "Ebs": {"VolumeSize": 20, "VolumeType": "gp3"}}],
        MetadataOptions={"HttpTokens": "required"},
        TagSpecifications=[{"ResourceType": "instance", "Tags": TAGS + [{"Key": "Name", "Value": NAME}]},
                           {"ResourceType": "volume", "Tags": TAGS}],
    )["Instances"][0]
    print(f"[created] instance {inst['InstanceId']} ({INSTANCE_TYPE}, Ubuntu {ver}); waiting for it to run…")
    ec2.get_waiter("instance_running").wait(InstanceIds=[inst["InstanceId"]])
    return find_instance(ec2)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--allow", metavar="IP", help="also allow this IP to reach ports 22 and 8000")
    ap.add_argument("--open-all", action="store_true", help="open port 8000 to everyone (judging window)")
    ap.add_argument("--close-all", action="store_true", help="remove the open-to-everyone rule")
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args()

    s = boto3.session.Session(region_name=settings.aws_region)
    ec2, ssm = s.client("ec2"), s.client("ssm")
    if args.status:
        inst = find_instance(ec2)
        print(inst and f"{inst['InstanceId']} {inst['State']['Name']} {inst.get('PublicIpAddress')}")
        return

    sg_id = ensure_sg(ec2)
    if args.open_all:
        allow(ec2, sg_id, "0.0.0.0/0", ports=(8000,))
        return
    if args.close_all:
        revoke(ec2, sg_id, "0.0.0.0/0", 8000)
        return

    ensure_key(ec2)
    allow(ec2, sg_id, f"{my_ip()}/32")
    if args.allow:
        allow(ec2, sg_id, f"{args.allow}/32")
    inst = ensure_instance(ec2, ssm, sg_id)
    ip = inst.get("PublicIpAddress")
    print(f"\nInstance {inst['InstanceId']}  public IP {ip}")
    print(f"Next:  bash deploy/push.sh {ip}")


if __name__ == "__main__":
    main()
