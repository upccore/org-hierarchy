CREATE TABLE IF NOT EXISTS org_unit (
    id        integer  PRIMARY KEY,
    parent_id integer  REFERENCES org_unit (id) DEFERRABLE INITIALLY DEFERRED,
    name      text     NOT NULL,
    type      smallint NOT NULL CHECK (type IN (1, 2, 3))
);

CREATE INDEX IF NOT EXISTS org_unit_parent_id_idx ON org_unit (parent_id);
