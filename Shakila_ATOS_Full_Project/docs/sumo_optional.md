# Using real SUMO instead of the built-in microsimulator (optional)
The proposal names SUMO. The default engine (`tools/sumo/microsim.py`) reproduces the same experiment design without installation.
To run real SUMO: install SUMO (`pip install eclipse-sumo traci`), generate a 5-junction grid with
`netgenerate --grid --grid.x-number 5 --grid.y-number 2 -o tools/sumo/corridor.net.xml`, create demand with `randomTrips.py`, block a lane with a stopped vehicle
(`traci.vehicle.setSpeed(v, 0)`), change phases with `traci.trafficlight.setPhaseDuration`, reroute with `traci.vehicle.rerouteTraveltime`,
and compute the same four metrics. Keep `analyze_results.to_markdown` for the table.
