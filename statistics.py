import sqlite3, pandas, plotly.express

conn = sqlite3.connect("astronauts.db")
conn.row_factory = sqlite3.Row
cur = conn.cursor()
measurements = cur.execute("SELECT * FROM measurement_history WHERE astronaut_id = 1 ORDER BY recorded_at ASC").fetchall()

all_measurements = {}
for measurement in measurements:
    if len(all_measurements.keys()) < 11:
        for data in measurement.keys()[3:]:
            if type(measurement[data]) == float or type(measurement[data]) == int:
                all_measurements[data] = [{"Maximum": measurement[data], "Minimum": measurement[data], "Sum": measurement[data], "Count": 1}, {data: measurement[data], "Record time": measurement["recorded_at"]}]

    else: 
        for data in measurement.keys()[3:]:
            if type(measurement[data]) == float or type(measurement[data]) == int:
                all_measurements[data].append({data: measurement[data], "Record time": measurement['recorded_at']})
                if measurement[data] > all_measurements[data][0]['Maximum']:
                    all_measurements[data][0]["Maximum"] = measurement[data]
                elif measurement[data] < all_measurements[data][0]["Minimum"]:
                    all_measurements[data][0]["Minimum"] = measurement[data]
                all_measurements[data][0]["Sum"] += measurement[data]
                all_measurements[data][0]["Count"] += 1

for measurement in all_measurements.keys():
    print(all_measurements[measurement])
    df = pandas.DataFrame(all_measurements[measurement][1:])
    fig = plotly.express.line(df, x="Record time", y=measurement, title=measurement.replace("_", " ").capitalize())
    fig.show()
    print(f"Maximum: {all_measurements[measurement][0]['Maximum']}")
    print(f"Minimum: {all_measurements[measurement][0]['Minimum']}")
    print(f"Average: {round(all_measurements[measurement][0]['Sum']/all_measurements[measurement][0]['Count'], 2)}")

conn.commit()
conn.close()