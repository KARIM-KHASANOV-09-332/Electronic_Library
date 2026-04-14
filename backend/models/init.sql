CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- =========================
-- Пользователи
-- =========================
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    phone_number VARCHAR(20) UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    library_card VARCHAR(20) UNIQUE,
    role VARCHAR(20) DEFAULT 'reader',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =========================
-- Очередь фоновых задач
-- =========================
CREATE TABLE IF NOT EXISTS analysis_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_email VARCHAR(100) NOT NULL,
    task_type VARCHAR(50) DEFAULT 'generate_card',
    status VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =========================
-- Книги
-- =========================
CREATE TABLE IF NOT EXISTS books (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    description TEXT DEFAULT '',
    genre VARCHAR(100),
    cover_image_path TEXT,

    author_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    uploaded_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,

    access_level VARCHAR(30) NOT NULL DEFAULT 'free',
    copyright_holder VARCHAR(255),
    license_name VARCHAR(255),

    status VARCHAR(30) NOT NULL DEFAULT 'published',
    source_type VARCHAR(30) NOT NULL DEFAULT 'moderator_direct',
    moderator_comment TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    published_at TIMESTAMP
);

-- =========================
-- Файлы книг
-- =========================
CREATE TABLE IF NOT EXISTS book_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    book_id UUID NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    file_type VARCHAR(10) NOT NULL,
    file_path TEXT NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =========================
-- История статусов книг
-- =========================
CREATE TABLE IF NOT EXISTS book_status_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    book_id UUID NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    old_status VARCHAR(30),
    new_status VARCHAR(30) NOT NULL,
    comment TEXT,
    changed_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);