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
The reasoning behind choosing this model:
...