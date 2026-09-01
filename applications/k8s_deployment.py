from kubernetes import client


def build_deployment_body(app: "App") -> client.V1Deployment:
    labels = {"app": app.name}
    container = client.V1Container(
        name=app.name,
        image=app.image,
        resources=client.V1ResourceRequirements(
            requests={"cpu": app.cpu, "memory": app.memory},
            limits={"cpu": app.cpu, "memory": app.memory},
        ),
    )
    template = client.V1PodTemplateSpec(
        metadata=client.V1ObjectMeta(labels=labels),
        spec=client.V1PodSpec(containers=[container]),
    )
    spec = client.V1DeploymentSpec(
        replicas=app.replicas,
        selector=client.V1LabelSelector(match_labels=labels),
        template=template,
    )
    return client.V1Deployment(metadata=client.V1ObjectMeta(name=app.name, labels=labels), spec=spec)


def get_pod_statuses(core_api, namespace_name: str, app_name: str) -> list[dict]:
    """Live pod status straight from Kubernetes, never from DB."""
    pods = core_api.list_namespaced_pod(
        namespace_name, label_selector=f"app={app_name}", _request_timeout=10
    )
    statuses = []
    for pod in pods.items:
        ready = False
        if pod.status.conditions:
            ready = any(c.type == "Ready" and c.status == "True" for c in pod.status.conditions)
        statuses.append({"name": pod.metadata.name, "ready": ready})
    return statuses
