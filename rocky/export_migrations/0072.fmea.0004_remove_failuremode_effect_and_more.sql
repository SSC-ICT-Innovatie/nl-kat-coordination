--
-- Remove field effect from failuremode
--
DROP TABLE "fmea_failuremode_effect" CASCADE;
--
-- Remove field failure_mode from failuremodeaffectedobject
--
ALTER TABLE "fmea_failuremodeaffectedobject" DROP COLUMN "failure_mode_id" CASCADE;
--
-- Delete model FailureModeTreeObject
--
DROP TABLE "fmea_failuremodetreeobject" CASCADE;
--
-- Delete model FailureMode
--
DROP TABLE "fmea_failuremode" CASCADE;
--
-- Delete model FailureModeAffectedObject
--
DROP TABLE "fmea_failuremodeaffectedobject" CASCADE;
--
-- Delete model FailureModeEffect
--
DROP TABLE "fmea_failuremodeeffect" CASCADE;
