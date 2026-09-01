from django.db import IntegrityError, transaction
from kubernetes.client.rest import ApiException
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from clusters.k8s_client import get_apps_v1_api, get_core_v1_api
from namespaces.models import Namespace
from namespaces.validators import validate_k8s_name

from .k8s_deployment import build_deployment_body, get_pod_statuses
from .models import App
from .serializers import AppSerializer
from django.core.cache import cache


class AppListCreateView(APIView):
	def get(self, request):
		namespace_id = request.query_params.get("namespace_id")

		if not namespace_id:
			return Response(
				{"error": "namespace_id is required"},
				status=status.HTTP_400_BAD_REQUEST,
			)

		if not str(namespace_id).isdigit():
			return Response(
				{"error": "namespace_id must be an integer"},
				status=status.HTTP_400_BAD_REQUEST,
			)

		try:
			namespace = Namespace.objects.select_related(
				"cluster"
			).get(id=namespace_id)
		except Namespace.DoesNotExist:
			return Response(
				{"error": "Namespace not found"},
				status=status.HTTP_404_NOT_FOUND,
			)

		apps = App.objects.filter(namespace=namespace)
		core_api = get_core_v1_api(namespace.cluster)

		result = []

		for app in apps:
			cache_key = f"app_status:{app.id}"

			cached_status = cache.get(cache_key)

			if cached_status is not None:
				data = AppSerializer(app).data
				data.update(cached_status)
				result.append(data)
				continue

			try:
				pods = get_pod_statuses(
					core_api,
					namespace.name,
					app.name,
				)

				ready_count = 0
				for pod in pods:
					if pod["ready"]:
						ready_count += 1

				overall_ready = ready_count >= app.replicas

			except Exception:
				pods = []
				overall_ready = None

			live_status = {
				"ready": overall_ready,
				"pods": pods,
			}

			if overall_ready is not None:
				cache.set(
					cache_key,
					live_status,
					timeout=60,
				)

			data = AppSerializer(app).data
			data.update(live_status)
			result.append(data)

		return Response(result)

	def post(self, request):
		namespace_id = request.data.get('namespace_id')
		name = request.data.get('name')
		image = request.data.get('image')
		replicas = request.data.get('replicas', 1)
		cpu = request.data.get('cpu', '250m')
		memory = request.data.get('memory', '256Mi')

		if not namespace_id or not name or not image:
			return Response({"error": "namespace_id, name and image are required"}, status=status.HTTP_400_BAD_REQUEST)
		if not str(namespace_id).isdigit():
			return Response({"error": "namespace_id must be an integer"}, status=status.HTTP_400_BAD_REQUEST)

		name_error = validate_k8s_name(name)
		if name_error:
			return Response({"error": name_error}, status=status.HTTP_400_BAD_REQUEST)

		try:
			namespace = Namespace.objects.select_related('cluster').get(id=namespace_id)
		except Namespace.DoesNotExist:
			return Response({"error": "Namespace not found"}, status=status.HTTP_404_NOT_FOUND)

		if App.objects.filter(namespace=namespace, name=name).exists():
			return Response({"error": "App already recorded for this namespace"}, status=status.HTTP_409_CONFLICT)

		app = App(namespace=namespace, name=name, image=image, replicas=replicas, cpu=cpu, memory=memory)

		apps_api = get_apps_v1_api(namespace.cluster)
		body = build_deployment_body(app)
		try:
			apps_api.create_namespaced_deployment(namespace.name, body, _request_timeout=5)
		except ApiException as e:
			if e.status == 409:
				return Response({"error": "Deployment already exists in Kubernetes"}, status=status.HTTP_409_CONFLICT)
			elif e.status in (401, 403):
				return Response({"error": "Not authorized to create deployment"}, status=e.status)
			else:
				return Response({"error": "Kubernetes error", "detail": str(e)}, status=status.HTTP_502_BAD_GATEWAY)
		except Exception as e:
			return Response({"error": "Cannot reach Kubernetes cluster", "detail": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

		try:
			with transaction.atomic():
				app.save()
		except IntegrityError:
			return Response(
				{"error": "Deployment created in Kubernetes but a matching DB record already existed (race condition)"},
				status=status.HTTP_409_CONFLICT,
			)
		except Exception as e:
			return Response(
				{"error": "Deployment created in Kubernetes but failed to save DB record", "detail": str(e)},
				status=status.HTTP_500_INTERNAL_SERVER_ERROR,
			)

		return Response(AppSerializer(app).data, status=status.HTTP_201_CREATED)


class AppDetailView(APIView):
	def patch(self, request, pk):
		try:
			app = App.objects.select_related('namespace', 'namespace__cluster').get(id=pk)
		except App.DoesNotExist:
			return Response({"error": "App not found"}, status=status.HTTP_404_NOT_FOUND)

		cpu = request.data.get('cpu', app.cpu)
		memory = request.data.get('memory', app.memory)
		replicas = request.data.get('replicas', app.replicas)

		app.cpu, app.memory, app.replicas = cpu, memory, replicas
		apps_api = get_apps_v1_api(app.namespace.cluster)
		body = build_deployment_body(app)
		try:
			apps_api.patch_namespaced_deployment(app.name, app.namespace.name, body, _request_timeout=5)
		except ApiException as e:
			if e.status == 404:
				return Response({"error": "Deployment not found in Kubernetes"}, status=status.HTTP_404_NOT_FOUND)
			elif e.status in (401, 403):
				return Response({"error": "Not authorized to update deployment"}, status=e.status)
			else:
				return Response({"error": "Kubernetes error", "detail": str(e)}, status=status.HTTP_502_BAD_GATEWAY)
		except Exception as e:
			return Response({"error": "Cannot reach Kubernetes cluster", "detail": str(e)}, status=status.HTTP_502_BAD_GATEWAY)

		app.save()
		return Response(AppSerializer(app).data)

	def delete(self, request, pk):
		try:
			with transaction.atomic():

				# Lock this App row so concurrent DELETE requests
				# cannot process the same App at the same time.
				app = (
					App.objects
					.select_related('namespace', 'namespace__cluster')
					.select_for_update()
					.get(id=pk)
				)

				apps_api = get_apps_v1_api(app.namespace.cluster)

				try:
					apps_api.delete_namespaced_deployment(
						app.name,
						app.namespace.name,
						_request_timeout=5
					)

				except ApiException as e:
					if e.status == 404:
						# Deployment is already gone from Kubernetes.
						# We can safely remove the DB record.
						app.delete()

						return Response(
							status=status.HTTP_204_NO_CONTENT
						)

					elif e.status in (401, 403):
						return Response(
							{"error": "Not authorized to delete deployment"},
							status=e.status
						)

					else:
						return Response(
							{
								"error": "Kubernetes error",
								"detail": str(e)
							},
							status=status.HTTP_502_BAD_GATEWAY
						)

				except Exception as e:
					return Response(
						{
							"error": "Cannot reach Kubernetes cluster",
							"detail": str(e)
						},
						status=status.HTTP_502_BAD_GATEWAY
					)

				# Kubernetes deletion succeeded.
				app.delete()

				return Response(
					status=status.HTTP_204_NO_CONTENT
				)

		except App.DoesNotExist:
			return Response(
				{"error": "App not found"},
				status=status.HTTP_404_NOT_FOUND
			)
