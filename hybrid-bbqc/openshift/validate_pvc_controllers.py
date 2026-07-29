#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys


def owner_matches(
    owner_references: list[dict], kind: str, name: str, uid: str
) -> bool:
    return any(
        owner.get("controller") is True
        and owner.get("kind") == kind
        and owner.get("name") == name
        and owner.get("uid") == uid
        for owner in owner_references
    )


def pod_template_spec(item: dict) -> dict:
    spec = item["spec"]
    if item["kind"] == "CronJob":
        return spec.get("jobTemplate", {}).get("spec", {}).get("template", {}).get(
            "spec", {}
        )
    return spec.get("template", {}).get("spec", {})


def uses_pvc(item: dict, pvc: str) -> bool:
    return any(
        volume.get("persistentVolumeClaim", {}).get("claimName") == pvc
        for volume in pod_template_spec(item).get("volumes", [])
    )


def validate_pvc_controllers(
    items: list[dict],
    *,
    pvc: str,
    deployment: str,
    deployment_uid: str,
    require_scaled_zero: bool = False,
) -> list[tuple[str, str, str]]:
    consumers: list[tuple[str, str, str]] = []
    unexpected: list[tuple[str, str, str]] = []
    current_deployment: dict | None = None
    exact_replica_sets: list[dict] = []
    for item in items:
        kind = item["kind"]
        metadata = item["metadata"]
        name = metadata["name"]
        uid = metadata.get("uid", "")
        if kind == "HorizontalPodAutoscaler":
            target = item["spec"].get("scaleTargetRef", {})
            if target.get("kind") == "Deployment" and target.get("name") == deployment:
                unexpected.append((kind, name, uid))
            continue
        is_current_deployment = (
            kind == "Deployment" and name == deployment and uid == deployment_uid
        )
        is_exact_replica_set = (
            kind == "ReplicaSet"
            and bool(uid)
            and owner_matches(
                metadata.get("ownerReferences", []),
                "Deployment",
                deployment,
                deployment_uid,
            )
        )
        if is_exact_replica_set:
            exact_replica_sets.append(item)
        if not uses_pvc(item, pvc):
            continue
        identity = (kind, name, uid)
        consumers.append(identity)
        if is_current_deployment:
            if current_deployment is not None:
                unexpected.append(identity)
            current_deployment = item
        elif not is_exact_replica_set:
            unexpected.append(identity)
    if current_deployment is None:
        raise ValueError(
            f"current Deployment/{deployment} UID {deployment_uid} does not own PVC {pvc}"
        )
    if unexpected:
        raise ValueError(f"unexpected PVC controllers: {unexpected}")
    if require_scaled_zero:
        nonzero = []
        for item in [current_deployment, *exact_replica_sets]:
            if item["spec"].get("replicas", 1) != 0:
                nonzero.append(
                    (
                        item["kind"],
                        item["metadata"]["name"],
                        item["metadata"].get("uid", ""),
                        item["spec"].get("replicas"),
                    )
                )
        if nonzero:
            raise ValueError(f"PVC controllers not scaled to zero: {nonzero}")
    return consumers


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pvc", required=True)
    parser.add_argument("--deployment", required=True)
    parser.add_argument("--deployment-uid", required=True)
    parser.add_argument("--require-scaled-zero", action="store_true")
    args = parser.parse_args()
    items = json.load(sys.stdin)["items"]
    consumers = validate_pvc_controllers(
        items,
        pvc=args.pvc,
        deployment=args.deployment,
        deployment_uid=args.deployment_uid,
        require_scaled_zero=args.require_scaled_zero,
    )
    print({"PVC controllers": consumers, "scaled_zero": args.require_scaled_zero})


if __name__ == "__main__":
    main()
