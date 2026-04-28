-- Run this migration on an existing database where backend/models/init.sql
-- has already been applied by Docker's first-start initialization.

CREATE TABLE IF NOT EXISTS book_loans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    book_id UUID NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    borrowed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    due_at TIMESTAMP NOT NULL DEFAULT (CURRENT_TIMESTAMP + INTERVAL '14 days'),
    returned_at TIMESTAMP,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_active_book_loan_per_user
ON book_loans (user_id, book_id)
WHERE status = 'active';

CREATE INDEX IF NOT EXISTS idx_book_loans_user_status
ON book_loans (user_id, status);

CREATE INDEX IF NOT EXISTS idx_book_loans_book
ON book_loans (book_id);

CREATE TABLE IF NOT EXISTS book_bookmarks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    book_id UUID NOT NULL REFERENCES books(id) ON DELETE CASCADE,
    page_number INTEGER,
    position_label VARCHAR(255),
    progress_percent NUMERIC(5, 2),
    note TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_book_bookmarks_user_book
ON book_bookmarks (user_id, book_id);
