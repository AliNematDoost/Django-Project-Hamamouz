import base64
import io
import tarfile

from kubernetes.stream import stream


def copy_backup_from_pod(
    core_api,
    pod_name: str,
    namespace_name: str,
    source_path: str,
) -> bytes:
    command = [
        "tar",
        "czf",
        "-",
        source_path,
    ]

    response = stream(
        core_api.connect_get_namespaced_pod_exec,
        pod_name,
        namespace_name,
        command=command,
        stderr=True,
        stdin=False,
        stdout=True,
        tty=False,
        _preload_content=False,
    )

    output = bytearray()

    while response.is_open():
        response.update(timeout=5)

        if response.peek_stdout():
            output.extend(response.read_stdout().encode())

        if response.peek_stderr():
            error = response.read_stderr()
            if error:
                raise RuntimeError(error)

    return bytes(output)