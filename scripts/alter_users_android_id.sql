-- ShortDrama: add users.android_id (run manually later; do NOT auto-apply from this file)
-- MySQL
ALTER TABLE `users` ADD COLUMN `android_id` VARCHAR(64) NULL;
CREATE UNIQUE INDEX `idx_users_android_id_unique` ON `users` (`android_id`);

-- SQLite (if needed)
-- ALTER TABLE "users" ADD COLUMN "android_id" VARCHAR(64);
-- CREATE UNIQUE INDEX idx_users_android_id_unique ON users (android_id);

-- Notes:
-- 1) Project also has ensure_demo_schema_compatibility()/_migrate_users() which will
--    add the column + unique index on next create_tables / schema ensure path.
-- 2) Multiple NULLs are allowed under MySQL UNIQUE; only non-NULL android_id values must be unique.
-- 3) Do not run this against live DB until you intentionally migrate.
