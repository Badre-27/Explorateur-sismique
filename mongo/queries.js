// Helper: print the results of a query
function show(title, result) {
  print("\n=== " + title + " ===");
  const docs = result.toArray ? result.toArray() : [result];
  docs.forEach(d => printjson(d));
  print("(" + docs.length + " result(s))");
}

print("Total events: " + db.events.countDocuments());

// Q1 (READ, by date): strongest events of the first month in the dataset
const first = db.events.find().sort({ event_ts: 1 }).limit(1).toArray()[0].event_ts;
const start = new Date(Date.UTC(first.getUTCFullYear(), first.getUTCMonth(), 1));
const end = new Date(Date.UTC(first.getUTCFullYear(), first.getUTCMonth() + 1, 1));
show("Q1 - Top 10 events of the first month",
  db.events.find({ event_ts: { $gte: start, $lt: end } },
                 { _id: 0, event_ts: 1, mag: 1, place: 1 })
    .sort({ mag: -1 }).limit(10));

// Q2 (FILTER, by magnitude): very strong events
show("Q2 - Events with magnitude >= 6.5",
  db.events.find({ mag: { $gte: 6.5 } }, { _id: 0, event_ts: 1, mag: 1, place: 1 })
    .sort({ mag: -1 }));

// Q3 (FILTER, by location text, regex)
show("Q3 - Place contains 'japan'",
  db.events.find({ place: /japan/i }, { _id: 0, mag: 1, place: 1 }).limit(10));

// Q4 (FILTER, full-text search on the text index)
show("Q4 - Text search 'Indonesia'",
  db.events.find({ $text: { $search: "Indonesia" } }, { _id: 0, mag: 1, place: 1 }).limit(10));

// Q5 (AGGREGATE): top areas by number of events
show("Q5 - Top 10 areas",
  db.events.aggregate([
    { $group: { _id: "$area", n: { $sum: 1 }, maxMag: { $max: "$mag" } } },
    { $sort: { n: -1 } },
    { $limit: 10 }
  ]));

// Q6 (UPDATE): flag the strongest event as reviewed
const top = db.events.find().sort({ mag: -1 }).limit(1).toArray()[0];
const upd = db.events.updateOne({ _id: top._id }, { $set: { reviewed: true } });
print("\n=== Q6 - Update ===");
print("Modified: " + upd.modifiedCount);
show("Q6 - Verification", db.events.find({ reviewed: true }, { _id: 0, mag: 1, place: 1, reviewed: 1 }));

// Q7 (DELETE): insert a test document, then remove it
db.events.insertOne({ id: "test1", mag: 0, place: "test" });
const del = db.events.deleteOne({ id: "test1" });
print("\n=== Q7 - Delete ===");
print("Deleted: " + del.deletedCount);
