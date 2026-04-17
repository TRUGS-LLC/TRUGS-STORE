-- TRUGS_STORE PostgreSQL schema
-- Shared contract between trugs-store (Python) and PORT (Go) — see #686

CREATE TABLE IF NOT EXISTS graphs (
    graph_id    TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    version     TEXT NOT NULL DEFAULT '1.0.0',
    type        TEXT,
    description TEXT,
    metadata    JSONB NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS nodes (
    id          TEXT NOT NULL,
    graph_id    TEXT NOT NULL REFERENCES graphs(graph_id) ON DELETE CASCADE,
    type        TEXT NOT NULL,
    properties  JSONB NOT NULL DEFAULT '{}',
    metric_level TEXT,
    parent_id   TEXT,
    contains    TEXT[] NOT NULL DEFAULT '{}',
    dimension   TEXT,
    PRIMARY KEY (graph_id, id)
);

CREATE TABLE IF NOT EXISTS edges (
    graph_id    TEXT NOT NULL REFERENCES graphs(graph_id) ON DELETE CASCADE,
    from_id     TEXT NOT NULL,
    to_id       TEXT NOT NULL,
    relation    TEXT NOT NULL,
    weight      REAL DEFAULT 1.0,
    properties  JSONB NOT NULL DEFAULT '{}',
    PRIMARY KEY (graph_id, from_id, to_id, relation)
);

-- Indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(graph_id, type);
CREATE INDEX IF NOT EXISTS idx_nodes_parent ON nodes(graph_id, parent_id);
CREATE INDEX IF NOT EXISTS idx_nodes_dimension ON nodes(graph_id, dimension);
CREATE INDEX IF NOT EXISTS idx_nodes_props ON nodes USING GIN(properties jsonb_path_ops);
CREATE INDEX IF NOT EXISTS idx_edges_from ON edges(graph_id, from_id);
CREATE INDEX IF NOT EXISTS idx_edges_to ON edges(graph_id, to_id);
CREATE INDEX IF NOT EXISTS idx_edges_relation ON edges(graph_id, relation);
