"""Schema type definitions for cliyard YAML specs.

All types represent the structure of YAML configuration files used to define
API services and resources. These are plain TypedDict definitions with no
runtime validation logic — just type hints for IDE support and static analysis.

Example usage::

    from cliyard.schema.types import ServiceSpec
    spec: ServiceSpec = {
        "name": "my-service",
        "version": "1.0.0",
        "description": "My API",
        "server": {"base_url": "https://api.example.com"},
        "auth": {"steps": []},
        "resources": [],
    }
"""

from __future__ import annotations

from typing import Any, TypedDict


# ---------------------------------------------------------------------------
# Top-level: _service.yaml
# ---------------------------------------------------------------------------


class ServerConfig(TypedDict, total=False):
    """Server connection configuration.

    Attributes:
        base_url: Base URL of the API (required).
        prefix: URL prefix for all endpoints (default: "").
        timeout: Request timeout in seconds (default: 30).
    """

    base_url: str
    prefix: str
    timeout: int


class AuthStep(TypedDict, total=False):
    """Single authentication step.

    Attributes:
        name: Human-readable name for this step.
        type: Authentication type: "env", "login", or "inject".
        config: Flexible configuration dict specific to the auth type.
        extract: JSONPath extraction map (``field_name → jsonpath``) for
            ``login`` steps.
    """

    name: str
    type: str
    config: dict[str, Any]
    extract: dict[str, str]


class AuthPersistField(TypedDict, total=False):
    """Single field in the persist configuration.

    Attributes:
        from_: Step.field reference (e.g. ``"create_token.token"``).
        default: Fallback value if the referenced field is missing.
    """

    from_: str
    default: Any


class AuthPersist(TypedDict, total=False):
    """Credential persistence configuration.

    Attributes:
        to: Storage target — ``"cliyard-config"`` (default), ``"env"``,
            or ``"file"``.
        fields: Mapping of ``field_name → {from: "step.field"}``.
    """

    to: str
    fields: dict[str, AuthPersistField]


class AuthChain(TypedDict, total=False):
    """Authentication chain — ordered list of auth steps.

    Attributes:
        id: Optional service identifier for credential persistence.
        steps: List of AuthStep definitions to execute in order.
        persist: Optional persistence configuration for saving credentials.
    """

    id: str
    steps: list[AuthStep]
    persist: AuthPersist


class ServiceSpec(TypedDict):
    """Top-level structure of a `_service.yaml` file.

    This is the root type for a cliyard service definition. It describes
    the service metadata, server connection, authentication, and resources.

    Attributes:
        name: Service name identifier.
        version: Semver version string.
        description: Human-readable service description.
        server: Server connection configuration.
        auth: Authentication chain (can be empty steps list).
        resources: List of resource specifications.
    """

    name: str
    version: str
    description: str
    server: ServerConfig
    auth: AuthChain
    resources: list[ResourceSpec]


# ---------------------------------------------------------------------------
# Resource: per-resource YAML file
# ---------------------------------------------------------------------------


class ParamSpec(TypedDict, total=False):
    """Single parameter definition.

    Attributes:
        name: Parameter name.
        type: Parameter type: "string", "int", "float", "bool", "enum".
        required: Whether parameter is required (default: False).
        default: Default value if not required.
        description: Human-readable parameter description.
        choices: Allowed values for "enum" type parameters.
        depends_on: Dependencies on other parameters.
    """

    name: str
    type: str
    required: bool
    default: Any
    description: str
    choices: list[str]
    depends_on: dict[str, Any]


class ParamConfig(TypedDict, total=False):
    """Parameters organized by location.

    Attributes:
        path: Path parameters (e.g., /repos/{id}).
        query: Query string parameters.
        header: HTTP header parameters.
        body: Request body parameters.
    """

    path: list[ParamSpec]
    query: list[ParamSpec]
    header: list[ParamSpec]
    body: list[ParamSpec]


class HttpConfig(TypedDict):
    """HTTP request configuration.

    Attributes:
        method: HTTP method (GET, POST, PUT, DELETE).
        path: URL path (may include path parameters).
    """

    method: str
    path: str


class FieldSpec(TypedDict, total=False):
    """Field definition for output formatting.

    Attributes:
        name: Field name in the response.
        alias: Display alias for the field (optional).
    """

    name: str
    alias: str


class OutputSpec(TypedDict, total=False):
    """Output configuration for parsing API responses.

    Attributes:
        items_path: JSONPath to the list of items.
        total_path: JSONPath to total count (optional).
        fields: List of field definitions for output display.
    """

    items_path: str
    total_path: str
    fields: list[FieldSpec]


class MethodSpec(TypedDict, total=False):
    """Method definition within a resource.

    Attributes:
        http: HTTP request configuration.
        params: Parameters organized by location.
        output: Output configuration (optional).
        request_body: Request body template (optional).
    """

    http: HttpConfig
    params: ParamConfig
    output: OutputSpec
    request_body: dict[str, Any]


class ResourceSpec(TypedDict):
    """Resource YAML file top-level structure.

    This represents a single resource file (e.g., repos.yaml, users.yaml).
    It defines the resource path, description, available methods, and
    optional resource-level authentication.

    Attributes:
        description: Human-readable resource description.
        path: URL path segment for this resource.
        methods: Dict mapping method names to MethodSpec definitions.
        auth: Optional resource-level auth override.
    """

    description: str
    path: str
    methods: dict[str, MethodSpec]
    auth: AuthChain
