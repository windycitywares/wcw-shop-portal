-- Reverses 0007_engagement.sql
DROP TABLE campaigns;
DROP TABLE stock_alerts;
DROP TABLE wishlist_items;
DROP TABLE review_votes;
DROP TABLE reviews;
ALTER TABLE newsletter_subscribers DROP COLUMN locale, DROP COLUMN source, DROP COLUMN unsubscribe_token, DROP COLUMN unsubscribed_at, DROP COLUMN welcome_coupon;
ALTER TABLE products DROP COLUMN rating_avg, DROP COLUMN rating_count;
