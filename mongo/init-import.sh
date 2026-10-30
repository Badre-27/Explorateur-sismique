#!/bin/bash
set -e

mongoimport --db seismic --collection events \
  --file /seed/events.json --drop

mongosh seismic --quiet --eval '
  db.events.updateMany({}, [{ $set: { event_ts: { $toDate: "$event_ts" } } }]);
  db.events.createIndex({ event_ts: 1 });
  db.events.createIndex({ mag: -1 });
  db.events.createIndex({ place: "text" });
  print("Imported: " + db.events.countDocuments());
'
