INSERT INTO products (id, title, price, stock, reserved, version)
SELECT gen_random_uuid(),
       (ARRAY['Клавиатура', 'Мышь', 'Монитор', 'Наушники', 'Коврик', 'Кабель', 'Хаб', 'Микрофон'])[1 + (g % 8)]
           || ' ' || (ARRAY['keychron', 'logitech', 'razer', 'steelseries', 'hyperx', 'xiaomi'])[1 + (g % 6)]
           || ' модель ' || g,
       (100 + (g * 37) % 20000)::numeric(12,2),
       (g % 50),
       0,
       0
FROM generate_series(1, 100000) AS g;
ANALYZE products;
