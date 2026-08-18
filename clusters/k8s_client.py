from kubernetes import client


def get_api_client(cluster) -> client.ApiClient:
    configuration = client.Configuration()
    address = cluster.address
    if not address.startswith("http"):
        address = f"https://{address}"
    configuration.host = address
    configuration.verify_ssl = False  # self-signed cert on the VM cluster
    configuration.api_key = {"authorization": f"Bearer {cluster.token}"}
    return client.ApiClient(configuration)


def get_core_v1_api(cluster) -> client.CoreV1Api:
    return client.CoreV1Api(get_api_client(cluster))


def get_apps_v1_api(cluster) -> client.AppsV1Api:
    return client.AppsV1Api(get_api_client(cluster))