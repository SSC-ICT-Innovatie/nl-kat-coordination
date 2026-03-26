--
-- Create model AuthToken
--
CREATE TABLE "account_authtoken" (
  "digest" varchar(128) NOT NULL PRIMARY KEY,
  "token_key" varchar(25) NOT NULL,
  "created" timestamp with time zone NOT NULL,
  "expiry" timestamp with time zone NULL,
  "name" varchar(150) NOT NULL,
  "user_id" integer NOT NULL
);
--
-- Create constraint unique name on model authtoken
--
CREATE UNIQUE INDEX "unique name" ON "account_authtoken" ("user_id", (LOWER("name")));
ALTER TABLE "account_authtoken" ADD CONSTRAINT "account_authtoken_user_id_4acc5a34_fk_account_katuser_id" FOREIGN KEY ("user_id") REFERENCES "account_katuser" ("id") DEFERRABLE INITIALLY DEFERRED;
CREATE INDEX "account_authtoken_digest_1c05223c_like" ON "account_authtoken" ("digest" varchar_pattern_ops);
CREATE INDEX "account_authtoken_token_key_134d6886" ON "account_authtoken" ("token_key");
CREATE INDEX "account_authtoken_token_key_134d6886_like" ON "account_authtoken" ("token_key" varchar_pattern_ops);
CREATE INDEX "account_authtoken_user_id_4acc5a34" ON "account_authtoken" ("user_id");
