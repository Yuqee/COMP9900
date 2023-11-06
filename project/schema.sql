BEGIN TRANSACTION;
CREATE TABLE IF NOT EXISTS "Users" (
	"id"	integer,
	"email"	text NOT NULL CHECK("email" LIKE '%@%.%') UNIQUE,
	"password"	text NOT NULL,
	"name"	text NOT NULL UNIQUE,
	"picture"	blob DEFAULT null,
	"is_host"	bool NOT NULL DEFAULT 0,
	PRIMARY KEY("id" AUTOINCREMENT)
);
CREATE TABLE IF NOT EXISTS "SoldTickets" (
	"id"	integer,
	"soldTo"	integer NOT NULL,
	"forEvent"	integer NOT NULL,
	"row"	integer NOT NULL,
	"column"	integer NOT NULL,
	"transactionId"	integer NOT NULL,
	"soldPrice"	float NOT NULL CHECK("soldPrice" >= 0),
	"status"	char(1) NOT NULL CHECK("status" IN ('v', 'c')),
	PRIMARY KEY("id" AUTOINCREMENT),
	FOREIGN KEY("forEvent") REFERENCES "Events"("id"),
	FOREIGN KEY("transactionId") REFERENCES "Transactions"("id"),
	FOREIGN KEY("soldTo") REFERENCES "Users"("id")
);
CREATE TABLE IF NOT EXISTS "Transactions" (
	"id"	integer,
	"boughtBy"	integer NOT NULL,
	"transactionDate"	date NOT NULL,
	PRIMARY KEY("id" AUTOINCREMENT),
	FOREIGN KEY("boughtBy") REFERENCES "Users"("id")
);
CREATE TABLE IF NOT EXISTS "Layouts" (
	"id"	integer,
	"row"	integer NOT NULL,
	"column"	integer NOT NULL,
	PRIMARY KEY("id" AUTOINCREMENT)
);
CREATE TABLE IF NOT EXISTS "Zones" (
	"id"	integer,
	"startRow"	integer NOT NULL,
	"endRow"	integer NOT NULL,
	"layoutId"	integer NOT NULL,
	PRIMARY KEY("id" AUTOINCREMENT),
	FOREIGN KEY("layoutId") REFERENCES "Layouts"("id")
);
CREATE TABLE IF NOT EXISTS "Wishlist" (
	"userId"	integer NOT NULL,
	"eventId"	integer NOT NULL,
	PRIMARY KEY("userId","eventId"),
	FOREIGN KEY("eventId") REFERENCES "Events"("id"),
	FOREIGN KEY("userId") REFERENCES "Users"("id")
);
CREATE TABLE IF NOT EXISTS "Comments" (
	"id"	INTEGER,
	"comment"	TEXT NOT NULL,
	"commentTime"	DATETIME NOT NULL,
	"userId"	INTEGER NOT NULL,
	"eventId"	INTEGER NOT NULL,
	PRIMARY KEY("id" AUTOINCREMENT),
	FOREIGN KEY("eventId") REFERENCES "Events"("id"),
	FOREIGN KEY("userId") REFERENCES "Users"("id")
);
CREATE TABLE IF NOT EXISTS "Replies" (
	"id"	INTEGER,
	"reply"	TEXT NOT NULL,
	"replyTime"	DATETIME NOT NULL,
	"commentId"	INTEGER NOT NULL,
	"hostId"	INTEGER NOT NULL,
	PRIMARY KEY("id" AUTOINCREMENT),
	FOREIGN KEY("commentId") REFERENCES "Comments"("id") ON DELETE CASCADE,
	FOREIGN KEY("hostId") REFERENCES "Users"("id")
);
CREATE TABLE IF NOT EXISTS "Price" (
	"id"	integer,
	"forEvent"	integer NOT NULL,
	"forZone"	integer NOT NULL,
	"price"	float NOT NULL CHECK("price" >= 0),
	"status"	char(1) NOT NULL CHECK("status" IN ('v', 'c')),
	"fireSales"	bool NOT NULL DEFAULT 0,
	"origPriceId"	INTEGER NOT NULL DEFAULT -1,
	PRIMARY KEY("id" AUTOINCREMENT),
	FOREIGN KEY("forZone") REFERENCES "Zones"("id"),
	FOREIGN KEY("forEvent") REFERENCES "Events"("id")
);
CREATE TABLE IF NOT EXISTS "Events" (
	"id"	integer,
	"title"	text NOT NULL,
	"startDate"	date NOT NULL,
	"startTime"	time NOT NULL,
	"endDate"	date NOT NULL,
	"endTime"	time NOT NULL,
	"location"	text NOT NULL,
	"hostedBy"	integer NOT NULL,
	"poster"	blob NOT NULL,
	"layoutId"	integer NOT NULL,
	"status"	char(1) NOT NULL CHECK("status" IN ('v', 'c')),
	PRIMARY KEY("id" AUTOINCREMENT),
	FOREIGN KEY("layoutId") REFERENCES "Layouts"("id"),
	FOREIGN KEY("hostedBy") REFERENCES "Users"("id")
);
COMMIT;
