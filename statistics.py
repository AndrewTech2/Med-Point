import sqlite3, pandas, plotly.express

conn = sqlite3.connect("astronauts.db")
conn.row_factory = sqlite3.Row
cur = conn.cursor()
measurements = cur.execute("SELECT * FROM measurement_history WHERE astronaut_id = 1").fetchall()

all_measurements = {}
for measurement in measurements:
    if len(all_measurements.keys()) < 11:
        for data in measurement.keys()[3:]:
            if type(measurement[data]) == float or type(measurement[data]) == int:
                all_measurements[data] = [{data: measurement[data], "Record time": measurement["recorded_at"]}]
    else: 
        for data in measurement.keys()[3:]:
            if type(measurement[data]) == float or type(measurement[data]) == int:
                all_measurements[data].append({data: measurement[data], "Record time": measurement['recorded_at']})

for measurement in all_measurements.keys():
    print(all_measurements[measurement])
    df = pandas.DataFrame(all_measurements[measurement])
    fig = plotly.express.line(df, x="Record time", y=measurement, title=measurement.replace("_", " ").capitalize())
    fig.show()
