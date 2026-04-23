"""Default HTML report template with blue-theme table style."""

DEFAULT_STYLES = """
body {
    margin: 0;
    padding: 30px 40px;
    background: linear-gradient(160deg, #0b1a3b 0%, #102050 40%, #0b1a3b 100%);
    color: #fff;
    font-family: "PingFang SC", "Microsoft YaHei", "Noto Sans SC", sans-serif;
    min-height: 100vh;
    box-sizing: border-box;
}
.report-container {
    max-width: 920px;
    margin: 0 auto;
}
.report-title {
    text-align: center;
    font-size: 26px;
    font-weight: 700;
    color: #fff;
    letter-spacing: 3px;
    margin-bottom: 18px;
}
table {
    width: 100%;
    border-collapse: collapse;
    border: 2px solid #1c3d7a;
}
th {
    background: #0c1d42;
    color: #d4a017;
    padding: 13px 18px;
    text-align: center;
    font-size: 18px;
    font-weight: 700;
    border: 1px solid #1c3d7a;
}
td {
    padding: 11px 18px;
    text-align: center;
    font-size: 16px;
    color: #fff;
    border: 1px solid #1c3d7a;
    background: #0f2a55;
}
.region-cell {
    color: #d4a017;
    font-weight: 700;
    font-size: 18px;
    background: #0c1d42 !important;
    vertical-align: middle;
}
.highlight {
    color: #d4a017;
    font-weight: 700;
}
.frame {
    border: 3px solid rgba(255,215,0,0.6);
    border-radius: 12px;
    padding: 40px 36px 30px;
    position: relative;
}
.title {
    text-align: center;
    font-size: 42px;
    font-weight: 700;
    color: #FFD700;
    text-shadow: 2px 2px 8px rgba(0,0,0,0.6);
    margin-bottom: 8px;
}
.date-line {
    text-align: center;
    font-size: 18px;
    color: #ccc;
    margin-bottom: 24px;
}
.divider {
    text-align: center;
    margin: 20px 0;
    position: relative;
}
.divider::before, .divider::after {
    content: "";
    display: inline-block;
    width: 35%;
    border-top: 1px solid rgba(255,215,0,0.4);
    vertical-align: middle;
}
.divider-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    background: rgba(255,215,0,0.5);
    border-radius: 50%;
    margin: 0 12px;
    vertical-align: middle;
}
.metrics {
    display: flex;
    flex-wrap: wrap;
    gap: 14px;
    justify-content: center;
    margin: 20px 0;
}
.metric-card {
    background: rgba(15,42,85,0.85);
    border-radius: 10px;
    padding: 16px 24px 12px;
    min-width: 200px;
    text-align: center;
    flex: 1;
    max-width: 260px;
    position: relative;
    overflow: hidden;
}
.metric-card::before {
    content: "";
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 4px;
    background: #1c3d7a;
    border-radius: 10px 10px 0 0;
}
.metric-value {
    font-size: 32px;
    font-weight: 700;
    color: #d4a017;
    text-shadow: 1px 1px 4px rgba(0,0,0,0.5);
    margin-bottom: 6px;
}
.metric-label {
    font-size: 16px;
    color: #bbb;
}
.footer-section {
    margin-top: 24px;
    text-align: center;
}
.footer-line {
    font-size: 22px;
    margin: 8px 0;
}
.footer-line:first-child {
    color: #d4a017;
    font-weight: 700;
    font-size: 24px;
}
.footer-line:not(:first-child) {
    color: #ddd;
}
.bottom-strip {
    margin-top: 30px;
    text-align: center;
    padding: 14px 0;
    font-size: 20px;
    font-weight: 700;
    color: #FFF0B4;
    background: linear-gradient(180deg, rgba(12,29,66,0.8), rgba(8,18,42,0.95));
    border-radius: 8px;
    text-shadow: 1px 1px 3px rgba(0,0,0,0.5);
}
"""


def wrap_html(body_html: str) -> str:
    """Wrap body HTML into a full document with default styles."""
    import datetime
    now = datetime.datetime.now()
    date_str = now.strftime("%Y年%m月%d日  %H:%M 播报")

    # inject date placeholder if not present
    body = body_html.replace("{{REPORT_DATE}}", date_str)

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
{DEFAULT_STYLES}
</style>
</head>
<body>
{body}
</body>
</html>"""
