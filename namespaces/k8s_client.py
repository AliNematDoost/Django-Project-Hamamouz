from kubernetes import client


def get_core_v1_api(cluster) -> client.CoreV1Api:
    configuration = client.Configuration()
    address = cluster.address
    if not address.startswith("http"):
        address = f"https://{address}"
    configuration.host = address
    configuration.verify_ssl = False  # self-signed cert on the VM cluster
    configuration.api_key = {"authorization": f"Bearer {cluster.token}"}
    api_client = client.ApiClient(configuration)
    return client.CoreV1Api(api_client)
