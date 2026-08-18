import re


DNS_1123_LABEL = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")


def validate_k8s_name(value: str):
    if not isinstance(value, str) or not value.strip():
        return "name is required"
    if len(value) > 63:
        return "name must be 63 characters or less"
    if not DNS_1123_LABEL.match(value):
        return "name must contain only lowercase letters, numbers or '-', and must start/end with an alphanumeric character"
    return None