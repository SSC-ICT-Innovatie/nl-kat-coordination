ALTER TABLE public.crisis_room_dashboarddata RENAME TO "crisis_room_dashboarditem";
ALTER TABLE public.crisis_room_dashboarditem RENAME COLUMN "query_from" TO "source";
CREATE UNIQUE INDEX "unique_findings_dashboard_per_dashboard" ON public.crisis_room_dashboarditem ("dashboard_id") WHERE "findings_dashboard";
