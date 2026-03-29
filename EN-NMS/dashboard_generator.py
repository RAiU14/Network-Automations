import sqlite3
import jinja2
from pathlib import Path

def generate_static(config):
    db_path = config['database']['path']
    static_dir = Path(config['static']['output_dir'])
    static_dir.mkdir(parents=True, exist_ok=True)

    assets_dir = static_dir / 'assets'
    assets_dir.mkdir(exist_ok=True)
    (assets_dir / 'style.css').write_text('''\
body { font-family: sans-serif; margin: 2em; }
table { border-collapse: collapse; width: 100%; }
th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
th { background-color: #f2f2f2; }
''')

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    template_dir = Path(config['templates']['dir'])
    env = jinja2.Environment(loader=jinja2.FileSystemLoader(template_dir))

    cursor.execute("SELECT COUNT(*) FROM devices")
    total = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(DISTINCT device_id) FROM metrics WHERE metric_name='sysUpTime' AND value IS NOT NULL")
    up = cursor.fetchone()[0]
    html = env.get_template("index.html.j2").render(total=total, up=up)
    (static_dir / "index.html").write_text(html)

    cursor.execute("SELECT id, name, ip FROM devices")
    devices = cursor.fetchall()
    html = env.get_template("devices.html.j2").render(devices=devices)
    (static_dir / "devices.html").write_text(html)

    for dev_id, name, ip in devices:
        cursor.execute("SELECT metric_name, value, polled_at FROM metrics WHERE device_id=? ORDER BY polled_at DESC LIMIT 10", (dev_id,))
        metrics = cursor.fetchall()
        html = env.get_template("device_detail.html.j2").render(device_id=dev_id, name=name, ip=ip, metrics=metrics)
        (static_dir / f"device_{dev_id}.html").write_text(html)

    conn.close()
    print(f"Static dashboard generated in {static_dir}")

if __name__ == "__main__":
    import yaml
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)
    generate_static(config)