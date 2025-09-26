# IDrinkYourMILKSHAKE (Cloud)

Use AWS VPC Flow Logs as a remote, observable counter for PacketFS-style "firewall compute".

What it does
- Sets up VPC Flow Logs to a CloudWatch Logs group
- Emits traffic (you) and observes ACCEPT/REJECT, packets, bytes via CloudWatch Logs Insights
- Interprets packet/byte deltas as the result of your "program" (e.g., send N probes on UDP port P)

Components
- aws_flowlogs_setup.sh: create CWL group, IAM role, and VPC Flow Logs for a VPC
- aws_flowlogs_query.py: run Logs Insights query with filters (eni, ports, action, protocol)

Prereqs
- AWS CLI and boto3 configured (env or profile)
- Your VPC has Flow Logs to CloudWatch Logs (use the setup script)

Examples
```
# Setup (once)
./scripts/cloud_milkshake/aws_flowlogs_setup.sh vpc-0123456789abcdef /aws/vpc/flow-logs/my-vpc FlowLogsToCloudWatch us-east-1

# Query last 5 minutes for UDP dstport 51999 on interface eni-abc...
/home/punk/.venv/bin/python scripts/cloud_milkshake/aws_flowlogs_query.py \
  --log-group /aws/vpc/flow-logs/my-vpc \
  --interface-id eni-0123456789abcdef0 \
  --dstport 51999 --protocol 17 --minutes 5 --region us-east-1
```