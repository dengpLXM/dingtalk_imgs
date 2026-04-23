import json
from datetime import datetime, date
from bson import ObjectId
from pymongo import MongoClient
from urllib.parse import quote_plus
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


def run_script(script_content: str, mongo_config: MongoConfig) -> tuple[object, dict]:
    """Returns (result, debug_info)."""
    uri = _build_uri(mongo_config)
    # mask password in debug output
    debug_uri = uri
    if mongo_config.password:
        debug_uri = uri.replace(quote_plus(mongo_config.password), "***")

    client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    try:
        db = client[mongo_config.database]
        collections = db.list_collection_names()
        local_vars: dict = {"db": db, "result": None}
        exec(script_content, {"__builtins__": __builtins__}, local_vars)  # noqa: S102
        result = local_vars.get("result")
        debug = {
            "uri": debug_uri,
            "database": mongo_config.database,
            "collections": collections,
            "result_type": type(result).__name__,
            "result_count": len(result) if isinstance(result, (list, dict)) else None,
        }
        return result, debug
    finally:
        client.close()


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
