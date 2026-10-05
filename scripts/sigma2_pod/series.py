# Read-only: every simulated-discharge and observed-discharge series in a container,
# with its stored period. Interpretation (completeness) happens locally.
sts, client = dts_client(ARGS["dtss"])
container = ARGS["container"]


def found(pattern):
    rows = []
    for info in client.find(sts.shyft_url(container, pattern)):
        period = info.data_period
        rows.append({"name": str(info.name),
                     "start": iso(period.start), "end": iso(period.end)})
    return sorted(rows, key=lambda r: r["name"])


try:
    result = {"container": container,
              "simulated": found(ARGS["simulated_pattern"]),
              "observed": found(ARGS["observed_pattern"])}
finally:
    client.close()
emit(result)
