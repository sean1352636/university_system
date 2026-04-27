CREATE TABLE IF NOT EXISTS alternative_materials (
    material_id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_id INTEGER NOT NULL,
    original_material_id INTEGER,
    format_type TEXT NOT NULL,  -- braille, audio, large_print, digital
    file_url TEXT,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by INTEGER
);
