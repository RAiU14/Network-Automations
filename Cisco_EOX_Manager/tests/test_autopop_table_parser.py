from __future__ import annotations

from tools.auto_pop_pid_database import _parse_announcement_tables_from_html, _records_from_full_announcement


HTML = """
<html>
  <body>
    <h1>End-of-Sale and End-of-Life Announcement for Cisco Sample</h1>
    <h2>Milestones</h2>
    <table>
      <tr><th>Milestone</th><th>Definition</th><th>Date</th></tr>
      <tr><td>End-of-Sale Date</td><td>Final order date</td><td>January 31, 2027</td></tr>
      <tr><td>Last Date of Support</td><td>Final support date</td><td>January 31, 2032</td></tr>
    </table>
    <h2>Affected Product IDs</h2>
    <table>
      <tr><th>End-of-Sale Product Part Number</th><th>Product Description</th><th>Replacement Product Part Number</th></tr>
      <tr><td>C9300-24T</td><td>Catalyst 9300 24-port data only</td><td>C9300-24T-A</td></tr>
      <tr><td>C9300-48P, C9300-48T</td><td>Catalyst 9300 48-port models</td><td>C9300-48P-A</td></tr>
    </table>
  </body>
</html>
"""


def test_full_table_parser_preserves_all_tables() -> None:
    parsed = _parse_announcement_tables_from_html("https://example.test/eox", HTML)
    assert parsed["title"] == "End-of-Sale and End-of-Life Announcement for Cisco Sample"
    assert parsed["table_count"] == 2
    assert parsed["tables"][1]["headers"] == [
        "End-of-Sale Product Part Number",
        "Product Description",
        "Replacement Product Part Number",
    ]


def test_records_from_full_announcement_map_every_affected_pid() -> None:
    parsed = _parse_announcement_tables_from_html("https://example.test/eox", HTML)
    records = _records_from_full_announcement(
        announcement_data=parsed,
        announcement_name="Sample Announcement",
        announcement_url="https://example.test/eox",
        technology="Switches",
        series_name="Catalyst 9300 Series",
        series_url="https://example.test/series",
        birth_certificate={},
        series_record={"pid": "Catalyst 9300 Series", "product_url": "https://example.test/series"},
    )
    pids = {record["pid"] for record in records}
    assert {"C9300-24T", "C9300-48P", "C9300-48T"}.issubset(pids)
    first = next(record for record in records if record["pid"] == "C9300-24T")
    assert first["payload"]["End-of-Sale Date"] == "January 31, 2027"
    assert first["payload"]["Last Date of Support"] == "January 31, 2032"
    assert first["payload"]["affected_product_row"]["columns"]["Product Description"] == "Catalyst 9300 24-port data only"
    assert len(first["payload"]["announcement_tables"]) == 2
