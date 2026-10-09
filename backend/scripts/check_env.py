"""Preflight: confirm Python deps, data, secrets and AWS credentials are in place.

Usage:  python backend/scripts/check_env.py
Never prints secret values, only whether they are set.
"""

import importlib
import os
import sys

from sabwat.config import settings

DEPS = ["pandas", "pyarrow", "lightgbm", "shap", "networkx", "sklearn", "anthropic", "pydantic",
        "fastapi", "boto3"]


def check(label: str, ok: bool, detail: str = "") -> bool:
    print(f"[{'OK ' if ok else '!! '}] {label}{'  - ' + detail if detail else ''}")
    return ok


def main() -> int:
    ok = check("python", sys.version_info >= (3, 11), sys.version.split()[0])
    for mod in DEPS:
        try:
            m = importlib.import_module(mod)
            check(mod, True, getattr(m, "__version__", ""))
        except ImportError as e:
            ok = check(mod, False, str(e)) and ok
    ok = check("data dir", settings.risk_dir.is_dir(), str(settings.risk_dir)) and ok
    key_var = "GEMINI_API_KEY" if settings.llm_provider == "gemini" else "ANTHROPIC_API_KEY"
    check(f"LLM ({settings.llm_provider}: {settings.llm_model})", settings.llm_enabled,
          f"{key_var} set" if settings.llm_enabled else f"{key_var} unset -> template-brief fallback")

    check("DB_BACKEND", True, settings.db_backend)
    aws_set = all(os.getenv(k) for k in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"))
    if check("AWS keys in env", aws_set, "local only; EC2 uses the instance role"):
        try:
            import boto3
            from botocore.exceptions import BotoCoreError, ClientError

            ident = boto3.client("sts").get_caller_identity()
            check("AWS STS identity", True, ident["Arn"])
            ddb = boto3.client("dynamodb", region_name=settings.aws_region)
            for table in (settings.ddb_table_decisions, settings.ddb_table_briefs):
                try:
                    status = ddb.describe_table(TableName=table)["Table"]["TableStatus"]
                    check(f"DynamoDB {table}", status == "ACTIVE", status)
                except ddb.exceptions.ResourceNotFoundException:
                    check(f"DynamoDB {table}", False, "missing - run scripts/provision_aws.py")
        except (BotoCoreError, ClientError) as e:  # expired session token is the usual cause
            check("AWS STS identity", False, type(e).__name__ + ": " + str(e)[:120])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
