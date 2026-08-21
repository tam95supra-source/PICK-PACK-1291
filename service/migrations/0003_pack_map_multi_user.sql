DROP INDEX IF EXISTS uq_pack_user_shift;

CREATE TABLE resource_pack_map_v2 (
  pack_table TEXT NOT NULL,
  shift TEXT NOT NULL,
  user_pack TEXT NOT NULL,
  label TEXT NOT NULL,
  available INTEGER NOT NULL CHECK(available IN (0,1)),
  source_row INTEGER NOT NULL,
  source_checksum TEXT NOT NULL,
  PRIMARY KEY(pack_table,shift,user_pack)
);

INSERT OR IGNORE INTO resource_pack_map_v2(pack_table,shift,user_pack,label,available,source_row,source_checksum)
SELECT pack_table,shift,user_pack,label,available,source_row,source_checksum
FROM resource_pack_map;

DROP TABLE resource_pack_map;
ALTER TABLE resource_pack_map_v2 RENAME TO resource_pack_map;

CREATE UNIQUE INDEX uq_pack_user_shift ON resource_pack_map(shift,user_pack);
CREATE INDEX idx_pack_map_table_shift ON resource_pack_map(pack_table,shift,user_pack);
