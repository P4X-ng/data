#!/usr/bin/env bash
set -euo pipefail
# IDrinkYourMILKSHAKE (Cloud) — Setup VPC Flow Logs to CloudWatch Logs
# This script creates (if needed):
# - CloudWatch Logs group for VPC Flow Logs
# - IAM role permitting VPC Flow Logs delivery
# - VPC Flow Logs for the specified VPC to the log group
#
# Usage:
#   aws_flowlogs_setup.sh <VPC_ID> <LOG_GROUP_NAME> [ROLE_NAME] [REGION]
#
# Requirements:
# - AWS CLI configured (env or profile)
# - Permissions: iam:CreateRole, iam:PutRolePolicy, logs:CreateLogGroup, ec2:CreateFlowLogs

VPC_ID=${1:-}
LOG_GROUP=${2:-}
ROLE_NAME=${3:-FlowLogsToCloudWatch}
REGION=${4:-}

if [[ -z "$VPC_ID" || -z "$LOG_GROUP" ]]; then
  echo "usage: $0 <VPC_ID> <LOG_GROUP_NAME> [ROLE_NAME] [REGION]" >&2
  exit 2
fi

AWS=aws
if [[ -n "$REGION" ]]; then
  AWS="aws --region $REGION"
fi

ACCOUNT_ID=$($AWS sts get-caller-identity --query 'Account' --output text)
PARTITION=$($AWS sts get-caller-identity --query 'Arn' --output text | awk -F: '{print $2}')

# 1) Create log group if not exists
if ! $AWS logs describe-log-groups --log-group-name-prefix "$LOG_GROUP" --query "logGroups[?logGroupName=='$LOG_GROUP'] | length(@)" --output text | grep -q '^1$'; then
  echo "[setup] creating log group $LOG_GROUP"
  $AWS logs create-log-group --log-group-name "$LOG_GROUP"
else
  echo "[setup] log group $LOG_GROUP exists"
fi

# 2) Create IAM role for VPC Flow Logs delivery (if not exists)
ASSUME_ROLE_DOC=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "vpc-flow-logs.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}
EOF
)

POLICY_DOC=$(cat <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "logs:DescribeLogGroups",
        "logs:DescribeLogStreams"
      ],
      "Resource": "arn:$PARTITION:logs:*:$ACCOUNT_ID:log-group:$LOG_GROUP:*"
    }
  ]
}
EOF
)

if ! $AWS iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1; then
  echo "[setup] creating IAM role $ROLE_NAME"
  $AWS iam create-role --role-name "$ROLE_NAME" --assume-role-policy-document "$ASSUME_ROLE_DOC" >/dev/null
else
  echo "[setup] IAM role $ROLE_NAME exists"
fi

# Attach inline policy (idempotent via put-role-policy)
echo "[setup] attaching inline policy to $ROLE_NAME for $LOG_GROUP"
$AWS iam put-role-policy --role-name "$ROLE_NAME" --policy-name FlowLogsToCWL --policy-document "$POLICY_DOC" >/dev/null

ROLE_ARN=$($AWS iam get-role --role-name "$ROLE_NAME" --query 'Role.Arn' --output text)

# 3) Create Flow Logs for VPC (if not already delivering to this group)
EXISTING=$($AWS ec2 describe-flow-logs --filter Name=resource-id,Values=$VPC_ID --query "FlowLogs[?LogGroupName=='$LOG_GROUP'] | length(@)" --output text)
if [[ "$EXISTING" != "1" ]]; then
  echo "[setup] creating VPC Flow Logs for $VPC_ID -> $LOG_GROUP"
  $AWS ec2 create-flow-logs \
    --resource-type VPC \
    --resource-ids "$VPC_ID" \
    --traffic-type ALL \
    --log-destination-type cloud-watch-logs \
    --log-group-name "$LOG_GROUP" \
    --deliver-logs-permission-arn "$ROLE_ARN" >/dev/null
else
  echo "[setup] flow logs already configured for $VPC_ID to $LOG_GROUP"
fi

echo "[ok] VPC Flow Logs -> $LOG_GROUP ready"