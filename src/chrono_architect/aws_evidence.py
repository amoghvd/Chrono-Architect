from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import UTC, datetime, timedelta

from decimal import Decimal
from typing import Any

from .analysis import summarize
from .mcp_gateway import AwsGateway, McpError
from .models import CheckStatus, CostEvidence, DependencyCheck, InstanceSnapshot, MetricSummary
from .policy import PolicyViolation, validate_identifier

REGION_LOCATIONS = {
    "us-east-1": "US East (N. Virginia)", "us-east-2": "US East (Ohio)",
    "us-west-1": "US West (N. California)", "us-west-2": "US West (Oregon)",
    "eu-west-1": "EU (Ireland)", "eu-central-1": "EU (Frankfurt)",
    "ap-south-1": "Asia Pacific (Mumbai)", "ap-southeast-1": "Asia Pacific (Singapore)",
    "ap-southeast-2": "Asia Pacific (Sydney)", "ap-northeast-1": "Asia Pacific (Tokyo)",
}


def _fingerprint(data: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _instance(payload: dict[str, Any]) -> dict[str, Any]:
    reservations = payload.get("Reservations", [])
    if not reservations or not reservations[0].get("Instances"):
        raise PolicyViolation("Instance was not found")
    return reservations[0]["Instances"][0]


class EvidenceCollector:
    def __init__(self, gateway: AwsGateway, region: str):
        self.gateway, self.region = gateway, region

    async def snapshot(self, instance_id: str) -> InstanceSnapshot:
        validate_identifier(instance_id, "instance id")
        identity = await self.gateway.call_cli("aws sts get-caller-identity")
        desc_cmd = f"aws ec2 describe-instances --instance-ids {instance_id} --region {self.region}"
        raw = _instance(await self.gateway.call_cli(desc_cmd))
        asg_cmd = f"aws autoscaling describe-auto-scaling-instances --instance-ids {instance_id} --region {self.region}"
        asg = await self.gateway.call_cli(asg_cmd)
        asg_items = asg.get("AutoScalingInstances", [])
        tags = {t["Key"]: t.get("Value", "") for t in raw.get("Tags", [])}
        relevant = {
            "InstanceId": raw["InstanceId"], "InstanceType": raw["InstanceType"],
            "State": raw.get("State", {}).get("Name"), "Architecture": raw.get("Architecture"),
            "InstanceLifecycle": raw.get("InstanceLifecycle", "on-demand"),
            "RootDeviceType": raw.get("RootDeviceType"), "BlockDeviceMappings": raw.get("BlockDeviceMappings", []),
            "NetworkInterfaces": raw.get("NetworkInterfaces", []), "SecurityGroups": raw.get("SecurityGroups", []),
            "Tags": tags, "ASG": asg_items,
        }
        return InstanceSnapshot(
            account_id=str(identity["Account"]), region=self.region, instance_id=raw["InstanceId"],
            instance_type=raw["InstanceType"], state=raw.get("State", {}).get("Name", "unknown"),
            architecture=raw.get("Architecture", "unknown"), lifecycle=raw.get("InstanceLifecycle", "on-demand"),
            root_device_type=raw.get("RootDeviceType", "unknown"),
            asg_name=asg_items[0].get("AutoScalingGroupName") if asg_items else None,
            tags=tags,
            volume_ids=[b["Ebs"]["VolumeId"] for b in raw.get("BlockDeviceMappings", []) if "Ebs" in b],
            eni_ids=[n["NetworkInterfaceId"] for n in raw.get("NetworkInterfaces", [])],
            security_group_ids=[g["GroupId"] for g in raw.get("SecurityGroups", [])],
            public_ip=raw.get("PublicIpAddress"),
            has_instance_store_mapping=any("VirtualName" in b for b in raw.get("BlockDeviceMappings", [])),
            raw_fingerprint=_fingerprint(relevant),
        )

    async def checks(self, snap: InstanceSnapshot, target_type: str, managed_key: str,
                     managed_value: str) -> list[DependencyCheck]:
        validate_identifier(target_type, "target type")
        current_cmd = f"aws ec2 describe-instance-types --instance-types {snap.instance_type} {target_type} --region {self.region}"
        types = await self.gateway.call_cli(current_cmd)
        by_name = {x["InstanceType"]: x for x in types.get("InstanceTypes", [])}
        target = by_name.get(target_type, {})
        target_arches = target.get("ProcessorInfo", {}).get("SupportedArchitectures", [])
        checks = [
            DependencyCheck(name="managed-tag", status=CheckStatus.PASS if snap.tags.get(managed_key) == managed_value else CheckStatus.FAIL,
                            explanation="Resource must explicitly opt in to Chrono-Architect actions", evidence={"tag": managed_key}),
            DependencyCheck(name="standalone-instance", status=CheckStatus.PASS if not snap.asg_name else CheckStatus.FAIL,
                            explanation="ASG members require launch-template/instance-refresh workflow", evidence={"asg": snap.asg_name}),
            DependencyCheck(name="on-demand", status=CheckStatus.PASS if snap.lifecycle == "on-demand" else CheckStatus.FAIL,
                            explanation="Spot instances are outside the first safe-action slice", evidence={"lifecycle": snap.lifecycle}),
            DependencyCheck(name="ebs-backed", status=CheckStatus.PASS if snap.root_device_type == "ebs" else CheckStatus.FAIL,
                            explanation="Stop/start requires an EBS-backed root device", evidence={"root": snap.root_device_type}),
            DependencyCheck(name="no-instance-store", status=CheckStatus.PASS if not snap.has_instance_store_mapping else CheckStatus.FAIL,
                            explanation="Stop/type-change can destroy instance-store data"),
            DependencyCheck(name="architecture-compatible", status=CheckStatus.PASS if snap.architecture in target_arches else CheckStatus.FAIL,
                            explanation="Target must support the current architecture", evidence={"supported": target_arches}),
        ]
        eni_limit = target.get("NetworkInfo", {}).get("MaximumNetworkInterfaces")
        checks.append(DependencyCheck(
            name="eni-capacity", status=CheckStatus.PASS if eni_limit is not None and len(snap.eni_ids) <= eni_limit else CheckStatus.UNKNOWN,
            explanation="Target instance must support attached ENIs", evidence={"attached": len(snap.eni_ids), "limit": eni_limit}
        ))
        return checks

    async def metrics(self, instance_id: str, days: int) -> list[MetricSummary]:
        end = datetime.now(UTC).replace(microsecond=0)
        start = end - timedelta(days=days)
        specs = [("CPUUtilization", "Percent"), ("NetworkIn", "Bytes"), ("NetworkOut", "Bytes"),
                 ("EBSReadBytes", "Bytes"), ("EBSWriteBytes", "Bytes")]
        period = 3600

        async def _fetch_one(metric: str, unit: str) -> MetricSummary:
            cmd = (f"aws cloudwatch get-metric-statistics --namespace AWS/EC2 --metric-name {metric} "
                   f"--dimensions Name=InstanceId,Value={instance_id} --start-time {start.isoformat()} "
                   f"--end-time {end.isoformat()} --period {period} --statistics Average Maximum "
                   f"--region {self.region}")
            payload = await self.gateway.call_cli(cmd)
            points = [(p.get("Timestamp"), p.get("Average", p.get("Maximum"))) for p in payload.get("Datapoints", [])]
            return summarize(metric, unit, points, start, end)

        return list(await asyncio.gather(*(_fetch_one(m, u) for m, u in specs)))


    async def resource_cost(self, instance_id: str, days: int) -> CostEvidence:
        end = datetime.now(UTC).date()
        start = end - timedelta(days=min(days, 14))
        expression = json.dumps({"And": [
            {"Dimensions": {"Key": "SERVICE", "Values": ["Amazon Elastic Compute Cloud - Compute"]}},
            {"Dimensions": {"Key": "RESOURCE_ID", "Values": [instance_id]}},
        ]}, separators=(",", ":"))
        cmd = (f"aws ce get-cost-and-usage-with-resources --time-period Start={start},End={end} "
               f"--granularity DAILY --metrics UnblendedCost --filter '{expression}' --region us-east-1")
        payload = await self.gateway.call_cli(cmd)
        amount = Decimal(0)
        currency = "USD"
        for period in payload.get("ResultsByTime", []):
            total = period.get("Total", {}).get("UnblendedCost")
            if total:
                amount += Decimal(total.get("Amount", "0"))
                currency = total.get("Unit", currency)
            for group in period.get("Groups", []):
                metric = group.get("Metrics", {}).get("UnblendedCost", {})
                amount += Decimal(metric.get("Amount", "0"))
                currency = metric.get("Unit", currency)
        return CostEvidence(metric="UnblendedCost", start=datetime.combine(start, datetime.min.time(), UTC),
                            end=datetime.combine(end, datetime.min.time(), UTC), amount=amount,
                            currency=currency, resource_level=True,
                            caveats=["Cost Explorer data is delayed and resource-level EC2 data requires opt-in."])

    async def hourly_price(self, instance_type: str, architecture: str) -> Decimal:
        location = REGION_LOCATIONS.get(self.region)
        if location:
            os_name = "Linux"
            cmd = ("aws pricing get-products --service-code AmazonEC2 --region us-east-1 "
                   f"--filters Type=TERM_MATCH,Field=instanceType,Value={instance_type} "
                   f"Type=TERM_MATCH,Field=location,Value=\"{location}\" "
                   f"Type=TERM_MATCH,Field=operatingSystem,Value={os_name} "
                   "Type=TERM_MATCH,Field=tenancy,Value=Shared "
                   "Type=TERM_MATCH,Field=preInstalledSw,Value=NA "
                   "Type=TERM_MATCH,Field=capacitystatus,Value=Used")
            try:
                payload = await self.gateway.call_cli(cmd)
                price_list = payload.get("PriceList", [])
                if price_list:
                    product = json.loads(price_list[0]) if isinstance(price_list[0], str) else price_list[0]
                    terms = product.get("terms", {}).get("OnDemand", {})
                    for term in terms.values():
                        for dimension in term.get("priceDimensions", {}).values():
                            if dimension.get("unit") == "Hrs":
                                return Decimal(dimension["pricePerUnit"]["USD"])
            except McpError:
                pass

        FALLBACK_PRICES = {
            "t3.nano": Decimal("0.0052"), "t3.micro": Decimal("0.0104"), "t3.small": Decimal("0.0208"),
            "t3.medium": Decimal("0.0416"), "t3.large": Decimal("0.0832"), "t3.xlarge": Decimal("0.1664"),
            "t3.2xlarge": Decimal("0.3328"), "m6i.large": Decimal("0.0960"), "m6i.xlarge": Decimal("0.1920"),
            "c6i.large": Decimal("0.0850"), "r6i.large": Decimal("0.1260"), "t4g.micro": Decimal("0.0084"),
            "t4g.small": Decimal("0.0168"), "t2.micro": Decimal("0.0116"), "t2.small": Decimal("0.023"),
        }
        if instance_type in FALLBACK_PRICES:
            return FALLBACK_PRICES[instance_type]
        raise McpError(f"No pricing available for {instance_type}")

