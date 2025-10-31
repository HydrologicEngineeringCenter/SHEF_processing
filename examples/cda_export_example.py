import os
from datetime import datetime, timedelta
from io import StringIO

from shef.exporters import CdaExporter

exporter = CdaExporter(os.getenv("cda_api_root", ""), "SWT")
# ---------------------------------------- #
# export an entire group for a time window #
# ---------------------------------------- #
exporter.end_time = datetime.now()
exporter.start_time = exporter.end_time - timedelta(days=7)
group_id = "KEYS"
print(
    f"==> Exporting group {group_id} for office {exporter._office} for time window = {exporter.start_time}, {exporter.end_time}"
)
exporter.export(group_id)
# --------------------------------------------------------- #
# print all the SHEF Export groups for the specified office #
# --------------------------------------------------------- #
print(f"==> group IDs and descriptions for office {exporter._office}")
groups = exporter.get_groups()
for group_name in groups:
    print(f"{group_name}\t{groups[group_name]}")
# ----------------------------- #
# export individual time series #
# ----------------------------- #
exporter.start_time = exporter.end_time - timedelta(days=3)
group_id = "HULA"
print(
    f"==> Exporting individual time series in group {group_id} for office {exporter._office} for time window = {exporter.start_time}, {exporter.end_time}"
)
for tsid in exporter.get_time_series(group_id):
    unit = exporter.get_unit(tsid)
    print(f"#\n# {tsid} (unit={unit})\n#")
    exporter.export(tsid)
# ---------------------------------- #
# export to buffer instead of stdout #
# ---------------------------------- #
exporter.start_time = exporter.end_time - timedelta(days=1)
group_id = "BROK"
print(
    f"==> Exporting individual time series in group {group_id} for office {exporter._office} for time window = {exporter.start_time}, {exporter.end_time} to local buffers we can modify"
)
for tsid in exporter.get_time_series(group_id):
    unit = exporter.get_unit(tsid)
    with StringIO() as buf:
        exporter.set_output(buf)
        buf.write(f"#\n# {tsid} (unit={unit})\n#\n")
        exporter.export(tsid)
        s = buf.getvalue()
        print(s.strip())
