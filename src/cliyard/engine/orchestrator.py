"""cliyard.engine.orchestrator — Sequential flow execution engine.

Executes flow definitions (:class:`~cliyard.engine.flow.FlowSpec`) by iterating
through steps sequentially, resolving Jinja2 templates at each step, delegating
to resource methods via the standard pipeline, and accumulating results.

Pipeline per step (matching :func:`~cliyard.engine.builder._make_callback`):

    1. **Resolve templates** — render ``{{ flow.xxx }}`` / ``{{ step.xxx }}``
    2. **Bind & validate** — via :func:`~cliyard.engine.binder.bind_and_validate`
    3. **Merge params** — group by HTTP location for the assembler
    4. **Assemble request** — via :func:`~cliyard.engine.assembler.assemble_request`
    5. **Execute HTTP** — via the shared :class:`~cliyard.client.http.HttpClient`
    6. **Parse response** — JSONPath extraction (if configured in the step)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from cliyard.engine.assembler import assemble_request
from cliyard.engine.binder import bind_and_validate
from cliyard.engine.errors import CliyError
from cliyard.engine.template import Template

# ---------------------------------------------------------------------------
# Flow context
# ---------------------------------------------------------------------------


@dataclass
class FlowContext:
    """Runtime context carried through all steps of a flow execution.

    Attributes:
        flow_params: Raw CLI argument values from Click (``**kwargs``).
        step_state: Accumulated step results keyed by ``step.id``.
        http_client: Shared, authenticated HTTP client for all step requests.
        console: ``rich.console.Console`` for user-facing output.
        service_spec: Full loaded service spec (for resource/method lookup).
        base_url: Base URL for the default server.
        prefix: URL prefix for the default server.
    """

    flow_params: dict = field(default_factory=dict)
    step_state: dict = field(default_factory=dict)
    http_client: Any = None
    console: Any = None
    service_spec: dict = field(default_factory=dict)
    base_url: str = ""
    prefix: str = ""


# ---------------------------------------------------------------------------
# Template resolver
# ---------------------------------------------------------------------------


def resolve_template(obj: Any, context: dict) -> Any:
    """Recursively resolve Jinja2 templates in a nested object.

    Strings containing ``{{`` are rendered via the sandboxed
    :class:`~cliyard.engine.template.Template` engine.  Dicts and lists
    are recursed. Non-string values pass through unchanged.

    Graceful degradation: if rendering fails (e.g. missing variable),
    the original string is returned unchanged.

    Args:
        obj: The object to resolve (str, dict, list, or scalar).
        context: Template variables (``{"flow": ..., "step": ...}``).

    Returns:
        The resolved object with all templates rendered.
    """
    if isinstance(obj, str):
        if "{{" not in obj:
            return obj
        try:
            return Template(obj).render(**context)
        except Exception:
            return obj
    elif isinstance(obj, dict):
        return {k: resolve_template(v, context) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [resolve_template(item, context) for item in obj]
    return obj


# ---------------------------------------------------------------------------
# Resource / method lookup
# ---------------------------------------------------------------------------


def _lookup_resource_method(
    use: str,
    service_spec: dict,
) -> tuple[dict, dict]:
    """Parse ``resource.method`` and return (resource_spec, method_spec).

    Args:
        use: Dot-separated ``"resource_name.method_name"``.
        service_spec: Full loaded service with a ``resources`` key.

    Returns:
        Tuple of ``(resource_spec, method_spec)``.

    Raises:
        ValueError: If the resource or method is not found.
    """
    parts = use.rsplit(".", 1)
    if len(parts) != 2:
        raise ValueError(
            f"Invalid 'use' format {use!r}: expected 'resource.method'"
        )

    resource_name, method_name = parts

    for resource in service_spec.get("resources", []):
        if resource.get("name") == resource_name:
            methods = resource.get("methods", {})
            if method_name not in methods:
                raise ValueError(
                    f"Method {method_name!r} not found in "
                    f"resource {resource_name!r}"
                )
            return resource, methods[method_name]

    raise ValueError(f"Resource {resource_name!r} not found in service spec")


# ---------------------------------------------------------------------------
# Template context builder
# ---------------------------------------------------------------------------


def _build_template_context(context: FlowContext) -> dict:
    """Build the Jinja2 template variable dict from flow context.

    Exposes:
    - ``flow`` — full flow_params dict
    - ``step`` — full step_state dict (step_id → result)
    - Individual step results as top-level keys (when scalar)

    Args:
        context: Current flow execution context.

    Returns:
        Dict of template variables.
    """
    ctx: dict = {
        "flow": context.flow_params,
        "step": context.step_state,
    }
    # Expose individual step results at top level for convenience
    for step_id, result in context.step_state.items():
        if isinstance(result, (str, int, float, bool)):
            ctx[step_id] = result
    return ctx


# ---------------------------------------------------------------------------
# Step execution
# ---------------------------------------------------------------------------


def execute_use_step(
    step,
    resolved_params: dict,
    context: FlowContext,
) -> dict:
    """Execute a ``use: resource.method`` step through the pipeline.

    Pipeline stages (mirrors ``_make_callback()`` in builder.py):

    1. Look up ``resource.method`` in service_spec
    2. Bind & validate params via ``bind_and_validate()``
    3. Merge params grouped by HTTP location
    4. Assemble HTTP request via ``assemble_request()``
    5. Execute via ``context.http_client.request()``
    6. Parse response (JSONPath extraction if ``step.extract`` is set)

    Args:
        step: :class:`~cliyard.engine.flow.FlowStep` dataclass instance.
        resolved_params: Step parameters after template resolution.
        context: :class:`FlowContext` with shared client and service data.

    Returns:
        Parsed response data (typically a ``dict``).

    Raises:
        CliyError: If any pipeline stage fails.
    """
    try:
        # --- Stage 1-2: Look up resource & method specs ---
        resource_spec, method_spec = _lookup_resource_method(
            step.use, context.service_spec
        )

        # Ensure http.path falls back to resource path (matching builder.py)
        if not method_spec.get("http", {}).get("path"):
            method_spec.setdefault("http", {})["path"] = resource_spec.get(
                "path", resource_spec.get("name", "")
            )

        # --- Stage 3: Bind & validate ---
        validated = bind_and_validate(resolved_params, method_spec)

        # --- Stage 4: Merge params (matching builder.py pattern) ---
        merged: dict[str, Any] = {}
        for loc in ("query", "body", "header"):
            merged[loc] = getattr(validated, loc)
        merged["path"] = getattr(validated, "path")
        merged.update(getattr(validated, "path"))
        merged.update(getattr(validated, "body"))
        merged.update(getattr(validated, "argument"))

        # Merge auth-injected headers into merged params
        if context.http_client and context.http_client.default_headers:
            merged.setdefault("header", {})
            if isinstance(merged.get("header"), dict):
                merged["header"].update(context.http_client.default_headers)

        # Resolve resource-level server config (per-resource overrides)
        base_url = context.base_url
        prefix = context.prefix
        resource_server_name = resource_spec.get("server", "")
        if resource_server_name:
            servers = context.service_spec.get("servers", {})
            srv = servers.get(resource_server_name, {})
            if srv:
                base_url = srv.get("base_url", base_url)
                prefix = srv.get("prefix", prefix)

        # --- Stage 5: Assemble HTTP request ---
        req = assemble_request(
            method_spec,
            merged,
            base_url=base_url,
            prefix=prefix,
        )

        # --- Stage 6: Execute HTTP request ---
        _timeout = method_spec.get("http", {}).get("timeout", 30)
        response = context.http_client.request(
            method=req.method,
            url=req.url,
            data=req.body,
            query_params=req.query_params,
            headers=req.headers,
            timeout=_timeout,
        )

        # --- Stage 7: Parse response ---
        resp_data = response.json()

        # Extract specific fields if configured in step.extract
        if step.extract:
            import jsonpath_ng as _jp

            extracted: dict[str, Any] = {}
            for field_name, json_path in step.extract.items():
                try:
                    expr = _jp.parse(json_path)
                    matches = expr.find(resp_data)
                    extracted[field_name] = (
                        matches[0].value if matches else None
                    )
                except Exception:
                    extracted[field_name] = None
            return extracted

        return resp_data

    except CliyError:
        raise
    except Exception as e:
        raise CliyError(f"Step {step.id!r} failed: {e}") from e


# ---------------------------------------------------------------------------
# Flow runner
# ---------------------------------------------------------------------------


def run_flow(
    flow_spec,
    flow_params: dict,
    service_ctx,
    service_spec: dict,
) -> None:
    """Execute a flow definition sequentially.

    Creates a shared :class:`~cliyard.client.http.HttpClient`, runs the
    auth chain if the service has one, then iterates through each step:

    * Resolves step params via ``{{ flow.* }}`` / ``{{ step.* }}``
    * Delegates ``use:`` steps to :func:`execute_use_step`
    * Stores results in ``step_state[step.id]``
    * Prints progress and error messages via ``rich.console.Console``

    Args:
        flow_spec: :class:`~cliyard.engine.flow.FlowSpec` with ``steps``.
        flow_params: CLI argument dict from Click (``**kwargs``).
        service_ctx: :class:`~cliyard.engine.builder.ServiceContext` with
            ``base_url``, ``prefix``, ``auth_spec``, ``pre_filled_auth``.
        service_spec: Full loaded service dict (for resource/method lookup).

    Raises:
        CliyError: If any step fails (flow is aborted).
    """
    from rich.console import Console

    from cliyard.client.auth import run_auth_chain
    from cliyard.client.http import HttpClient

    console = Console()

    # Create shared HTTP client
    client = HttpClient(service_ctx.base_url, timeout=service_ctx.timeout)

    # Run auth chain if configured
    if service_ctx.auth_spec:
        console.print("[dim]Authenticating...[/dim]")
        run_auth_chain(
            service_ctx.auth_spec,
            http_client=client,
            pre_filled=service_ctx.pre_filled_auth,
        )

    # Build flow context
    context = FlowContext(
        flow_params=flow_params,
        http_client=client,
        console=console,
        service_spec=service_spec,
        base_url=service_ctx.base_url,
        prefix=service_ctx.prefix,
    )

    # Execute steps sequentially
    for step in flow_spec.steps:
        label = step.description or step.id
        console.print(f"[blue]→[/blue] {label}")

        try:
            # Build template context from accumulated state
            template_ctx = _build_template_context(context)

            # Resolve step params (render {{ flow.* }} / {{ step.* }})
            resolved = resolve_template(step.params, template_ctx)

            if step.use:
                result = execute_use_step(step, resolved, context)
            else:
                # No use target — store resolved params directly
                result = resolved

            # Store result in step_state for subsequent steps
            context.step_state[step.id] = result

        except CliyError as e:
            _msg = str(e).replace("[", "[[]").replace("]", "[]]")
            console.print(f"[red]✗ Step {step.id!r} failed:[/red] {_msg}")
            return
        except Exception as e:
            _msg = str(e).replace("[", "[[]").replace("]", "[]]")
            console.print(f"[red]✗ Step {step.id!r} failed:[/red] {_msg}")
            return

    console.print("[green]✓ Flow completed successfully[/green]")
