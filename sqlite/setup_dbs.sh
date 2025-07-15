sqlite3 /data/mydb.db <<EOF
CREATE TABLE IF NOT EXISTS t1 (id INTEGER PRIMARY KEY, name TEXT);
INSERT INTO t1 (name) VALUES ('Alice'), ('Bob');
EOF

socat TCP-LISTEN:12346,fork,reuseaddr UNIX-CONNECT:/data/mydb.db