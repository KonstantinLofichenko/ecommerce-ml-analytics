WITH examples AS (
    SELECT ['Electronics', 'Camera & Photo'] AS path, ['Electronics', 'Camera & Photo', 'Camera & Photo', 'Camera & Photo', 'Camera & Photo'] AS expected
    UNION ALL SELECT ['Electronics', 'Camera & Photo', 'Lighting & Studio', 'Backgrounds'], ['Electronics', 'Camera & Photo', 'Lighting & Studio', 'Backgrounds', 'Backgrounds']
    UNION ALL SELECT ['Electronics', 'Computers', 'Accessories', 'Cables', 'Interconnects', 'Ethernet', 'Cat 6'], ['Electronics', 'Computers', 'Accessories', 'Cables', 'Interconnects']
), actual AS (SELECT path, expected, {{ category_hierarchy('path') }} FROM examples)
SELECT path FROM actual
WHERE [category_level_1, category_level_2, category_level_3, category_level_4, category_level_5] != expected
    OR category_depth != length(path) OR category_leaf != path[-1]
