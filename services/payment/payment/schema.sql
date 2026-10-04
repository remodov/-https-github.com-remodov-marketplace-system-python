CREATE TABLE IF NOT EXISTS payments (
    id         uuid PRIMARY KEY,
    order_id   uuid NOT NULL UNIQUE,
    amount     numeric(12, 2) NOT NULL CHECK (amount > 0),
    currency   char(3) NOT NULL,
    status     varchar(16) NOT NULL,
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL
);
