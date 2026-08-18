# Project Report

## Testing the Program

Using postman I have tested all senarios on APIs designed for Cluster, Namespace and Application. screenshots of tests are provided in this google drive `https://drive.google.com/drive/folders/1sBlLaGUU1SMOwKey6YAY7P79XEvpsCFM?usp=sharing`

For `application` I have used these fields ( a sample request body is provided )
```json
{
    "namespace_id": 2, 
    "name": "my-app", 
    "image": "nginx:latest", 
    "replicas": 2, 
    "cpu": "300m", 
    "memory": "64Mi"
}
```

The `App` model contains fields such as `namespace`, `name`, `image`, `replicas`, `cpu`, `memory`, and `created_at`. The `namespace` identifies where the App is deployed, while `name` and `image` define the application and its Docker image. `replicas`, `cpu`, and `memory` are used to specify the desired number of Pods and their resource requirements, with the same CPU and memory values used for both requests and limits. The `created_at` field records when the App was created. Additionally, the Deployment and all Pods it creates use the label `app: <app-name>`, which is also used by the Deployment selector to associate the Pods with the correct App.


## Problems which I solved

### PATCH request to update expired token of a cluster 
To handle cases where a Cluster token expires, a dedicated `PATCH` API was added to update only the token without creating a new Cluster or changing its existing information. This keeps the Cluster ID and its relationships with other resources unchanged while allowing the Kubernetes credential to be replaced. The API endpoint is `PATCH /cluster/<cluster_id>`. For example:

```json
{
    "token": "new-kubernetes-token"
}
```

The token is accepted in the request but is not returned in the response for security reasons.

### Consistency Between Database and Kubernetes

When deleting a Namespace, the operation involves two separate systems: the Django database and Kubernetes. Because they cannot be part of one atomic transaction, an inconsistency can occur if the Namespace is successfully deleted from Kubernetes but the backend crashes before removing its database record. To handle this, a later DELETE request checks Kubernetes again; if Kubernetes returns `404 Not Found`, it means the Namespace is already deleted there, so the backend safely removes the remaining database record as well. This allows the system to recover from this intermediate inconsistent state.

### Handling Concurrent DELETE Requests

If two DELETE requests for the same Namespace arrive at nearly the same time, `select_for_update()` places a row-level lock on the corresponding database record. The first transaction that acquires the lock performs the deletion and commits, while the other request waits until that transaction finishes. After the lock is released, the second request continues and finds that the database record has already been deleted, so it returns `404 Not Found`. This serializes concurrent database access to the same Namespace and prevents race conditions.


These two updates are applied to both namespace and application delete operations.