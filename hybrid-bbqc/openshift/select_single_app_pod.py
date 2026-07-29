#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


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


def exact_owned_replica_sets(
    replica_sets: list[dict], deployment: str, deployment_uid: str
) -> dict[str, str]:
    return {
        item["metadata"]["name"]: item["metadata"]["uid"]
        for item in replica_sets
        if item.get("metadata", {}).get("uid")
        and owner_matches(
            item["metadata"].get("ownerReferences", []),
            "Deployment",
            deployment,
            deployment_uid,
        )
    }


def pod_uses_pvc(pod: dict, pvc: str) -> bool:
    return any(
        volume.get("persistentVolumeClaim", {}).get("claimName") == pvc
        for volume in pod.get("spec", {}).get("volumes", [])
    )


def pod_owned_by_replica_set(pod: dict, replica_sets: dict[str, str]) -> bool:
    owners = pod.get("metadata", {}).get("ownerReferences", [])
    return any(
        owner_matches(owners, "ReplicaSet", name, uid)
        for name, uid in replica_sets.items()
    )


def validate_all_pvc_pods(
    pods: list[dict], replica_sets: dict[str, str], pvc: str
) -> list[str]:
    pvc_pods = [pod for pod in pods if pod_uses_pvc(pod, pvc)]
    unexpected = [
        pod["metadata"]["name"]
        for pod in pvc_pods
        if not pod_owned_by_replica_set(pod, replica_sets)
    ]
    if unexpected:
        raise ValueError(f"PVC pods outside exact Deployment UID chain: {unexpected}")
    return [pod["metadata"]["name"] for pod in pvc_pods]


def select_single_app_pod(
    pods: list[dict],
    replica_sets: list[dict],
    *,
    deployment: str,
    deployment_uid: str,
    pvc: str,
    containers: set[str],
    pvc_container: str,
    pvc_mount_path: str,
) -> str:
    owned_replica_sets = exact_owned_replica_sets(
        replica_sets, deployment, deployment_uid
    )
    validate_all_pvc_pods(pods, owned_replica_sets, pvc)
    candidates: list[str] = []
    for pod in pods:
        metadata = pod["metadata"]
        if metadata.get("deletionTimestamp") is not None:
            continue
        if pod.get("status", {}).get("phase") != "Running":
            continue
        conditions = {
            condition.get("type"): condition.get("status")
            for condition in pod.get("status", {}).get("conditions", [])
        }
        if conditions.get("Ready") != "True":
            continue
        if not pod_owned_by_replica_set(pod, owned_replica_sets):
            continue
        volumes = pod.get("spec", {}).get("volumes", [])
        pvc_volume_names = {
            volume.get("name")
            for volume in volumes
            if volume.get("persistentVolumeClaim", {}).get("claimName") == pvc
        }
        if not pvc_volume_names:
            continue
        declared_containers = pod.get("spec", {}).get("containers", [])
        declared = {container.get("name") for container in declared_containers}
        data_container = next(
            (
                container
                for container in declared_containers
                if container.get("name") == pvc_container
            ),
            None,
        )
        if data_container is None or not any(
            mount.get("name") in pvc_volume_names
            and mount.get("mountPath") == pvc_mount_path
            for mount in data_container.get("volumeMounts", [])
        ):
            continue
        ready = {
            status.get("name")
            for status in pod.get("status", {}).get("containerStatuses", [])
            if status.get("ready") is True
        }
        if not containers.issubset(declared) or not containers.issubset(ready):
            continue
        candidates.append(metadata["name"])
    if len(candidates) != 1:
        raise ValueError(
            f"expected exactly one ready pod owned by Deployment/{deployment} "
            f"UID {deployment_uid}; found {candidates}"
        )
    return candidates[0]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pods", type=Path, required=True)
    parser.add_argument("--replicasets", type=Path, required=True)
    parser.add_argument("--deployment", required=True)
    parser.add_argument("--deployment-uid", required=True)
    parser.add_argument("--pvc", required=True)
    parser.add_argument("--container", action="append", required=True)
    parser.add_argument("--pvc-container", required=True)
    parser.add_argument("--pvc-mount-path", required=True)
    args = parser.parse_args()
    pods = json.loads(args.pods.read_text())["items"]
    replica_sets = json.loads(args.replicasets.read_text())["items"]
    print(
        select_single_app_pod(
            pods,
            replica_sets,
            deployment=args.deployment,
            deployment_uid=args.deployment_uid,
            pvc=args.pvc,
            containers=set(args.container),
            pvc_container=args.pvc_container,
            pvc_mount_path=args.pvc_mount_path,
        )
    )


if __name__ == "__main__":
    main()
