CREATE UNIQUE INDEX catalog_search_id_idx
ON catalog_search (id);

CREATE UNIQUE INDEX catalog_search_entity_idx
ON catalog_search (entity_type, entity_id);

CREATE INDEX catalog_search_search_vector_idx
ON catalog_search
USING GIN (search_vector);

CREATE INDEX catalog_search_search_text_trgm_idx
ON catalog_search
USING GIN (search_text gin_trgm_ops);
