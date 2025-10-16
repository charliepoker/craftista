-- Sample origami data for voting service testing

INSERT INTO origami (origami_id, name, description, image_url, vote_count, active, created_at, updated_at) VALUES
('crane-001', 'Test Origami Crane', 'Beautiful crane for testing', '/images/test-crane.png', 15, true, NOW(), NOW()),
('butterfly-002', 'Test Butterfly', 'Colorful butterfly for testing', '/images/test-butterfly.png', 23, true, NOW(), NOW()),
('dragon-003', 'Test Dragon', 'Complex dragon design for testing', '/images/test-dragon.png', 45, true, NOW(), NOW()),
('flower-004', 'Test Flower', 'Simple flower for testing', '/images/test-flower.png', 8, true, NOW(), NOW()),
('elephant-005', 'Test Elephant', 'Cute elephant for testing', '/images/test-elephant.png', 12, true, NOW(), NOW()),
('inactive-006', 'Inactive Test Item', 'This item is inactive', '/images/test-inactive.png', 3, false, NOW(), NOW());

-- Add some vote history data
INSERT INTO origami (origami_id, name, description, image_url, vote_count, active, created_at, updated_at) VALUES
('popular-007', 'Popular Test Item', 'Very popular test item', '/images/test-popular.png', 150, true, NOW() - INTERVAL '7 days', NOW()),
('trending-008', 'Trending Test Item', 'Currently trending item', '/images/test-trending.png', 89, true, NOW() - INTERVAL '2 days', NOW()),
('classic-009', 'Classic Test Item', 'Classic design that never goes out of style', '/images/test-classic.png', 67, true, NOW() - INTERVAL '30 days', NOW()),
('new-010', 'New Test Item', 'Brand new design', '/images/test-new.png', 5, true, NOW() - INTERVAL '1 hour', NOW());

-- Performance testing data (larger dataset)
INSERT INTO origami (origami_id, name, description, image_url, vote_count, active, created_at, updated_at)
SELECT 
    'perf-' || LPAD(generate_series::text, 4, '0'),
    'Performance Test Item ' || generate_series,
    'Performance testing origami item number ' || generate_series,
    '/images/perf-test-' || generate_series || '.png',
    (generate_series % 100),
    (generate_series % 10 != 0),
    NOW() - (generate_series || ' minutes')::INTERVAL,
    NOW() - (generate_series || ' minutes')::INTERVAL
FROM generate_series(1, 500);