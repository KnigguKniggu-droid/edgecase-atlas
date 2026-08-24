"""Typer CLI for local Atlas generation, replay, and offline reporting."""

from __future__ import annotations

import asyncio
import importlib
import importlib.util
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from types import ModuleType
from typing import Annotated, NoReturn, cast

import typer
import yaml
from jinja2 import TemplateError
from pydantic import ValidationError

from edgecase_atlas import __version__
from edgecase_atlas.adapters import (
    AdapterError,
    DecisionCallable,
    FunctionAdapter,
    JsonlSubprocessAdapter,
    OpenAICompatibleAdapter,
)
from edgecase_atlas.comparison import compare_run_documents, render_comparison_html
from edgecase_atlas.config import (
    DEFAULT_CONFIG_YAML,
    AtlasConfig,
    OpenAIAdapterConfig,
    PythonAdapterConfig,
    SubprocessAdapterConfig,
    load_config,
)
from edgecase_atlas.engine import (
    AtlasEngine,
    _engine_config_hash,
    _property_digest,
    recompute_certificate_id,
)
from edgecase_atlas.evaluation import (
    AgentAdapter,
    CallLedger,
    ReproductionResult,
    SeedStreams,
    adapter_model_id,
    evaluate_suspected_violation,
    model_config_hash,
)
from edgecase_atlas.fixtures import FaultyDemonstrationAgent
from edgecase_atlas.metadrive_export import export_metadrive_abstract
from edgecase_atlas.models import Counterfactual, FailureCertificate
from edgecase_atlas.properties import (
    CONFIRMATION_TRIALS,
    REQUIRED_REPRODUCTIONS,
    STARTER_PROPERTY_PACK,
    SafetyProperty,
)
from edgecase_atlas.reporting import render_html_report
from edgecase_atlas.serialization import (
    load_json,
    run_document,
    trace_events,
    validate_run_document,
    write_canonical_json,
    write_jsonl,
)

_RUN_ID = re.compile(r"^run-[0-9a-f]{16}$")
app = typer.Typer(
    name="atlas",
    help="Constraint-guided counterfactual testing for simulated driving-decision agents.",
    no_args_is_help=True,
    add_completion=False,
)


@app.command("init")
def init_command(
    path: Annotated[Path, typer.Option("--path", help="Configuration file to create.")] = Path(
        "atlas.yaml"
    ),
    force: Annotated[bool, typer.Option("--force", help="Replace existing configuration.")] = False,
) -> None:
    """Create a safe no-key demonstration configuration."""
    if path.exists() and not force:
        _fail(f"Configuration already exists: {path}. Use --force to replace it.")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(DEFAULT_CONFIG_YAML, encoding="utf-8", newline="\n")
    except OSError:
        _fail("Atlas init failed. Filesystem details are not printed.")
    typer.echo(f"Created {path}")


@app.command("validate")
def validate_command(
    path: Annotated[Path, typer.Argument(help="Strict Atlas YAML configuration.")] = Path(
        "atlas.yaml"
    ),
) -> None:
    """Validate configuration without resolving its API key environment variable."""
    config = _load_config_or_exit(path)
    typer.echo(f"Valid atlas-config-v1 configuration for adapter kind: {config.adapter.kind}")


@app.command("test")
def test_command(
    config_path: Annotated[
        Path, typer.Option("--config", help="Strict Atlas YAML configuration.")
    ] = Path("atlas.yaml"),
    budget: Annotated[int, typer.Option("--budget", min=1, max=100_000)] = 100,
    seed: Annotated[int, typer.Option("--seed", min=0)] = 42,
) -> None:
    """Write canonical run, trace, certificate, and HTML artifacts."""
    config = _load_config_or_exit(config_path)
    try:
        paths = asyncio.run(_run_test(config, budget=budget, seed=seed))
    except (
        AdapterError,
        ImportError,
        AttributeError,
        TemplateError,
        OSError,
        TypeError,
        ValueError,
    ):
        _fail("Atlas test failed. Target details and secrets are not printed.")
    typer.echo(f"Run: {paths['run']}")
    typer.echo(f"Trace: {paths['trace']}")
    typer.echo(f"Report: {paths['report']}")
    typer.echo(f"Certificates: {paths['certificate_count']}")
    if paths["certificate_count"] == 0:
        typer.echo(
            "No repeatable failure was found under this budget, seed, and property selection. "
            "That is not evidence that the agent is safe. A suspected failure that passed the "
            "repeatability gate is still discarded if it stops reproducing while being "
            "minimized, so this can also mean a real but unstable finding was dropped."
        )


@app.command("gate")
def gate_command(
    config_path: Annotated[
        Path, typer.Option("--config", help="Strict Atlas YAML configuration.")
    ] = Path("atlas.yaml"),
    budget: Annotated[int, typer.Option("--budget", min=1, max=100_000)] = 100,
    seed: Annotated[int, typer.Option("--seed", min=0)] = 42,
) -> None:
    """Write all test artifacts and fail CI when a certificate is found."""
    config = _load_config_or_exit(config_path)
    try:
        paths = asyncio.run(_run_test(config, budget=budget, seed=seed))
    except (
        AdapterError,
        ImportError,
        AttributeError,
        TemplateError,
        OSError,
        TypeError,
        ValueError,
    ):
        _fail("Atlas gate failed. Target details and secrets are not printed.")
    typer.echo(f"Run: {paths['run']}")
    typer.echo(f"Trace: {paths['trace']}")
    typer.echo(f"Report: {paths['report']}")
    certificate_count = paths["certificate_count"]
    if not isinstance(certificate_count, int) or isinstance(certificate_count, bool):
        _fail("Atlas gate failed. Certificate accounting is invalid.")
    typer.echo(f"Certificates: {certificate_count}")
    if certificate_count > 0:
        typer.echo(
            "Atlas gate rejected this run because failure certificates were found.", err=True
        )
        raise typer.Exit(code=1)


@app.command("replay")
def replay_command(
    certificate_path: Path,
    config_path: Annotated[
        Path, typer.Option("--config", help="Configuration used to re-evaluate the certificate.")
    ] = Path("atlas.yaml"),
) -> None:
    """Re-evaluate a minimized pair using its recorded alpha shrink seeds."""
    config = _load_config_or_exit(config_path)
    try:
        certificate = FailureCertificate.model_validate_json(
            certificate_path.read_text(encoding="utf-8")
        )
        result = asyncio.run(_replay(config, certificate))
    except (
        OSError,
        ValidationError,
        AdapterError,
        ImportError,
        AttributeError,
        TypeError,
        ValueError,
    ):
        _fail("Atlas replay failed. Evidence or configuration did not match.")
    typer.echo(
        f"Reproduced {result.reproduction_count}/{result.reproduction_trials} "
        f"with {result.phase} seeds."
    )


@app.command("report")
def report_command(
    run_path: Path,
    format_name: Annotated[str, typer.Option("--format")] = "html",
) -> None:
    """Render a standalone offline report from canonical run JSON."""
    if format_name.casefold() != "html":
        _fail("Only --format html is supported in alpha 0.1.")
    try:
        document = validate_run_document(load_json(run_path))
        if not isinstance(document, Mapping):
            raise TypeError("Run document must be a mapping")
        metadata = document.get("metadata")
        if not isinstance(metadata, Mapping):
            raise TypeError("Run metadata must be a mapping")
        run_id = str(metadata["run_id"])
        if not _RUN_ID.fullmatch(run_id):
            raise ValueError("Run ID is not a canonical Atlas identifier")
        output = Path("reports") / f"{run_id}.html"
        render_html_report(document, output)
    except (OSError, KeyError, TemplateError, TypeError, ValueError):
        _fail("Atlas report failed. The run artifact is invalid.")
    typer.echo(f"Report: {output}")


@app.command("compare")
def compare_command(
    run_a: Path,
    run_b: Path,
    format_name: Annotated[str, typer.Option("--format")] = "json",
) -> None:
    """Compare two compatible canonical run artifacts."""
    format_name = format_name.casefold()
    if format_name not in {"json", "html"}:
        _fail("Only --format json and --format html are supported.")
    try:
        comparison = compare_run_documents(load_json(run_a), load_json(run_b))
        runs = comparison["runs"]
        if not isinstance(runs, Mapping):
            raise TypeError("Comparison run identifiers are invalid")
        run_a_id, run_b_id = str(runs["a"]), str(runs["b"])
        if not _RUN_ID.fullmatch(run_a_id) or not _RUN_ID.fullmatch(run_b_id):
            raise ValueError("Comparison run identifiers are invalid")
        output = Path("comparisons") / f"{run_a_id}-vs-{run_b_id}.{format_name}"
        if format_name == "json":
            write_canonical_json(output, comparison)
        else:
            render_comparison_html(comparison, output)
    except (OSError, KeyError, TypeError, ValueError):
        _fail("Atlas compare failed. Run artifacts are invalid or incompatible.")
    typer.echo(f"Comparison: {output}")


@app.command("export-metadrive")
def export_metadrive_command(
    certificate_path: Path,
    output: Annotated[Path, typer.Option("--output")],
) -> None:
    """Export verified abstract evidence for later reviewed MetaDrive construction."""
    try:
        certificate = FailureCertificate.model_validate_json(
            certificate_path.read_text(encoding="utf-8")
        )
        write_canonical_json(output, export_metadrive_abstract(certificate))
    except (OSError, ValidationError, TypeError, ValueError):
        _fail("Atlas MetaDrive export failed. The certificate is invalid or unsupported.")
    typer.echo(f"Export: {output}")


async def _run_test(config: AtlasConfig, *, budget: int, seed: int) -> dict[str, object]:
    adapter = _build_adapter(config)
    try:
        run = await AtlasEngine().run(
            adapter, _selected_properties(config), seed=seed, budget=budget
        )
    finally:
        await _close_adapter(adapter)
    document = run_document(run)
    run_id = run.metadata.run_id
    run_path = write_canonical_json(Path("runs") / f"{run_id}.json", document)
    trace_path = write_jsonl(Path("traces") / f"{run_id}.jsonl", trace_events(run))
    for item in run.certificates:
        write_canonical_json(
            Path("certificates") / f"{item.certificate.certificate_id}.json", item.certificate
        )
    report_path = render_html_report(document, Path("reports") / f"{run_id}.html")
    return {
        "run": run_path,
        "trace": trace_path,
        "report": report_path,
        "certificate_count": len(run.certificates),
    }


async def _replay(config: AtlasConfig, certificate: FailureCertificate) -> ReproductionResult:
    canonical_command = f"atlas replay certificates/{certificate.certificate_id}.json"
    if certificate.replay_command != canonical_command:
        raise ValueError("Certificate replay command is not canonical")
    adapter = _build_adapter(config)
    try:
        property_ = _property_by_id(certificate.property_id)
        if certificate.reproduction_trials != CONFIRMATION_TRIALS:
            raise ValueError("Alpha replay requires exactly five recorded trials")
        if recompute_certificate_id(certificate) != certificate.certificate_id:
            raise ValueError("Certificate content digest does not match its identifier")
        if certificate.property_id not in config.property_ids:
            raise ValueError("Certificate property is not enabled by the configuration")
        if adapter_model_id(adapter) != certificate.model_id:
            raise ValueError("Configured model ID does not match the certificate")
        if model_config_hash(adapter) != certificate.model_config_hash:
            raise ValueError("Configured model hash does not match the certificate")
        if certificate.software_version != __version__:
            raise ValueError("Software version does not match the certificate")
        if certificate.engine_config_hash != _engine_config_hash():
            raise ValueError("Engine configuration does not match the certificate")
        if certificate.property_semantics_digest != _property_digest(property_):
            raise ValueError("Property semantics do not match the certificate")
        relation = Counterfactual(
            source=certificate.source,
            follow_up=certificate.minimized_follow_up,
            changed_fields=certificate.changed_fields,
            relation_id=certificate.relation_id,
        )
        seeds = SeedStreams(certificate.seed).shrink_seeds(5)
        return await evaluate_suspected_violation(
            adapter,
            property_,
            relation,
            seeds,
            CallLedger(),
            phase="minimization",
            required_reproductions=REQUIRED_REPRODUCTIONS,
        )
    finally:
        await _close_adapter(adapter)


def _import_agent_module(name: str) -> ModuleType:
    """Import a configured agent module, preferring an installed one over a local file.

    The installed ``atlas`` console script does not place the working directory on
    ``sys.path``, so a plain import cannot see the ``agent.py`` that sits beside the user's
    ``atlas.yaml``. Every other CLI path already resolves against the working directory, so
    the local file is looked up there too. An installed module still wins, which keeps a
    packaged agent working unchanged.

    Only a miss on this exact module falls through; a ``ModuleNotFoundError`` raised by the
    user's own imports propagates so a missing dependency is never reported as a missing agent.
    Local resolution executes the named file, which is the documented purpose of the Python
    adapter. It is a local CLI capability only and is never reachable from the hosted app.
    """
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError as error:
        if error.name != name:
            raise
    candidate = Path.cwd().joinpath(*name.split(".")).with_suffix(".py")
    if not candidate.is_file():
        raise ModuleNotFoundError(f"No module named {name!r}", name=name)
    specification = importlib.util.spec_from_file_location(name, candidate)
    if specification is None or specification.loader is None:
        raise ModuleNotFoundError(f"No module named {name!r}", name=name)
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


def _build_adapter(config: AtlasConfig) -> AgentAdapter:
    adapter_config = config.adapter
    if adapter_config.kind == "faulty":
        return FaultyDemonstrationAgent()
    if isinstance(adapter_config, PythonAdapterConfig):
        target = getattr(_import_agent_module(adapter_config.module), adapter_config.callable)
        if not callable(target):
            raise TypeError("Configured Python target is not callable")
        return FunctionAdapter(
            cast(DecisionCallable, target), timeout_seconds=adapter_config.timeout_seconds
        )
    if isinstance(adapter_config, SubprocessAdapterConfig):
        return JsonlSubprocessAdapter(
            adapter_config.command,
            timeout_seconds=adapter_config.timeout_seconds,
            shutdown_timeout_seconds=adapter_config.shutdown_timeout_seconds,
            stderr_limit_bytes=adapter_config.stderr_limit_bytes,
            model_id=adapter_config.model_id,
        )
    if isinstance(adapter_config, OpenAIAdapterConfig):
        return OpenAICompatibleAdapter(
            base_url=adapter_config.base_url,
            model=adapter_config.model,
            api_key_env=adapter_config.api_key_env,
            network_enabled=adapter_config.network_enabled,
            timeout_seconds=adapter_config.timeout_seconds,
            max_retries=adapter_config.max_retries,
            retry_backoff_seconds=adapter_config.retry_backoff_seconds,
            input_cost_per_million_tokens=adapter_config.input_cost_per_million_tokens,
            output_cost_per_million_tokens=adapter_config.output_cost_per_million_tokens,
            input_token_reservation=adapter_config.input_token_reservation,
            max_tokens=adapter_config.max_tokens,
            cost_cap_usd=adapter_config.cost_cap_usd,
        )
    raise TypeError("Unsupported adapter configuration")


async def _close_adapter(adapter: AgentAdapter) -> None:
    close = getattr(adapter, "aclose", None)
    if close is not None:
        await close()


def _selected_properties(config: AtlasConfig) -> tuple[SafetyProperty, ...]:
    properties = {item.property_id: item for item in STARTER_PROPERTY_PACK}
    return tuple(properties[property_id] for property_id in config.property_ids)


def _property_by_id(property_id: str) -> SafetyProperty:
    for item in STARTER_PROPERTY_PACK:
        if item.property_id == property_id:
            return item
    raise ValueError("Certificate references an unknown property")


def _load_config_or_exit(path: Path) -> AtlasConfig:
    try:
        return load_config(path)
    except (OSError, ValidationError, yaml.YAMLError, ValueError):
        _fail("Configuration is invalid. Secret values are never printed.")


def _fail(message: str) -> NoReturn:
    typer.echo(message, err=True)
    raise typer.Exit(code=2)
