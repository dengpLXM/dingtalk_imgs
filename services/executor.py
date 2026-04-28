import json
from datetime import datetime, date
from bson import ObjectId
from pymongo import MongoClient
from urllib.parse import quote_plus
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from models import MongoConfig


class _JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        if isinstance(o, ObjectId):
            return str(o)
        return super().default(o)


def _build_uri(cfg: MongoConfig) -> str:
    if cfg.uri:
        return cfg.uri
    if cfg.db_type == "mysql":
        return str(
            URL.create(
                "mysql+pymysql",
                username=cfg.username or None,
                password=cfg.password or None,
                host=cfg.host,
                port=cfg.port or 3306,
                database=cfg.database,
            )
        )
    if cfg.db_type == "pgsql":
        return str(
            URL.create(
                "postgresql+psycopg2",
                username=cfg.username or None,
                password=cfg.password or None,
                host=cfg.host,
                port=cfg.port or 5432,
                database=cfg.database,
            )
        )
    if cfg.username and cfg.password:
        auth = f"{quote_plus(cfg.username)}:{quote_plus(cfg.password)}@"
        auth_source = cfg.auth_source or "admin"
    else:
        auth = ""
        auth_source = cfg.auth_source or None
    uri = f"mongodb://{auth}{cfg.host}:{cfg.port}/{cfg.database}"
    if auth_source:
        uri += f"?authSource={auth_source}"
    return uri


def _mask_uri(uri: str, cfg: MongoConfig) -> str:
    if cfg.password and quote_plus(cfg.password) in uri:
        return uri.replace(quote_plus(cfg.password), "***")
    if cfg.password and cfg.password in uri:
        return uri.replace(cfg.password, "***")
    return uri


def _build_mongodb_python(script_content: str) -> str:
    return (
        "# Auto generated from mongodb query script\n"
        "result = None\n"
        f"{script_content.strip()}\n"
    )


def _build_sql_python(script_content: str) -> str:
    query = script_content.strip()
    query_json = json.dumps(query, ensure_ascii=False)
    return (
        "# Auto generated from SQL query script\n"
        f"query = {query_json}\n"
        "stmt = text(query)\n"
        "res = conn.execute(stmt)\n"
        "result = [dict(row._mapping) for row in res]\n"
    )


def _build_python_script(script_content: str, script_format: str) -> str:
    fmt = (script_format or "mongodb").lower()
    if fmt == "mongodb":
        return _build_mongodb_python(script_content)
    if fmt in {"mysql", "pgsql"}:
        return _build_sql_python(script_content)
    raise ValueError(f"不支持的脚本格式: {script_format}")


def _run_mongodb_script(
    mongo_config: MongoConfig,
    generated_python: str,
    debug_uri: str,
) -> tuple[object, dict]:
    client = MongoClient(_build_uri(mongo_config), serverSelectionTimeoutMS=10000)
    try:
        db = client[mongo_config.database]
        collections = db.list_collection_names()
        local_vars: dict = {"db": db, "result": None}
        exec(generated_python, {"__builtins__": __builtins__}, local_vars)  # noqa: S102
        result = local_vars.get("result")
        debug = {
            "uri": debug_uri,
            "database": mongo_config.database,
            "db_type": "mongodb",
            "collections": collections,
            "generated_python": generated_python,
            "result_type": type(result).__name__,
            "result_count": len(result) if isinstance(result, (list, dict)) else None,
        }
        return result, debug
    finally:
        client.close()


def _run_sql_script(
    mongo_config: MongoConfig,
    generated_python: str,
    debug_uri: str,
) -> tuple[object, dict]:
    engine = create_engine(_build_uri(mongo_config), future=True)
    try:
        with engine.connect() as conn:
            local_vars = {"conn": conn, "text": text, "result": None}
            exec(generated_python, {"__builtins__": __builtins__}, local_vars)  # noqa: S102
            result = local_vars.get("result")
            debug = {
                "uri": debug_uri,
                "database": mongo_config.database,
                "db_type": mongo_config.db_type,
                "generated_python": generated_python,
                "result_type": type(result).__name__,
                "result_count": len(result) if isinstance(result, list) else None,
            }
            return result, debug
    finally:
        engine.dispose()


def run_script(
    script_content: str,
    mongo_config: MongoConfig,
    script_format: str = "mongodb",
) -> tuple[object, dict]:
    """Returns (result, debug_info)."""
    uri = _build_uri(mongo_config)
    debug_uri = _mask_uri(uri, mongo_config)
    fmt = (script_format or mongo_config.db_type or "mongodb").lower()
    generated_python = _build_python_script(script_content, fmt)
    if fmt == "mongodb":
        return _run_mongodb_script(mongo_config, generated_python, debug_uri)
    if fmt in {"mysql", "pgsql"}:
        return _run_sql_script(mongo_config, generated_python, debug_uri)
    raise ValueError(f"不支持的脚本格式: {script_format}")


def format_result(result: object) -> str:
    return json.dumps(result, ensure_ascii=False, indent=2, cls=_JSONEncoder)


def render_template(template: str, result: object) -> str:
    from jinja2 import Template, StrictUndefined
    result_str = format_result(result)
    ctx: dict = {"result": result, "result_json": result_str}
    if isinstance(result, dict):
        ctx.update(result)
    elif isinstance(result, list) and result and isinstance(result[0], dict):
        ctx["items"] = result
    tmpl = Template(template, undefined=StrictUndefined)
    return tmpl.render(**ctx)


def render_html_template(template: str, result: object) -> str:
    """Render Jinja2 template as HTML, wrap in full document if needed."""
    from services.html_template import wrap_html
    rendered = render_template(template, result)
    if "<html" in rendered.lower() or "<body" in rendered.lower():
        return rendered
    return wrap_html(rendered)
